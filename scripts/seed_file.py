"""Prepare a peer's piece storage from the original file.

Example:
    python scripts/seed_file.py \\
        --file data/input_files/sample.bin \\
        --metadata data/metadata/sample.bin.json \\
        --peer-id seed1
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow direct script execution from the project root without an editable install.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import argparse
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.storage.file_workflow import seed_source_file
from src.storage.paths import (
    DEFAULT_STORAGE_ROOT,
    resolve_project_path,
    resolve_storage_root,
)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Validate a source file and prepare a PeerTorrent seeder."
    )
    parser.add_argument("--file", required=True, help="Original file to seed.")
    parser.add_argument(
        "--metadata", required=True, help="Metainfo JSON for the source file."
    )
    parser.add_argument(
        "--peer-id", required=True, help="Peer ID that will act as the seeder."
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=None,
        help=f"Base piece-storage directory (default: {DEFAULT_STORAGE_ROOT}).",
    )
    args = parser.parse_args()

    metadata = load_metadata(resolve_project_path(args.metadata))
    source_path = resolve_project_path(args.file)
    storage_root = resolve_storage_root(args.storage)
    print(f"Storage root: {storage_root}")
    storage = seed_source_file(
        source_path=source_path,
        metadata=metadata,
        peer_id=args.peer_id,
        storage_root=storage_root,
    )

    print("Seeder storage prepared successfully.")
    print(f"Peer ID:      {args.peer_id}")
    print(f"File:         {metadata.file_name}")
    print(f"File ID:      {calculate_file_id(metadata)}")
    print(f"Pieces ready: {metadata.piece_count}")
    storage_path = storage_root / args.peer_id / calculate_file_id(metadata)
    print(f"Storage:      {storage_path}")


if __name__ == "__main__":
    main()
