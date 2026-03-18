#!/usr/bin/env python3
"""
regenerate_progress.py

Regenerates icloud_mp1_pairs_v4_safe_progress.csv by checking the actual
filesystem state for each row in v4_safe.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v4_safe.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v4_safe_progress.csv")

MP1_PREFIX = r"C:\Users\windo\My_Pictures1"
QUARANTINE_ROOT = Path(r"C:\Users\windo\My_Pictures1\_JPG_TO_DELETE")


def compute_quarantine_path(mp1_jpg_path: str) -> str:
    """Derive the expected quarantine path preserving folder structure."""
    mp1_base = Path(MP1_PREFIX)
    jpg = Path(mp1_jpg_path)
    try:
        rel = jpg.relative_to(mp1_base)
    except ValueError:
        return ""
    return str(QUARANTINE_ROOT / rel)


def main() -> None:
    print("Reading v4_safe CSV ...")
    rows: list[dict[str, str]] = []
    fieldnames: list[str] = []

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        fieldnames = list(reader.fieldnames or [])
        for row in reader:
            rows.append(row)

    print(f"  Total rows: {len(rows):,}")
    print("\nChecking filesystem state ...")

    # Add new columns
    extra_cols = []
    if "progress_status" not in fieldnames:
        extra_cols.append("progress_status")
    if "quarantine_expected_path" not in fieldnames:
        extra_cols.append("quarantine_expected_path")
    out_columns = fieldnames + extra_cols

    counts = {"COMPLETED": 0, "COPY_DONE_MOVE_PENDING": 0, "NOT_STARTED": 0, "OTHER": 0}

    for i, row in enumerate(rows):
        if (i + 1) % 1000 == 0 or (i + 1) == len(rows):
            print(f"  {i + 1:,} / {len(rows):,}")

        copied_path = row.get("copied_heic_path", "")
        mp1_jpg_path = row.get("target_jpg_path", "") or row.get("mp1_file_to_replace", "")
        quarantine_path = compute_quarantine_path(mp1_jpg_path)

        copied_exists = Path(copied_path).exists() if copied_path else False
        jpg_exists = Path(mp1_jpg_path).exists() if mp1_jpg_path else False
        in_quarantine = Path(quarantine_path).exists() if quarantine_path else False

        if copied_exists and (not jpg_exists or in_quarantine):
            status = "COMPLETED"
        elif copied_exists and jpg_exists and not in_quarantine:
            status = "COPY_DONE_MOVE_PENDING"
        elif not copied_exists and jpg_exists:
            status = "NOT_STARTED"
        else:
            status = "OTHER"

        row["progress_status"] = status
        row["quarantine_expected_path"] = quarantine_path
        counts[status] += 1

    # Write output
    print(f"\nWriting -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    # Summary
    print(f"\n{'=' * 60}")
    print(f"  PROGRESS SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total rows:              {len(rows):,}")
    print(f"  COMPLETED:               {counts['COMPLETED']:,}")
    print(f"  COPY_DONE_MOVE_PENDING:  {counts['COPY_DONE_MOVE_PENDING']:,}")
    print(f"  NOT_STARTED:             {counts['NOT_STARTED']:,}")
    print(f"  OTHER:                   {counts['OTHER']:,}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
