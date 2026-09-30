from __future__ import annotations

import argparse
import time

from src.common.constants import (
    DEFAULT_PEER_PORT,
    DEFAULT_PIECE_SIZE,
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
)
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.pieces.piece_manager import PieceManager
from src.peer.peer import Peer
from src.storage.piece_storage import PieceStorage


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Start a PeerTorrent peer."
    )

    parser.add_argument(
        "--peer-id",
        required=True,
        help="Unique identifier for this peer.",
    )

    parser.add_argument(
        "--metadata",
        required=True,
        help="Path to the file metadata JSON.",
    )

    parser.add_argument(
        "--port",
        type=int,
        default=DEFAULT_PEER_PORT,
        help=f"Peer listening port (default: {DEFAULT_PEER_PORT}).",
    )

    parser.add_argument(
        "--host",
        default="127.0.0.1",
        help="Peer listening/advertised host.",
    )

    parser.add_argument(
        "--storage",
        default="data/peer_storage",
        help="Base directory for peer piece storage.",
    )

    parser.add_argument(
        "--tracker-host",
        default=DEFAULT_TRACKER_HOST,
        help=f"Tracker host (default: {DEFAULT_TRACKER_HOST}).",
    )

    parser.add_argument(
        "--tracker-port",
        type=int,
        default=DEFAULT_TRACKER_PORT,
        help=f"Tracker port (default: {DEFAULT_TRACKER_PORT}).",
    )

    args = parser.parse_args()

    metadata = load_metadata(args.metadata)
    file_id = calculate_file_id(metadata)

    storage = PieceStorage(
        storage_dir=args.storage,
        peer_id=args.peer_id,
        file_id=file_id,
    )

    piece_manager = PieceManager(
        metadata,
        storage,
    )

    peer = Peer(
        peer_id=args.peer_id,
        file_id=file_id,
        piece_manager=piece_manager,
        host=args.host,
        port=args.port,
        storage=storage,
    )

    peer._tracker_client.host = args.tracker_host
    peer._tracker_client.port = args.tracker_port

    peer.start()

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        peer.stop()


if __name__ == "__main__":
    main()
