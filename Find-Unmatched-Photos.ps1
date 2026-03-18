# =========================
# CONFIG
# =========================
$photosRoot = "C:\Users\windo\Pictures\Photos"
$icloudRoot = "C:\Users\windo\Pictures\iCloud Photos\Photos"
$exiftool   = "exiftool"

$reportDir  = "C:\Users\windo\Desktop\PhotoAudit"
$reportPath = Join-Path $reportDir "unmatched_photos_report.txt"
$tmpList    = Join-Path $env:TEMP "icloud_candidates.txt"

# =========================
# SETUP OUTPUT
# =========================
if (-not (Test-Path $reportDir)) {
    New-Item -ItemType Directory -Path $reportDir | Out-Null
}

if (Test-Path $reportPath) {
    Remove-Item $reportPath -Force
}

if (Test-Path $tmpList) {
    Remove-Item $tmpList -Force
}

# =========================
# FUNCTIONS
# =========================

function Get-NormalizedBaseName {
    param([string]$FileName)

    $base = [System.IO.Path]::GetFileNameWithoutExtension($FileName)
    $base = $base -replace '\(\d+\)$', ''
    return $base.ToUpperInvariant()
}

function Normalize-Date {
    param([string]$Raw)

    if (-not $Raw) { return $null }

    $d = $Raw -replace '^(\d{4}):(\d{2}):(\d{2})', '$1-$2-$3'
    $d = $d -replace '\.\d+', ''

    try {
        return ([datetimeoffset]::Parse($d)).ToString("yyyy-MM-dd HH:mm:ss")
    } catch {
        try {
            return ([datetime]::Parse($d)).ToString("yyyy-MM-dd HH:mm:ss")
        } catch {
            return $null
        }
    }
}

function Parse-ExifRows {
    param($lines)

    $out = @()

    foreach ($l in $lines) {
        if (-not $l) { continue }

        $p = $l -split "`t"
        if ($p.Count -lt 6) { continue }

        $raw = $null

        if ($p[2]) { $raw = $p[2] }
        elseif ($p[3]) { $raw = $p[3] }
        elseif ($p[4]) { $raw = $p[4] }
        elseif ($p[5]) { $raw = $p[5] }

        $out += [pscustomobject]@{
            Path     = $p[0]
            Name     = $p[1]
            Base     = Get-NormalizedBaseName $p[1]
            RawDate  = $raw
            NormDate = Normalize-Date $raw
        }
    }

    return $out
}

# =========================
# STEP 1: SCAN PHOTOS
# =========================
Write-Host "Scanning Photos..."

$photosFiles = Get-ChildItem $photosRoot -File -Recurse

$neededBases = @{}
foreach ($f in $photosFiles) {
    $neededBases[(Get-NormalizedBaseName $f.Name)] = $true
}

# =========================
# STEP 2: FILTER ICLOUD FILES
# =========================
Write-Host "Filtering iCloud candidates..."

$icloudCandidates = New-Object System.Collections.Generic.List[string]

Get-ChildItem $icloudRoot -File -Recurse | ForEach-Object {
    $base = Get-NormalizedBaseName $_.Name
    if ($neededBases.ContainsKey($base)) {
        $icloudCandidates.Add($_.FullName)
    }
}

$icloudCandidates | Sort-Object -Unique | Set-Content $tmpList

# =========================
# STEP 3: METADATA (FAST)
# =========================
Write-Host "Reading Photos metadata..."

$photosLines = & $exiftool -m `
    -r `
    -DateTimeOriginal -CreateDate -MediaCreateDate -CreationDate `
    -p '$FilePath`t$FileName`t$DateTimeOriginal`t$CreateDate`t$MediaCreateDate`t$CreationDate' `
    -- $photosRoot

$photosData = Parse-ExifRows $photosLines

Write-Host "Reading iCloud metadata..."

$icloudLines = & $exiftool -m `
    -DateTimeOriginal -CreateDate -MediaCreateDate -CreationDate `
    -p '$FilePath`t$FileName`t$DateTimeOriginal`t$CreateDate`t$MediaCreateDate`t$CreationDate' `
    -@ $tmpList

$icloudData = Parse-ExifRows $icloudLines

# =========================
# STEP 4: INDEX ICLOUD
# =========================
$icloudIndex = @{}

foreach ($i in $icloudData) {
    if (-not $icloudIndex.ContainsKey($i.Base)) {
        $icloudIndex[$i.Base] = @()
    }
    $icloudIndex[$i.Base] += $i
}

# =========================
# STEP 5: COMPARE
# =========================
Write-Host "Comparing..."

$results = @()
$total = $photosData.Count
$count = 0

foreach ($p in $photosData) {
    $count++
    Write-Progress -Activity "Comparing" -Status "$count / $total" -PercentComplete (($count / $total) * 100)

    if (-not $p.NormDate) {
        $results += [pscustomobject]@{
            Status="NO_DATE"
            File=$p.Path
            Date=""
            Candidates=""
        }
        continue
    }

    if (-not $icloudIndex.ContainsKey($p.Base)) {
        $results += [pscustomobject]@{
            Status="NO_NAME_MATCH"
            File=$p.Path
            Date=$p.NormDate
            Candidates=""
        }
        continue
    }

    $match = $false

    foreach ($c in $icloudIndex[$p.Base]) {
        if ($c.NormDate -eq $p.NormDate) {
            $match = $true
            break
        }
    }

    if (-not $match) {
        $results += [pscustomobject]@{
            Status="DATE_MISMATCH"
            File=$p.Path
            Date=$p.NormDate
            Candidates=($icloudIndex[$p.Base].Count)
        }
    }
}

Write-Progress -Completed -Activity "Comparing"

# =========================
# STEP 6: REPORT
# =========================
"Unmatched Photos Report" | Set-Content $reportPath
"Generated: $(Get-Date)" | Add-Content $reportPath
"" | Add-Content $reportPath

foreach ($r in $results) {
    "$($r.Status) | $($r.File) | $($r.Date) | Candidates: $($r.Candidates)" | Add-Content $reportPath
}

Remove-Item $tmpList -ErrorAction SilentlyContinue

Write-Host ""
Write-Host "DONE"
Write-Host "Unmatched:" $results.Count
Write-Host "Report:" $reportPath