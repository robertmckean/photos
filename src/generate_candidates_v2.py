#!/usr/bin/env python3
"""
generate_candidates_v2.py

Preview-only analysis of SAFE copy candidates from iCloud -> MP1.
Includes ALL image types (HEIC, JPG, PNG, etc.).
Matches on capture_time_best + comparison_stem (1-to-1 only).

Does NOT copy, move, delete, or rename anything.
"""

from __future__ import annotations

import csv
import re
from collections import Counter, defaultdict
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\copy_candidates_refined_v2.csv")

ICLOUD_PREFIX = r"C:\Users\windo\Pictures\iCloud Photos\Photos"
MP1_PREFIX = r"C:\Users\windo\My_Pictures1"

IMAGE_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng",
}

DUP_SUFFIX_RE = re.compile(r"\(\d+\)$")

OUTPUT_COLUMNS: list[str] = [
    "source_full_path",
    "source_file_name",
    "source_extension",
    "source_capture_time",
    "source_comparison_stem",
    "matched_mp1_file_full_path",
    "matched_mp1_file_name",
    "matched_mp1_extension",
    "matched_mp1_comparison_stem",
    "target_folder",
    "proposed_copied_file_path",
    "destination_exists",
    "candidate_count_for_match",
    "match_status",
    "skip_reason",
]


def derive_comparison_stem(filename: str) -> str:
    """Remove extension and trailing (1)/(2)/etc. for matching only."""
    stem = Path(filename).stem
    return DUP_SUFFIX_RE.sub("", stem).strip()


def main() -> None:
    print("Reading CSV ...")

    # MP1 lookup: (capture_time, comparison_stem) -> list of row dicts
    mp1_files: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    icloud_files: list[dict[str, str]] = []
    total_icloud = 0
    total_mp1 = 0

    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fp = row.get("full_path", "")
            ext = row.get("extension", "").lower()
            ct = row.get("capture_time_best", "").strip()

            if MP1_PREFIX in fp and ext in IMAGE_EXTENSIONS:
                total_mp1 += 1
                if ct:
                    cstem = derive_comparison_stem(row.get("file_name", ""))
                    mp1_files[(ct, cstem)].append(row)

            elif ICLOUD_PREFIX in fp:
                total_icloud += 1
                if ext in IMAGE_EXTENSIONS and ct:
                    icloud_files.append(row)

    print(f"  iCloud files scanned:    {total_icloud:,}")
    print(f"  MP1 files scanned:       {total_mp1:,}")
    print(f"  iCloud image candidates: {len(icloud_files):,}")

    print("\nEvaluating matches ...")

    results: list[dict[str, str]] = []
    safe_count = 0
    ambiguous_count = 0
    skip_reasons: dict[str, int] = defaultdict(int)

    for irow in icloud_files:
        ct = irow.get("capture_time_best", "").strip()
        src_name = irow.get("file_name", "")
        src_ext = irow.get("extension", "").lower()
        src_cstem = derive_comparison_stem(src_name)
        src_path = irow.get("full_path", "")

        key = (ct, src_cstem)
        candidates = mp1_files.get(key, [])
        candidate_count = len(candidates)

        base_row = {
            "source_full_path": src_path,
            "source_file_name": src_name,
            "source_extension": src_ext,
            "source_capture_time": ct,
            "source_comparison_stem": src_cstem,
        }

        if candidate_count == 0:
            results.append({
                **base_row,
                "matched_mp1_file_full_path": "",
                "matched_mp1_file_name": "",
                "matched_mp1_extension": "",
                "matched_mp1_comparison_stem": "",
                "target_folder": "",
                "proposed_copied_file_path": "",
                "destination_exists": "",
                "candidate_count_for_match": "0",
                "match_status": "SKIPPED",
                "skip_reason": "no MP1 match",
            })
            skip_reasons["no MP1 match"] += 1
            continue

        if candidate_count > 1:
            for mp1_row in candidates:
                mp1_folder = mp1_row.get("parent_folder", "")
                dest = str(Path(mp1_folder) / src_name)
                results.append({
                    **base_row,
                    "matched_mp1_file_full_path": mp1_row.get("full_path", ""),
                    "matched_mp1_file_name": mp1_row.get("file_name", ""),
                    "matched_mp1_extension": mp1_row.get("extension", "").lower(),
                    "matched_mp1_comparison_stem": derive_comparison_stem(mp1_row.get("file_name", "")),
                    "target_folder": mp1_folder,
                    "proposed_copied_file_path": dest,
                    "destination_exists": str(Path(dest).exists()),
                    "candidate_count_for_match": str(candidate_count),
                    "match_status": "AMBIGUOUS",
                    "skip_reason": f"multiple MP1 candidates ({candidate_count})",
                })
            ambiguous_count += 1
            skip_reasons["ambiguous"] += 1
            continue

        # Exactly one candidate
        mp1_row = candidates[0]
        mp1_folder = mp1_row.get("parent_folder", "")
        dest = Path(mp1_folder) / src_name
        dest_exists = dest.exists()

        match_row = {
            **base_row,
            "matched_mp1_file_full_path": mp1_row.get("full_path", ""),
            "matched_mp1_file_name": mp1_row.get("file_name", ""),
            "matched_mp1_extension": mp1_row.get("extension", "").lower(),
            "matched_mp1_comparison_stem": derive_comparison_stem(mp1_row.get("file_name", "")),
            "target_folder": mp1_folder,
            "proposed_copied_file_path": str(dest),
            "destination_exists": str(dest_exists),
            "candidate_count_for_match": "1",
        }

        if dest_exists:
            match_row["match_status"] = "SKIPPED"
            match_row["skip_reason"] = "destination file already exists"
            results.append(match_row)
            skip_reasons["destination file already exists"] += 1
        else:
            match_row["match_status"] = "SAFE"
            match_row["skip_reason"] = ""
            results.append(match_row)
            safe_count += 1

    # Write CSV
    print(f"\nWriting preview -> {OUTPUT_CSV}")
    with open(OUTPUT_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=OUTPUT_COLUMNS)
        writer.writeheader()
        writer.writerows(results)

    # Summary
    print(f"\n{'=' * 70}")
    print(f"  SUMMARY")
    print(f"{'=' * 70}")
    print(f"  iCloud files scanned:    {total_icloud:,}")
    print(f"  MP1 files scanned:       {total_mp1:,}")
    print(f"  SAFE matches:            {safe_count:,}")
    print(f"  AMBIGUOUS matches:       {ambiguous_count:,}")
    print(f"  SKIPPED by reason:")
    for reason, count in sorted(skip_reasons.items(), key=lambda x: -x[1]):
        print(f"    {reason}: {count:,}")
    print(f"{'=' * 70}")

    # SAFE breakdown by extension
    safe_exts: Counter[str] = Counter()
    for r in results:
        if r["match_status"] == "SAFE":
            safe_exts[r["source_extension"]] += 1
    print(f"\n  SAFE breakdown by source extension:")
    for ext, cnt in safe_exts.most_common():
        print(f"    {ext}: {cnt:,}")

    print(f"\n  Preview CSV: {OUTPUT_CSV}")
    print(f"  DO NOT copy yet — review and approve first.\n")


if __name__ == "__main__":
    main()
