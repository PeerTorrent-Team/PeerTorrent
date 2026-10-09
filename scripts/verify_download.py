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
        default="data/peer_storage",
        help="Base piece-storage directory (default: data/peer_storage).",
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

    metadata = load_metadata(args.metadata)
    file_id = calculate_file_id(metadata)
    storage = PieceStorage(
        storage_dir=args.storage,
        peer_id=args.peer_id,
        file_id=file_id,
    )
    safe_file_name = Path(metadata.file_name.replace("\\", "/")).name
    output_path = args.output or str(Path("data/downloads") / safe_file_name)

    output = verify_downloaded_file(
        metadata=metadata,
        storage=storage,
        output_path=output_path,
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
