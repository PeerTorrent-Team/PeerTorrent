from __future__ import annotations

import threading

from src.common.constants import DEFAULT_PEER_PORT
from src.common.logger import get_logger
from src.network.connection_pool import ConnectionPool
from src.network.socket_manager import SocketManager
from src.pieces.piece_manager import PieceManager
from src.protocol.handshake import Handshake
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.selection.sequential_selector import SequentialSelector
from src.storage.piece_storage import PieceStorage

from .download_manager import DownloadManager
from .peer_state import PeerState
from .scheduler import Scheduler
from .upload_manager import UploadManager


class Peer:
    """
    Main PeerTorrent peer component.

    Coordinates:
        - network connections
        - protocol messages
        - piece state
        - downloading
        - uploading
        - piece selection
    """

    def __init__(
        self,
        peer_id: str,
        file_id: str,
        piece_manager: PieceManager,
        *,
        host: str = "127.0.0.1",
        port: int = DEFAULT_PEER_PORT,
        storage: PieceStorage | None = None,
        selector=None,
        max_connections: int | None = None,
    ) -> None:

        self.peer_id = peer_id
        self.file_id = file_id
        self.host = host
        self.port = port

        self._piece_manager = piece_manager

        self._storage = storage or PieceStorage()

        self._state = PeerState(
            total_pieces=piece_manager.piece_count()
        )

        # Restore state from PieceManager
        for index in range(self._state.total_pieces):
            if piece_manager.has_piece(index):
                self._state.add_piece(index)

        # Gives peer access to network layer
        self._socket_manager = SocketManager()

        #Stores active connections to other peers
        self._connections = ConnectionPool(
            max_connections=max_connections
        )

        # Create download manager
        self._download_manager = DownloadManager(
            piece_manager=self._piece_manager,
            storage=self._storage,
            state=self._state,
        )

        # Create upload manager
        self._upload_manager = UploadManager(
            storage=self._storage,
            state=self._state,
        )

        #Create selector
        self._selector = selector or SequentialSelector()

        # Create scheduler
        self._scheduler = Scheduler(
            state=self._state,
            selector=self._selector,
        )

        # Gives this particular peer its own logger
        self._logger = get_logger(
            f"peer.{self.peer_id}"
        )

        self._running = False
        self._lock = threading.RLock()

    # Lifecycle

    def start(self) -> None:
        """Start the peer."""

        with self._lock:
            if self._running:
                return

            self._running = True

        self._logger.info(
            "Peer %s started for file %s",
            self.peer_id,
            self.file_id,
        )

    def stop(self) -> None:
        """Stop the peer and close all active connections."""

        with self._lock:
            if not self._running:
                return

            self._running = False

        # Go through every active connection
        for peer_id, connection in list(
            self._connections.connections.items()
        ):
            try:
                connection.close()
            except OSError:
                pass

            self._state.remove_peer(peer_id)

        self._logger.info(
            "Peer %s stopped",
            self.peer_id,
        )

    # Connection management

    def add_connection(self, peer_id: str, connection) -> None:
        """Register an already-created connection."""

        self._connections.add(
            peer_id,
            connection,
        )

        # Update peer state
        self._state.add_connected_peer(peer_id)

        self._logger.info(
            "Connected to peer %s",
            peer_id,
        )

    def remove_connection(self, peer_id: str) -> None:
        """Remove and close a peer connection."""

        connection = self._connections.get(peer_id)

        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

        self._connections.remove(peer_id)
        self._state.remove_peer(peer_id)

    # Handshake

    def create_handshake(self) -> Message:
        return Handshake.create_handshake(
            self.peer_id,
            self.file_id,
        )

    def handle_handshake(
        self,
        peer_id: str,
        message: Message,
    ) -> bool:
        """Validate a remote handshake."""

        if not Handshake.validate_handshake(message):
            return False

        remote_file_id = message.payload.get("file_id")

        if remote_file_id != self.file_id:
            self._logger.warning(
                "Peer %s attempted to connect for wrong file",
                peer_id,
            )
            return False

        return True

    # Bitfield
    # Position corresponds to piece, creates the actual protocol message
    def create_bitfield(self) -> Message:
        pieces = [
            1 if self._piece_manager.has_piece(index) else 0
            for index in range(self._state.total_pieces)
        ]

        return Message(
            type=MessageType.BITFIELD,
            payload={
                "pieces": pieces,
            },
        )

    # Update peer state availability information based on a received BITFIELD message
    def handle_bitfield(
        self,
        peer_id: str,
        message: Message,
    ) -> None:
        if message.type != MessageType.BITFIELD:
            raise ValueError("Expected BITFIELD message")

        pieces = message.payload.get("pieces")

        if not isinstance(pieces, list):
            raise ValueError("BITFIELD pieces must be a list")

        available = {
            index
            for index, value in enumerate(pieces)
            if value == 1
        }

        self._state.update_peer_pieces(
            peer_id,
            available,
        )

    # HAVE

    def handle_have(
        self,
        peer_id: str,
        message: Message,
    ) -> None:
        if message.type != MessageType.HAVE:
            raise ValueError("Expected HAVE message")

        piece_index = message.payload["piece_index"]

        self._state.add_peer_piece(
            peer_id,
            piece_index,
        )

    #Let peers know that this peer has a piece
    def create_have(self, piece_index: int) -> Message:
        return Message(
            type=MessageType.HAVE,
            payload={
                "piece_index": piece_index,
            },
        )

    # Message handling

    def handle_message(
        self,
        peer_id: str,
        message: Message,
    ) -> Message | None:
        """
        Process one message received from a remote peer.

        Some messages generate a response.
        """

        if message.type == MessageType.HANDSHAKE:
            if not self.handle_handshake(peer_id, message):
                raise ValueError("Invalid handshake")

            return self.create_handshake()

        if message.type == MessageType.BITFIELD:
            self.handle_bitfield(peer_id, message)
            return None

        if message.type == MessageType.HAVE:
            self.handle_have(peer_id, message)
            return None

        if message.type == MessageType.REQUEST:
            piece_index = message.payload["piece_index"]

            connection = self._connections.get(peer_id)

            if connection is not None:
                self._upload_manager.handle_request(
                    connection,
                    piece_index,
                )

            return None

        if message.type == MessageType.PIECE:
            valid = self._download_manager.handle_piece(
                message
            )

            if valid:
                piece_index = message.payload["piece_index"]
                return self.create_have(piece_index)

            return None

        if message.type == MessageType.CHOKE:
            self._state.set_choked(peer_id, True)
            return None

        if message.type == MessageType.UNCHOKE:
            self._state.set_choked(peer_id, False)
            return None

        if message.type == MessageType.INTERESTED:
            return None

        if message.type == MessageType.NOT_INTERESTED:
            return None

        raise ValueError(
            f"Unsupported message type: {message.type}"
        )

    # Scheduling

    def schedule_next_request(self) -> bool:
        """
        Select and request the next available piece.

        Returns True if a request was sent.
        """

        scheduled = self._scheduler.schedule()

        if scheduled is None:
            return False

        peer_id, piece_index = scheduled

        connection = self._connections.get(peer_id)

        if connection is None:
            return False

        self._download_manager.request_piece(
            connection,
            piece_index,
        )

        return True

    # State access

    def get_state(self) -> PeerState:
        return self._state

    def get_connections(self) -> ConnectionPool:
        return self._connections

    def is_complete(self) -> bool:
        return self._piece_manager.is_complete()

    