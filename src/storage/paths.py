from __future__ import annotations

import os
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_STORAGE_ROOT = PROJECT_ROOT / "data" / "peer_storage"
STORAGE_ROOT_ENV = "PEERTORRENT_STORAGE_ROOT"
DEFAULT_DOWNLOAD_ROOT = PROJECT_ROOT / "data" / "downloads"


def resolve_storage_root(path: str | Path | None = None) -> Path:
    """Resolve the shared piece-storage root, anchoring relative paths at repo root."""
    selected = path or os.environ.get(STORAGE_ROOT_ENV) or DEFAULT_STORAGE_ROOT
    resolved = Path(selected).expanduser()
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved.resolve()


def resolve_project_path(path: str | Path) -> Path:
    """Resolve a relative project data path from the repository root."""
    resolved = Path(path).expanduser()
    if not resolved.is_absolute():
        resolved = PROJECT_ROOT / resolved
    return resolved.resolve()