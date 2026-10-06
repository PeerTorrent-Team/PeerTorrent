import pytest
from pathlib import Path

from src.common.types import FileMetadata, PieceInfo
from src.pieces.metadata_serializer import build_metadata, save_metadata, load_metadata
from src.pieces.metadata import calculate_file_id
from src.pieces.hash_utils import calculate_hash

def test_build_metadata_valid(tmp_path: Path):
    file_path = tmp_path / "test_file.txt"
    data = b"0123456789"
    file_path.write_bytes(data)

    piece_size = 4
    metadata = build_metadata(str(file_path), piece_size)

    assert metadata.file_name == "test_file.txt"
    assert metadata.file_size == 10
    assert metadata.piece_size == 4
    assert metadata.piece_count == 3

    assert len(metadata.pieces) == 3

    assert metadata.pieces[0].index == 0
    assert metadata.pieces[0].size == 4
    assert metadata.pieces[0].hash == calculate_hash(b"0123")

    assert metadata.pieces[1].index == 1
    assert metadata.pieces[1].size == 4
    assert metadata.pieces[1].hash == calculate_hash(b"4567")

    assert metadata.pieces[2].index == 2
    assert metadata.pieces[2].size == 2
    assert metadata.pieces[2].hash == calculate_hash(b"89")


def test_build_metadata_invalid_piece_size(tmp_path: Path):
    file_path = tmp_path / "test.txt"
    file_path.write_bytes(b"test")

    with pytest.raises(ValueError, match="piece_size must be a positive integer"):
        build_metadata(str(file_path), 0)

    with pytest.raises(ValueError, match="piece_size must be a positive integer"):
        build_metadata(str(file_path), -1)

    with pytest.raises(ValueError, match="piece_size must be a positive integer"):
        build_metadata(str(file_path), True)


def test_build_metadata_file_not_found(tmp_path: Path):
    file_path = tmp_path / "missing.txt"
    with pytest.raises(FileNotFoundError):
        build_metadata(str(file_path), 1024)


def test_metadata_serialization(tmp_path: Path):
    file_path = tmp_path / "test_file.txt"
    file_path.write_bytes(b"hello world")
    metadata = build_metadata(str(file_path), 5)

    meta_file = tmp_path / "meta.json"
    save_metadata(metadata, str(meta_file))

    assert meta_file.exists()

    loaded_metadata = load_metadata(str(meta_file))

    assert loaded_metadata.file_name == metadata.file_name
    assert loaded_metadata.file_size == metadata.file_size
    assert loaded_metadata.piece_size == metadata.piece_size
    assert loaded_metadata.piece_count == metadata.piece_count

    assert len(loaded_metadata.pieces) == len(metadata.pieces)
    for p1, p2 in zip(loaded_metadata.pieces, metadata.pieces):
        assert p1.index == p2.index
        assert p1.size == p2.size
        assert p1.hash == p2.hash


def test_load_metadata_not_found(tmp_path: Path):
    meta_file = tmp_path / "nonexistent.json"
    with pytest.raises(FileNotFoundError):
        load_metadata(str(meta_file))


def test_calculate_file_id():
    pieces = (
        PieceInfo(index=0, hash="a"*64, size=4),
        PieceInfo(index=1, hash="b"*64, size=2),
    )
    metadata = FileMetadata(
        file_name="test.bin",
        file_size=6,
        piece_size=4,
        piece_count=2,
        pieces=pieces,
    )

    # 1. Deterministic
    file_id1 = calculate_file_id(metadata)
    file_id2 = calculate_file_id(metadata)
    assert file_id1 == file_id2

    # 2. 64-character hexadecimal result
    assert isinstance(file_id1, str)
    assert len(file_id1) == 64
    assert all(c in "0123456789abcdefABCDEF" for c in file_id1)

    # 3. Changing relevant metadata changes the file ID
    metadata2 = FileMetadata(
        file_name="test2.bin",
        file_size=6,
        piece_size=4,
        piece_count=2,
        pieces=pieces,
    )
    file_id3 = calculate_file_id(metadata2)
    assert file_id1 != file_id3


def test_file_metadata_validation():
    pieces = (
        PieceInfo(index=0, hash="a"*64, size=4),
        PieceInfo(index=1, hash="b"*64, size=2),
    )
    # Valid
    FileMetadata("t.txt", 6, 4, 2, pieces)

    # Empty file_name
    with pytest.raises(ValueError, match="file_name must be a non-empty string"):
        FileMetadata("", 6, 4, 2, pieces)

    # Invalid file_size
    with pytest.raises(ValueError, match="file_size must be non-negative"):
        FileMetadata("t.txt", -1, 4, 2, pieces)

    # Invalid piece_size
    with pytest.raises(ValueError, match="piece_size must be greater than 0"):
        FileMetadata("t.txt", 6, 0, 2, pieces)

    # Invalid piece_count
    with pytest.raises(ValueError, match="piece_count must be non-negative"):
        FileMetadata("t.txt", 6, 4, -1, pieces)

    # piece_count mismatch
    with pytest.raises(ValueError, match="piece_count does not match file_size and piece_size"):
        FileMetadata("t.txt", 6, 4, 3, pieces)

    # piece_count must match number of pieces
    with pytest.raises(ValueError, match="piece_count must match the number of pieces"):
        bad_pieces = (
            PieceInfo(index=0, hash="a"*64, size=2),
            PieceInfo(index=1, hash="b"*64, size=2),
            PieceInfo(index=2, hash="c"*64, size=2),
        )
        FileMetadata("t.txt", 6, 4, 2, bad_pieces)

    # total piece bytes mismatch
    with pytest.raises(ValueError, match="piece sizes do not match file_size"):
        bad_pieces = (
            PieceInfo(index=0, hash="a"*64, size=4),
            PieceInfo(index=1, hash="b"*64, size=1),
        )
        FileMetadata("t.txt", 6, 4, 2, bad_pieces)

    # invalid/non-sequential piece indices
    with pytest.raises(ValueError, match="pieces must have sequential indexes"):
        bad_pieces = (
            PieceInfo(index=1, hash="a"*64, size=4),
            PieceInfo(index=0, hash="b"*64, size=2),
        )
        FileMetadata("t.txt", 6, 4, 2, bad_pieces)

    # invalid piece sizes
    with pytest.raises(ValueError, match="piece size must be greater than 0"):
        bad_pieces = (
            PieceInfo(index=0, hash="a"*64, size=0),
            PieceInfo(index=1, hash="b"*64, size=6),
        )
        FileMetadata("t.txt", 6, 4, 2, bad_pieces)

    # piece size greater than piece_size
    with pytest.raises(ValueError, match="piece size cannot exceed piece_size"):
        bad_pieces = (
            PieceInfo(index=0, hash="a"*64, size=5),
            PieceInfo(index=1, hash="b"*64, size=1),
        )
        FileMetadata("t.txt", 6, 4, 2, bad_pieces)
