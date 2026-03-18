#!/usr/bin/env python3
"""
copy_non_jpg_heic_to_mp1.py

Copies the 402 non-JPG/HEIC iCloud files (not yet in MP1) into their
corresponding MP1 date folders.

NON-DESTRUCTIVE — copies only. No moves, deletions, renames, or overwrites.
"""

from __future__ import annotations

import csv
import shutil
from collections import Counter
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\non_jpg_heic_mp1_check.csv")
REPORT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\copy_non_jpg_heic_report.csv")

REPORT_COLUMNS = [
    "file_name",
    "extension",
    "capture_time_best",
    "icloud_full_path",
    "destination_path",
    "status",
    "error_message",
]


def main() -> None:
    print("Reading check results ...")
    to_copy: list[dict[str, str]] = []

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("exists_in_mp1") == "No":
                to_copy.append(row)

    print(f"  Files to copy: {len(to_copy):,}")
    print("\nCopying ...")

    results: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()
    ext_counts: Counter[str] = Counter()

    for i, row in enumerate(to_copy, 1):
        if i % 100 == 0 or i == len(to_copy):
            print(f"  {i:,} / {len(to_copy):,}")

        src = Path(row["icloud_full_path"])
        dest_folder = Path(row["expected_mp1_folder"])
        dest = dest_folder / src.name
        ext = row.get("extension", "").lower()

        report_row = {
            "file_name": src.name,
            "extension": ext,
            "capture_time_best": row.get("capture_time_best", ""),
            "icloud_full_path": str(src),
            "destination_path": str(dest),
            "status": "",
            "error_message": "",
        }

        if dest.exists():
            report_row["status"] = "destination_exists"
            status_counts["destination_exists"] += 1
        elif not src.exists():
            report_row["status"] = "source_missing"
            status_counts["source_missing"] += 1
        else:
            try:
                dest_folder.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                report_row["status"] = "Success"
                status_counts["Success"] += 1
                ext_counts[ext] += 1
            except Exception as exc:
                report_row["status"] = "Error"
                report_row["error_message"] = str(exc)
                status_counts["Error"] += 1

        results.append(report_row)

    print(f"\nWriting -> {REPORT_CSV}")
    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 60}")
    print(f"  COPY REPORT")
    print(f"{'=' * 60}")
    print(f"  Total processed:     {len(results):,}")
    for s, c in status_counts.most_common():
        print(f"    {s}: {c:,}")
    print(f"")
    print(f"  Copied by extension:")
    for ext, c in ext_counts.most_common():
        print(f"    {ext}: {c:,}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
