#!/usr/bin/env python3
"""
build_non_jpg_heic_review.py

Builds a review CSV for the 625 non-JPG/HEIC iCloud files (on or before 2019-10-15).
Includes hyperlinks for files not yet in MP1.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\non_jpg_heic_mp1_check.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\non_jpg_heic_review.csv")

OUTPUT_COLUMNS = [
    "file_name",
    "extension",
    "capture_time_best",
    "icloud_full_path",
    "icloud_hyperlink",
    "expected_mp1_folder",
    "mp1_match_path",
    "exists_in_mp1",
    "file_size_bytes",
]


def main() -> None:
    print("Reading check results ...")
    rows: list[dict[str, str]] = []

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            icloud_path = row.get("icloud_full_path", "")
            exists = row.get("exists_in_mp1", "")

            # Hyperlink for files NOT in MP1 so user can open and review
            if exists == "No":
                hyperlink = f'=HYPERLINK("{icloud_path}","Open")'
            else:
                hyperlink = ""

            rows.append({
                "file_name": row.get("file_name", ""),
                "extension": row.get("extension", ""),
                "capture_time_best": row.get("capture_time_best", ""),
                "icloud_full_path": icloud_path,
                "icloud_hyperlink": hyperlink,
                "expected_mp1_folder": row.get("expected_mp1_folder", ""),
                "mp1_match_path": row.get("mp1_match_path", ""),
                "exists_in_mp1": exists,
                "file_size_bytes": row.get("file_size_bytes", ""),
            })

    print(f"  Total rows: {len(rows)}")

    print(f"Writing -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    yes = sum(1 for r in rows if r["exists_in_mp1"] == "Yes")
    no = sum(1 for r in rows if r["exists_in_mp1"] == "No")
    print(f"\n  In MP1 (Yes): {yes:,}")
    print(f"  Not in MP1 (No): {no:,}  (hyperlinks added)")
    print(f"  Total: {len(rows):,}")


if __name__ == "__main__":
    main()
