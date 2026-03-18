#!/usr/bin/env python3
"""
copy_live_photo_heic.py

Copies HEIC sources for Live Photo rows from v4_excluded into MP1.
Does NOT quarantine or move the existing JPG or MOV.

NON-DESTRUCTIVE — copies only. No moves, deletions, renames, or overwrites.
"""

from __future__ import annotations

import csv
import shutil
from collections import Counter
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v4_excluded.csv")
REPORT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\copy_live_photo_heic_report.csv")

LIVE_PHOTO_REASONS = {
    "SOURCE_LIVE_PHOTO_HINT; LIVE_PHOTO_MOV_COMPANION",
    "SOURCE_LIVE_PHOTO_HINT",
}

REPORT_COLUMNS = [
    "source_heic_path",
    "copied_heic_path",
    "target_folder",
    "exclusion_reason",
    "status",
    "error_message",
]


def main() -> None:
    print("Reading v4_excluded ...")
    to_copy: list[dict[str, str]] = []

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("exclusion_reason", "") in LIVE_PHOTO_REASONS:
                to_copy.append(row)

    print(f"  Live Photo rows to process: {len(to_copy)}")
    print("\nCopying ...")

    results: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()

    for i, row in enumerate(to_copy, 1):
        src = Path(row.get("source_heic_path", ""))
        dest = Path(row.get("copied_heic_path", ""))
        folder = row.get("target_folder", "")

        report_row = {
            "source_heic_path": str(src),
            "copied_heic_path": str(dest),
            "target_folder": folder,
            "exclusion_reason": row.get("exclusion_reason", ""),
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
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src), str(dest))
                report_row["status"] = "Success"
                status_counts["Success"] += 1
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
    print(f"  LIVE PHOTO HEIC COPY REPORT")
    print(f"{'=' * 60}")
    print(f"  Total processed:     {len(results)}")
    for s, c in status_counts.most_common():
        print(f"    {s}: {c}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
