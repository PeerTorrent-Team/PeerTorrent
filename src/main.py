from __future__ import annotations

import signal
import argparse
import json
import shlex
import time
from pathlib import Path

from src.common.constants import (
    DEFAULT_PEER_PORT,
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
)
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.pieces.piece_manager import PieceManager
from src.peer.peer import Peer
from src.selection.selector_factory import (
    DEFAULT_STRATEGY,
    SUPPORTED_STRATEGIES,
    create_selector,
)
from src.peer.dynamic_session import DynamicPeerSession
from src.storage.piece_storage import PieceStorage
from src.storage.paths import (
    DEFAULT_STORAGE_ROOT,
    resolve_project_path,
    resolve_storage_root,
)


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
        help="Path to the file metadata JSON.",
    )

    parser.add_argument("--catalog", help="Path to a JSON file catalog.")
    parser.add_argument("--request-file", help="File name to resolve in the catalog.")

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
        default=None,
        help=f"Base directory for peer piece storage (default: {DEFAULT_STORAGE_ROOT}).",
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

    parser.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGIES,
        default=DEFAULT_STRATEGY,
        help="Piece selection: rarest-first, sequential, or random.",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        help="Seed for the random piece selector (random strategy only).",
    )

    parser.add_argument(
        "--no-upload",
        action="store_true",
        help="Do not upload pieces; used for the free-rider experiment.",
    )

    parser.add_argument(
     "--upload-rate-limit",
     type=int,
     default=None,
     help="Simulated upload rate limit in bytes per second.",
    )

    parser.add_argument(
        "--stats-output",
        help="Optional path to write peer transfer and choking statistics as JSON.",
    )

    parser.add_argument(
        "--interactive",
        action="store_true",
        help="Accept runtime commands to switch the requested file.",
    )

    args = parser.parse_args()
    storage_root = resolve_storage_root(args.storage)
    print(f"Storage root: {storage_root}")

    if args.catalog or args.request_file:
        if not args.catalog or not args.request_file or args.metadata:
            parser.error(
                "--catalog and --request-file must be used together and cannot "
                "be combined with --metadata"
            )
        try:
            session = DynamicPeerSession(
                peer_id=args.peer_id,
                catalog_path=resolve_project_path(args.catalog),
                host=args.host,
                port=args.port,
                storage_dir=storage_root,
                tracker_host=args.tracker_host,
                tracker_port=args.tracker_port,
                strategy=args.strategy,
                random_seed=args.random_seed,
                upload_enabled=not args.no_upload,
            )
            entry = session.start(args.request_file)
        except (ValueError, FileNotFoundError) as exc:
            parser.error(str(exc))

        print(
            f"Peer {args.peer_id} joined file '{entry.name}' "
            f"(file_id={entry.file_id})."
        )
        try:
            if args.interactive:
                print("Commands: request <catalog-name>, status, help, quit")
                while True:
                    try:
                        command = input("peertorrent> ")
                    except EOFError:
                        break
                    try:
                        parts = shlex.split(command)
                    except ValueError as exc:
                        print(f"Invalid command: {exc}")
                        continue
                    if not parts:
                        continue
                    action = parts[0].lower()
                    if action in {"quit", "exit"} and len(parts) == 1:
                        break
                    if action == "help" and len(parts) == 1:
                        print("Commands: request <catalog-name>, status, help, quit")
                    elif action == "status" and len(parts) == 1:
                        active = session.current_entry
                        if active is None or session.peer is None:
                            print("No file swarm is active.")
                        else:
                            print(
                                f"Active file: {active.name} "
                                f"(file_id={active.file_id}, "
                                f"complete={session.peer.is_complete()})"
                            )
                    elif action == "request" and len(parts) == 2:
                        try:
                            requested = session.request_file(parts[1])
                        except (ValueError, FileNotFoundError, RuntimeError) as exc:
                            print(f"Request failed: {exc}")
                        else:
                            print(
                                f"Peer {args.peer_id} joined file '{requested.name}' "
                                f"(file_id={requested.file_id})."
                            )
                    else:
                        print("Invalid command. Type 'help' for commands.")
            else:
                while True:
                    time.sleep(1)
        except KeyboardInterrupt:
            pass
        finally:
            session.stop()
        return

    if args.interactive:
        parser.error("--interactive requires --catalog and --request-file")
    if not args.metadata:
        parser.error("either --metadata or --catalog with --request-file is required")

    metadata = load_metadata(resolve_project_path(args.metadata))
    file_id = calculate_file_id(metadata)

    storage = PieceStorage(
        storage_dir=storage_root,
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
        selector=create_selector(args.strategy, random_seed=args.random_seed),
        upload_enabled=not args.no_upload,
        upload_rate_limit=args.upload_rate_limit,
    )

    peer._tracker_client.host = args.tracker_host
    peer._tracker_client.port = args.tracker_port

    peer.start()

    def handle_shutdown_signal(signum, frame):
      raise KeyboardInterrupt

    signal.signal(signal.SIGTERM, handle_shutdown_signal)
    signal.signal(signal.SIGINT, handle_shutdown_signal)


    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        pass
    finally:
        peer.stop()
        if args.stats_output:
            stats = peer.get_transfer_stats()
            stats["choking"] = peer._choking_manager.get_stats()
            stats_path = Path(args.stats_output)
            stats_path.parent.mkdir(parents=True, exist_ok=True)
            stats_path.write_text(
                json.dumps(stats, indent=2),
                encoding="utf-8",
            )


if __name__ == "__main__":
    main()
