"""
Prepare and display a PeerTorrent two-peer experiment.

This script does not start multiple peers automatically.
It prepares the experiment information and prints the commands
needed to run the tracker and two peers.

Example:
    python scripts/run_experiment.py \
        --metadata data/metadata/test.txt.json \
        --peer1 peer1 \
        --peer2 peer2
"""

from __future__ import annotations

import argparse

from src.common.constants import (
    DEFAULT_PEER_PORT,
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
)
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Prepare a PeerTorrent experiment."
    )

    parser.add_argument(
        "--metadata",
        required=True,
        help="Path to the metadata JSON file.",
    )

    parser.add_argument(
        "--peer1",
        default="peer1",
        help="First peer ID.",
    )

    parser.add_argument(
        "--peer2",
        default="peer2",
        help="Second peer ID.",
    )

    parser.add_argument(
        "--peer1-port",
        type=int,
        default=DEFAULT_PEER_PORT,
        help="Port for the first peer.",
    )

    parser.add_argument(
        "--peer2-port",
        type=int,
        default=DEFAULT_PEER_PORT + 1,
        help="Port for the second peer.",
    )

    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    file_id = calculate_file_id(metadata)

    print("=" * 60)
    print("PeerTorrent Experiment")
    print("=" * 60)

    print(f"File:          {metadata.file_name}")
    print(f"File size:     {metadata.file_size} bytes")
    print(f"Piece size:    {metadata.piece_size} bytes")
    print(f"Piece count:   {metadata.piece_count}")
    print(f"File ID:       {file_id}")
    print()

    print("Tracker:")
    print(
        f"  {DEFAULT_TRACKER_HOST}:{DEFAULT_TRACKER_PORT}"
    )
    print()

    print("Peer 1:")
    print(f"  ID:   {args.peer1}")
    print(f"  Port: {args.peer1_port}")
    print()

    print("Peer 2:")
    print(f"  ID:   {args.peer2}")
    print(f"  Port: {args.peer2_port}")
    print()

    print("Start the tracker in Terminal 1:")
    print()
    print("  python scripts/run_tracker.py")
    print()

    print("Start Peer 1 in Terminal 2:")
    print()
    print(
        "  python scripts/run_peer.py "
        f"--peer-id {args.peer1} "
        f"--metadata {args.metadata} "
        f"--port {args.peer1_port}"
    )
    print()

    print("Start Peer 2 in Terminal 3:")
    print()
    print(
        "  python scripts/run_peer.py "
        f"--peer-id {args.peer2} "
        f"--metadata {args.metadata} "
        f"--port {args.peer2_port}"
    )
    print()

    print("=" * 60)
    print("Experiment setup complete.")
    print("=" * 60)


if __name__ == "__main__":
    main()