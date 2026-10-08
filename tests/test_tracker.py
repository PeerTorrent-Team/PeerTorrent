import threading
import time

import pytest

from src.common.types import PeerInfo
from src.tracker.peer_registry import PeerRegistry
from src.tracker.swarm_manager import SwarmManager
from src.tracker.tracker_client import TrackerClient
from src.tracker.tracker_main import TrackerRequestHandler, TrackerTCPServer
from src.tracker.tracker_server import TrackerServer


def peer(peer_id: str, port: int = 6881) -> PeerInfo:
    return PeerInfo(peer_id=peer_id, ip="127.0.0.1", port=port)


class FakeClock:
    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now

    def advance(self, seconds: float):
        self.now += seconds


def announce(
    peer_id="peer1",
    file_id="fileA",
    port=6881,
    left=100,
    uploaded=0,
    downloaded=0,
    is_seeder=False,
):
    return {
        "type": "ANNOUNCE",
        "peer_id": peer_id,
        "ip": "127.0.0.1",
        "port": port,
        "file_id": file_id,
        "left": left,
        "uploaded": uploaded,
        "downloaded": downloaded,
        "is_seeder": is_seeder,
    }


def make_tracker(peer_ttl=90, clock=None):
    registry = PeerRegistry(peer_ttl=peer_ttl, clock=clock or time.monotonic)
    return TrackerServer(registry, SwarmManager(registry))


# ------------------------- PeerRegistry -------------------------

def test_register_and_lookup():
    registry = PeerRegistry()
    p = peer("peer1")

    registry.register_peer(
        p, left=1000, uploaded=20, downloaded=50, is_seeder=False
    )

    assert registry.get_peer("peer1") == p
    assert registry.get_peers() == [p]


def test_register_updates_existing_peer():
    registry = PeerRegistry()

    registry.register_peer(
        peer("peer1", 6881),
        left=500,
        uploaded=10,
        downloaded=30,
        is_seeder=False,
    )
    registry.register_peer(
        peer("peer1", 6882),
        left=0,
        uploaded=40,
        downloaded=80,
        is_seeder=True,
    )

    assert registry.get_peer("peer1") == peer("peer1", 6882)
    assert len(registry.get_peers()) == 1

    record = registry.get_records()[0]
    assert (record.left, record.uploaded, record.downloaded, record.is_seeder) == (
        0,
        40,
        80,
        True,
    )


def test_remove_peer():
    registry = PeerRegistry()
    registry.register_peer(peer("peer1"))

    registry.remove_peer("peer1")

    assert registry.get_peer("peer1") is None
    assert registry.get_peers() == []


def test_remove_unknown_peer_is_safe():
    registry = PeerRegistry()
    registry.remove_peer("unknown")
    assert registry.get_peers() == []


def test_reap_stale_peers():
    clock = FakeClock()
    registry = PeerRegistry(peer_ttl=10, clock=clock)
    registry.register_peer(peer("peer1"))

    clock.advance(9)
    assert registry.reap_stale_peers() == []

    clock.advance(2)
    assert registry.reap_stale_peers() == ["peer1"]
    assert registry.get_peer("peer1") is None


def test_reregister_refreshes_last_seen():
    clock = FakeClock()
    registry = PeerRegistry(peer_ttl=10, clock=clock)
    registry.register_peer(peer("peer1"))

    clock.advance(8)
    registry.register_peer(peer("peer1", 6882))

    clock.advance(5)
    assert registry.reap_stale_peers() == []

    clock.advance(6)
    assert registry.reap_stale_peers() == ["peer1"]


# ------------------------- SwarmManager -------------------------

def test_add_and_get_peers():
    registry = PeerRegistry()
    swarm = SwarmManager(registry)
    p1, p2 = peer("peer1"), peer("peer2", 6882)

    registry.register_peer(p1)
    registry.register_peer(p2)
    swarm.add_peer("fileA", p1)
    swarm.add_peer("fileA", p2)

    assert {p.peer_id for p in swarm.get_peers("fileA")} == {"peer1", "peer2"}


def test_different_files_are_separate():
    registry = PeerRegistry()
    swarm = SwarmManager(registry)
    p1, p2 = peer("peer1"), peer("peer2", 6882)

    registry.register_peer(p1)
    registry.register_peer(p2)
    swarm.add_peer("fileA", p1)
    swarm.add_peer("fileB", p2)

    assert [p.peer_id for p in swarm.get_peers("fileA")] == ["peer1"]
    assert [p.peer_id for p in swarm.get_peers("fileB")] == ["peer2"]


def test_move_peer_between_files():
    registry = PeerRegistry()
    swarm = SwarmManager(registry)
    p = peer("peer1")

    registry.register_peer(p)
    swarm.add_peer("fileA", p)
    swarm.move_peer("fileA", "fileB", p)

    assert swarm.get_peers("fileA") == []
    assert swarm.get_peers("fileB") == [p]


def test_remove_peer_from_swarm():
    registry = PeerRegistry()
    swarm = SwarmManager(registry)
    p = peer("peer1")

    registry.register_peer(p)
    swarm.add_peer("fileA", p)
    swarm.remove_peer("fileA", "peer1")

    assert swarm.get_peers("fileA") == []


def test_stale_swarm_entry_is_cleaned():
    registry = PeerRegistry()
    swarm = SwarmManager(registry)
    swarm.add_peer("fileA", peer("peer1"))

    assert swarm.get_peers("fileA") == []
    assert swarm.get_peers("fileA") == []


# ------------------------- TrackerServer -------------------------

def test_announce_registers_peer():
    tracker = make_tracker()

    response = tracker.handle_request(announce("peer1"))

    assert response["ok"] is True
    assert response["type"] == "ANNOUNCE_RESPONSE"
    assert response["peers"] == []


def test_announce_returns_other_peers_in_same_swarm():
    tracker = make_tracker()
    tracker.handle_request(announce("peer1", port=6881))

    response = tracker.handle_request(announce("peer2", port=6882))

    assert response["peers"] == [
        {"peer_id": "peer1", "ip": "127.0.0.1", "port": 6881}
    ]


def test_announce_excludes_same_peer():
    tracker = make_tracker()
    response = tracker.handle_request(announce("peer1"))

    assert all(item["peer_id"] != "peer1" for item in response["peers"])


def test_announce_does_not_mix_files():
    tracker = make_tracker()
    tracker.handle_request(announce("peer1", file_id="fileA"))

    response = tracker.handle_request(announce("peer2", file_id="fileB"))

    assert response["peers"] == []


def test_reannounce_moves_peer_to_new_swarm():
    tracker = make_tracker()
    tracker.handle_request(announce("peer1", file_id="fileA"))
    tracker.handle_request(announce("peer2", file_id="fileB", port=6882))
    tracker.handle_request(announce("peer1", file_id="fileB"))

    response = tracker.handle_request(
        {"type": "GET_PEERS", "peer_id": "peer3", "file_id": "fileB"}
    )

    assert {item["peer_id"] for item in response["peers"]} == {"peer1", "peer2"}


def test_get_peers():
    tracker = make_tracker()
    tracker.handle_request(announce("peer1", port=6881))
    tracker.handle_request(announce("peer2", port=6882))

    response = tracker.handle_request(
        {"type": "GET_PEERS", "peer_id": "peer1", "file_id": "fileA"}
    )

    assert response == {
        "ok": True,
        "type": "GET_PEERS_RESPONSE",
        "peers": [{"peer_id": "peer2", "ip": "127.0.0.1", "port": 6882}],
    }


@pytest.mark.parametrize(
    ("bad_request", "field"),
    [
        ({"type": "ANNOUNCE", "peer_id": "peer1"}, "ip"),
        (
            {
                **announce("peer1"),
                "left": -1,
            },
            "left",
        ),
        ({"type": "GET_PEERS", "peer_id": "peer1"}, "file_id"),
    ],
)
def test_invalid_requests_are_rejected(bad_request, field):
    response = make_tracker().handle_request(bad_request)

    assert response["ok"] is False
    assert response["field"] == field


def test_unknown_request_type_is_rejected():
    assert make_tracker().handle_request({"type": "UNKNOWN"}) == {
        "ok": False,
        "error": "UNKNOWN_TYPE",
    }


def test_stats():
    tracker = make_tracker()
    tracker.handle_request(
        announce(
            "peer1",
            left=0,
            uploaded=100,
            downloaded=200,
            is_seeder=True,
        )
    )
    tracker.handle_request(
        announce(
            "peer2",
            port=6882,
            left=500,
            uploaded=10,
            downloaded=20,
            is_seeder=False,
        )
    )

    assert tracker.handle_request({"type": "STATS"}) == {
        "ok": True,
        "type": "STATS_RESPONSE",
        "peer_count": 2,
        "seeder_count": 1,
        "leecher_count": 1,
        "uploaded": 110,
        "downloaded": 220,
    }


def test_stale_peer_is_removed_from_tracker_swarm():
    clock = FakeClock()
    tracker = make_tracker(peer_ttl=10, clock=clock)
    tracker.handle_request(announce("peer1"))

    clock.advance(11)
    response = tracker.handle_request(
        {"type": "GET_PEERS", "peer_id": "peer2", "file_id": "fileA"}
    )

    assert response["peers"] == []


def test_peer_limit():
    tracker = make_tracker()
    for i in range(5):
        tracker.handle_request(announce(f"peer{i}", port=6881 + i))

    response = tracker.handle_request(
        {"type": "GET_PEERS", "peer_id": "requester", "file_id": "fileA"}
    )

    assert len(response["peers"]) == 3


# ---------------- TrackerClient + TCP integration ----------------

@pytest.fixture
def running_tracker():
    registry = PeerRegistry()
    tracker = TrackerServer(registry, SwarmManager(registry))

    class TestHandler(TrackerRequestHandler):
        tracker = None

    server = TrackerTCPServer(("127.0.0.1", 0), TestHandler, tracker)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()

    try:
        yield server.server_address
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


def test_tracker_client_end_to_end(running_tracker):
    host, port = running_tracker

    p1 = TrackerClient(
        host, port, "peer1", "127.0.0.1", 6881, "fileA"
    )
    p2 = TrackerClient(
        host, port, "peer2", "127.0.0.1", 6882, "fileA"
    )

    assert p1.announce(left=100, uploaded=0, downloaded=0, is_seeder=False) == []

    assert p2.announce(
        left=50, uploaded=0, downloaded=50, is_seeder=False
    ) == [
        {"peer_id": "peer1", "ip": "127.0.0.1", "port": 6881}
    ]

    assert p1.get_peers() == [
        {"peer_id": "peer2", "ip": "127.0.0.1", "port": 6882}
    ]