from __future__ import annotations

import shutil
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.storage.file_workflow import seed_source_file
from src.storage.piece_storage import PieceStorage

STORAGE_ROOT = PROJECT_ROOT / "data" / "peer_storage"
DOWNLOAD_ROOT = PROJECT_ROOT / "data" / "downloads"

# "even" means indices 0, 2, 4, ...
# "quarter" means indices 1, 5, 9, ... (index % 4 == 1)
# "none" means no initial pieces.
SWARMS = [
    {
        "name": "20MB swarm",
        "source": PROJECT_ROOT / "data/input_files/20MB_text_file.txt",
        "metadata": PROJECT_ROOT / "data/metadata/20MB_text_file.json",
        "seed": "peer 1",
        "partials": {
            "peer 2": "even",
            "peer 3": "quarter",
            "peer 4": "none",
        },
    },
    {
        "name": "50MB swarm",
        "source": PROJECT_ROOT / "data/input_files/50mb.txt",
        "metadata": PROJECT_ROOT / "data/metadata/50mb.json",
        "seed": "peer 5",
        "partials": {
            "peer 6": "even",
            "peer 7": "quarter",
            "peer 8": "none",
        },
    },
]


def prepare_swarm(swarm: dict) -> None:
    source_path = Path(swarm["source"])
    metadata_path = Path(swarm["metadata"])

    if not source_path.is_file():
        raise FileNotFoundError(f"Source file not found: {source_path}")
    if not metadata_path.is_file():
        raise FileNotFoundError(f"Metadata file not found: {metadata_path}")

    metadata = load_metadata(metadata_path)
    file_id = calculate_file_id(metadata)
    all_peers = [swarm["seed"], *swarm["partials"].keys()]

    # Reset existing piece storage and previous downloaded outputs for all peers in swarm
    safe_filename = Path(metadata.file_name.replace("\\", "/")).name
    for peer_id in all_peers:
        peer_storage_dir = STORAGE_ROOT / peer_id / file_id
        if peer_storage_dir.exists():
            shutil.rmtree(peer_storage_dir)

        download_peer_dir = DOWNLOAD_ROOT / peer_id
        download_peer_dir.mkdir(parents=True, exist_ok=True)
        downloaded_file = download_peer_dir / safe_filename
        if downloaded_file.exists():
            downloaded_file.unlink()

    # 1. Seed complete file to the seeder
    seed_peer = swarm["seed"]
    seed_source_file(
        source_path=source_path,
        metadata=metadata,
        peer_id=seed_peer,
        storage_root=STORAGE_ROOT,
    )
    seeder_storage = PieceStorage(
        storage_dir=STORAGE_ROOT,
        peer_id=seed_peer,
        file_id=file_id,
    )
    print(
        f"[{swarm['name']}] {seed_peer} (seed): "
        f"{metadata.piece_count}/{metadata.piece_count} pieces "
        f"({metadata.file_size}/{metadata.file_size} bytes, 100.00%)"
    )

    # 2. Populate partial peers from the seeder
    for peer_id, distribution in swarm["partials"].items():
        if distribution == "even":
            indices = [i for i in range(metadata.piece_count) if i % 2 == 0]
        elif distribution == "quarter":
            indices = [i for i in range(metadata.piece_count) if i % 4 == 1]
        elif distribution == "none":
            indices = []
        else:
            raise ValueError(f"Unknown distribution mode: {distribution}")

        peer_storage = PieceStorage(
            storage_dir=STORAGE_ROOT,
            peer_id=peer_id,
            file_id=file_id,
        )

        total_bytes = 0
        for idx in indices:
            data = seeder_storage.load_piece(idx)
            peer_storage.save_piece(idx, data)
            total_bytes += len(data)

        pct = (total_bytes / metadata.file_size * 100) if metadata.file_size > 0 else 0.0
        print(
            f"[{swarm['name']}] {peer_id} ({distribution}): "
            f"{len(indices)}/{metadata.piece_count} pieces "
            f"({total_bytes}/{metadata.file_size} bytes, {pct:.2f}%)"
        )


def prepare_all_swarms() -> None:
    print("Preparing swarm data and initializing peer storage...")
    for swarm in SWARMS:
        prepare_swarm(swarm)
    print("All swarms prepared successfully.\n")


def main() -> None:
    prepare_all_swarms()


if __name__ == "__main__":
    main()
