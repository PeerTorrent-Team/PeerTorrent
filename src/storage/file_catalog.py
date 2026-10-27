from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from src.common.types import FileMetadata
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata


@dataclass(frozen=True)
class CatalogEntry:
    name: str
    metadata_path: Path
    metadata: FileMetadata
    file_id: str


class FileCatalog:
    def __init__(self, catalog_path: str | Path) -> None:
        self.catalog_path = Path(catalog_path).resolve()
        payload = json.loads(self.catalog_path.read_text(encoding="utf-8"))
        files = payload.get("files") if isinstance(payload, dict) else None
        if not isinstance(files, list):
            raise ValueError("Catalog must contain a 'files' list")

        entries: dict[str, Path] = {}
        for item in files:
            if not isinstance(item, dict):
                raise ValueError("Each catalog file entry must be an object")
            name = item.get("name")
            metadata = item.get("metadata")
            if not isinstance(name, str) or not name.strip():
                raise ValueError("Catalog file names must be non-empty strings")
            if not isinstance(metadata, str) or not metadata.strip():
                raise ValueError(f"Catalog entry {name!r} needs a metadata path")
            if name in entries:
                raise ValueError(f"Duplicate catalog file name: {name}")
            entries[name] = (self.catalog_path.parent / metadata).resolve()
        self._entries = entries

    def resolve(self, name: str) -> CatalogEntry:
        try:
            metadata_path = self._entries[name]
        except KeyError as exc:
            raise ValueError(f"File name is not in the catalog: {name}") from exc
        metadata = load_metadata(metadata_path)
        return CatalogEntry(
            name=name,
            metadata_path=metadata_path,
            metadata=metadata,
            file_id=calculate_file_id(metadata),
        )