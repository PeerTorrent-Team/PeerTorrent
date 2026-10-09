"""
Create PeerTorrent metadata for a file.

Example:
    python scripts/create_metadata.py data/input_files/sample.txt

Or specify the output location and piece size:

    python scripts/create_metadata.py data/input_files/sample.txt \
        --output data/metadata/sample.json \
        --piece-size 262144
"""

from __future__ import annotations

import sys
from pathlib import Path

# Allow direct script execution from the project root without an editable install.
_PROJECT_ROOT = str(Path(__file__).resolve().parents[1])
if _PROJECT_ROOT not in sys.path:
    sys.path.insert(0, _PROJECT_ROOT)

import argparse

from src.common.constants import DEFAULT_PIECE_SIZE
from src.pieces.metadata_serializer import build_metadata, save_metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Create PeerTorrent metadata for a file."
    )

    parser.add_argument(
        "file",
        help="Path to the file that will be shared.",
    )

    parser.add_argument(
        "--output",
        default=None,
        help="Output metadata JSON path.",
    )

    parser.add_argument(
        "--piece-size",
        type=int,
        default=DEFAULT_PIECE_SIZE,
        help=(
            f"Piece size in bytes "
            f"(default: {DEFAULT_PIECE_SIZE})."
        ),
    )

    args = parser.parse_args()

    metadata = build_metadata(
        args.file,
        args.piece_size,
    )

    if args.output is None:
        output_path = f"data/metadata/{metadata.file_name}.json"
    else:
        output_path = args.output

    save_metadata(
        metadata,
        output_path,
    )

    print("Metadata created successfully.")
    print(f"File:         {metadata.file_name}")
    print(f"File size:    {metadata.file_size} bytes")
    print(f"Piece size:   {metadata.piece_size} bytes")
    print(f"Piece count:  {metadata.piece_count}")
    print(f"File hash:    {metadata.file_hash}")
    print(f"Metadata:     {output_path}")


if __name__ == "__main__":
    main()