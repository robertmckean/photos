#!/usr/bin/env python3
"""
check_non_jpg_heic_in_mp1.py

For non-JPG/HEIC iCloud files with capture_time_best on or before 2019-10-15,
checks whether the file exists in the corresponding MP1 date folder.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
import os
from collections import Counter
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\non_jpg_heic_mp1_check.csv")

ICLOUD_PREFIX = r"C:\Users\windo\Pictures\iCloud Photos\Photos"
MP1_ROOT = Path(r"C:\Users\windo\My_Pictures1")

# Extensions to SKIP (already handled)
SKIP_EXTENSIONS = {".jpg", ".jpeg", ".heic", ".heif"}

# Extensions to CHECK
CHECK_EXTENSIONS = {".png", ".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts",
                    ".3gp", ".mpg", ".mpeg", ".wmv", ".gif", ".webp",
                    ".tif", ".tiff", ".bmp", ".dng"}

# Cutoff date (inclusive)
CUTOFF = "2019:10:15 23:59:59"

OUTPUT_COLUMNS = [
    "icloud_full_path",
    "file_name",
    "extension",
    "capture_time_best",
    "capture_time_source",
    "file_size_bytes",
    "expected_mp1_folder",
    "exists_in_mp1",
    "mp1_match_path",
]


def capture_date_to_folder(ct: str) -> str:
    """Convert '2019:03:05 12:34:56' to '2019_03_05'."""
    if len(ct) < 10:
        return ""
    return ct[:10].replace(":", "_")


def main() -> None:
    print("Reading inventory ...")

    # Build MP1 file index: folder -> set of lowercase filenames
    # for fast lookup
    mp1_index: dict[str, set[str]] = {}
    icloud_candidates: list[dict[str, str]] = []

    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fp = row.get("full_path", "")

            if ICLOUD_PREFIX in fp:
                ext = row.get("extension", "").lower()
                if ext in SKIP_EXTENSIONS or ext not in CHECK_EXTENSIONS:
                    continue
                ct = row.get("capture_time_best", "").strip()
                if ct and ct <= CUTOFF:
                    icloud_candidates.append(row)

            elif r"My_Pictures1" in fp and r"_JPG_TO_DELETE" not in fp:
                parent = row.get("parent_folder", "")
                fname = row.get("file_name", "").lower()
                if parent not in mp1_index:
                    mp1_index[parent] = set()
                mp1_index[parent].add(fname)

    print(f"  iCloud candidates (non-JPG/HEIC, <= 2019-10-15): {len(icloud_candidates):,}")
    print(f"  MP1 folders indexed: {len(mp1_index):,}")

    # Also scan MP1 filesystem for files that may not be in the inventory
    # (files we copied in recent batches)
    print("\nScanning MP1 filesystem for current state ...")
    mp1_fs_index: dict[str, set[str]] = {}
    for dirpath, _, filenames in os.walk(MP1_ROOT):
        if "_JPG_TO_DELETE" in dirpath:
            continue
        lower_files = {fn.lower() for fn in filenames}
        mp1_fs_index[dirpath] = lower_files

    print(f"  MP1 filesystem folders scanned: {len(mp1_fs_index):,}")

    # Check each candidate
    print("\nChecking ...")
    results: list[dict[str, str]] = []
    yes_count = 0
    no_count = 0
    ext_counts: Counter[str] = Counter()

    for row in icloud_candidates:
        ct = row.get("capture_time_best", "").strip()
        fname = row.get("file_name", "")
        ext = row.get("extension", "").lower()

        folder_name = capture_date_to_folder(ct)
        expected_folder = str(MP1_ROOT / folder_name)

        # Check both inventory index and filesystem
        fname_lower = fname.lower()
        in_inventory = fname_lower in mp1_index.get(expected_folder, set())
        in_filesystem = fname_lower in mp1_fs_index.get(expected_folder, set())

        exists = in_inventory or in_filesystem
        match_path = str(Path(expected_folder) / fname) if exists else ""

        ext_counts[ext] += 1
        if exists:
            yes_count += 1
        else:
            no_count += 1

        results.append({
            "icloud_full_path": row.get("full_path", ""),
            "file_name": fname,
            "extension": ext,
            "capture_time_best": ct,
            "capture_time_source": row.get("capture_time_source", ""),
            "file_size_bytes": row.get("file_size_bytes", ""),
            "expected_mp1_folder": expected_folder,
            "exists_in_mp1": "Yes" if exists else "No",
            "mp1_match_path": match_path,
        })

    # Sort by capture_time_best
    results.sort(key=lambda r: r["capture_time_best"])

    print(f"\nWriting -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 60}")
    print(f"  NON-JPG/HEIC iCloud CHECK (on or before 2019-10-15)")
    print(f"{'=' * 60}")
    print(f"  Total checked:       {len(results):,}")
    print(f"  In MP1 (Yes):        {yes_count:,}")
    print(f"  Not in MP1 (No):     {no_count:,}")
    print(f"")
    print(f"  By extension:")
    for ext, cnt in ext_counts.most_common():
        yes_for_ext = sum(1 for r in results if r["extension"] == ext and r["exists_in_mp1"] == "Yes")
        no_for_ext = cnt - yes_for_ext
        print(f"    {ext}: {cnt:,}  (Yes: {yes_for_ext:,}, No: {no_for_ext:,})")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
