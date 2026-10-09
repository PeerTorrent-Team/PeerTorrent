import pytest
from unittest.mock import Mock

from src.common.types import FileMetadata, PieceInfo
from src.pieces.piece_manager import PieceManager
from src.storage.piece_storage import PieceStorage

@pytest.fixture
def dummy_metadata():
    pieces = (
        PieceInfo(index=0, hash="a"*64, size=4),
        PieceInfo(index=1, hash="b"*64, size=4),
        PieceInfo(index=2, hash="c"*64, size=2),
    )
    return FileMetadata(
        file_name="test.bin",
        file_size=10,
        piece_size=4,
        piece_count=3,
        pieces=pieces,
    )

@pytest.fixture
def mock_storage():
    storage = Mock(spec=PieceStorage)
    storage.has_piece.return_value = False
    return storage

def test_piece_manager_initial_state(dummy_metadata, mock_storage):
    pm = PieceManager(dummy_metadata, mock_storage)

    assert pm.piece_count() == 3
    assert not pm.is_complete()
    assert pm.get_missing_pieces() == [0, 1, 2]

    for i in range(3):
        assert not pm.has_piece(i)
        piece = pm.get_piece(i)
        assert piece.index == i
        assert piece.size == dummy_metadata.pieces[i].size
        assert piece.expected_hash == dummy_metadata.pieces[i].hash
        assert piece.data is None
        assert not piece.is_complete

def test_piece_manager_mark_complete(dummy_metadata, mock_storage):
    pm = PieceManager(dummy_metadata, mock_storage)

    pm.mark_piece_complete(1)

    assert pm.has_piece(1)
    assert not pm.has_piece(0)
    assert not pm.has_piece(2)

    assert pm.get_missing_pieces() == [0, 2]
    assert not pm.is_complete()

    pm.mark_piece_complete(0)
    pm.mark_piece_complete(2)

    assert pm.is_complete()
    assert pm.get_missing_pieces() == []

def test_piece_manager_set_piece_data(dummy_metadata, mock_storage):
    pm = PieceManager(dummy_metadata, mock_storage)

    pm.set_piece_data(0, b"1234")
    piece = pm.get_piece(0)
    assert piece.data == b"1234"

    with pytest.raises(TypeError, match="piece data must be bytes"):
        pm.set_piece_data(0, "not bytes")

def test_piece_manager_invalid_indices(dummy_metadata, mock_storage):
    pm = PieceManager(dummy_metadata, mock_storage)

    with pytest.raises(IndexError, match="Piece index out of range"):
        pm.has_piece(3)

    with pytest.raises(IndexError, match="Piece index out of range"):
        pm.has_piece(-1)

    with pytest.raises(TypeError, match="piece index must be an integer"):
        pm.has_piece("0")

    with pytest.raises(TypeError, match="piece index must be an integer"):
        pm.has_piece(True)

def test_piece_manager_invalid_metadata(mock_storage):
    class BadMetaPieceCount:
        piece_count = 2
        pieces = (PieceInfo(index=0, hash="a"*64, size=4),)

    with pytest.raises(ValueError, match="metadata.piece_count does not match the number of pieces"):
        PieceManager(BadMetaPieceCount(), mock_storage)

    class BadMetaIndex:
        piece_count = 1
        pieces = (PieceInfo(index=1, hash="a"*64, size=4),)

    with pytest.raises(ValueError, match="Invalid piece index"):
        PieceManager(BadMetaIndex(), mock_storage)
