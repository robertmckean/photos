#!/usr/bin/env python3
"""
build_photo_inventory.py

Recursively scans configured photo/video folder trees and writes a single
UTF-8 CSV inventory file with per-file metadata extracted via ExifTool.

NON-DESTRUCTIVE — only reads source files and writes the CSV output.
"""

from __future__ import annotations

import csv
import datetime as dt
import hashlib
import json
import os
import subprocess
import sys
import time
from pathlib import Path

# ── Configuration ────────────────────────────────────────────────────────────

SOURCE_ROOTS: list[Path] = [
    Path(r"C:\Users\windo\Pictures"),
    Path(r"C:\Users\windo\My_Pictures1"),
]

OUTPUT_DIR: Path = Path(r"C:\Users\windo\VS_Code\photos\results")

PHOTO_EXTENSIONS: set[str] = {
    ".jpg", ".jpeg", ".png", ".heic", ".heif",
    ".tif", ".tiff", ".bmp", ".gif", ".webp", ".dng",
}

VIDEO_EXTENSIONS: set[str] = {
    ".mov", ".mp4", ".m4v", ".avi", ".mts", ".m2ts",
    ".3gp", ".mpg", ".mpeg", ".wmv",
}

SUPPORTED_EXTENSIONS: set[str] = PHOTO_EXTENSIONS | VIDEO_EXTENSIONS

CSV_COLUMNS: list[str] = [
    "root_source",
    "full_path",
    "parent_folder",
    "file_name",
    "file_stem",
    "extension",
    "file_size_bytes",
    "created_time_fs",
    "modified_time_fs",
    "datetime_original",
    "create_date",
    "media_create_date",
    "track_create_date",
    "modify_date",
    "media_modify_date",
    "capture_time_best",
    "capture_time_source",
    "file_type",
    "mime_type",
    "image_width",
    "image_height",
    "megapixels",
    "orientation",
    "make",
    "model",
    "lens_model",
    "software",
    "duration_seconds",
    "rotation",
    "live_photo_hint",
    "content_hash_sha256",
    "exif_error",
]

# ExifTool tags we request (keys are the ExifTool tag names)
EXIF_TAGS: list[str] = [
    "DateTimeOriginal",
    "CreateDate",
    "MediaCreateDate",
    "TrackCreateDate",
    "ModifyDate",
    "MediaModifyDate",
    "FileType",
    "MIMEType",
    "ImageWidth",
    "ImageHeight",
    "Megapixels",
    "Orientation",
    "Make",
    "Model",
    "LensModel",
    "Software",
    "Duration",
    "Rotation",
    "ContentIdentifier",  # indicates a Live Photo companion
]

# Capture-time priority: (exiftool_key, csv_source_label)
CAPTURE_TIME_PRIORITY: list[tuple[str, str]] = [
    ("DateTimeOriginal", "DateTimeOriginal"),
    ("CreateDate", "CreateDate"),
    ("MediaCreateDate", "MediaCreateDate"),
    ("TrackCreateDate", "TrackCreateDate"),
    ("ModifyDate", "ModifyDate"),
    ("MediaModifyDate", "MediaModifyDate"),
]

HASH_CHUNK_SIZE: int = 1 << 16  # 64 KiB

EXIFTOOL_BATCH_SIZE: int = 200


# ── Helpers ──────────────────────────────────────────────────────────────────

def discover_files(roots: list[Path]) -> list[tuple[Path, Path]]:
    """Walk *roots* recursively and return (root, file_path) pairs for supported extensions."""
    found: list[tuple[Path, Path]] = []
    for root in roots:
        if not root.exists():
            print(f"  WARNING: source root does not exist, skipping: {root}")
            continue
        for dirpath, _dirnames, filenames in os.walk(root):
            for fname in filenames:
                p = Path(dirpath) / fname
                if p.suffix.lower() in SUPPORTED_EXTENSIONS:
                    found.append((root, p))
    return found


def sha256_of_file(path: Path) -> str:
    """Return the hex SHA-256 digest of *path*, reading in streaming chunks."""
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        while True:
            chunk = fh.read(HASH_CHUNK_SIZE)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def fs_timestamp(ts: float) -> str:
    """Format a filesystem timestamp as an ISO-style local-time string."""
    return dt.datetime.fromtimestamp(ts).strftime("%Y-%m-%d %H:%M:%S")


def run_exiftool_batch(paths: list[Path]) -> dict[str, dict[str, str]]:
    """
    Run exiftool in batch JSON mode on *paths* and return a dict keyed by
    the normalised (resolved) file path, with values being tag dicts.
    """
    tag_args = []
    for tag in EXIF_TAGS:
        tag_args.append(f"-{tag}")

    cmd: list[str] = [
        "exiftool",
        "-json",
        "-n",           # numeric values (avoid localized strings for Rotation etc.)
        "-charset", "filename=utf8",
        *tag_args,
        *[str(p) for p in paths],
    ]

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        timeout=300,
    )

    records: dict[str, dict[str, str]] = {}
    if result.stdout.strip():
        try:
            data = json.loads(result.stdout)
        except json.JSONDecodeError:
            return records
        for entry in data:
            src = entry.get("SourceFile", "")
            records[str(Path(src).resolve())] = entry
    return records


def parse_duration(raw) -> str:
    """
    Normalise an ExifTool Duration value (may be seconds as float/int,
    or a string like '0:05:12') into total seconds as a string.
    """
    if raw is None or raw == "":
        return ""
    if isinstance(raw, (int, float)):
        return str(round(raw, 2))
    if isinstance(raw, str):
        parts = raw.split(":")
        try:
            if len(parts) == 3:
                h, m, s = parts
                return str(round(int(h) * 3600 + int(m) * 60 + float(s), 2))
            if len(parts) == 2:
                m, s = parts
                return str(round(int(m) * 60 + float(s), 2))
            return str(round(float(raw), 2))
        except (ValueError, TypeError):
            return raw
    return str(raw)


def exif_val(meta: dict, key: str) -> str:
    """Return a string value from ExifTool metadata, or '' if missing/empty."""
    v = meta.get(key)
    if v is None:
        return ""
    s = str(v).strip()
    if s in ("0000:00:00 00:00:00", "0000:00:00", ""):
        return ""
    return s


def build_row(
    root: Path,
    fpath: Path,
    meta: dict[str, str] | None,
    exif_error: str,
) -> dict[str, str]:
    """
    Build a single CSV-row dict for *fpath* using filesystem info,
    ExifTool *meta*, and any *exif_error* message.
    """
    stat = fpath.stat()
    row: dict[str, str] = {
        "root_source": str(root),
        "full_path": str(fpath),
        "parent_folder": str(fpath.parent),
        "file_name": fpath.name,
        "file_stem": fpath.stem,
        "extension": fpath.suffix.lower(),
        "file_size_bytes": str(stat.st_size),
        "created_time_fs": fs_timestamp(stat.st_ctime),
        "modified_time_fs": fs_timestamp(stat.st_mtime),
        "exif_error": exif_error,
    }

    if meta is None:
        meta = {}

    # Populate date/time columns from EXIF
    row["datetime_original"] = exif_val(meta, "DateTimeOriginal")
    row["create_date"] = exif_val(meta, "CreateDate")
    row["media_create_date"] = exif_val(meta, "MediaCreateDate")
    row["track_create_date"] = exif_val(meta, "TrackCreateDate")
    row["modify_date"] = exif_val(meta, "ModifyDate")
    row["media_modify_date"] = exif_val(meta, "MediaModifyDate")

    # Determine capture_time_best using priority list
    capture_best = ""
    capture_source = ""
    for exif_key, label in CAPTURE_TIME_PRIORITY:
        val = exif_val(meta, exif_key)
        if val:
            capture_best = val
            capture_source = label
            break
    if not capture_best:
        capture_best = row["created_time_fs"]
        capture_source = "filesystem_created"
    row["capture_time_best"] = capture_best
    row["capture_time_source"] = capture_source

    # Other metadata fields
    row["file_type"] = exif_val(meta, "FileType")
    row["mime_type"] = exif_val(meta, "MIMEType")
    row["image_width"] = exif_val(meta, "ImageWidth")
    row["image_height"] = exif_val(meta, "ImageHeight")
    row["megapixels"] = exif_val(meta, "Megapixels")
    row["orientation"] = exif_val(meta, "Orientation")
    row["make"] = exif_val(meta, "Make")
    row["model"] = exif_val(meta, "Model")
    row["lens_model"] = exif_val(meta, "LensModel")
    row["software"] = exif_val(meta, "Software")
    row["duration_seconds"] = parse_duration(meta.get("Duration"))
    row["rotation"] = exif_val(meta, "Rotation")

    # Live Photo hint: presence of ContentIdentifier
    ci = exif_val(meta, "ContentIdentifier")
    row["live_photo_hint"] = "yes" if ci else ""

    return row


def sort_key(row: dict[str, str]) -> tuple:
    """
    Sort key: capture_time_best ascending (blanks last), then full_path ascending.
    """
    ct = row.get("capture_time_best", "")
    if ct:
        return (0, ct, row.get("full_path", ""))
    return (1, "", row.get("full_path", ""))


# ── Main ─────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point: discover files, extract metadata, hash, write CSV."""
    t_start = time.time()

    print("=" * 70)
    print("  Photo / Video Inventory Builder")
    print("=" * 70)

    # 1. Discover files
    print("\n[1/4] Discovering files …")
    file_pairs = discover_files(SOURCE_ROOTS)
    total = len(file_pairs)
    print(f"       Found {total:,} supported files across {len(SOURCE_ROOTS)} root(s).")

    if total == 0:
        print("\nNo files to process. Exiting.")
        return

    # 2. Run ExifTool in batches
    print(f"\n[2/4] Extracting metadata via ExifTool (batch size {EXIFTOOL_BATCH_SIZE}) …")
    all_paths = [fp for _, fp in file_pairs]
    exif_data: dict[str, dict[str, str]] = {}
    exif_errors: dict[str, str] = {}

    for batch_start in range(0, total, EXIFTOOL_BATCH_SIZE):
        batch = all_paths[batch_start : batch_start + EXIFTOOL_BATCH_SIZE]
        batch_end = min(batch_start + EXIFTOOL_BATCH_SIZE, total)
        print(f"       Batch {batch_start + 1}–{batch_end} of {total} …")
        try:
            result = run_exiftool_batch(batch)
            exif_data.update(result)
        except subprocess.TimeoutExpired:
            msg = "ExifTool batch timed out"
            print(f"       WARNING: {msg}")
            for p in batch:
                exif_errors[str(p.resolve())] = msg
        except Exception as exc:
            msg = f"ExifTool batch error: {exc}"
            print(f"       WARNING: {msg}")
            for p in batch:
                exif_errors[str(p.resolve())] = msg

    # 3. Build rows (hash + assemble)
    print(f"\n[3/4] Hashing files and building rows …")
    rows: list[dict[str, str]] = []
    errors = 0

    for idx, (root, fpath) in enumerate(file_pairs, 1):
        if idx % 500 == 0 or idx == total:
            print(f"       {idx:,} / {total:,}")

        resolved_key = str(fpath.resolve())
        meta = exif_data.get(resolved_key)
        err = exif_errors.get(resolved_key, "")

        if meta is None and not err:
            err = "no ExifTool output for file"

        try:
            row = build_row(root, fpath, meta, err)
        except Exception as exc:
            # If even stat/build fails, create a minimal row
            row = {c: "" for c in CSV_COLUMNS}
            row["root_source"] = str(root)
            row["full_path"] = str(fpath)
            row["file_name"] = fpath.name
            row["exif_error"] = f"row build error: {exc}"
            errors += 1

        # SHA-256
        try:
            row["content_hash_sha256"] = sha256_of_file(fpath)
        except Exception as exc:
            row["content_hash_sha256"] = ""
            if row["exif_error"]:
                row["exif_error"] += f"; hash error: {exc}"
            else:
                row["exif_error"] = f"hash error: {exc}"
            errors += 1

        rows.append(row)

    # 4. Sort and write CSV
    rows.sort(key=sort_key)

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    csv_path = OUTPUT_DIR / "photo_inventory.csv"

    print(f"\n[4/4] Writing CSV → {csv_path}")
    with open(csv_path, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=CSV_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    elapsed = time.time() - t_start

    # Summary
    photo_count = sum(1 for r in rows if r["extension"] in PHOTO_EXTENSIONS)
    video_count = sum(1 for r in rows if r["extension"] in VIDEO_EXTENSIONS)
    total_bytes = sum(int(r["file_size_bytes"]) for r in rows if r["file_size_bytes"])
    total_gb = total_bytes / (1024 ** 3)

    print("\n" + "=" * 70)
    print("  SUMMARY")
    print("=" * 70)
    print(f"  Total files:   {total:,}")
    print(f"  Photos:        {photo_count:,}")
    print(f"  Videos:        {video_count:,}")
    print(f"  Total size:    {total_gb:,.2f} GB")
    print(f"  Errors:        {errors:,}")
    print(f"  CSV written:   {csv_path}")
    print(f"  Elapsed:       {elapsed:,.1f}s")
    print("=" * 70)


if __name__ == "__main__":
    main()
