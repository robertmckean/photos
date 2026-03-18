#!/usr/bin/env python3
"""
reconcile_wn_icloud.py

Reconciles files in D:\Why not iPhone against iCloud Photos.
Analysis and reporting only -- does NOT modify, move, delete, or rename anything.

Uses ExifTool for metadata extraction. Does NOT trust filesystem timestamps.
"""

from __future__ import annotations

import csv
import datetime as dt
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

WN_ROOT = Path(r"D:\Why not iPhone")
ICLOUD_ROOT = Path(r"C:\Users\windo\Pictures\iCloud Photos\Photos")
OUTPUT_DIR = Path(r"C:\Users\windo\VS_Code\photos\results")

MEDIA_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng",
    ".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts",
    ".3gp", ".mpg", ".mpeg", ".wmv",
}

IMAGE_EXTENSIONS = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng",
}

VIDEO_EXTENSIONS = {
    ".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts",
    ".3gp", ".mpg", ".mpeg", ".wmv",
}

# Suffixes to strip for normalization
DUP_SUFFIX_RE = re.compile(r"[_(]\d+\)$")
SLOWMO_RE = re.compile(r"_slowmo$", re.IGNORECASE)

EXIFTOOL_BATCH_SIZE = 200
TIMESTAMP_TOLERANCE_SECS = 2

EXIF_TAGS = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "ModifyDate",
    "MediaModifyDate",
]

CAPTURE_PRIORITY = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "ModifyDate",
    "MediaModifyDate",
]

REPORT_COLUMNS = [
    "wn_full_path",
    "wn_filename",
    "wn_extension",
    "wn_normalized_base",
    "wn_capture_date",
    "wn_metadata_field_used",
    "matched_icloud_path",
    "matched_icloud_filename",
    "matched_icloud_capture_date",
    "matched_icloud_metadata_field",
    "match_status",
    "match_confidence",
    "ambiguity_notes",
]


def normalize_base(filename: str) -> str:
    """Normalize a filename to its base for matching.
    Strip extension, trailing dup suffixes, _slowmo, and lowercase.
    """
    stem = Path(filename).stem
    # Strip _slowmo
    stem = SLOWMO_RE.sub("", stem)
    # Strip trailing (0), (1), _(1), etc.
    stem = DUP_SUFFIX_RE.sub("", stem)
    return stem.strip().lower()


def normalize_datetime_str(s: str) -> str:
    """Normalize date/time to YYYY:MM:DD HH:MM:SS. Returns '' if invalid."""
    if not s:
        return ""
    s = str(s).strip()
    if s in ("0000:00:00 00:00:00", "0000:00:00", ""):
        return ""
    try:
        parts = s.split(" ", 1)
        date_part = parts[0].replace("-", ":")
        time_part = parts[1] if len(parts) > 1 else "00:00:00"
        # Strip timezone offset
        for tz_sep in ("+", "-"):
            idx = time_part.find(tz_sep, 6)
            if idx > 0:
                time_part = time_part[:idx]
                break
        # Strip fractional seconds
        dot_idx = time_part.find(".")
        if dot_idx > 0:
            time_part = time_part[:dot_idx]
        d = dt.datetime.strptime(
            f"{date_part} {time_part}".replace(":", "-", 2), "%Y-%m-%d %H:%M:%S"
        )
        return d.strftime("%Y:%m:%d %H:%M:%S")
    except (ValueError, IndexError):
        return ""


def parse_exif_dt(s: str) -> dt.datetime | None:
    """Parse YYYY:MM:DD HH:MM:SS to datetime."""
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.replace(":", "-", 2), "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return None


def dates_compatible(d1: str, d2: str) -> bool:
    """Check if two date strings are within TIMESTAMP_TOLERANCE_SECS."""
    dt1 = parse_exif_dt(d1)
    dt2 = parse_exif_dt(d2)
    if dt1 is None or dt2 is None:
        return False
    return abs((dt2 - dt1).total_seconds()) <= TIMESTAMP_TOLERANCE_SECS


def run_exiftool_batch(paths: list[Path]) -> dict[str, dict]:
    """Run ExifTool in batch JSON mode, return dict keyed by resolved path."""
    tag_args = [f"-{tag}" for tag in EXIF_TAGS]
    cmd = [
        "exiftool", "-json", "-n",
        "-charset", "filename=utf8",
        *tag_args,
        *[str(p) for p in paths],
    ]
    result = subprocess.run(cmd, capture_output=True, text=True, timeout=600)
    records: dict[str, dict] = {}
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return records
        for entry in data:
            src = entry.get("SourceFile", "")
            records[str(Path(src).resolve())] = entry
    return records


def extract_capture_date(meta: dict | None) -> tuple[str, str]:
    """Return (normalized_date, field_used) from ExifTool metadata."""
    if meta is None:
        return ("", "")
    for field in CAPTURE_PRIORITY:
        raw = meta.get(field)
        if raw is None:
            continue
        val = normalize_datetime_str(str(raw))
        if val:
            return (val, field)
    return ("", "")


def discover_files(root: Path) -> list[Path]:
    """Find all media files under root."""
    found = []
    for dirpath, _, filenames in os.walk(root):
        for fname in filenames:
            p = Path(dirpath) / fname
            if p.suffix.lower() in MEDIA_EXTENSIONS:
                found.append(p)
    return found


def extract_all_metadata(files: list[Path], label: str) -> dict[str, dict]:
    """Run ExifTool on all files in batches, return dict by resolved path."""
    all_meta: dict[str, dict] = {}
    total = len(files)
    for i in range(0, total, EXIFTOOL_BATCH_SIZE):
        batch = files[i:i + EXIFTOOL_BATCH_SIZE]
        end = min(i + EXIFTOOL_BATCH_SIZE, total)
        print(f"  [{label}] ExifTool batch {i + 1}-{end} of {total} ...")
        try:
            result = run_exiftool_batch(batch)
            all_meta.update(result)
        except Exception as exc:
            print(f"    WARNING: batch error: {exc}")
    return all_meta


def main() -> None:
    print("=" * 70)
    print("  WHY NOT iPHONE vs iCLOUD RECONCILIATION")
    print("=" * 70)

    # 1. Discover files
    print("\n[1/5] Discovering files ...")
    wn_files = discover_files(WN_ROOT)
    icloud_files = discover_files(ICLOUD_ROOT)
    print(f"  WN files:     {len(wn_files):,}")
    print(f"  iCloud files: {len(icloud_files):,}")

    # 2. Build base name index for iCloud (no ExifTool yet)
    print("\n[2/5] Indexing iCloud by normalized base name ...")
    icloud_by_base: dict[str, list[Path]] = defaultdict(list)
    for fpath in icloud_files:
        nbase = normalize_base(fpath.name)
        icloud_by_base[nbase].append(fpath)

    # Find which WN bases have iCloud candidates
    wn_bases = {normalize_base(f.name) for f in wn_files}
    matched_bases = wn_bases & set(icloud_by_base.keys())
    icloud_to_scan = []
    for base in matched_bases:
        icloud_to_scan.extend(icloud_by_base[base])

    print(f"  Unique WN bases: {len(wn_bases):,}")
    print(f"  Bases with iCloud candidates: {len(matched_bases):,}")
    print(f"  iCloud files needing ExifTool: {len(icloud_to_scan):,} (of {len(icloud_files):,})")

    # 3. Extract metadata only for WN files + matched iCloud subset
    print("\n[3/5] Extracting metadata via ExifTool ...")
    wn_meta = extract_all_metadata(wn_files, "WN")
    icloud_meta = extract_all_metadata(icloud_to_scan, "iCloud-subset")

    # 4. Build iCloud index with metadata
    print("\n[4/5] Building iCloud index with capture dates ...")
    icloud_index: dict[str, list[tuple[Path, str, str]]] = defaultdict(list)

    for fpath in icloud_files:
        nbase = normalize_base(fpath.name)
        resolved = str(fpath.resolve())
        meta = icloud_meta.get(resolved)
        cap_date, cap_field = extract_capture_date(meta)
        icloud_index[nbase].append((fpath, cap_date, cap_field))

    print(f"  Unique normalized bases in iCloud: {len(icloud_index):,}")

    # 5. Match WN files
    print("\n[5/5] Matching WN files against iCloud ...")
    results: list[dict[str, str]] = []

    bucket_counts = Counter()
    no_metadata_count = 0

    for wn_path in wn_files:
        resolved = str(wn_path.resolve())
        meta = wn_meta.get(resolved)
        wn_cap_date, wn_cap_field = extract_capture_date(meta)
        ext = wn_path.suffix.lower()
        nbase = normalize_base(wn_path.name)
        is_video = ext in VIDEO_EXTENSIONS
        is_mov = ext == ".mov"

        row = {
            "wn_full_path": str(wn_path),
            "wn_filename": wn_path.name,
            "wn_extension": ext,
            "wn_normalized_base": nbase,
            "wn_capture_date": wn_cap_date,
            "wn_metadata_field_used": wn_cap_field,
            "matched_icloud_path": "",
            "matched_icloud_filename": "",
            "matched_icloud_capture_date": "",
            "matched_icloud_metadata_field": "",
            "match_status": "",
            "match_confidence": "",
            "ambiguity_notes": "",
        }

        if not wn_cap_date:
            no_metadata_count += 1

        # Find candidates by normalized base
        candidates = icloud_index.get(nbase, [])

        if not candidates:
            # No base name match at all
            if is_mov:
                row["match_status"] = "UNMATCHED_MOV"
                row["match_confidence"] = "no_base_match"
            else:
                row["match_status"] = "UNMATCHED_OTHER"
                row["match_confidence"] = "no_base_match"
            bucket_counts[row["match_status"]] += 1
            results.append(row)
            continue

        if not wn_cap_date:
            # WN has no metadata date -- cannot confirm match
            if is_mov:
                row["match_status"] = "UNMATCHED_MOV"
            else:
                row["match_status"] = "UNMATCHED_OTHER"
            row["match_confidence"] = "base_match_but_no_wn_metadata"
            row["ambiguity_notes"] = (
                f"{len(candidates)} iCloud base match(es) but WN file has no metadata date"
            )
            bucket_counts[row["match_status"]] += 1
            results.append(row)
            continue

        # Check date compatibility with candidates
        date_matches: list[tuple[Path, str, str]] = []
        date_no_meta: list[tuple[Path, str, str]] = []

        for ic_path, ic_date, ic_field in candidates:
            if not ic_date:
                date_no_meta.append((ic_path, ic_date, ic_field))
            elif dates_compatible(wn_cap_date, ic_date):
                date_matches.append((ic_path, ic_date, ic_field))

        if len(date_matches) == 1:
            # Single confirmed match
            ic_path, ic_date, ic_field = date_matches[0]
            if is_mov:
                row["match_status"] = "MATCHED_MOV_RELATED"
            else:
                row["match_status"] = "MATCHED_IMAGE_CANDIDATE"
            row["match_confidence"] = "high"
            row["matched_icloud_path"] = str(ic_path)
            row["matched_icloud_filename"] = ic_path.name
            row["matched_icloud_capture_date"] = ic_date
            row["matched_icloud_metadata_field"] = ic_field

        elif len(date_matches) > 1:
            # Multiple date matches -- ambiguous, pick closest but flag
            best = min(
                date_matches,
                key=lambda x: abs(
                    (parse_exif_dt(wn_cap_date) - parse_exif_dt(x[1])).total_seconds()
                )
                if parse_exif_dt(x[1]) else 999999,
            )
            ic_path, ic_date, ic_field = best
            if is_mov:
                row["match_status"] = "MATCHED_MOV_RELATED"
            else:
                row["match_status"] = "MATCHED_IMAGE_CANDIDATE"
            row["match_confidence"] = "ambiguous_multiple_date_matches"
            row["matched_icloud_path"] = str(ic_path)
            row["matched_icloud_filename"] = ic_path.name
            row["matched_icloud_capture_date"] = ic_date
            row["matched_icloud_metadata_field"] = ic_field
            row["ambiguity_notes"] = (
                f"{len(date_matches)} iCloud files match base+date"
            )

        else:
            # Base matches but no date match
            if is_mov:
                row["match_status"] = "UNMATCHED_MOV"
            else:
                row["match_status"] = "UNMATCHED_OTHER"
            row["match_confidence"] = "base_match_but_date_mismatch"

            # Include closest candidate info for review
            dated_candidates = [
                (p, d, f) for p, d, f in candidates if d
            ]
            if dated_candidates:
                closest = min(
                    dated_candidates,
                    key=lambda x: abs(
                        (parse_exif_dt(wn_cap_date) - parse_exif_dt(x[1])).total_seconds()
                    )
                    if parse_exif_dt(x[1]) else 999999,
                )
                ic_path, ic_date, ic_field = closest
                diff = abs(
                    (parse_exif_dt(wn_cap_date) - parse_exif_dt(ic_date)).total_seconds()
                )
                row["matched_icloud_path"] = str(ic_path)
                row["matched_icloud_filename"] = ic_path.name
                row["matched_icloud_capture_date"] = ic_date
                row["matched_icloud_metadata_field"] = ic_field
                row["ambiguity_notes"] = (
                    f"closest iCloud date diff: {diff:.0f}s; "
                    f"{len(candidates)} base match(es), 0 date matches"
                )
            elif date_no_meta:
                row["ambiguity_notes"] = (
                    f"{len(date_no_meta)} iCloud base match(es) but none have metadata dates"
                )

        bucket_counts[row["match_status"]] += 1
        results.append(row)

    # Write reports
    print("\nWriting reports ...")

    # Full report
    full_path = OUTPUT_DIR / "wn_icloud_reconciliation_full.csv"
    with open(full_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)
    print(f"  Full report:   {full_path}")

    # Bucket-specific reports
    buckets = {
        "MATCHED_IMAGE_CANDIDATE": "wn_matched_image_candidates.csv",
        "MATCHED_MOV_RELATED": "wn_matched_mov_related.csv",
        "UNMATCHED_MOV": "wn_unmatched_mov.csv",
        "UNMATCHED_OTHER": "wn_unmatched_other.csv",
    }

    for status, fname in buckets.items():
        bucket_rows = [r for r in results if r["match_status"] == status]
        path = OUTPUT_DIR / fname
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
            writer.writeheader()
            writer.writerows(bucket_rows)
        print(f"  {status}: {path} ({len(bucket_rows):,} rows)")

    # Summary
    total_wn = len(results)
    print(f"\n{'=' * 70}")
    print(f"  RECONCILIATION SUMMARY")
    print(f"{'=' * 70}")
    print(f"  WN files scanned:            {total_wn:,}")
    print(f"  iCloud files scanned:        {len(icloud_files):,}")
    print(f"  WN files with no metadata:   {no_metadata_count:,}")
    print(f"")
    print(f"  MATCHED_IMAGE_CANDIDATE:     {bucket_counts.get('MATCHED_IMAGE_CANDIDATE', 0):,}")
    print(f"  MATCHED_MOV_RELATED:         {bucket_counts.get('MATCHED_MOV_RELATED', 0):,}")
    print(f"  UNMATCHED_MOV:               {bucket_counts.get('UNMATCHED_MOV', 0):,}")
    print(f"  UNMATCHED_OTHER:             {bucket_counts.get('UNMATCHED_OTHER', 0):,}")
    print(f"{'=' * 70}")

    # Sample rows from each bucket
    for status in buckets:
        bucket_rows = [r for r in results if r["match_status"] == status]
        if bucket_rows:
            print(f"\n  Sample {status} rows:")
            for r in bucket_rows[:3]:
                ic = r["matched_icloud_filename"] or "(none)"
                conf = r["match_confidence"]
                print(f"    {r['wn_filename']} -> {ic}  [{conf}]")

    # Confidence breakdown
    print(f"\n  Match confidence breakdown:")
    conf_counts: Counter[str] = Counter()
    for r in results:
        conf_counts[r["match_confidence"]] += 1
    for conf, cnt in conf_counts.most_common():
        print(f"    {conf}: {cnt:,}")

    print(f"\n  Metadata fields used (WN):")
    field_counts: Counter[str] = Counter()
    for r in results:
        f = r["wn_metadata_field_used"]
        if f:
            field_counts[f] += 1
    for field, cnt in field_counts.most_common():
        print(f"    {field}: {cnt:,}")

    print(f"\n{'=' * 70}")
    print(f"  INTERPRETATION")
    print(f"{'=' * 70}")
    matched_img = bucket_counts.get("MATCHED_IMAGE_CANDIDATE", 0)
    matched_mov = bucket_counts.get("MATCHED_MOV_RELATED", 0)
    unmatched_mov = bucket_counts.get("UNMATCHED_MOV", 0)
    unmatched_other = bucket_counts.get("UNMATCHED_OTHER", 0)
    print(f"  {matched_img:,} still images in WN appear to already exist in iCloud")
    print(f"    and are candidates for safe removal from WN.")
    print(f"  {matched_mov:,} MOV files in WN are related to iCloud assets")
    print(f"    but cannot be merged into iCloud -- review separately.")
    print(f"  {unmatched_mov:,} MOV files in WN have no iCloud match")
    print(f"    and should be archived separately.")
    print(f"  {unmatched_other:,} non-MOV files in WN have no iCloud match")
    print(f"    and should be kept.")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    main()
