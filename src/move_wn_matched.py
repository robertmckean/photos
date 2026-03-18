#!/usr/bin/env python3
"""
move_wn_matched.py

Moves the 200 MATCHED_IMAGE_CANDIDATE files from D:\Why not iPhone
to D:\Why not iPhone_DELETE_PENDING_WN.

MOVE only. Does NOT delete, rename, or modify any files.
Does NOT touch iCloud.
"""

from __future__ import annotations

import csv
import shutil
from collections import Counter
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\wn_matched_image_candidates.csv")
DEST_ROOT = Path(r"D:\Why not iPhone\_DELETE_PENDING_WN")
REPORT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\move_wn_matched_report.csv")

REPORT_COLUMNS = [
    "wn_full_path",
    "destination_path",
    "status",
    "error_message",
]


def main() -> None:
    print("Reading matched image candidates ...")
    to_move: list[dict[str, str]] = []

    with open(INPUT_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            to_move.append(row)

    print(f"  Files to move: {len(to_move)}")

    DEST_ROOT.mkdir(parents=True, exist_ok=True)

    results: list[dict[str, str]] = []
    status_counts: Counter[str] = Counter()

    for i, row in enumerate(to_move, 1):
        src = Path(row.get("wn_full_path", ""))
        dest = DEST_ROOT / src.name

        report_row = {
            "wn_full_path": str(src),
            "destination_path": str(dest),
            "status": "",
            "error_message": "",
        }

        if not src.exists():
            report_row["status"] = "source_missing"
            status_counts["source_missing"] += 1
        elif dest.exists():
            report_row["status"] = "destination_exists"
            status_counts["destination_exists"] += 1
        else:
            try:
                shutil.move(str(src), str(dest))
                report_row["status"] = "Moved"
                status_counts["Moved"] += 1
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
    print(f"  MOVE REPORT")
    print(f"{'=' * 60}")
    print(f"  Total processed:     {len(results)}")
    for s, c in status_counts.most_common():
        print(f"    {s}: {c}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
