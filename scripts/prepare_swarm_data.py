from __future__ import annotations

import argparse
import json
import shutil
import sys
import tempfile
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.storage.file_workflow import seed_source_file
from src.storage.piece_storage import PieceStorage

from src.storage.paths import (
    DEFAULT_DOWNLOAD_ROOT,
    DEFAULT_STORAGE_ROOT,
    resolve_project_path,
    resolve_storage_root,
)

STORAGE_ROOT = DEFAULT_STORAGE_ROOT
DOWNLOAD_ROOT = DEFAULT_DOWNLOAD_ROOT
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "configs" / "swarm_config.json"


def _piece_indices(distribution: str | int | list[int], piece_count: int) -> list[int]:
    if not isinstance(piece_count, int) or isinstance(piece_count, bool) or piece_count < 0:
        raise ValueError("piece_count must be a non-negative integer")
    if isinstance(distribution, bool):
        raise ValueError("Piece count must be an integer, not a boolean")
    if distribution == "all":
        return list(range(piece_count))
    if distribution == "none":
        return []
    if distribution == "even":
        return list(range(0, piece_count, 2))
    if distribution == "quarter":
        return list(range(1, piece_count, 4))
    if isinstance(distribution, int):
        if distribution < 0 or distribution > piece_count:
            raise ValueError(
                f"Piece count must be between 0 and {piece_count}, got {distribution}"
            )
        return list(range(distribution))
    if isinstance(distribution, list):
        if any(not isinstance(index, int) or isinstance(index, bool) for index in distribution):
            raise ValueError("Piece indices must be integers")
        if len(set(distribution)) != len(distribution):
            raise ValueError("Piece indices must not contain duplicates")
        if any(index < 0 or index >= piece_count for index in distribution):
            raise ValueError(f"Piece indices must be between 0 and {piece_count - 1}")
        return sorted(distribution)
    raise ValueError(
        f"Unsupported piece distribution {distribution!r}; expected all, none, "
        "even, quarter, an integer count, or a list of piece indices"
    )


def prepare_from_config(
    config_path: str | Path,
    storage_root: str | Path | None = None,
    download_root: str | Path = DOWNLOAD_ROOT,
    *,
    reset: bool = False,
    reset_peer_files: set[tuple[str, str]] | None = None,
    only_peer_files: set[tuple[str, str]] | None = None,
) -> None:
    config_file = resolve_project_path(config_path)
    resolved_storage_root = resolve_storage_root(storage_root)
    resolved_download_root = Path(download_root).expanduser()
    if not resolved_download_root.is_absolute():
        resolved_download_root = PROJECT_ROOT / resolved_download_root
    resolved_download_root = resolved_download_root.resolve()
    try:
        payload = json.loads(config_file.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config {config_file}: {exc}") from exc
    if not isinstance(payload, dict) or not isinstance(payload.get("files"), dict):
        raise ValueError("Config must contain a 'files' object")
    if not isinstance(payload.get("peers"), list):
        raise ValueError("Config must contain a 'peers' list")
    if not payload["files"]:
        raise ValueError("Config 'files' object must not be empty")

    loaded_files = {}
    for name, file_config in payload["files"].items():
        if not isinstance(name, str) or not name.strip():
            raise ValueError("File names in config must be non-empty strings")
        if not isinstance(file_config, dict):
            raise ValueError(f"File config {name!r} must be an object")
        try:
            source = file_config["source"]
            metadata_file = file_config["metadata"]
        except KeyError as exc:
            raise ValueError(f"File config {name!r} needs source and metadata paths") from exc
        if not isinstance(source, str) or not source.strip():
            raise ValueError(f"File config {name!r} has an invalid source path")
        if not isinstance(metadata_file, str) or not metadata_file.strip():
            raise ValueError(f"File config {name!r} has an invalid metadata path")
        source_path = (config_file.parent / source).resolve()
        metadata_path = (config_file.parent / metadata_file).resolve()
        if not source_path.is_file():
            raise FileNotFoundError(f"Source file not found: {source_path}")
        if not metadata_path.is_file():
            raise FileNotFoundError(
                f"Metadata file not found for {name!r}: {metadata_path}"
            )
        try:
            metadata = load_metadata(metadata_path)
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise ValueError(f"Could not load metadata for {name!r}: {exc}") from exc
        safe_filename = Path(metadata.file_name.replace("\\", "/")).name
        if not safe_filename or safe_filename in {".", ".."}:
            raise ValueError(f"Metadata for {name!r} has an invalid file name")
        loaded_files[name] = {
            "source": source_path,
            "metadata": metadata,
            "file_id": calculate_file_id(metadata),
            "safe_filename": safe_filename,
        }

    assignments: dict[str, dict[str, tuple[object, list[int]]]] = {}
    for peer_index, peer in enumerate(payload["peers"]):
        if not isinstance(peer, dict):
            raise ValueError(f"Peer assignment at index {peer_index} must be an object")
        peer_id = peer.get("peer_id")
        peer_files = peer.get("files")
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValueError(f"Peer assignment at index {peer_index} needs a peer_id")
        if (
            peer_id != peer_id.strip()
            or peer_id in {".", ".."}
            or "\x00" in peer_id
            or any(char in peer_id for char in ("/", "\\"))
        ):
            raise ValueError(f"Peer ID is not a safe directory name: {peer_id!r}")
        if not isinstance(peer_files, dict) or not peer_files:
            raise ValueError(f"Peer {peer_id!r} must have a non-empty 'files' object")
        assigned_files = assignments.setdefault(peer_id, {})
        for file_name, distribution in peer_files.items():
            if file_name not in loaded_files:
                raise ValueError(
                    f"Peer {peer_id!r} references unknown file {file_name!r}"
                )
            if file_name in assigned_files:
                raise ValueError(
                    f"Duplicate assignment for peer/file pair {peer_id!r}/"
                    f"{file_name!r}"
                )
            metadata = loaded_files[file_name]["metadata"]
            indices = _piece_indices(distribution, metadata.piece_count)
            assigned_files[file_name] = (distribution, indices)
    if not assignments:
        raise ValueError("Config 'peers' list must contain at least one assignment")

    reset_peer_files = reset_peer_files or set()
    selected_peer_files = only_peer_files or {
        (peer_id, file_name)
        for peer_id, peer_files in assignments.items()
        for file_name in peer_files
    }
    configured_peer_files = {
        (peer_id, file_name)
        for peer_id, peer_files in assignments.items()
        for file_name in peer_files
    }
    unknown_pairs = selected_peer_files - configured_peer_files
    if unknown_pairs:
        raise ValueError(f"Requested preparation scope is not configured: {sorted(unknown_pairs)}")
    if reset_peer_files - selected_peer_files:
        raise ValueError("reset_peer_files must be contained in only_peer_files")

    if not reset:
        for peer_id, peer_files in assignments.items():
            for file_name, (_, indices) in peer_files.items():
                if (peer_id, file_name) not in selected_peer_files:
                    continue
                if (peer_id, file_name) in reset_peer_files:
                    continue
                file_id = loaded_files[file_name]["file_id"]
                target_dir = resolved_storage_root / peer_id / file_id
                if not target_dir.is_dir():
                    continue
                actual_indices = sorted(
                    int(path.stem.removeprefix("piece_"))
                    for path in target_dir.glob("piece_*.bin")
                    if path.stem.removeprefix("piece_").isdigit()
                )
                if actual_indices != indices:
                    raise FileExistsError(
                        f"Existing pieces for {peer_id}/{file_name} do not match "
                        "the requested distribution; rerun with --reset to replace "
                        "only configured peer/file storage"
                    )

    print("Preparing configured swarm data...")
    print(f"Storage root: {resolved_storage_root}")
    selected_files = {
        file_name for _, file_name in selected_peer_files
    }
    with tempfile.TemporaryDirectory(prefix="peertorrent-config-seed-") as temp_dir:
        staged_files = {}
        for file_index, file_name in enumerate(selected_files):
            spec = loaded_files[file_name]
            staged_files[file_name] = seed_source_file(
                source_path=spec["source"],
                metadata=spec["metadata"],
                peer_id=f"source-{file_index}",
                storage_root=temp_dir,
            )

        # All metadata/source validation is complete before configured storage is reset.
        for peer_id, peer_files in assignments.items():
            for file_name, (distribution, indices) in peer_files.items():
                if (peer_id, file_name) not in selected_peer_files:
                    continue
                spec = loaded_files[file_name]
                metadata = spec["metadata"]
                file_id = spec["file_id"]
                target_dir = resolved_storage_root / peer_id / file_id
                should_reset = reset or (peer_id, file_name) in reset_peer_files
                if should_reset and target_dir.exists():
                    shutil.rmtree(target_dir)
                target_dir.mkdir(parents=True, exist_ok=True)
                target = PieceStorage(
                    storage_dir=resolved_storage_root,
                    peer_id=peer_id,
                    file_id=file_id,
                )

                total_bytes = 0
                staged = staged_files[file_name]
                for index in indices:
                    data = staged.load_piece(index)
                    target.save_piece(index, data)
                    total_bytes += len(data)

                safe_filename = spec["safe_filename"]
                output_path = resolved_download_root / peer_id / safe_filename
                if should_reset and (output_path.is_file() or output_path.is_symlink()):
                    output_path.unlink()
                percentage = (
                    total_bytes / metadata.file_size * 100
                    if metadata.file_size
                    else 0.0
                )
                print(
                    f"[{file_name}] {peer_id} ({distribution}): "
                    f"{len(indices)}/{metadata.piece_count} pieces "
                    f"({total_bytes}/{metadata.file_size} bytes, {percentage:.2f}%)"
                )
    print("Configured swarms prepared successfully.\n")


def main() -> None:
    parser = argparse.ArgumentParser(description="Prepare PeerTorrent swarm data.")
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"JSON swarm configuration path (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=None,
        help=f"Canonical peer storage root (default: {DEFAULT_STORAGE_ROOT}).",
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset only configured peer/file stores and matching download outputs.",
    )
    args = parser.parse_args()
    prepare_from_config(args.config, storage_root=args.storage, reset=args.reset)


if __name__ == "__main__":
    main()
