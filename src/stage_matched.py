#!/usr/bin/env python3
"""
stage_matched.py — Moves files from /Photos that have an exact filename match
(including extension) anywhere in /iCloud Photos/Photos into stage_for_delete.

Only /Photos is touched. iCloud Photos is never modified.
A CSV move log is written to results/move_log.csv.
"""

import csv
import os
import sys
from pathlib import Path

# =============================================================================
# CONFIG
# =============================================================================

PHOTOS_ROOT   = Path(r"C:\Users\windo\Pictures\Photos")
ICLOUD_ROOT   = Path(r"C:\Users\windo\Pictures\iCloud Photos\Photos")
STAGE_DIR     = Path(r"C:\Users\windo\Desktop\PhotoAudit\stage_for_delete")
REPORT_DIR    = Path(r"C:\Users\windo\VS_Code\photos\results")
MOVE_LOG_PATH = REPORT_DIR / "move_log.csv"

SKIP_EXTS = {".aae", ".thm", ".xmp", ".db", ".ini", ".ds_store", ".ps1"}

# =============================================================================
# MAIN
# =============================================================================

def main():
    for root, label in [(PHOTOS_ROOT, "Photos"), (ICLOUD_ROOT, "iCloud Photos")]:
        if not root.exists():
            sys.exit(f"ERROR: {label} folder not found: {root}")

    os.makedirs(str(REPORT_DIR), exist_ok=True)
    os.makedirs(str(STAGE_DIR), exist_ok=True)

    # -------------------------------------------------------------------------
    # STEP 1: Build set of all filenames in iCloud (case-insensitive)
    # -------------------------------------------------------------------------
    print("Scanning iCloud ...")
    icloud_names = {}
    for f in ICLOUD_ROOT.rglob("*"):
        if f.is_file() and f.suffix.lower() not in SKIP_EXTS:
            icloud_names[f.name.upper()] = f
    print(f"  {len(icloud_names)} files indexed")

    # -------------------------------------------------------------------------
    # STEP 2: Scan /Photos and find exact filename matches
    # -------------------------------------------------------------------------
    print("Scanning /Photos ...")
    photos_files = [
        f for f in PHOTOS_ROOT.rglob("*")
        if f.is_file()
        and f.suffix.lower() not in SKIP_EXTS
        and STAGE_DIR not in f.parents
    ]
    print(f"  {len(photos_files)} files found")

    to_move = [
        (f, icloud_names[f.name.upper()])
        for f in photos_files
        if f.name.upper() in icloud_names
    ]
    print(f"  {len(to_move)} exact filename matches found")

    # -------------------------------------------------------------------------
    # STEP 3: Move and log
    # -------------------------------------------------------------------------
    print(f"Moving to {STAGE_DIR} ...")
    log_rows = []
    moved = 0
    errors = 0

    for src, icloud_match in to_move:
        rel = src.relative_to(PHOTOS_ROOT)
        dst = STAGE_DIR / rel
        os.makedirs(str(dst.parent), exist_ok=True)

        try:
            os.rename(str(src), str(dst))
            log_rows.append({
                "result":       "MOVED",
                "source":       str(src),
                "destination":  str(dst),
                "icloud_match": str(icloud_match),
                "error":        "",
            })
            moved += 1
        except Exception as e:
            log_rows.append({
                "result":       "ERROR",
                "source":       str(src),
                "destination":  str(dst),
                "icloud_match": str(icloud_match),
                "error":        str(e),
            })
            errors += 1

    fieldnames = ["result", "source", "destination", "icloud_match", "error"]
    with MOVE_LOG_PATH.open("w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(log_rows)

    # -------------------------------------------------------------------------
    # Summary
    # -------------------------------------------------------------------------
    print()
    print("=" * 50)
    print("STAGING SUMMARY")
    print("=" * 50)
    print(f"  Matches found      : {len(to_move)}")
    print(f"  Successfully moved : {moved}")
    print(f"  Errors             : {errors}")
    print()
    print(f"  Staged to : {STAGE_DIR}")
    print(f"  Move log  : {MOVE_LOG_PATH}")
    print("=" * 50)
    print("iCloud Photos was not touched.")


if __name__ == "__main__":
    main()
