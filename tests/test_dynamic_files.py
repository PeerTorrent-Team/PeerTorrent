from __future__ import annotations

import json
from pathlib import Path

import pytest

from scripts.prepare_swarm_data import _piece_indices, prepare_from_config
from src.common.types import FileMetadata
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import build_metadata, save_metadata
from src.storage.file_catalog import FileCatalog
from src.storage.piece_storage import PieceStorage

PROJECT_ROOT = Path(__file__).resolve().parents[1]


def test_file_catalog_resolves_metadata_and_canonical_file_id(tmp_path: Path) -> None:
    source = tmp_path / "sample.bin"
    source.write_bytes(b"catalog content")
    metadata = build_metadata(str(source), piece_size=4)
    metadata_path = tmp_path / "sample.json"
    save_metadata(metadata, str(metadata_path))
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(
        json.dumps({"files": [{"name": "sample", "metadata": "sample.json"}]}),
        encoding="utf-8",
    )

    entry = FileCatalog(catalog_path).resolve("sample")

    assert entry.metadata == metadata
    assert entry.metadata_path == metadata_path.resolve()
    assert entry.file_id == calculate_file_id(metadata)


def test_file_catalog_rejects_unknown_name(tmp_path: Path) -> None:
    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text('{"files": []}', encoding="utf-8")

    with pytest.raises(ValueError, match="not in the catalog"):
        FileCatalog(catalog_path).resolve("missing")


def _small_file(config_dir: Path, alias: str, content: bytes) -> tuple[dict, FileMetadata]:
    source_dir = config_dir.parent / "input"
    metadata_dir = config_dir.parent / "metadata"
    source_dir.mkdir(exist_ok=True)
    metadata_dir.mkdir(exist_ok=True)
    source = source_dir / f"{alias}.bin"
    source.write_bytes(content)
    metadata = build_metadata(str(source), piece_size=2)
    metadata_path = metadata_dir / f"{alias}.json"
    save_metadata(metadata, str(metadata_path))
    return (
        {
            "source": f"../input/{alias}.bin",
            "metadata": f"../metadata/{alias}.json",
        },
        metadata,
    )


def test_project_config_has_eleven_peer_assignments() -> None:
    config_path = PROJECT_ROOT / "configs" / "swarm_config.json"
    payload = json.loads(config_path.read_text(encoding="utf-8"))
    peers = {peer["peer_id"]: peer["files"] for peer in payload["peers"]}

    assert set(peers) == {f"peer{index}" for index in range(1, 12)}
    assert len(peers) == 11
    assert peers["peer1"] == {"file_20mb": "all"}
    assert peers["peer2"] == {"file_50mb": "all"}
    assert peers["peer3"] == {"video_mp4": "all"}
    assert peers["peer4"] == {"file_20mb": "even"}
    assert peers["peer5"] == {"file_50mb": "even"}
    assert peers["peer6"] == {"video_mp4": "even"}
    assert peers["peer7"] == {
        "file_20mb": "all",
        "file_50mb": "all",
        "video_mp4": "all",
    }
    assert peers["peer8"] == {
        "file_20mb": "none",
        "file_50mb": "none",
        "video_mp4": "none",
    }
    assert peers["peer9"] == peers["peer8"]
    assert peers["peer10"] == peers["peer8"]
    assert peers["peer11"] == peers["peer8"]


def test_project_assignment_matrix_prepares_all_eleven_peers_and_three_files(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    file_configs = {}
    metadata_by_alias = {}
    for alias, content in (
        ("file_20mb", b"abcdefghijkl"),
        ("file_50mb", b"mnopqrstuvwx"),
        ("video_mp4", b"0123456789ab"),
    ):
        file_configs[alias], metadata_by_alias[alias] = _small_file(
            config_dir, alias, content
        )
    project_payload = json.loads(
        (PROJECT_ROOT / "configs" / "swarm_config.json").read_text(
            encoding="utf-8"
        )
    )
    peers = project_payload["peers"]
    config_path = config_dir / "swarm.json"
    config_path.write_text(
        json.dumps({"files": file_configs, "peers": peers}),
        encoding="utf-8",
    )
    storage_root = tmp_path / "storage"

    prepare_from_config(config_path, storage_root, tmp_path / "downloads")

    for peer_config in peers:
        for alias, distribution in peer_config["files"].items():
            metadata = metadata_by_alias[alias]
            storage = PieceStorage(
                storage_root,
                peer_id=peer_config["peer_id"],
                file_id=calculate_file_id(metadata),
            )
            expected = _piece_indices(distribution, metadata.piece_count)
            actual = [
                index for index in range(metadata.piece_count) if storage.has_piece(index)
            ]
            assert actual == expected

    assert len(peers) == 11
    for alias, metadata in metadata_by_alias.items():
        file_id = calculate_file_id(metadata)
        peer7_store = PieceStorage(storage_root, peer_id="peer7", file_id=file_id)
        assert all(peer7_store.has_piece(index) for index in range(metadata.piece_count))
        for peer_id in ("peer8", "peer9", "peer10", "peer11"):
            empty_store = PieceStorage(storage_root, peer_id=peer_id, file_id=file_id)
            assert not any(
                empty_store.has_piece(index) for index in range(metadata.piece_count)
            )


def test_configurable_piece_preparation_supports_full_partial_and_empty(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    file_config, metadata = _small_file(config_dir, "sample", b"abcdefghijkl")
    config_path = tmp_path / "configs" / "swarm.json"
    config_path.write_text(
        json.dumps(
            {
                "files": {"sample": file_config},
                "peers": [
                    {"peer_id": "complete", "files": {"sample": "all"}},
                    {"peer_id": "partial", "files": {"sample": [0, 2, 4]}},
                    {"peer_id": "empty", "files": {"sample": "none"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    storage_root = tmp_path / "peer_storage"

    prepare_from_config(
        config_path,
        storage_root=storage_root,
        download_root=tmp_path / "downloads",
    )

    file_id = calculate_file_id(metadata)
    complete = PieceStorage(storage_root, peer_id="complete", file_id=file_id)
    partial = PieceStorage(storage_root, peer_id="partial", file_id=file_id)
    empty = PieceStorage(storage_root, peer_id="empty", file_id=file_id)
    assert [complete.load_piece(index) for index in range(6)] == [
        b"ab", b"cd", b"ef", b"gh", b"ij", b"kl"
    ]
    assert partial.load_piece(0) == b"ab"
    assert partial.load_piece(2) == b"ef"
    assert partial.load_piece(4) == b"ij"
    assert not partial.has_piece(1)
    assert not any(empty.has_piece(index) for index in range(6))


def test_one_peer_can_store_multiple_files_in_one_config(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    first_config, first_metadata = _small_file(config_dir, "first", b"first file")
    second_config, second_metadata = _small_file(config_dir, "second", b"second file")
    config_path = config_dir / "swarm.json"
    config_path.write_text(
        json.dumps(
            {
                "files": {"first": first_config, "second": second_config},
                "peers": [
                    {"peer_id": "peer7", "files": {"first": "all"}},
                    {"peer_id": "peer7", "files": {"second": "all"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    storage_root = tmp_path / "storage"

    prepare_from_config(config_path, storage_root, tmp_path / "downloads")

    for metadata in (first_metadata, second_metadata):
        storage = PieceStorage(
            storage_root,
            peer_id="peer7",
            file_id=calculate_file_id(metadata),
        )
        assert all(storage.has_piece(index) for index in range(metadata.piece_count))


def test_explicit_reset_is_scoped_to_selected_peer_file_pair(tmp_path: Path) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    first_config, first_metadata = _small_file(config_dir, "first", b"first file")
    second_config, second_metadata = _small_file(config_dir, "second", b"second file")
    config_path = config_dir / "swarm.json"
    config_path.write_text(
        json.dumps(
            {
                "files": {"first": first_config, "second": second_config},
                "peers": [
                    {"peer_id": "peer7", "files": {"first": "all", "second": "all"}}
                ],
            }
        ),
        encoding="utf-8",
    )
    storage_root = tmp_path / "storage"
    download_root = tmp_path / "downloads"
    prepare_from_config(config_path, storage_root, download_root)

    first_id = calculate_file_id(first_metadata)
    second_id = calculate_file_id(second_metadata)
    first_store = PieceStorage(storage_root, peer_id="peer7", file_id=first_id)
    second_store = PieceStorage(storage_root, peer_id="peer7", file_id=second_id)
    first_store.save_piece(0, b"stale")
    first_output = download_root / "peer7" / first_metadata.file_name
    second_output = download_root / "peer7" / second_metadata.file_name
    first_output.parent.mkdir(parents=True, exist_ok=True)
    first_output.write_bytes(b"stale output")
    second_output.write_bytes(b"preserve output")

    prepare_from_config(
        config_path,
        storage_root,
        download_root,
        reset_peer_files={("peer7", "first")},
    )

    assert first_store.load_piece(0) == b"fi"
    assert second_store.load_piece(0) == b"se"
    assert not first_output.exists()
    assert second_output.read_bytes() == b"preserve output"


def test_sequential_workloads_reinitialize_only_their_configured_pairs(
    tmp_path: Path,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    first_config, first_metadata = _small_file(config_dir, "first", b"first file")
    second_config, second_metadata = _small_file(config_dir, "second", b"second file")
    config_path = config_dir / "swarm.json"
    config_path.write_text(
        json.dumps(
            {
                "files": {"first": first_config, "second": second_config},
                "peers": [
                    {"peer_id": "peer1", "files": {"first": "all"}},
                    {"peer_id": "peer2", "files": {"second": "none"}},
                ],
            }
        ),
        encoding="utf-8",
    )
    storage_root = tmp_path / "storage"
    download_root = tmp_path / "downloads"
    first_pair = {("peer1", "first")}
    second_pair = {("peer2", "second")}

    prepare_from_config(
        config_path,
        storage_root,
        download_root,
        reset_peer_files=first_pair,
        only_peer_files=first_pair,
    )
    first_store = PieceStorage(
        storage_root,
        peer_id="peer1",
        file_id=calculate_file_id(first_metadata),
    )
    first_store.save_piece(first_metadata.piece_count, b"downloaded in workload one")

    prepare_from_config(
        config_path,
        storage_root,
        download_root,
        reset_peer_files=second_pair,
        only_peer_files=second_pair,
    )

    second_store = PieceStorage(
        storage_root,
        peer_id="peer2",
        file_id=calculate_file_id(second_metadata),
    )
    assert not any(
        second_store.has_piece(index)
        for index in range(second_metadata.piece_count)
    )
    assert first_store.has_piece(first_metadata.piece_count)


@pytest.mark.parametrize(
    ("peers", "message"),
    [
        (
            [
                {"peer_id": "peer7", "files": {"sample": "all"}},
                {"peer_id": "peer7", "files": {"sample": "none"}},
            ],
            "Duplicate assignment for peer/file pair",
        ),
        (
            [{"peer_id": "peer7", "files": {"missing": "all"}}],
            "unknown file 'missing'",
        ),
    ],
)
def test_duplicate_or_unknown_assignments_are_rejected(
    tmp_path: Path,
    peers: list[dict[str, object]],
    message: str,
) -> None:
    config_dir = tmp_path / "configs"
    config_dir.mkdir()
    file_config, _ = _small_file(config_dir, "sample", b"sample content")
    config_path = config_dir / "swarm.json"
    config_path.write_text(
        json.dumps({"files": {"sample": file_config}, "peers": peers}),
        encoding="utf-8",
    )

    with pytest.raises(ValueError, match=message):
        prepare_from_config(config_path, tmp_path / "storage", tmp_path / "downloads")


@pytest.mark.parametrize(
    ("distribution", "expected"),
    [
        ("all", [0, 1, 2, 3, 4, 5]),
        ("none", []),
        ("even", [0, 2, 4]),
        ("quarter", [1, 5]),
        (3, [0, 1, 2]),
        ([0, 2, 5], [0, 2, 5]),
    ],
)
def test_piece_indices(distribution, expected) -> None:
    assert _piece_indices(distribution, 6) == expected


@pytest.mark.parametrize(
    ("distribution", "message"),
    [
        (-1, "between 0 and 6"),
        (7, "between 0 and 6"),
        ([0, 6], "between 0 and 5"),
        ([1, 1], "duplicates"),
        (True, "not a boolean"),
        ("random", "Unsupported piece distribution"),
    ],
)
def test_piece_indices_reject_invalid_assignments(distribution, message) -> None:
    with pytest.raises(ValueError, match=message):
        _piece_indices(distribution, 6)