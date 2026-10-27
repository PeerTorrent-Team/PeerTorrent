"""Runtime file selection for a single PeerTorrent peer process.

A session has one active file swarm at a time. Switching files stops the
current network Peer and starts a new one for the requested file.
"""

from __future__ import annotations

import time
from pathlib import Path
from typing import Any, Callable

from src.common.constants import (
    DEFAULT_PEER_PORT,
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
)
from src.peer.peer import Peer
from src.pieces.piece_manager import PieceManager
from src.selection.selector_factory import create_selector
from src.storage.file_catalog import CatalogEntry, FileCatalog
from src.storage.paths import resolve_storage_root
from src.storage.piece_storage import PieceStorage


class DynamicPeerSession:
    """Manage dynamic file requests for one peer ID."""

    def __init__(
        self,
        *,
        peer_id: str,
        catalog_path: str | Path,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PEER_PORT,
        storage_dir: str | Path | None = None,
        tracker_host: str = DEFAULT_TRACKER_HOST,
        tracker_port: int = DEFAULT_TRACKER_PORT,
        strategy: str = "rarest-first",
        random_seed: int | None = None,
        upload_enabled: bool = True,
        peer_factory: Callable[..., Any] | None = None,
        switch_delay: float = 0.15,
    ) -> None:
        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValueError("peer_id must be a non-empty string")

        self.peer_id = peer_id
        self.catalog = FileCatalog(catalog_path)
        self.host = host
        self.port = port
        self.storage_dir = resolve_storage_root(storage_dir)
        self.tracker_host = tracker_host
        self.tracker_port = tracker_port
        self.strategy = strategy
        self.random_seed = random_seed
        self.upload_enabled = upload_enabled
        self._peer_factory = peer_factory or Peer
        self._switch_delay = max(0.0, switch_delay)
        self.peer: Any | None = None
        self.current_entry: CatalogEntry | None = None

    def _build_peer(self, entry: CatalogEntry) -> Any:
        storage = PieceStorage(
            storage_dir=self.storage_dir,
            peer_id=self.peer_id,
            file_id=entry.file_id,
        )
        piece_manager = PieceManager(entry.metadata, storage)
        peer = self._peer_factory(
            peer_id=self.peer_id,
            file_id=entry.file_id,
            piece_manager=piece_manager,
            host=self.host,
            port=self.port,
            storage=storage,
            selector=create_selector(self.strategy, random_seed=self.random_seed),
            upload_enabled=self.upload_enabled,
        )
        peer._tracker_client.host = self.tracker_host
        peer._tracker_client.port = self.tracker_port
        return peer

    def start(self, name: str) -> CatalogEntry:
        """Resolve and start the initial file swarm."""
        if self.peer is not None:
            raise RuntimeError("Session is already started")
        return self.request_file(name)

    def request_file(self, name: str) -> CatalogEntry:
        """Switch to a catalog file, leaving the active swarm if needed."""
        entry = self.catalog.resolve(name)
        if self.current_entry is not None and entry.file_id == self.current_entry.file_id:
            self.current_entry = entry
            return entry

        new_peer = self._build_peer(entry)
        previous_peer = self.peer
        if previous_peer is not None:
            previous_peer.stop()
            self.peer = None
            self.current_entry = None
            if self._switch_delay:
                time.sleep(self._switch_delay)

        try:
            new_peer.start()
        except Exception:
            new_peer.stop()
            raise
        self.peer = new_peer
        self.current_entry = entry
        return entry

    def stop(self) -> None:
        """Stop the active peer and clear the session state."""
        peer = self.peer
        self.peer = None
        self.current_entry = None
        if peer is not None:
            peer.stop()