#!/usr/bin/env python3
"""
audit_photos.py — READ-ONLY photo audit script.

Compares files in /Photos against /iCloud Photos/Photos and reports
which files in /Photos have no matching counterpart in iCloud.

NO FILES ARE MODIFIED, MOVED, OR DELETED BY THIS SCRIPT.
"""

import csv
import re
import subprocess
import sys
import tempfile
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================

PHOTOS_ROOT = Path(r"C:\Users\windo\Pictures\Photos")
ICLOUD_ROOT = Path(r"C:\Users\windo\Pictures\iCloud Photos\Photos")
REPORT_DIR  = Path(r"C:\Users\windo\VS_Code\photos\results")
REPORT_PATH = REPORT_DIR / "unmatched_photos_report.csv"
EXIFTOOL    = "exiftool"

IMAGE_EXTS = {".jpg", ".jpeg", ".heic", ".png", ".gif", ".tiff", ".tif", ".bmp", ".webp"}
VIDEO_EXTS = {".mov", ".mp4", ".m4v", ".avi", ".mkv", ".3gp"}
SKIP_EXTS  = {".aae", ".thm", ".xmp", ".db", ".ini", ".ds_store"}

# ExifTool date tags in priority order: DateTimeOriginal first, then fallbacks
DATE_TAGS = ["DateTimeOriginal", "CreateDate", "MediaCreateDate", "CreationDate"]

# =============================================================================
# HELPERS
# =============================================================================

def media_class(path: Path) -> str | None:
    """Return 'image', 'video', or None for unknown/skipped types."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    return None


def normalize_basename(name: str) -> str:
    """Strip extension, remove trailing (n) duplicate suffixes, uppercase."""
    base = Path(name).stem
    base = re.sub(r'\s*\(\d+\)$', '', base)
    return base.upper().strip()


def normalize_date(raw: str) -> str | None:
    """Convert ExifTool date string to UTC 'YYYY-MM-DD HH:MM:SS' or None.
    Timezone-aware dates are converted to UTC so local-time and UTC
    representations of the same moment compare equal."""
    if not raw or not raw.strip():
        return None
    # ExifTool uses YYYY:MM:DD — fix date separator
    d = re.sub(r'^(\d{4}):(\d{2}):(\d{2})', r'\1-\2-\3', raw.strip())
    # Drop sub-seconds
    d = re.sub(r'\.\d+', '', d)
    # Try parsing with timezone offset (e.g. 2020-04-24 19:14:03-07:00)
    try:
        dt = datetime.fromisoformat(d)
        if dt.tzinfo is not None:
            dt = dt.astimezone(timezone.utc).replace(tzinfo=None)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        pass
    # Fallback: parse bare datetime (already treated as UTC)
    try:
        return datetime.strptime(d[:19], "%Y-%m-%d %H:%M:%S").strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        return None


def run_exiftool_on_filelist(paths: list[Path]) -> list[dict]:
    """
    Run exiftool on a list of file paths (written to a temp file to avoid
    command-line length limits). Returns a list of parsed metadata records.
    Read-only operation — exiftool is invoked with no write flags.
    """
    if not paths:
        return []

    # Build the tab-separated format string requesting each date tag
    fmt = "\t".join(["$FilePath", "$FileName"] + [f"${t}" for t in DATE_TAGS])

    with tempfile.NamedTemporaryFile(
        mode="w", suffix=".txt", delete=False, encoding="utf-8"
    ) as tmp:
        tmp.write("\n".join(str(p) for p in paths))
        tmp_path = tmp.name

    cmd = [
        EXIFTOOL,
        "-m",                  # suppress minor errors
        "-charset", "utf8",
        "-p", fmt,
        "-@", tmp_path,        # read file list from temp file
    ]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
    finally:
        Path(tmp_path).unlink(missing_ok=True)

    records = []
    for line in result.stdout.splitlines():
        parts = line.split("\t")
        if len(parts) < 2 + len(DATE_TAGS):
            continue

        filepath  = parts[0].strip()
        filename  = parts[1].strip()
        date_vals = [p.strip() for p in parts[2:2 + len(DATE_TAGS)]]

        # Pick the first non-empty date value (priority order from DATE_TAGS)
        raw_date = next((v for v in date_vals if v), None)

        records.append({
            "path":        Path(filepath),
            "name":        filename,
            "base":        normalize_basename(filename),
            "raw_date":    raw_date,
            "date":        normalize_date(raw_date) if raw_date else None,
            "media_class": media_class(Path(filename)),
        })

    return records


# =============================================================================
# MAIN
# =============================================================================

def main() -> None:
    # Validate roots exist before doing any work
    for root, label in [(PHOTOS_ROOT, "Photos"), (ICLOUD_ROOT, "iCloud Photos")]:
        if not root.exists():
            sys.exit(f"ERROR: {label} folder not found: {root}")

    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    # -------------------------------------------------------------------------
    # STEP 1: Collect media files from /Photos
    # -------------------------------------------------------------------------
    print("Scanning /Photos ...")
    photos_files = [
        f for f in PHOTOS_ROOT.rglob("*")
        if f.is_file()
        and f.suffix.lower() not in SKIP_EXTS
        and media_class(f) is not None
    ]
    print(f"  {len(photos_files)} media files found")

    if not photos_files:
        sys.exit("No media files found in /Photos. Nothing to do.")

    needed_bases = {normalize_basename(f.name) for f in photos_files}

    # -------------------------------------------------------------------------
    # STEP 2: Collect iCloud candidates (only files whose basename appears in /Photos)
    # -------------------------------------------------------------------------
    print("Scanning iCloud for candidates ...")
    icloud_candidates = [
        f for f in ICLOUD_ROOT.rglob("*")
        if f.is_file()
        and f.suffix.lower() not in SKIP_EXTS
        and media_class(f) is not None
        and normalize_basename(f.name) in needed_bases
    ]
    print(f"  {len(icloud_candidates)} candidate files found")

    # -------------------------------------------------------------------------
    # STEP 3: Read metadata via ExifTool (read-only)
    # -------------------------------------------------------------------------
    print("Reading /Photos metadata via ExifTool ...")
    photos_data = run_exiftool_on_filelist(photos_files)
    print(f"  {len(photos_data)} records parsed")

    print("Reading iCloud metadata via ExifTool ...")
    icloud_data = run_exiftool_on_filelist(icloud_candidates)
    print(f"  {len(icloud_data)} records parsed")

    # -------------------------------------------------------------------------
    # STEP 4: Build iCloud index  { normalized_base -> [record, ...] }
    # -------------------------------------------------------------------------
    icloud_index: dict[str, list[dict]] = {}
    for rec in icloud_data:
        icloud_index.setdefault(rec["base"], []).append(rec)

    # -------------------------------------------------------------------------
    # STEP 5: Compare — classify each /Photos file
    # -------------------------------------------------------------------------
    print("Comparing ...")
    report_rows = []
    matched_count = 0

    for p in photos_data:
        base    = p["base"]
        p_class = p["media_class"]
        p_date  = p["date"]

        # --- Tier 5: no readable metadata date ---
        if not p_date:
            report_rows.append({
                "status":            "NO_DATE",
                "photos_path":       str(p["path"]),
                "photos_date":       "",
                "icloud_match_path": "",
                "icloud_match_date": "",
                "note":              "No readable metadata date found by ExifTool",
            })
            continue

        candidates = icloud_index.get(base, [])

        # --- Tier 4: no file with same basename in iCloud at all ---
        if not candidates:
            report_rows.append({
                "status":            "NO_NAME_MATCH",
                "photos_path":       str(p["path"]),
                "photos_date":       p_date,
                "icloud_match_path": "",
                "icloud_match_date": "",
                "note":              "No file with matching basename found in iCloud",
            })
            continue

        # --- Tier 1: same media class + same date → MATCHED (not reported) ---
        same_class = [c for c in candidates if c["media_class"] == p_class]
        if any(c["date"] == p_date for c in same_class):
            matched_count += 1
            continue

        # --- Tier 2: Live Photo — .mov in /Photos paired with .heic/.jpg in iCloud ---
        if p_class == "video" and p["path"].suffix.lower() == ".mov":
            live_matches = [
                c for c in candidates
                if c["media_class"] == "image"
                and c["path"].suffix.lower() in {".heic", ".jpg", ".jpeg"}
                and c["date"] == p_date
            ]
            if live_matches:
                lc = live_matches[0]
                report_rows.append({
                    "status":            "LIVE_PHOTO_MATCH",
                    "photos_path":       str(p["path"]),
                    "photos_date":       p_date,
                    "icloud_match_path": str(lc["path"]),
                    "icloud_match_date": lc["date"] or "",
                    "note": (
                        "MOV in /Photos matches a HEIC/JPG in iCloud with the same "
                        "basename and date — likely the still half of a Live Photo pair"
                    ),
                })
                continue

        # --- Tier 3: basename + same class found but dates differ ---
        if same_class:
            candidate_summary = "; ".join(
                f"{c['path'].name} [{c['date'] or 'no date'}]" for c in same_class
            )
            report_rows.append({
                "status":            "DATE_MISMATCH",
                "photos_path":       str(p["path"]),
                "photos_date":       p_date,
                "icloud_match_path": same_class[0]["path"].name,
                "icloud_match_date": same_class[0]["date"] or "",
                "note":              f"All iCloud candidates: {candidate_summary}",
            })
            continue

        # --- Tier 3b: basename found in iCloud but only as a different media class ---
        cross_summary = "; ".join(
            f"{c['path'].name} ({c['media_class']}) [{c['date'] or 'no date'}]"
            for c in candidates
        )
        report_rows.append({
            "status":            "NO_CLASS_MATCH",
            "photos_path":       str(p["path"]),
            "photos_date":       p_date,
            "icloud_match_path": "",
            "icloud_match_date": "",
            "note": (
                f"iCloud has same basename but only as a different media class "
                f"(not a Live Photo date match): {cross_summary}"
            ),
        })

    # -------------------------------------------------------------------------
    # STEP 6: Write CSV report
    # -------------------------------------------------------------------------
    print(f"Writing report to {REPORT_PATH} ...")
    fieldnames = [
        "status", "photos_path", "photos_date",
        "icloud_match_path", "icloud_match_date", "note",
    ]
    with REPORT_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(report_rows)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    counts = Counter(r["status"] for r in report_rows)
    print()
    print("=" * 50)
    print("AUDIT SUMMARY")
    print("=" * 50)
    print(f"  /Photos files scanned      : {len(photos_data)}")
    print(f"  Fully matched (not in CSV) : {matched_count}")
    print()
    for status in ["LIVE_PHOTO_MATCH", "DATE_MISMATCH", "NO_CLASS_MATCH", "NO_NAME_MATCH", "NO_DATE"]:
        if status in counts:
            print(f"  {status:<22}: {counts[status]}")
    print()
    print(f"Report : {REPORT_PATH}")
    print("=" * 50)
    print("No files were modified, moved, or deleted.")


if __name__ == "__main__":
    main()
