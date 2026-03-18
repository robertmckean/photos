#!/usr/bin/env python3
"""
transform_photo_inventory.py

One-time script to transform photo_inventory_1.csv:
- Reorder columns to match the iCloud inventory layout
- Normalize all date/time columns to EXIF format (YYYY:MM:DD HH:MM:SS)
- Add a hyperlink column with Excel =HYPERLINK() formulas
"""

from __future__ import annotations

import csv
import datetime as dt
from pathlib import Path

INPUT_CSV = Path(r"C:\Users\windo\VS_Code\photos\results\photo_inventory_1.csv")

# Target column order (matches icloud_verified_inventory.csv)
OUTPUT_COLUMNS: list[str] = [
    "root_source",
    "parent_folder",
    "full_path",
    "file_name",
    "hyperlink",
    "capture_time_best",
    "capture_time_dup",
    "datetime_original",
    "create_date",
    "file_stem",
    "extension",
    "file_size_bytes",
    "created_time_fs",
    "modified_time_fs",
    "media_create_date",
    "track_create_date",
    "modify_date",
    "media_modify_date",
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

# Date columns that need normalization
DATE_COLUMNS: list[str] = [
    "capture_time_best",
    "datetime_original",
    "create_date",
    "media_create_date",
    "track_create_date",
    "modify_date",
    "media_modify_date",
    "created_time_fs",
    "modified_time_fs",
]


def normalize_datetime(s: str) -> str:
    """Normalize a date/time string to YYYY:MM:DD HH:MM:SS EXIF format."""
    if not s:
        return ""
    # Already in EXIF format
    if len(s) >= 10 and s[4] == ":" and s[7] == ":":
        return s
    # ISO format: 2019-01-11 23:03:24
    try:
        parts = s.split(" ", 1)
        date_part = parts[0].replace("-", ":")
        time_part = parts[1] if len(parts) > 1 else "00:00:00"
        # Strip timezone offset
        for tz_sep in ("+", "-"):
            idx = time_part.find(tz_sep, 6)
            if idx > 0:
                time_part = time_part[:idx]
                break
        d = dt.datetime.strptime(f"{date_part} {time_part}".replace(":", "-", 2), "%Y-%m-%d %H:%M:%S")
        return d.strftime("%Y:%m:%d %H:%M:%S")
    except (ValueError, IndexError):
        return s


def parse_exif_dt(s: str) -> dt.datetime | None:
    """Parse a YYYY:MM:DD HH:MM:SS string into a datetime, or None."""
    if not s:
        return None
    try:
        return dt.datetime.strptime(s.replace(":", "-", 2), "%Y-%m-%d %H:%M:%S")
    except (ValueError, IndexError):
        return None


def sort_key(row: dict[str, str]) -> tuple:
    """Sort by capture_time_best ascending, blanks last, then full_path."""
    ct = row.get("capture_time_best", "")
    if ct:
        return (0, ct, row.get("full_path", ""))
    return (1, "", row.get("full_path", ""))


def main() -> None:
    """Read, transform, sort, mark near-duplicates, and overwrite photo_inventory_1.csv."""
    print(f"Reading {INPUT_CSV} …")
    rows: list[dict[str, str]] = []

    with open(INPUT_CSV, "r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            # Normalize dates
            for col in DATE_COLUMNS:
                if col in row:
                    row[col] = normalize_datetime(row.get(col, ""))
            # Add hyperlink
            full_path = row.get("full_path", "")
            row["hyperlink"] = f'=HYPERLINK("{full_path}","Open")' if full_path else ""
            rows.append(row)

    # Sort by capture_time_best
    print("Sorting by capture_time_best …")
    rows.sort(key=sort_key)

    # Mark rows where capture_time_best is within 1 second of a neighbor
    print("Marking near-duplicate timestamps …")
    parsed = [parse_exif_dt(r.get("capture_time_best", "")) for r in rows]
    one_sec = dt.timedelta(seconds=1)
    marked = [False] * len(rows)

    for i in range(len(rows) - 1):
        if parsed[i] is not None and parsed[i + 1] is not None:
            if abs(parsed[i + 1] - parsed[i]) <= one_sec:
                marked[i] = True
                marked[i + 1] = True

    for i, row in enumerate(rows):
        row["capture_time_dup"] = "same" if marked[i] else ""

    print(f"Writing {len(rows):,} rows back to {INPUT_CSV} …")
    with open(INPUT_CSV, "w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=OUTPUT_COLUMNS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    dup_count = sum(marked)
    print(f"Done. {dup_count:,} rows marked as 'same'.")


if __name__ == "__main__":
    main()
