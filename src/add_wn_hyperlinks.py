#!/usr/bin/env python3
"""
add_wn_hyperlinks.py

Adds hyperlink columns to all 5 WN reconciliation CSVs so files
can be opened directly from Excel.

REPORT ONLY -- does NOT modify any original files.
"""

from __future__ import annotations

import csv
from pathlib import Path

RESULTS_DIR = Path(r"C:\Users\windo\VS_Code\photos\results")

FILES = [
    "wn_icloud_reconciliation_full.csv",
    "wn_matched_image_candidates.csv",
    "wn_matched_mov_related.csv",
    "wn_unmatched_mov.csv",
    "wn_unmatched_other.csv",
]


def process_file(filepath: Path) -> int:
    rows: list[dict[str, str]] = []
    with open(filepath, encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        original_columns = list(reader.fieldnames or [])
        for row in reader:
            rows.append(row)

    if not rows:
        # Empty file, just add columns to header
        out_columns = original_columns + ["wn_hyperlink", "icloud_hyperlink"]
        with open(filepath, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=out_columns)
            writer.writeheader()
        return 0

    # Add hyperlink columns
    for row in rows:
        wn_path = row.get("wn_full_path", "")
        ic_path = row.get("matched_icloud_path", "")

        row["wn_hyperlink"] = f'=HYPERLINK("{wn_path}","Open WN")' if wn_path else ""
        row["icloud_hyperlink"] = f'=HYPERLINK("{ic_path}","Open iCloud")' if ic_path else ""

    out_columns = original_columns + ["wn_hyperlink", "icloud_hyperlink"]

    with open(filepath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=out_columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    return len(rows)


def main() -> None:
    for fname in FILES:
        filepath = RESULTS_DIR / fname
        if not filepath.exists():
            print(f"  SKIP (not found): {fname}")
            continue
        count = process_file(filepath)
        print(f"  {fname}: {count:,} rows, hyperlinks added")


if __name__ == "__main__":
    main()
