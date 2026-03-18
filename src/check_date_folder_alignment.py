#!/usr/bin/env python3
"""
check_date_folder_alignment.py

Compares capture_time_best (ExifTool-derived) against the MP1 folder name
for every file in My_Pictures1. Reports any file whose most likely date
taken differs from the folder it resides in.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
import re
from collections import Counter
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\date_folder_misalignment.csv")

MP1_PREFIX = r"C:\Users\windo\My_Pictures1"

# Regex to extract YYYY_MM_DD folder name
FOLDER_DATE_RE = re.compile(r"(\d{4}_\d{2}_\d{2})$")

OUTPUT_COLUMNS = [
    "full_path",
    "file_name",
    "extension",
    "capture_time_best",
    "capture_time_source",
    "expected_date_folder",
    "actual_folder_name",
    "actual_folder_path",
    "date_diff_days",
    "file_size_bytes",
]


def ct_to_folder_date(ct: str) -> str:
    """Convert '2019:03:05 12:34:56' to '2019_03_05'."""
    if len(ct) < 10:
        return ""
    return ct[:10].replace(":", "_")


def folder_date_to_comparable(folder: str) -> str:
    """Convert '2019_03_05' to '2019-03-05' for date math."""
    return folder.replace("_", "-")


def days_between(date1: str, date2: str) -> int | None:
    """Calculate days between two YYYY_MM_DD strings."""
    import datetime as dt
    try:
        d1 = dt.datetime.strptime(date1, "%Y_%m_%d")
        d2 = dt.datetime.strptime(date2, "%Y_%m_%d")
        return abs((d2 - d1).days)
    except (ValueError, TypeError):
        return None


def main() -> None:
    print("Reading inventory ...")

    total_mp1 = 0
    in_date_folder = 0
    not_in_date_folder = 0
    misaligned: list[dict[str, str]] = []
    aligned = 0
    no_capture_time = 0

    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fp = row.get("full_path", "")

            # Only MP1 active files (skip quarantine)
            if MP1_PREFIX not in fp or "_JPG_TO_DELETE" in fp:
                continue

            total_mp1 += 1
            parent = row.get("parent_folder", "")
            folder_name = Path(parent).name

            # Check if folder follows YYYY_MM_DD pattern
            m = FOLDER_DATE_RE.match(folder_name)
            if not m:
                not_in_date_folder += 1
                continue

            in_date_folder += 1
            actual_date = m.group(1)
            ct = row.get("capture_time_best", "").strip()

            if not ct:
                no_capture_time += 1
                continue

            expected_date = ct_to_folder_date(ct)
            if not expected_date:
                no_capture_time += 1
                continue

            if expected_date == actual_date:
                aligned += 1
                continue

            diff = days_between(expected_date, actual_date)

            misaligned.append({
                "full_path": fp,
                "file_name": row.get("file_name", ""),
                "extension": row.get("extension", "").lower(),
                "capture_time_best": ct,
                "capture_time_source": row.get("capture_time_source", ""),
                "expected_date_folder": expected_date,
                "actual_folder_name": actual_date,
                "actual_folder_path": parent,
                "date_diff_days": str(diff) if diff is not None else "",
                "file_size_bytes": row.get("file_size_bytes", ""),
            })

    # Sort by date diff descending (biggest misalignments first)
    misaligned.sort(key=lambda r: (
        -int(r["date_diff_days"]) if r["date_diff_days"] else 0,
        r["actual_folder_name"],
    ))

    print(f"\nWriting -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(misaligned)

    # Breakdown by diff range
    diff_ranges: Counter[str] = Counter()
    for r in misaligned:
        d = int(r["date_diff_days"]) if r["date_diff_days"] else 0
        if d == 0:
            diff_ranges["0 days"] += 1
        elif d == 1:
            diff_ranges["1 day"] += 1
        elif d <= 7:
            diff_ranges["2-7 days"] += 1
        elif d <= 30:
            diff_ranges["8-30 days"] += 1
        elif d <= 365:
            diff_ranges["31-365 days"] += 1
        else:
            diff_ranges["> 1 year"] += 1

    # Extension breakdown
    ext_counts: Counter[str] = Counter()
    for r in misaligned:
        ext_counts[r["extension"]] += 1

    # Capture time source breakdown
    src_counts: Counter[str] = Counter()
    for r in misaligned:
        src_counts[r["capture_time_source"]] += 1

    print(f"\n{'=' * 60}")
    print(f"  DATE / FOLDER ALIGNMENT REPORT")
    print(f"{'=' * 60}")
    print(f"  MP1 files total:             {total_mp1:,}")
    print(f"  In date folders:             {in_date_folder:,}")
    print(f"  Not in date folders:         {not_in_date_folder:,}")
    print(f"  No capture time:             {no_capture_time:,}")
    print(f"")
    print(f"  Aligned (date matches):      {aligned:,}")
    print(f"  MISALIGNED:                  {len(misaligned):,}")
    print(f"")
    print(f"  Misalignment by range:")
    for label in ["1 day", "2-7 days", "8-30 days", "31-365 days", "> 1 year"]:
        print(f"    {label}: {diff_ranges.get(label, 0):,}")
    print(f"")
    print(f"  Misaligned by extension:")
    for ext, cnt in ext_counts.most_common():
        print(f"    {ext}: {cnt:,}")
    print(f"")
    print(f"  Misaligned by capture_time_source:")
    for src, cnt in src_counts.most_common():
        print(f"    {src}: {cnt:,}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
