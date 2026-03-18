#!/usr/bin/env python3
"""
gap_analysis.py

Comprehensive gap analysis between iCloud and MP1 libraries using
photo_inventory_1.csv (ExifTool-derived capture_time_best).

Produces 4 reports + summary JSON:
  report1: iCloud files not present in MP1
  report2: MP1 files with no corresponding iCloud match
  report3: MOV file status
  report4: PNG file status

REPORT ONLY -- does NOT copy, move, rename, or delete anything.
"""

from __future__ import annotations

import csv
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

CSV_PATH = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")
OUTPUT_DIR = Path(r"C:\Users\windo\VS_Code\photos\results")

ICLOUD_PREFIX = r"C:\Users\windo\Pictures\iCloud Photos\Photos"
MP1_PREFIX = r"C:\Users\windo\My_Pictures1"
QUARANTINE_PREFIX = r"C:\Users\windo\My_Pictures1\_JPG_TO_DELETE"

IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".heic", ".heif",
                    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng"}
VIDEO_EXTENSIONS = {".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts",
                    ".3gp", ".mpg", ".mpeg", ".wmv"}
MEDIA_EXTENSIONS = IMAGE_EXTENSIONS | VIDEO_EXTENSIONS

DUP_SUFFIX_RE = re.compile(r"\(\d+\)$")


def comparison_stem(filename: str) -> str:
    stem = Path(filename).stem
    return DUP_SUFFIX_RE.sub("", stem).strip().lower()


def main() -> None:
    print("Reading inventory ...")

    # Separate iCloud and MP1 files
    icloud_rows: list[dict[str, str]] = []
    mp1_rows: list[dict[str, str]] = []
    mp1_quarantine_rows: list[dict[str, str]] = []

    with open(CSV_PATH, encoding="utf-8", newline="") as f:
        for row in csv.DictReader(f):
            fp = row.get("full_path", "")
            if ICLOUD_PREFIX in fp:
                icloud_rows.append(row)
            elif QUARANTINE_PREFIX in fp:
                mp1_quarantine_rows.append(row)
            elif MP1_PREFIX in fp:
                mp1_rows.append(row)

    print(f"  iCloud files:        {len(icloud_rows):,}")
    print(f"  MP1 active files:    {len(mp1_rows):,}")
    print(f"  MP1 quarantine:      {len(mp1_quarantine_rows):,}")

    # Build lookup indexes using (capture_time_best, comparison_stem)
    # MP1 index: for finding MP1 matches for iCloud files
    mp1_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    # Also index by stem only (for stem-match-only analysis)
    mp1_by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in mp1_rows:
        ext = row.get("extension", "").lower()
        if ext not in MEDIA_EXTENSIONS:
            continue
        ct = row.get("capture_time_best", "").strip()
        cstem = comparison_stem(row.get("file_name", ""))
        if ct:
            mp1_by_key[(ct, cstem)].append(row)
        mp1_by_stem[cstem].append(row)

    # iCloud index: for finding iCloud matches for MP1 files
    icloud_by_key: dict[tuple[str, str], list[dict[str, str]]] = defaultdict(list)
    icloud_by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in icloud_rows:
        ext = row.get("extension", "").lower()
        if ext not in MEDIA_EXTENSIONS:
            continue
        ct = row.get("capture_time_best", "").strip()
        cstem = comparison_stem(row.get("file_name", ""))
        if ct:
            icloud_by_key[(ct, cstem)].append(row)
        icloud_by_stem[cstem].append(row)

    # Also check quarantine for "already processed" status
    quarantine_stems: set[str] = set()
    for row in mp1_quarantine_rows:
        quarantine_stems.add(comparison_stem(row.get("file_name", "")))

    # ── REPORT 1: iCloud files not present in MP1 ──
    print("\nBuilding Report 1: iCloud not present in MP1 ...")
    r1_columns = [
        "full_path", "file_name", "extension", "capture_time_best",
        "capture_time_source", "comparison_stem", "file_size_bytes",
        "status", "notes",
    ]
    r1_results: list[dict[str, str]] = []
    r1_status_counts: Counter[str] = Counter()

    for row in icloud_rows:
        ext = row.get("extension", "").lower()
        if ext not in MEDIA_EXTENSIONS:
            continue
        ct = row.get("capture_time_best", "").strip()
        cstem = comparison_stem(row.get("file_name", ""))

        # Check for exact match (capture_time + stem)
        key = (ct, cstem)
        if ct and mp1_by_key.get(key):
            continue  # matched, skip

        # Check if stem matches but time differs
        stem_matches = mp1_by_stem.get(cstem, [])

        if not stem_matches:
            status = "NO_MP1_MATCH"
            notes = ""
        else:
            # Stem matches exist but time didn't match
            mp1_times = [r.get("capture_time_best", "") for r in stem_matches]
            status = "STEM_MATCH_TIME_DIFF"
            notes = f"mp1_times: {'; '.join(list(set(mp1_times))[:3])}"

        r1_status_counts[status] += 1
        r1_results.append({
            "full_path": row.get("full_path", ""),
            "file_name": row.get("file_name", ""),
            "extension": ext,
            "capture_time_best": ct,
            "capture_time_source": row.get("capture_time_source", ""),
            "comparison_stem": cstem,
            "file_size_bytes": row.get("file_size_bytes", ""),
            "status": status,
            "notes": notes,
        })

    r1_path = OUTPUT_DIR / "report1_icloud_not_in_mp1.csv"
    with open(r1_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r1_columns)
        writer.writeheader()
        writer.writerows(r1_results)
    print(f"  Written: {r1_path} ({len(r1_results):,} rows)")
    for s, c in r1_status_counts.most_common():
        print(f"    {s}: {c:,}")

    # ── REPORT 2: MP1 files with no corresponding iCloud match ──
    print("\nBuilding Report 2: MP1 no corresponding iCloud ...")
    r2_columns = [
        "full_path", "file_name", "extension", "capture_time_best",
        "capture_time_source", "comparison_stem", "file_size_bytes",
        "parent_folder", "status", "notes",
    ]
    r2_results: list[dict[str, str]] = []
    r2_status_counts: Counter[str] = Counter()

    for row in mp1_rows:
        ext = row.get("extension", "").lower()
        if ext not in MEDIA_EXTENSIONS:
            continue
        ct = row.get("capture_time_best", "").strip()
        cstem = comparison_stem(row.get("file_name", ""))

        key = (ct, cstem)
        if ct and icloud_by_key.get(key):
            continue  # matched

        # Check if in quarantine (already processed by our pipeline)
        if cstem in quarantine_stems:
            status = "ALREADY_PROCESSED"
            notes = "JPG quarantined, iCloud source copied"
        else:
            stem_matches = icloud_by_stem.get(cstem, [])
            if not stem_matches:
                status = "NO_ICLOUD_MATCH"
                notes = ""
            else:
                icloud_times = [r.get("capture_time_best", "") for r in stem_matches]
                status = "STEM_MATCH_TIME_DIFF"
                notes = f"icloud_times: {'; '.join(list(set(icloud_times))[:3])}"

        r2_status_counts[status] += 1
        r2_results.append({
            "full_path": row.get("full_path", ""),
            "file_name": row.get("file_name", ""),
            "extension": ext,
            "capture_time_best": ct,
            "capture_time_source": row.get("capture_time_source", ""),
            "comparison_stem": cstem,
            "file_size_bytes": row.get("file_size_bytes", ""),
            "parent_folder": row.get("parent_folder", ""),
            "status": status,
            "notes": notes,
        })

    r2_path = OUTPUT_DIR / "report2_mp1_no_icloud.csv"
    with open(r2_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r2_columns)
        writer.writeheader()
        writer.writerows(r2_results)
    print(f"  Written: {r2_path} ({len(r2_results):,} rows)")
    for s, c in r2_status_counts.most_common():
        print(f"    {s}: {c:,}")

    # ── REPORT 3: MOV file status ──
    print("\nBuilding Report 3: MOV status ...")
    r3_columns = [
        "full_path", "file_name", "capture_time_best", "capture_time_source",
        "comparison_stem", "file_size_bytes", "duration_seconds",
        "companion_image_path", "companion_location", "status", "notes",
    ]
    r3_results: list[dict[str, str]] = []
    r3_status_counts: Counter[str] = Counter()

    # Build image indexes by stem (for companion lookup)
    icloud_images_by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)
    mp1_images_by_stem: dict[str, list[dict[str, str]]] = defaultdict(list)

    for row in icloud_rows:
        ext = row.get("extension", "").lower()
        if ext in IMAGE_EXTENSIONS:
            cstem = comparison_stem(row.get("file_name", ""))
            icloud_images_by_stem[cstem].append(row)

    for row in mp1_rows:
        ext = row.get("extension", "").lower()
        if ext in IMAGE_EXTENSIONS:
            cstem = comparison_stem(row.get("file_name", ""))
            mp1_images_by_stem[cstem].append(row)

    icloud_movs = [r for r in icloud_rows if r.get("extension", "").lower() in (".mov",)]

    for row in icloud_movs:
        cstem = comparison_stem(row.get("file_name", ""))

        mp1_companions = mp1_images_by_stem.get(cstem, [])
        icloud_companions = icloud_images_by_stem.get(cstem, [])

        if mp1_companions:
            status = "IMAGE_IN_MP1"
            companion = mp1_companions[0].get("full_path", "")
            location = "MP1"
        elif icloud_companions:
            status = "IMAGE_IN_ICLOUD_ONLY"
            companion = icloud_companions[0].get("full_path", "")
            location = "iCloud"
        else:
            status = "NO_COMPANION_IMAGE"
            companion = ""
            location = ""

        notes = ""
        if len(mp1_companions) > 1:
            notes = f"multiple MP1 companions ({len(mp1_companions)})"

        r3_status_counts[status] += 1
        r3_results.append({
            "full_path": row.get("full_path", ""),
            "file_name": row.get("file_name", ""),
            "capture_time_best": row.get("capture_time_best", ""),
            "capture_time_source": row.get("capture_time_source", ""),
            "comparison_stem": cstem,
            "file_size_bytes": row.get("file_size_bytes", ""),
            "duration_seconds": row.get("duration_seconds", ""),
            "companion_image_path": companion,
            "companion_location": location,
            "status": status,
            "notes": notes,
        })

    r3_path = OUTPUT_DIR / "report3_mov_status.csv"
    with open(r3_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r3_columns)
        writer.writeheader()
        writer.writerows(r3_results)
    print(f"  Written: {r3_path} ({len(r3_results):,} rows)")
    for s, c in r3_status_counts.most_common():
        print(f"    {s}: {c:,}")

    # ── REPORT 4: PNG file status ──
    print("\nBuilding Report 4: PNG status ...")
    r4_columns = [
        "full_path", "file_name", "capture_time_best", "capture_time_source",
        "comparison_stem", "file_size_bytes",
        "mp1_match_path", "status", "notes",
    ]
    r4_results: list[dict[str, str]] = []
    r4_status_counts: Counter[str] = Counter()

    icloud_pngs = [r for r in icloud_rows if r.get("extension", "").lower() == ".png"]

    for row in icloud_pngs:
        ct = row.get("capture_time_best", "").strip()
        cstem = comparison_stem(row.get("file_name", ""))

        key = (ct, cstem)
        exact = mp1_by_key.get(key, []) if ct else []

        if exact:
            status = "MATCHED_IN_MP1"
            match_path = exact[0].get("full_path", "")
            notes = f"{len(exact)} match(es)" if len(exact) > 1 else ""
        else:
            stem_matches = mp1_by_stem.get(cstem, [])
            if stem_matches:
                status = "STEM_MATCH_TIME_DIFF"
                mp1_times = [r.get("capture_time_best", "") for r in stem_matches]
                match_path = stem_matches[0].get("full_path", "")
                notes = f"mp1_times: {'; '.join(list(set(mp1_times))[:3])}"
            else:
                status = "NO_MP1_MATCH"
                match_path = ""
                notes = ""

        r4_status_counts[status] += 1
        r4_results.append({
            "full_path": row.get("full_path", ""),
            "file_name": row.get("file_name", ""),
            "capture_time_best": ct,
            "capture_time_source": row.get("capture_time_source", ""),
            "comparison_stem": cstem,
            "file_size_bytes": row.get("file_size_bytes", ""),
            "mp1_match_path": match_path,
            "status": status,
            "notes": notes,
        })

    r4_path = OUTPUT_DIR / "report4_png_status.csv"
    with open(r4_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=r4_columns)
        writer.writeheader()
        writer.writerows(r4_results)
    print(f"  Written: {r4_path} ({len(r4_results):,} rows)")
    for s, c in r4_status_counts.most_common():
        print(f"    {s}: {c:,}")

    # ── SUMMARY JSON ──
    summary = {
        "source": "photo_inventory_1.csv (ExifTool-derived capture_time_best)",
        "icloud_total": len(icloud_rows),
        "mp1_active_total": len(mp1_rows),
        "mp1_quarantine_total": len(mp1_quarantine_rows),
        "report1_icloud_not_in_mp1": len(r1_results),
        "report1_breakdown": dict(r1_status_counts.most_common()),
        "report2_mp1_no_icloud": len(r2_results),
        "report2_breakdown": dict(r2_status_counts.most_common()),
        "report3_mov_files": len(r3_results),
        "report3_breakdown": dict(r3_status_counts.most_common()),
        "report4_png_files": len(r4_results),
        "report4_breakdown": dict(r4_status_counts.most_common()),
    }

    summary_path = OUTPUT_DIR / "gap_analysis_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, indent=2)

    print(f"\n{'=' * 70}")
    print(f"  GAP ANALYSIS SUMMARY (ExifTool-based)")
    print(f"{'=' * 70}")
    print(f"  iCloud total:            {len(icloud_rows):,}")
    print(f"  MP1 active:              {len(mp1_rows):,}")
    print(f"  MP1 quarantine:          {len(mp1_quarantine_rows):,}")
    print(f"")
    print(f"  Report 1 - iCloud not in MP1:    {len(r1_results):,}")
    for s, c in r1_status_counts.most_common():
        print(f"    {s}: {c:,}")
    print(f"")
    print(f"  Report 2 - MP1 no iCloud:        {len(r2_results):,}")
    for s, c in r2_status_counts.most_common():
        print(f"    {s}: {c:,}")
    print(f"")
    print(f"  Report 3 - MOV status:           {len(r3_results):,}")
    for s, c in r3_status_counts.most_common():
        print(f"    {s}: {c:,}")
    print(f"")
    print(f"  Report 4 - PNG status:           {len(r4_results):,}")
    for s, c in r4_status_counts.most_common():
        print(f"    {s}: {c:,}")
    print(f"{'=' * 70}")
    print(f"  Summary JSON: {summary_path}")


if __name__ == "__main__":
    main()
