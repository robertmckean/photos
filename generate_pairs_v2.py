#!/usr/bin/env python3
"""
generate_pairs_v2.py

Generates a pairing report of iCloud image files (HEIC/JPG/JPEG) matched
to MP1 JPG files by capture_time_best + comparison_stem (1-to-1 only).

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v2.csv")

ICLOUD_PREFIX = r"C:\Users\windo\Pictures\iCloud Photos\Photos"
MP1_PREFIX = r"C:\Users\windo\My_Pictures1"

SOURCE_EXTENSIONS: set[str] = {".heic", ".heif", ".jpg", ".jpeg"}
TARGET_EXTENSIONS: set[str] = {".jpg", ".jpeg"}

DUP_SUFFIX_RE = re.compile(r"\(\d+\)$")

OUTPUT_COLUMNS: list[str] = [
    "source_heic_path",
    "source_heic_file_name",
    "source_capture_time",
    "target_jpg_path",
    "target_jpg_file_name",
    "target_folder",
    "copied_heic_path",
    "comparison_stem",
    "file_size_heic",
    "file_size_jpg",
    "mp1_file_to_replace",
    "pairing_status",
]


def derive_comparison_stem(filename: str) -> str:
    """Remove extension and trailing (1)/(2)/etc. for matching only."""
    stem = Path(filename).stem
    return DUP_SUFFIX_RE.sub("", stem).strip()


def main() -> None:
    print("Reading CSV ...")

    # MP1 JPG lookup: (capture_time, comparison_stem) -> list of row dicts
    mp1_jpgs: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    icloud_files: list[dict[str, str]] = []
    total_icloud = 0
    total_mp1_jpg = 0

    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fp = row.get("full_path", "")
            ext = row.get("extension", "").lower()
            ct = row.get("capture_time_best", "").strip()

            if MP1_PREFIX in fp and ext in TARGET_EXTENSIONS:
                total_mp1_jpg += 1
                if ct:
                    cstem = derive_comparison_stem(row.get("file_name", ""))
                    mp1_jpgs[(ct, cstem)].append(row)

            elif ICLOUD_PREFIX in fp:
                total_icloud += 1
                if ext in SOURCE_EXTENSIONS and ct:
                    icloud_files.append(row)

    print(f"  iCloud files scanned:  {total_icloud:,}")
    print(f"  MP1 JPG files scanned: {total_mp1_jpg:,}")
    print(f"  iCloud candidates:     {len(icloud_files):,}")

    print("\nEvaluating matches ...")

    results: list[dict[str, str]] = []

    for irow in icloud_files:
        ct = irow.get("capture_time_best", "").strip()
        src_name = irow.get("file_name", "")
        src_cstem = derive_comparison_stem(src_name)
        src_path = irow.get("full_path", "")
        src_size = irow.get("file_size_bytes", "")

        key = (ct, src_cstem)
        candidates = mp1_jpgs.get(key, [])

        # Only EXPECTED_MATCH: exactly one MP1 JPG candidate
        if len(candidates) != 1:
            continue

        mp1_row = candidates[0]
        mp1_folder = mp1_row.get("parent_folder", "")
        copied_path = str(Path(mp1_folder) / src_name)

        results.append({
            "source_heic_path": src_path,
            "source_heic_file_name": src_name,
            "source_capture_time": ct,
            "target_jpg_path": mp1_row.get("full_path", ""),
            "target_jpg_file_name": mp1_row.get("file_name", ""),
            "target_folder": mp1_folder,
            "copied_heic_path": copied_path,
            "comparison_stem": src_cstem,
            "file_size_heic": src_size,
            "file_size_jpg": mp1_row.get("file_size_bytes", ""),
            "mp1_file_to_replace": mp1_row.get("full_path", ""),
            "pairing_status": "EXPECTED_MATCH",
        })

    # Sort by source_capture_time asc, then source_heic_path asc
    results.sort(key=lambda r: (r["source_capture_time"], r["source_heic_path"]))

    # Write CSV
    print(f"\nWriting -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    ext_counts: Counter[str] = Counter()
    for r in results:
        ext = Path(r["source_heic_file_name"]).suffix.lower()
        ext_counts[ext] += 1

    print(f"\n{'=' * 60}")
    print(f"  SUMMARY")
    print(f"{'=' * 60}")
    print(f"  iCloud files scanned:      {total_icloud:,}")
    print(f"  MP1 JPG files scanned:     {total_mp1_jpg:,}")
    print(f"  EXPECTED_MATCH rows:       {len(results):,}")
    print(f"")
    print(f"  By source extension:")
    for ext, cnt in ext_counts.most_common():
        print(f"    {ext}: {cnt:,}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
