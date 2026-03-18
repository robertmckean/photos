#!/usr/bin/env python3
"""
copy_icloud_to_mp1.py

Phase 1: PREVIEW ONLY — generates copy_candidates_refined.csv
Phase 2: After user approval, copies SAFE candidates.

Reads photo_inventory_1.csv and finds iCloud image files that match an MP1 JPG
by both capture_time_best AND comparison_stem (filename without extension and
trailing duplicate suffixes like (1), (2)).

NON-DESTRUCTIVE — copies only. No moves, deletions, renames, or overwrites.
"""

from __future__ import annotations

import csv
import re
import shutil
import sys
from collections import defaultdict
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\copy_candidates_refined.csv")

ICLOUD_PREFIX = r"C:\Users\windo\Pictures\iCloud Photos\Photos"
MP1_PREFIX = r"C:\Users\windo\My_Pictures1"

IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng",
}

OUTPUT_COLUMNS: list[str] = [
    "source_full_path",
    "source_file_name",
    "source_capture_time",
    "source_comparison_stem",
    "matched_mp1_jpg_full_path",
    "matched_mp1_jpg_file_name",
    "matched_mp1_jpg_comparison_stem",
    "target_folder",
    "proposed_copied_file_path",
    "destination_exists",
    "candidate_count_for_match",
    "match_status",
    "skip_reason",
]

# Regex to strip trailing (1), (2), etc. for comparison only
DUP_SUFFIX_RE = re.compile(r"\(\d+\)$")


def derive_comparison_stem(filename: str) -> str:
    """
    Derive a comparison stem from a filename: remove extension, then
    strip a trailing duplicate suffix like (1), (2), (3).
    Used for matching only — never for renaming.
    """
    stem = Path(filename).stem
    return DUP_SUFFIX_RE.sub("", stem).strip()


def main() -> None:
    """Build refined copy preview from CSV and write candidate CSV."""

    print("Reading CSV …")

    # MP1 JPG lookup: (capture_time, comparison_stem) -> list of row dicts
    mp1_jpgs: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    icloud_files: list[dict[str, str]] = []
    total_icloud = 0
    total_mp1_jpg = 0

    with open(CSV_PATH, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            fp = row.get("full_path", "")
            ext = row.get("extension", "").lower()
            ct = row.get("capture_time_best", "").strip()

            if MP1_PREFIX in fp and ext in (".jpg", ".jpeg"):
                total_mp1_jpg += 1
                if ct:
                    cstem = derive_comparison_stem(row.get("file_name", ""))
                    mp1_jpgs[(ct, cstem)].append(row)

            elif ICLOUD_PREFIX in fp:
                total_icloud += 1
                if ext in IMAGE_EXTENSIONS and ext not in (".jpg", ".jpeg") and ct:
                    icloud_files.append(row)

    print(f"  iCloud files scanned:  {total_icloud:,}")
    print(f"  MP1 JPG files scanned: {total_mp1_jpg:,}")
    print(f"  iCloud candidates:     {len(icloud_files):,}")

    # Evaluate each iCloud file
    print("\nEvaluating matches …")
    results: list[dict[str, str]] = []
    safe_count = 0
    ambiguous_count = 0
    skip_reasons: dict[str, int] = defaultdict(int)

    for irow in icloud_files:
        ct = irow.get("capture_time_best", "").strip()
        src_name = irow.get("file_name", "")
        src_cstem = derive_comparison_stem(src_name)
        src_path = irow.get("full_path", "")

        key = (ct, src_cstem)
        candidates = mp1_jpgs.get(key, [])
        candidate_count = len(candidates)

        if candidate_count == 0:
            # No match
            row = {
                "source_full_path": src_path,
                "source_file_name": src_name,
                "source_capture_time": ct,
                "source_comparison_stem": src_cstem,
                "matched_mp1_jpg_full_path": "",
                "matched_mp1_jpg_file_name": "",
                "matched_mp1_jpg_comparison_stem": "",
                "target_folder": "",
                "proposed_copied_file_path": "",
                "destination_exists": "",
                "candidate_count_for_match": "0",
                "match_status": "SKIPPED",
                "skip_reason": "no MP1 JPG match",
            }
            results.append(row)
            skip_reasons["no MP1 JPG match"] += 1
            continue

        if candidate_count > 1:
            # Ambiguous — multiple MP1 JPGs match
            for mp1_row in candidates:
                mp1_folder = mp1_row.get("parent_folder", "")
                dest = str(Path(mp1_folder) / src_name)
                dest_exists = str(Path(dest).exists())
                row = {
                    "source_full_path": src_path,
                    "source_file_name": src_name,
                    "source_capture_time": ct,
                    "source_comparison_stem": src_cstem,
                    "matched_mp1_jpg_full_path": mp1_row.get("full_path", ""),
                    "matched_mp1_jpg_file_name": mp1_row.get("file_name", ""),
                    "matched_mp1_jpg_comparison_stem": derive_comparison_stem(mp1_row.get("file_name", "")),
                    "target_folder": mp1_folder,
                    "proposed_copied_file_path": dest,
                    "destination_exists": dest_exists,
                    "candidate_count_for_match": str(candidate_count),
                    "match_status": "AMBIGUOUS",
                    "skip_reason": f"multiple MP1 JPG candidates ({candidate_count})",
                }
                results.append(row)
            ambiguous_count += 1
            skip_reasons[f"ambiguous ({candidate_count} candidates)"] += 1
            continue

        # Exactly one candidate
        mp1_row = candidates[0]
        mp1_folder = mp1_row.get("parent_folder", "")
        dest = Path(mp1_folder) / src_name
        dest_exists = dest.exists()

        if dest_exists:
            row = {
                "source_full_path": src_path,
                "source_file_name": src_name,
                "source_capture_time": ct,
                "source_comparison_stem": src_cstem,
                "matched_mp1_jpg_full_path": mp1_row.get("full_path", ""),
                "matched_mp1_jpg_file_name": mp1_row.get("file_name", ""),
                "matched_mp1_jpg_comparison_stem": derive_comparison_stem(mp1_row.get("file_name", "")),
                "target_folder": mp1_folder,
                "proposed_copied_file_path": str(dest),
                "destination_exists": "True",
                "candidate_count_for_match": "1",
                "match_status": "SKIPPED",
                "skip_reason": "destination file already exists",
            }
            results.append(row)
            skip_reasons["destination file already exists"] += 1
            continue

        # SAFE
        row = {
            "source_full_path": src_path,
            "source_file_name": src_name,
            "source_capture_time": ct,
            "source_comparison_stem": src_cstem,
            "matched_mp1_jpg_full_path": mp1_row.get("full_path", ""),
            "matched_mp1_jpg_file_name": mp1_row.get("file_name", ""),
            "matched_mp1_jpg_comparison_stem": derive_comparison_stem(mp1_row.get("file_name", "")),
            "target_folder": mp1_folder,
            "proposed_copied_file_path": str(dest),
            "destination_exists": "False",
            "candidate_count_for_match": "1",
            "match_status": "SAFE",
            "skip_reason": "",
        }
        results.append(row)
        safe_count += 1

    # Write preview CSV
    print(f"\nWriting preview → {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    # Console summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  iCloud files scanned:    {total_icloud:,}")
    print(f"  MP1 JPG files scanned:   {total_mp1_jpg:,}")
    print(f"  SAFE matches:            {safe_count:,}")
    print(f"  AMBIGUOUS matches:       {ambiguous_count:,}")
    print(f"  SKIPPED by reason:")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason}: {count:,}")
    print(f"{'=' * 70}")
    print(f"\n  Preview CSV written. Review it, then run:")
    print(f"    python copy_icloud_to_mp1.py --execute")
    print(f"  to perform the SAFE copies.\n")


def execute_safe_copies() -> None:
    """Read the preview CSV and copy all SAFE candidates."""
    if not OUTPUT_CSV.exists():
        print(f"ERROR: Preview CSV not found: {OUTPUT_CSV}")
        print("       Run without --execute first to generate the preview.")
        sys.exit(1)

    plan: list[tuple[Path, Path]] = []
    with open(OUTPUT_CSV, encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            if row.get("match_status") == "SAFE":
                src = Path(row["source_full_path"])
                dest = Path(row["proposed_copied_file_path"])
                plan.append((src, dest))

    if not plan:
        print("No SAFE candidates to copy.")
        return

    print(f"\n  {len(plan):,} SAFE files to copy.")
    response = input("  Proceed? (yes/no): ").strip().lower()
    if response not in ("yes", "y"):
        print("  Cancelled.")
        return

    print("\nCopying …")
    copied = 0
    skipped = 0
    errors = 0
    for i, (src, dest) in enumerate(plan, 1):
        if i % 100 == 0 or i == len(plan):
            print(f"  {i:,} / {len(plan):,}")
        # Final safety check
        if dest.exists():
            skipped += 1
            continue
        try:
            shutil.copy2(src, dest)
            copied += 1
        except Exception as exc:
            print(f"  ERROR copying {src.name}: {exc}")
            errors += 1

    print(f"\n{'=' * 70}")
    print(f"  DONE")
    print(f"  Copied:   {copied:,}")
    print(f"  Skipped:  {skipped:,}  (appeared since preview)")
    print(f"  Errors:   {errors:,}")
    print(f"{'=' * 70}")


if __name__ == "__main__":
    if "--execute" in sys.argv:
        execute_safe_copies()
    else:
        main()
