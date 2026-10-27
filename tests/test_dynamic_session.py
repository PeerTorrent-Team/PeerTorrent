from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.peer.dynamic_session import DynamicPeerSession
from src.pieces.metadata_serializer import build_metadata, save_metadata


class FakePeer:
    def __init__(self, **kwargs) -> None:
        self.kwargs = kwargs
        self.file_id = kwargs["file_id"]
        self._tracker_client = SimpleNamespace(host=None, port=None)
        self.started = False
        self.stopped = False

    def start(self) -> None:
        self.started = True

    def stop(self) -> None:
        self.stopped = True

    def is_complete(self) -> bool:
        return False


def make_catalog(tmp_path: Path) -> Path:
    files = []
    for name, content in (("alpha", b"alpha bytes"), ("beta", b"beta bytes")):
        source = tmp_path / f"{name}.bin"
        source.write_bytes(content)
        metadata_path = tmp_path / f"{name}.json"
        save_metadata(build_metadata(str(source), piece_size=3), str(metadata_path))
        files.append({"name": name, "metadata": metadata_path.name})

    catalog_path = tmp_path / "catalog.json"
    catalog_path.write_text(json.dumps({"files": files}), encoding="utf-8")
    return catalog_path


def make_session(catalog: Path, tmp_path: Path) -> DynamicPeerSession:
    return DynamicPeerSession(
        peer_id="peer7",
        catalog_path=catalog,
        port=6887,
        storage_dir=tmp_path / "storage",
        peer_factory=FakePeer,
        switch_delay=0,
    )


def test_request_file_replaces_peer_for_new_swarm(tmp_path: Path) -> None:
    session = make_session(make_catalog(tmp_path), tmp_path)

    first = session.start("alpha")
    first_peer = session.peer
    second = session.request_file("beta")

    assert first.name == "alpha"
    assert first_peer.started
    assert first_peer.kwargs["peer_id"] == "peer7"
    assert second.name == "beta"
    assert first_peer.stopped
    assert session.peer.started
    assert session.peer.kwargs["peer_id"] == "peer7"
    assert session.peer.kwargs["port"] == 6887
    assert session.peer.file_id == second.file_id

    session.stop()
    assert session.peer is None


def test_unknown_file_does_not_stop_current_swarm(tmp_path: Path) -> None:
    session = make_session(make_catalog(tmp_path), tmp_path)
    session.start("alpha")
    current_peer = session.peer

    with pytest.raises(ValueError, match="not in the catalog"):
        session.request_file("does-not-exist")

    assert session.peer is current_peer
    assert not current_peer.stopped
    session.stop()


def test_requesting_current_file_does_not_restart_peer(tmp_path: Path) -> None:
    session = make_session(make_catalog(tmp_path), tmp_path)
    first = session.start("alpha")
    current_peer = session.peer

    again = session.request_file("alpha")

    assert again.file_id == first.file_id
    assert session.peer is current_peer
    assert not current_peer.stopped
    session.stop()