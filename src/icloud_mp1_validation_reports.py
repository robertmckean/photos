import csv
import json
import os
import subprocess
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass, asdict
from datetime import datetime
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Tuple

ICLOUD_ROOT = Path(r"C:\Users\windo\Pictures\iCloud Photos\Photos")
MP1_ROOT = Path(r"C:\Users\windo\My_Pictures1")
RESULTS_DIR = Path(r"C:\Users\windo\VS_Code\photos\results")
QUARANTINE_NAME = "_JPG_TO_DELETE"

IMAGE_EXTS = {".jpg", ".jpeg", ".heic", ".png"}
VIDEO_EXTS = {".mov", ".mp4"}
ALL_TRACKED_EXTS = IMAGE_EXTS | VIDEO_EXTS

EXIFTOOL_TIME_TAGS = [
    "SubSecDateTimeOriginal",
    "DateTimeOriginal",
    "ContentCreateDate",
    "MediaCreateDate",
    "CreateDate",
    "TrackCreateDate",
    "ModifyDate",
    "FileModifyDate",
]


# Normalize an EXIF/date string to a second-resolution ISO timestamp.
def normalize_datetime_string(value: Optional[str]) -> Optional[str]:
    if not value:
        return None

    cleaned = str(value).strip()
    if not cleaned:
        return None

    cleaned = cleaned.replace("Z", "+00:00")

    if "." in cleaned:
        left, right = cleaned.split(".", 1)
        tz_pos = max(right.find("+"), right.find("-"))
        if tz_pos != -1:
            right = right[tz_pos:]
        else:
            right = ""
        cleaned = left + right

    patterns = [
        "%Y:%m:%d %H:%M:%S%z",
        "%Y:%m:%d %H:%M:%S",
        "%Y-%m-%d %H:%M:%S%z",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%dT%H:%M:%S%z",
        "%Y-%m-%dT%H:%M:%S",
    ]

    for pattern in patterns:
        try:
            parsed = datetime.strptime(cleaned, pattern)
            return parsed.strftime("%Y-%m-%d %H:%M:%S")
        except ValueError:
            pass

    return None


# Return a file's capture timestamp using available EXIF/metadata fields.
def extract_capture_time(metadata: Dict[str, object], file_path: Path) -> Tuple[Optional[str], str]:
    for tag in EXIFTOOL_TIME_TAGS:
        normalized = normalize_datetime_string(metadata.get(tag))
        if normalized:
            return normalized, f"exif:{tag}"

    stat = file_path.stat()
    fallback = datetime.fromtimestamp(stat.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
    return fallback, "filesystem:mtime"


@dataclass
class MediaRecord:
    root_name: str
    full_path: str
    relative_path: str
    parent_dir: str
    filename: str
    stem: str
    extension: str
    size_bytes: int
    capture_time: Optional[str]
    capture_time_source: str
    in_quarantine: bool


# Recursively collect candidate files from a root.
def collect_files(root: Path, root_name: str) -> List[Path]:
    paths: List[Path] = []
    for dirpath, _, filenames in os.walk(root):
        for filename in filenames:
            file_path = Path(dirpath) / filename
            paths.append(file_path)
    return paths


# Read metadata for a batch of files via exiftool.
def read_exiftool_metadata(files: List[Path]) -> Dict[str, Dict[str, object]]:
    if not files:
        return {}

    cmd = [
        "exiftool",
        "-j",
        "-n",
        "-api",
        "QuickTimeUTC=1",
    ]

    for tag in EXIFTOOL_TIME_TAGS:
        cmd.append(f"-{tag}")

    cmd.extend(str(path) for path in files)

    completed = subprocess.run(cmd, capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    return {str(Path(item["SourceFile"])): item for item in payload}


# Build MediaRecord objects for an entire tree.
def build_records(root: Path, root_name: str) -> Tuple[List[MediaRecord], List[str]]:
    file_paths = collect_files(root, root_name)
    warnings: List[str] = []
    metadata_by_path: Dict[str, Dict[str, object]] = {}

    try:
        batch_size = 1000
        for start in range(0, len(file_paths), batch_size):
            batch = file_paths[start:start + batch_size]
            metadata_by_path.update(read_exiftool_metadata(batch))
    except FileNotFoundError:
        warnings.append("exiftool was not found on PATH; falling back to filesystem modified time only.")
    except subprocess.CalledProcessError as exc:
        warnings.append(f"exiftool failed ({exc.returncode}); falling back to filesystem modified time only.")

    records: List[MediaRecord] = []

    for file_path in file_paths:
        metadata = metadata_by_path.get(str(file_path), {})
        capture_time, capture_time_source = extract_capture_time(metadata, file_path)
        ext = file_path.suffix.lower()
        in_quarantine = QUARANTINE_NAME.lower() in {part.lower() for part in file_path.parts}

        record = MediaRecord(
            root_name=root_name,
            full_path=str(file_path),
            relative_path=str(file_path.relative_to(root)),
            parent_dir=str(file_path.parent),
            filename=file_path.name,
            stem=file_path.stem.lower(),
            extension=ext,
            size_bytes=file_path.stat().st_size,
            capture_time=capture_time,
            capture_time_source=capture_time_source,
            in_quarantine=in_quarantine,
        )
        records.append(record)

    return records, warnings


# Build lookup indexes for matching by filename and capture time.
def build_indexes(records: List[MediaRecord]) -> Dict[str, Dict[Tuple[str, Optional[str]], List[MediaRecord]]]:
    exact_index: Dict[Tuple[str, Optional[str], str], List[MediaRecord]] = defaultdict(list)
    stem_time_index: Dict[Tuple[str, Optional[str]], List[MediaRecord]] = defaultdict(list)
    stem_only_index: Dict[str, List[MediaRecord]] = defaultdict(list)

    for record in records:
        exact_index[(record.filename.lower(), record.capture_time, record.extension)].append(record)
        stem_time_index[(record.stem, record.capture_time)].append(record)
        stem_only_index[record.stem].append(record)

    return {
        "exact": exact_index,
        "stem_time": stem_time_index,
        "stem_only": stem_only_index,
    }


# Find the best MP1 match for an iCloud source record.
def find_match_for_icloud(record: MediaRecord, mp1_indexes: Dict[str, Dict], active_mp1_records: List[MediaRecord]) -> Tuple[str, List[MediaRecord]]:
    same_stem_time = mp1_indexes["stem_time"].get((record.stem, record.capture_time), [])
    active_same_stem_time = [item for item in same_stem_time if not item.in_quarantine]
    quarantine_same_stem_time = [item for item in same_stem_time if item.in_quarantine]

    if active_same_stem_time:
        return "MATCHED_IN_ACTIVE_MP1", active_same_stem_time

    if quarantine_same_stem_time:
        return "ONLY_IN_QUARANTINE", quarantine_same_stem_time

    active_same_stem = [item for item in mp1_indexes["stem_only"].get(record.stem, []) if not item.in_quarantine]
    if active_same_stem:
        return "STEM_MATCH_ONLY_TIME_DIFF", active_same_stem

    return "NO_MP1_MATCH", []


# Find the best iCloud match for an MP1 record.
def find_match_for_mp1(record: MediaRecord, icloud_indexes: Dict[str, Dict]) -> Tuple[str, List[MediaRecord]]:
    same_stem_time = icloud_indexes["stem_time"].get((record.stem, record.capture_time), [])
    if same_stem_time:
        return "MATCHED_IN_ICLOUD", same_stem_time

    same_stem = icloud_indexes["stem_only"].get(record.stem, [])
    if same_stem:
        return "STEM_MATCH_ONLY_TIME_DIFF", same_stem

    return "NO_ICLOUD_MATCH", []


# Write rows to a CSV file.
def write_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames = sorted({key for row in rows for key in row.keys()}) if rows else ["status"]

    with path.open("w", newline="", encoding="utf-8-sig") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


# Convert a MediaRecord and optional counterpart into a flat CSV row.
def make_row(record: MediaRecord, status: str, counterpart: Optional[MediaRecord] = None, notes: str = "") -> Dict[str, object]:
    row = {
        "status": status,
        "notes": notes,
        "root_name": record.root_name,
        "full_path": record.full_path,
        "relative_path": record.relative_path,
        "parent_dir": record.parent_dir,
        "filename": record.filename,
        "stem": record.stem,
        "extension": record.extension,
        "size_bytes": record.size_bytes,
        "capture_time": record.capture_time,
        "capture_time_source": record.capture_time_source,
        "in_quarantine": record.in_quarantine,
    }

    if counterpart:
        row.update(
            {
                "counterpart_path": counterpart.full_path,
                "counterpart_filename": counterpart.filename,
                "counterpart_extension": counterpart.extension,
                "counterpart_capture_time": counterpart.capture_time,
                "counterpart_in_quarantine": counterpart.in_quarantine,
            }
        )

    return row


# Main entry point for report generation.
def main() -> int:
    print(f"Scanning iCloud root: {ICLOUD_ROOT}")
    icloud_records, icloud_warnings = build_records(ICLOUD_ROOT, "iCloud")
    print(f"Scanning MP1 root:    {MP1_ROOT}")
    mp1_records, mp1_warnings = build_records(MP1_ROOT, "MP1")

    warnings = icloud_warnings + mp1_warnings
    for warning in warnings:
        print(f"WARNING: {warning}")

    active_mp1_records = [record for record in mp1_records if not record.in_quarantine]
    quarantine_mp1_records = [record for record in mp1_records if record.in_quarantine]

    icloud_indexes = build_indexes(icloud_records)
    mp1_indexes = build_indexes(mp1_records)

    report1_rows: List[Dict[str, object]] = []
    report2_rows: List[Dict[str, object]] = []
    report3_rows: List[Dict[str, object]] = []
    report4_rows: List[Dict[str, object]] = []

    for record in icloud_records:
        status, matches = find_match_for_icloud(record, mp1_indexes, active_mp1_records)
        counterpart = matches[0] if matches else None

        if status != "MATCHED_IN_ACTIVE_MP1":
            report1_rows.append(make_row(record, status, counterpart))

        if record.extension == ".mov":
            image_match_status = "NO_CORRESPONDING_IMAGE"
            image_counterpart: Optional[MediaRecord] = None

            same_stem_icloud = [item for item in icloud_indexes["stem_only"].get(record.stem, []) if item.extension in IMAGE_EXTS]
            same_stem_mp1 = [item for item in mp1_indexes["stem_only"].get(record.stem, []) if item.extension in IMAGE_EXTS and not item.in_quarantine]

            if same_stem_mp1:
                image_match_status = "IMAGE_EXISTS_IN_MP1"
                image_counterpart = same_stem_mp1[0]
            elif same_stem_icloud:
                image_match_status = "IMAGE_EXISTS_IN_ICLOUD_ONLY"
                image_counterpart = same_stem_icloud[0]

            report3_rows.append(make_row(record, image_match_status, image_counterpart))

        if record.extension == ".png":
            report4_rows.append(make_row(record, status, counterpart))

    for record in active_mp1_records:
        status, matches = find_match_for_mp1(record, icloud_indexes)
        if status == "NO_ICLOUD_MATCH":
            report2_rows.append(make_row(record, status, None))

    summary = {
        "icloud_total_files": len(icloud_records),
        "mp1_total_files": len(mp1_records),
        "mp1_active_files": len(active_mp1_records),
        "mp1_quarantine_files": len(quarantine_mp1_records),
        "report1_icloud_not_present_in_mp1": len(report1_rows),
        "report1_status_breakdown": dict(Counter(row["status"] for row in report1_rows)),
        "report2_mp1_no_corresponding_icloud": len(report2_rows),
        "report2_status_breakdown": dict(Counter(row["status"] for row in report2_rows)),
        "report3_mov_files": len(report3_rows),
        "report3_status_breakdown": dict(Counter(row["status"] for row in report3_rows)),
        "report4_png_files": len(report4_rows),
        "report4_status_breakdown": dict(Counter(row["status"] for row in report4_rows)),
        "warnings": warnings,
    }

    report1_path = RESULTS_DIR / "report1_icloud_not_present_in_mp1.csv"
    report2_path = RESULTS_DIR / "report2_mp1_no_corresponding_icloud.csv"
    report3_path = RESULTS_DIR / "report3_mov_status.csv"
    report4_path = RESULTS_DIR / "report4_png_status.csv"
    summary_path = RESULTS_DIR / "report_summary.json"

    write_csv(report1_path, report1_rows)
    write_csv(report2_path, report2_rows)
    write_csv(report3_path, report3_rows)
    write_csv(report4_path, report4_rows)
    summary_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")

    print("\n=== SUMMARY ===")
    for key, value in summary.items():
        print(f"{key}: {value}")

    print("\n=== OUTPUT FILES ===")
    print(report1_path)
    print(report2_path)
    print(report3_path)
    print(report4_path)
    print(summary_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
