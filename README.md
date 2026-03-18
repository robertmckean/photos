# Photo Library Consolidation Toolkit

Toolkit for migrating iCloud Photos into a date-organized MP1 folder structure.
Includes inventory, matching, batch copy/move, and gap analysis scripts.

All operations are non-destructive by default (copy-only, guarded moves with
replacement checks, preview-before-execute pattern).

## Prerequisites

- **Python 3.11+**
- **ExifTool** installed and on PATH ([https://exiftool.org](https://exiftool.org))
  - Verify: `exiftool -ver`

No third-party Python packages are required — only the standard library.

## Scripts

### Inventory
| Script | Purpose |
|---|---|
| `build_photo_inventory.py` | Scan My_Pictures1 + iCloud, extract ExifTool metadata, write CSV |
| `build_icloud_inventory.py` | Scan H:\iCloud_Verified with ExifTool metadata |
| `transform_photo_inventory.py` | Reorder columns, normalize dates, mark near-duplicate timestamps |
| `add_hyperlinks.py` | Add Excel =HYPERLINK() column to finished CSV |

### Matching and pairing
| Script | Purpose |
|---|---|
| `generate_pairs_v2.py` | Generate 1-to-1 iCloud/MP1 pairs by capture_time + comparison_stem |
| `generate_candidates_v2.py` | Generate copy candidates (SAFE/AMBIGUOUS/SKIPPED) |
| `copy_icloud_to_mp1.py` | Two-phase: preview CSV, then `--execute` for SAFE copies |

### Batch processing
| Script | Purpose |
|---|---|
| `v4_batch_next_1000.py` | Batch copy + guarded quarantine move |
| `copy_non_jpg_heic_to_mp1.py` | Copy non-JPG/HEIC files (MOV, PNG, MP4) to MP1 |
| `copy_live_photo_heic.py` | Copy Live Photo HEICs (preserves JPG/MOV) |

### Analysis and verification
| Script | Purpose |
|---|---|
| `gap_analysis.py` | Comprehensive iCloud vs MP1 gap analysis |
| `check_date_folder_alignment.py` | Compare capture_time_best against MP1 folder dates |
| `check_non_jpg_heic_in_mp1.py` | Check non-JPG/HEIC iCloud files against MP1 |
| `regenerate_progress.py` | Regenerate progress CSV from filesystem state |
| `verify_restore_same_name_bug.py` | Verify restored same-name JPG bug files |

## Capture-time priority

`capture_time_best` is resolved using the first non-empty value from:

1. `DateTimeOriginal`
2. `CreateDate`
3. `MediaCreateDate`
4. `TrackCreateDate`
5. `ModifyDate`
6. `MediaModifyDate`
7. Filesystem created time

## Structure

- `changelogs/`: release notes
- `docs/`: documentation
- `results/`: generated CSV outputs (gitignored)
- `tools/`: local helper scripts
