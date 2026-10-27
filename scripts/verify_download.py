"""Verify a peer's stored pieces and reconstruct the completed download.

Example:
    python scripts/verify_download.py \\
        --metadata data/metadata/sample.bin.json \\
        --peer-id peer2 \\
        --output data/downloads/sample.bin
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
from src.storage.file_workflow import verify_downloaded_file
from src.storage.piece_storage import PieceStorage
from src.storage.paths import DEFAULT_STORAGE_ROOT, PROJECT_ROOT, resolve_storage_root


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Verify all pieces for a peer, reconstruct the file, and "
            "check its whole-file hash."
        )
    )
    parser.add_argument(
        "--metadata", required=True, help="Metainfo JSON for the download."
    )
    parser.add_argument(
        "--peer-id", required=True, help="Peer ID whose pieces should be checked."
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=None,
        help=f"Base piece-storage directory (default: {DEFAULT_STORAGE_ROOT}).",
    )
    parser.add_argument(
        "--output",
        default=None,
        help=(
            "Reconstructed output path (default: "
            "data/downloads/<metainfo filename>)."
        ),
    )
    args = parser.parse_args()

    metadata_path = Path(args.metadata).expanduser()
    if not metadata_path.is_absolute():
        metadata_path = PROJECT_ROOT / metadata_path
    metadata = load_metadata(metadata_path.resolve())
    file_id = calculate_file_id(metadata)
    storage_root = resolve_storage_root(args.storage)
    print(f"Storage root: {storage_root}")
    storage = PieceStorage(
        storage_dir=storage_root,
        peer_id=args.peer_id,
        file_id=file_id,
    )
    safe_file_name = Path(metadata.file_name.replace("\\", "/")).name
    output_path = Path(args.output) if args.output else Path("data/downloads") / safe_file_name
    if not output_path.is_absolute():
        output_path = PROJECT_ROOT / output_path

    output = verify_downloaded_file(
        metadata=metadata,
        storage=storage,
        output_path=output_path.resolve(),
    )

    print("Download verification passed.")
    print(f"Peer ID:       {args.peer_id}")
    print(f"File:          {output}")
    print(f"Bytes:         {metadata.file_size}")
    print(f"Pieces checked:{metadata.piece_count:>4}")
    if metadata.file_hash:
        print(f"SHA-256:       {metadata.file_hash}")


if __name__ == "__main__":
    main()
