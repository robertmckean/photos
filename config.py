# config.py
# Purpose: Central location for project paths and runtime settings
# Features: Workspace-relative defaults and placeholder configuration values
# Usage: Import from application code and replace placeholders as the project evolves

from pathlib import Path


PROJECT_ROOT = Path(__file__).resolve().parent
SRC_DIR = PROJECT_ROOT / "src"
DOCS_DIR = PROJECT_ROOT / "docs"
MODELS_DIR = PROJECT_ROOT / "models"
FILES_DIR = PROJECT_ROOT / "files"
RESULTS_DIR = PROJECT_ROOT / "results"

# Replace these placeholders with project-specific values.
PROJECT_NAME = PROJECT_ROOT.name
DATA_DIR = PROJECT_ROOT / "data"
DEFAULT_INPUT_PATH = DATA_DIR / "input"
DEFAULT_OUTPUT_PATH = RESULTS_DIR


def ensure_project_dirs() -> None:
    """Create common writable directories when a script needs them."""
    for path in (DOCS_DIR, MODELS_DIR, FILES_DIR, RESULTS_DIR):
        path.mkdir(parents=True, exist_ok=True)
