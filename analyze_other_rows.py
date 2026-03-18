#!/usr/bin/env python3
"""
analyze_other_rows.py

Analyzes all rows where progress_status = OTHER in v4_safe_progress.csv
and classifies why they are not COMPLETED.

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
from collections import Counter
from pathlib import Path

PROGRESS_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\icloud_mp1_pairs_v4_safe_progress.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\v4_other_analysis.csv")

OUTPUT_COLUMNS = [
    "source_heic_path",
    "copied_heic_path",
    "matched_mp1_jpg_path",
    "quarantine_expected_path",
    "source_heic_exists",
    "copied_heic_exists",
    "mp1_jpg_exists",
    "quarantine_jpg_exists",
    "issue_type",
]


def classify(src_exists: bool, copied_exists: bool, jpg_exists: bool, q_exists: bool) -> str:
    # Copied exists + JPG gone + not in quarantine = COMPLETED (shouldn't be OTHER)
    # But we're only called for OTHER rows, so figure out the issue.

    if not src_exists and not copied_exists:
        return "SOURCE_MISSING"

    if src_exists and not copied_exists:
        return "COPY_FAILED"

    if copied_exists and jpg_exists and q_exists:
        return "MOVE_SKIPPED_DESTINATION_EXISTS"

    if copied_exists and not jpg_exists and not q_exists:
        # Replacement exists, JPG gone, but not in quarantine either
        # JPG was deleted or moved elsewhere
        return "MOVE_SKIPPED_SOURCE_MISSING"

    if not copied_exists and not jpg_exists:
        return "NO_REPLACEMENT"

    return "UNKNOWN"


def main() -> None:
    print("Reading progress CSV ...")
    other_rows: list[dict[str, str]] = []

    with open(PROGRESS_CSV, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            if row.get("progress_status") == "OTHER":
                other_rows.append(row)

    print(f"  OTHER rows: {len(other_rows)}")
    print("\nAnalyzing ...")

    results: list[dict[str, str]] = []
    issue_counts: Counter[str] = Counter()

    for row in other_rows:
        src_heic = row.get("source_heic_path", "")
        copied_heic = row.get("copied_heic_path", "")
        mp1_jpg = row.get("target_jpg_path", "") or row.get("mp1_file_to_replace", "")
        quarantine = row.get("quarantine_expected_path", "")

        src_exists = Path(src_heic).exists() if src_heic else False
        copied_exists = Path(copied_heic).exists() if copied_heic else False
        jpg_exists = Path(mp1_jpg).exists() if mp1_jpg else False
        q_exists = Path(quarantine).exists() if quarantine else False

        issue = classify(src_exists, copied_exists, jpg_exists, q_exists)
        issue_counts[issue] += 1

        results.append({
            "source_heic_path": src_heic,
            "copied_heic_path": copied_heic,
            "matched_mp1_jpg_path": mp1_jpg,
            "quarantine_expected_path": quarantine,
            "source_heic_exists": str(src_exists),
            "copied_heic_exists": str(copied_exists),
            "mp1_jpg_exists": str(jpg_exists),
            "quarantine_jpg_exists": str(q_exists),
            "issue_type": issue,
        })

    print(f"\nWriting -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    print(f"\n{'=' * 60}")
    print(f"  OTHER ROWS ANALYSIS")
    print(f"{'=' * 60}")
    print(f"  Total OTHER rows: {len(other_rows)}")
    print(f"")
    for issue, cnt in issue_counts.most_common():
        print(f"    {issue}: {cnt}")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()
