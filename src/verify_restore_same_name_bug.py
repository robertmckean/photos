#!/usr/bin/env python3
"""
verify_restore_same_name_bug.py

Verification report for the 277 restored same-name JPG bug rows.
Checks that restored JPGs are back in MP1 and not still in quarantine.
Also finds empty quarantine folders.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
import os
from pathlib import Path

RESTORE_REPORT = Path(r"C:\Users\windo\VS_Code\photos\results\restore_jpgjpg_277_report.csv")
QUARANTINE_ROOT = Path(r"C:\Users\windo\My_Pictures1\_JPG_TO_DELETE")

OUTPUT_VERIFICATION = Path(r"C:\Users\windo\VS_Code\photos\results\restore_verification_same_name_bug.csv")
OUTPUT_EMPTY_FOLDERS = Path(r"C:\Users\windo\VS_Code\photos\results\empty_quarantine_folders.csv")

VERIFICATION_COLUMNS = [
    "original_mp1_path",
    "exists_in_mp1",
    "quarantine_path",
    "still_exists_in_quarantine",
    "verification_status",
]


def main() -> None:
    print("Reading restore report ...")
    rows: list[dict[str, str]] = []

    with open(RESTORE_REPORT, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            original = row.get("original_mp1_path", "")
            quarantine = row.get("quarantine_path", "")

            in_mp1 = Path(original).exists() if original else False
            in_quarantine = Path(quarantine).exists() if quarantine else False

            if in_mp1 and not in_quarantine:
                status = "RESTORED_OK"
            elif not in_mp1 and not in_quarantine:
                status = "MISSING_FROM_MP1"
            elif not in_mp1 and in_quarantine:
                status = "STILL_IN_QUARANTINE"
            elif in_mp1 and in_quarantine:
                status = "BOTH_PRESENT"
            else:
                status = "OTHER"

            rows.append({
                "original_mp1_path": original,
                "exists_in_mp1": str(in_mp1),
                "quarantine_path": quarantine,
                "still_exists_in_quarantine": str(in_quarantine),
                "verification_status": status,
            })

    # Write verification CSV
    print(f"Writing -> {OUTPUT_VERIFICATION}")
    with open(OUTPUT_VERIFICATION, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=VERIFICATION_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)

    # Find empty quarantine folders
    print(f"\nScanning for empty quarantine folders under {QUARANTINE_ROOT} ...")
    empty_folders: list[str] = []
    if QUARANTINE_ROOT.exists():
        for dirpath, dirnames, filenames in os.walk(QUARANTINE_ROOT):
            if not dirnames and not filenames:
                empty_folders.append(dirpath)

    print(f"Writing -> {OUTPUT_EMPTY_FOLDERS}")
    with open(OUTPUT_EMPTY_FOLDERS, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(["empty_folder_path"])
        for folder in sorted(empty_folders):
            writer.writerow([folder])

    # Summary
    counts = {"RESTORED_OK": 0, "MISSING_FROM_MP1": 0, "STILL_IN_QUARANTINE": 0, "BOTH_PRESENT": 0, "OTHER": 0}
    for r in rows:
        counts[r["verification_status"]] = counts.get(r["verification_status"], 0) + 1

    print(f"\n{'=' * 60}")
    print(f"  VERIFICATION SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total restored rows checked:  {len(rows)}")
    print(f"  RESTORED_OK:                  {counts['RESTORED_OK']}")
    print(f"  MISSING_FROM_MP1:             {counts['MISSING_FROM_MP1']}")
    print(f"  STILL_IN_QUARANTINE:          {counts['STILL_IN_QUARANTINE']}")
    print(f"  BOTH_PRESENT:                 {counts['BOTH_PRESENT']}")
    print(f"  OTHER:                        {counts['OTHER']}")
    print(f"")
    print(f"  Empty quarantine folders:     {len(empty_folders)}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
