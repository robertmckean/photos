#!/usr/bin/env python3
"""
add_hyperlinks.py

Post-processing script that reads the finished photo_inventory.csv and adds
an Excel-clickable =HYPERLINK() column, writing the result to a new file.

Does NOT modify the original CSV.
"""

from __future__ import annotations

import csv
import sys
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_linked.csv")


def main() -> None:
    """Read the inventory CSV, append a hyperlink column, write a new CSV."""
    if not INPUT_CSV.exists():
        print(f"ERROR: Input CSV not found: {INPUT_CSV}")
        sys.exit(1)

    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        fieldnames = list(reader.fieldnames or []) + ["hyperlink"]
        rows = []
        for row in reader:
            full_path = row.get("full_path", "")
            if full_path:
                row["hyperlink"] = f'=HYPERLINK("{full_path}","Open")'
            else:
                row["hyperlink"] = ""
            rows.append(row)

    with open(OUTPUT_CSV, "w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print(f"Done. {len(rows):,} rows written to: {OUTPUT_CSV}")


if __name__ == "__main__":
    main()
