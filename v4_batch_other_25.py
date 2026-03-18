#!/usr/bin/env python3
"""
v4_batch_other_25.py

Processes the 25 OTHER rows from v4_safe_progress.csv:
  Step 1: Copy iCloud source to MP1 (copied_heic_path)
  Step 2: Guarded move of MP1 JPG to quarantine (only if replacement exists)

NON-DESTRUCTIVE to iCloud sources. Moves MP1 JPGs only after confirming replacement.
"""

from __future__ import annotations

import csv
import shutil
from pathlib import Path

PROGRESS_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v4_safe_progress.csv")
REPORT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\v4_batch_other_25_report.csv")

REPORT_COLUMNS = [
    "source_heic_path",
    "copied_heic_path",
    "matched_mp1_jpg_path",
    "quarantine_expected_path",
    "copy_status",
    "move_status",
    "error_message",
]


def main() -> None:
    print("Reading progress CSV ...")
    other_rows: list[dict[str, str]] = []

    with open(PROGRESS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("progress_status") == "OTHER":
                other_rows.append(row)

    print(f"  OTHER rows: {len(other_rows)}")

    results: list[dict[str, str]] = []
    copy_counts = {"Success": 0, "destination_exists": 0, "source_missing": 0, "Error": 0}
    move_counts = {"Moved": 0, "destination_exists": 0, "source_missing": 0, "NO_REPLACEMENT": 0, "Error": 0}

    for i, row in enumerate(other_rows, 1):
        src_heic = row.get("source_heic_path", "")
        copied_heic = row.get("copied_heic_path", "")
        mp1_jpg = row.get("target_jpg_path", "") or row.get("mp1_file_to_replace", "")
        quarantine = row.get("quarantine_expected_path", "")

        report_row = {
            "source_heic_path": src_heic,
            "copied_heic_path": copied_heic,
            "matched_mp1_jpg_path": mp1_jpg,
            "quarantine_expected_path": quarantine,
            "copy_status": "",
            "move_status": "",
            "error_message": "",
        }

        # STEP 1: COPY
        src_path = Path(src_heic)
        dest_path = Path(copied_heic)

        if dest_path.exists():
            report_row["copy_status"] = "destination_exists"
            copy_counts["destination_exists"] += 1
        elif not src_path.exists():
            report_row["copy_status"] = "source_missing"
            copy_counts["source_missing"] += 1
        else:
            try:
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(str(src_path), str(dest_path))
                report_row["copy_status"] = "Success"
                copy_counts["Success"] += 1
            except Exception as exc:
                report_row["copy_status"] = "Error"
                report_row["error_message"] = f"copy error: {exc}"
                copy_counts["Error"] += 1

        # STEP 2: GUARDED MOVE
        jpg_path = Path(mp1_jpg)
        q_path = Path(quarantine)

        if not Path(copied_heic).exists():
            report_row["move_status"] = "NO_REPLACEMENT"
            move_counts["NO_REPLACEMENT"] += 1
        elif not jpg_path.exists():
            report_row["move_status"] = "source_missing"
            move_counts["source_missing"] += 1
        elif q_path.exists():
            report_row["move_status"] = "destination_exists"
            move_counts["destination_exists"] += 1
        else:
            try:
                q_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(jpg_path), str(q_path))
                report_row["move_status"] = "Moved"
                move_counts["Moved"] += 1
            except Exception as exc:
                report_row["move_status"] = "Error"
                if report_row["error_message"]:
                    report_row["error_message"] += f"; move error: {exc}"
                else:
                    report_row["error_message"] = f"move error: {exc}"
                move_counts["Error"] += 1

        results.append(report_row)
        print(f"  {i} / {len(other_rows)}: copy={report_row['copy_status']}, move={report_row['move_status']}")

    print(f"\nWriting -> {REPORT_CSV}")
    with open(REPORT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=REPORT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 60}")
    print(f"  BATCH SUMMARY")
    print(f"{'=' * 60}")
    print(f"  Total processed:         {len(results)}")
    print(f"")
    print(f"  COPY:")
    print(f"    Success:               {copy_counts['Success']}")
    print(f"    destination_exists:     {copy_counts['destination_exists']}")
    print(f"    source_missing:         {copy_counts['source_missing']}")
    print(f"    Error:                 {copy_counts['Error']}")
    print(f"")
    print(f"  MOVE:")
    print(f"    Moved:                 {move_counts['Moved']}")
    print(f"    destination_exists:     {move_counts['destination_exists']}")
    print(f"    source_missing:         {move_counts['source_missing']}")
    print(f"    NO_REPLACEMENT:        {move_counts['NO_REPLACEMENT']}")
    print(f"    Error:                 {move_counts['Error']}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
