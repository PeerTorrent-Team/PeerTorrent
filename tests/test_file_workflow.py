from __future__ import annotations

from pathlib import Path

import pytest

from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import build_metadata
from src.pieces.piece_manager import PieceManager
from src.peer.peer import Peer
from src.storage.file_workflow import seed_source_file, verify_downloaded_file
from src.storage.piece_storage import PieceStorage


def _peer_storage(root: Path, peer_id: str, metadata) -> PieceStorage:
    return PieceStorage(
        storage_dir=root,
        peer_id=peer_id,
        file_id=calculate_file_id(metadata),
    )


def test_seed_source_file_prepares_all_verified_pieces(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    content = b"PeerTorrent seeding works across piece boundaries."
    source.write_bytes(content)
    metadata = build_metadata(str(source), piece_size=7)

    storage = seed_source_file(
        source,
        metadata,
        peer_id="seed1",
        storage_root=tmp_path / "peer_storage",
    )

    assert all(storage.has_piece(i) for i in range(metadata.piece_count))
    assert b"".join(storage.load_piece(i) for i in range(metadata.piece_count)) == content


def test_seed_source_file_rejects_mismatched_piece_without_partial_seed(
    tmp_path: Path,
) -> None:
    expected = tmp_path / "expected.bin"
    wrong_source = tmp_path / "wrong.bin"
    # The first two pieces match; a later piece fails validation.
    expected.write_bytes(b"prefix--good")
    wrong_source.write_bytes(b"prefix--evil")
    metadata = build_metadata(str(expected), piece_size=4)
    storage_root = tmp_path / "peer_storage"

    with pytest.raises(ValueError, match="does not match metainfo hash"):
        seed_source_file(
            wrong_source,
            metadata,
            peer_id="seed1",
            storage_root=storage_root,
        )

    permanent_storage = _peer_storage(storage_root, "seed1", metadata)
    assert not any(
        permanent_storage.has_piece(i) for i in range(metadata.piece_count)
    )


def test_seed_source_file_rejects_wrong_whole_file_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"content with valid piece hashes")
    generated = build_metadata(str(source), piece_size=5)
    # Preserve the valid per-piece hashes but deliberately corrupt the file hash.
    from src.common.types import FileMetadata

    metadata = FileMetadata(
        file_name=generated.file_name,
        file_size=generated.file_size,
        piece_size=generated.piece_size,
        piece_count=generated.piece_count,
        pieces=generated.pieces,
        file_hash="0" * 64,
    )

    with pytest.raises(ValueError, match="Source file hash does not match metainfo"):
        seed_source_file(
            source,
            metadata,
            peer_id="seed1",
            storage_root=tmp_path / "peer_storage",
        )


def test_verify_downloaded_file_reconstructs_and_checks_hash(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    content = b"downloaded bytes are reconstructed in exact order"
    source.write_bytes(content)
    metadata = build_metadata(str(source), piece_size=6)
    storage = seed_source_file(
        source,
        metadata,
        peer_id="peer2",
        storage_root=tmp_path / "peer_storage",
    )

    output = verify_downloaded_file(
        metadata,
        storage,
        tmp_path / "downloads" / "restored.bin",
    )

    assert output.read_bytes() == content


def test_verify_downloaded_file_rejects_corrupt_piece_and_preserves_old_output(
    tmp_path: Path,
) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"correct content")
    metadata = build_metadata(str(source), piece_size=4)
    storage = seed_source_file(
        source,
        metadata,
        peer_id="peer2",
        storage_root=tmp_path / "peer_storage",
    )
    storage.save_piece(0, b"evil")

    output = tmp_path / "downloads" / "restored.bin"
    output.parent.mkdir(parents=True)
    output.write_bytes(b"keep the previous output")

    with pytest.raises(ValueError, match="Piece 0 failed SHA-256 verification"):
        verify_downloaded_file(metadata, storage, output)

    assert output.read_bytes() == b"keep the previous output"


def test_verify_downloaded_file_reports_missing_piece(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"piece that will be missing")
    metadata = build_metadata(str(source), piece_size=5)
    empty_storage = _peer_storage(tmp_path / "empty_storage", "peer2", metadata)

    with pytest.raises(FileNotFoundError, match="piece 0 is missing"):
        verify_downloaded_file(metadata, empty_storage, tmp_path / "out.bin")


def test_empty_file_can_be_seeded_and_verified(tmp_path: Path) -> None:
    source = tmp_path / "empty.bin"
    source.write_bytes(b"")
    metadata = build_metadata(str(source), piece_size=8)
    storage = seed_source_file(
        source,
        metadata,
        peer_id="seed1",
        storage_root=tmp_path / "peer_storage",
    )

    output = verify_downloaded_file(metadata, storage, tmp_path / "empty-out.bin")

    assert metadata.piece_count == 0
    assert output.read_bytes() == b""


def test_seeded_storage_is_ready_for_peer_startup(tmp_path: Path) -> None:
    source = tmp_path / "source.bin"
    source.write_bytes(b"seed startup integration")
    metadata = build_metadata(str(source), piece_size=5)
    storage = seed_source_file(
        source,
        metadata,
        peer_id="seed1",
        storage_root=tmp_path / "peer_storage",
    )
    piece_manager = PieceManager(metadata, storage)
    peer = Peer(
        peer_id="seed1",
        file_id=calculate_file_id(metadata),
        piece_manager=piece_manager,
        port=6881,
        storage=storage,
    )

    assert peer.is_complete()
    assert peer.create_bitfield().payload["pieces"] == [1] * metadata.piece_count
