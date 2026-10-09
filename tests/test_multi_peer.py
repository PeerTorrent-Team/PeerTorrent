import hashlib

import pytest

from src.common.types import FileMetadata, PieceInfo
from src.peer.choking_manager import ChokingManager
from src.peer.download_manager import DownloadManager
from src.peer.peer import Peer
from src.peer.peer_state import PeerState
from src.peer.request_manager import RequestManager
from src.peer.scheduler import Scheduler
from src.peer.upload_manager import UploadManager
from src.pieces.piece_manager import PieceManager
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.selection.random_selector import RandomSelector
from src.selection.rarest_first import RarestFirstSelector
from src.selection.sequential_selector import SequentialSelector
from src.storage.piece_storage import PieceStorage


class FakeConnection:
    def __init__(self, *, handshake_complete=True, handshake_sent=True):
        self.handshake_complete = handshake_complete
        self.handshake_sent = handshake_sent
        self.sent_messages = []
        self.closed = False

    def send_message(self, message):
        self.sent_messages.append(message)

    def close(self):
        self.closed = True


def make_metadata(parts: list[bytes]) -> FileMetadata:
    pieces = tuple(
        PieceInfo(
            index=index,
            hash=hashlib.sha256(part).hexdigest(),
            size=len(part),
        )
        for index, part in enumerate(parts)
    )
    file_size = sum(len(part) for part in parts)
    return FileMetadata(
        file_name="shared.bin",
        file_size=file_size,
        piece_size=max(len(part) for part in parts),
        piece_count=len(parts),
        pieces=pieces,
    )


def make_peer(tmp_path, parts=(b"hello", b"world")):
    storage = PieceStorage(tmp_path / "storage", peer_id="local")
    metadata = make_metadata(list(parts))
    manager = PieceManager(metadata, storage)
    return Peer(
        peer_id="local",
        file_id="file-id",
        piece_manager=manager,
        host="127.0.0.1",
        port=6882,
        storage=storage,
    )


def test_sequential_selector_chooses_lowest_available_missing_piece():
    selector = SequentialSelector()

    assert selector.select_piece([5, 2, 1], {1: 0, 2: 3, 5: 1}) == 2
    assert selector.select_piece([1, 2], {1: 0, 2: 0}) is None


def test_random_selector_only_returns_available_missing_piece():
    selector = RandomSelector()

    for _ in range(30):
        assert selector.select_piece([1, 2, 3], {1: 0, 2: 4, 3: 0}) == 2

    assert selector.select_piece([1, 2], {1: 0, 2: 0}) is None


def test_rarest_first_selector_chooses_least_available_piece():
    selector = RarestFirstSelector()

    assert selector.select_piece([0, 1, 2], {0: 5, 1: 1, 2: 3}) == 1
    assert selector.select_piece([0, 1], {0: 0, 1: 0}) is None
    assert selector.select_piece([], {}) is None


def test_peer_state_tracks_owned_requested_and_missing_pieces():
    state = PeerState(total_pieces=3)

    assert state.get_missing_pieces() == [0, 1, 2]
    state.mark_requested(1)
    assert state.is_requested(1)
    state.add_piece(1)
    assert state.has_piece(1)
    assert not state.is_requested(1)
    assert state.get_owned_pieces() == [1]
    assert state.get_missing_pieces() == [0, 2]
    assert not state.is_complete()

    state.add_piece(0)
    state.add_piece(2)
    assert state.is_complete()


def test_peer_state_tracks_remote_availability_and_cleans_removed_peer():
    state = PeerState(total_pieces=4)
    state.add_connected_peer("remote")
    state.update_peer_pieces("remote", [1, 3])
    state.set_interested("remote", True)
    state.set_choked("remote", False)

    assert state.get_peer_pieces("remote") == {1, 3}
    assert state.get_interested_peers() == ["remote"]
    assert not state.is_choked("remote")

    state.remove_peer("remote")
    assert "remote" not in state.get_connected_peers()
    assert state.get_peer_pieces("remote") == set()
    assert state.get_interested_peers() == []


def test_peer_state_rejects_invalid_piece_indices():
    state = PeerState(total_pieces=2)
    with pytest.raises(TypeError):
        state.add_piece(True)
    with pytest.raises(IndexError):
        state.add_piece(2)
    with pytest.raises(IndexError):
        state.mark_requested(-1)


def test_scheduler_skips_choked_disconnected_and_already_requested_pieces():
    state = PeerState(total_pieces=4)
    state.add_connected_peer("peer-a")
    state.add_connected_peer("peer-b")
    state.update_peer_pieces("peer-a", {0, 1})
    state.update_peer_pieces("peer-b", {1, 2})
    state.set_choked("peer-a", False)
    # peer-b remains choked; piece 2 must not be selected from it.

    scheduler = Scheduler(state, SequentialSelector())
    assert scheduler.schedule() == ("peer-a", 0)

    state.mark_requested(0)
    assert scheduler.schedule() == ("peer-a", 1)

    state.mark_requested(1)
    assert scheduler.schedule() is None


def test_scheduler_round_robins_between_peers_with_the_same_piece():
    state = PeerState(total_pieces=1)
    for peer_id in ("peer-a", "peer-b"):
        state.add_connected_peer(peer_id)
        state.update_peer_pieces(peer_id, {0})
        state.set_choked(peer_id, False)

    scheduler = Scheduler(state, SequentialSelector())
    first = scheduler.schedule()
    second = scheduler.schedule()

    assert first == ("peer-a", 0)
    assert second == ("peer-b", 0)


def test_request_manager_deduplicates_completes_and_expires_requests():
    manager = RequestManager(timeout=1.0)
    assert manager.add(2, "peer-a")
    assert not manager.add(2, "peer-b")
    assert manager.count() == 1
    assert manager.get(2).peer_id == "peer-a"
    assert manager.for_peer("peer-a")[0].piece_index == 2

    expired = manager.expire(now=manager.get(2).requested_at + 2)
    assert [request.piece_index for request in expired] == [2]
    assert manager.count() == 0
    assert manager.complete(2) is None


def test_download_manager_verifies_and_stores_valid_piece(tmp_path):
    data = b"good piece"
    storage = PieceStorage(tmp_path / "storage")
    manager = PieceManager(make_metadata([data]), storage)
    state = PeerState(total_pieces=1)
    requests = RequestManager(timeout=10)
    requests.add(0, "peer-a")
    state.mark_requested(0)
    downloader = DownloadManager(manager, storage, state, requests)

    valid = downloader.handle_piece(
        "peer-a",
        Message(MessageType.PIECE, {"piece_index": 0, "data": data}),
    )

    assert valid
    assert manager.has_piece(0)
    assert storage.load_piece(0) == data
    assert state.has_piece(0)
    assert not state.is_requested(0)
    assert requests.count() == 0


def test_download_manager_rejects_wrong_peer_or_corrupt_piece(tmp_path):
    expected = b"correct"
    storage = PieceStorage(tmp_path / "storage")
    manager = PieceManager(make_metadata([expected]), storage)
    state = PeerState(total_pieces=1)
    requests = RequestManager(timeout=10)
    downloader = DownloadManager(manager, storage, state, requests)

    requests.add(0, "peer-a")
    state.mark_requested(0)
    wrong_peer_result = downloader.handle_piece(
        "peer-b",
        {"piece_index": 0, "data": expected},
    )
    assert not wrong_peer_result
    assert requests.count() == 1

    corrupt = b"corrupt"
    corrupt_result = downloader.handle_piece(
        "peer-a",
        {"piece_index": 0, "data": corrupt},
    )
    assert not corrupt_result
    assert not manager.has_piece(0)
    assert not storage.has_piece(0)
    assert requests.count() == 0
    assert not state.is_requested(0)


def test_upload_manager_sends_piece_only_when_unchoked_and_owned(tmp_path):
    data = b"available"
    storage = PieceStorage(tmp_path / "storage")
    storage.save_piece(0, data)
    state = PeerState(total_pieces=1)
    state.add_piece(0)
    state.add_connected_peer("remote")
    state.set_choking("remote", False)
    connection = FakeConnection()
    uploader = UploadManager(storage, state)

    sent = uploader.handle_request("remote", connection, 0)

    assert sent == len(data)
    assert connection.sent_messages[-1].type is MessageType.PIECE
    assert connection.sent_messages[-1].payload == {"piece_index": 0, "data": data}
    assert uploader._uploads == {}

    state.set_choking("remote", True)
    assert uploader.handle_request("remote", connection, 0) == 0


def test_choking_manager_unchokes_top_contributor_and_optimistic_peer():
    state = PeerState(total_pieces=1)
    messages = []
    for peer_id in ("peer-a", "peer-b", "peer-c"):
        state.add_connected_peer(peer_id)
        state.set_interested(peer_id, True)

    downloaded = {"peer-a": 100, "peer-b": 50, "peer-c": 10}
    manager = ChokingManager(
        state,
        send_message=lambda peer_id, kind: messages.append((peer_id, kind)),
        bytes_downloaded_from_peer=lambda peer_id: downloaded[peer_id],
        max_unchoked=2,
    )

    manager.rebalance()

    assert not state.is_choking("peer-a")
    assert not state.is_choking("peer-b")
    assert state.is_choking("peer-c")
    assert set(messages) == {("peer-a", "UNCHOKE"), ("peer-b", "UNCHOKE")}


def test_peer_handshake_bitfield_and_scheduler_flow(tmp_path):
    peer = make_peer(tmp_path, parts=(b"hello", b"world"))
    peer._running = True
    connection = FakeConnection()
    peer.add_connection("remote", connection)

    peer.handle_message(
        "remote",
        Message(MessageType.BITFIELD, {"pieces": [1, 0]}),
    )
    assert peer.get_state().get_peer_pieces("remote") == {0}
    assert connection.sent_messages[-1].type is MessageType.INTERESTED

    peer.handle_message("remote", Message(MessageType.UNCHOKE, {}))
    assert not peer.get_state().is_choked("remote")
    assert peer.schedule_next_request()
    assert connection.sent_messages[-1].type is MessageType.REQUEST
    assert connection.sent_messages[-1].payload == {"piece_index": 0}
    assert peer.get_state().is_requested(0)

    # Stop the local object without opening real sockets or worker threads.
    peer._running = False
    peer.remove_connection("remote")