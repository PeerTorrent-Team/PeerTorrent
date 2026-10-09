from __future__ import annotations

import threading
import time

from src.common.constants import (
    ANNOUNCE_INTERVAL,
    DEFAULT_PEER_PORT,
    DEFAULT_TRACKER_HOST,
    DEFAULT_TRACKER_PORT,
    MAX_PIPELINE_REQUESTS,
    REQUEST_TIMEOUT,
)
from src.common.logger import get_logger
from src.network.connection import Connection
from src.network.connection_pool import ConnectionPool
from src.network.socket_manager import SocketManager
from src.pieces.piece_manager import PieceManager
from src.pieces.verifier import verify_piece
from src.protocol.handshake import Handshake
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from src.selection.sequential_selector import SequentialSelector
from src.storage.piece_storage import PieceStorage
from src.tracker.tracker_client import TrackerClient

from .choking_manager import ChokingManager
from .download_manager import DownloadManager
from .peer_state import PeerState
from .request_manager import RequestManager
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

        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValueError("peer_id must be a non-empty string")

        if not isinstance(file_id, str) or not file_id.strip():
            raise ValueError("file_id must be a non-empty string")

        if (
            not isinstance(port, int)
            or isinstance(port, bool)
            or not 1 <= port <= 65535
        ):
            raise ValueError(
                "port must be an integer between 1 and 65535"
            )

        self.peer_id = peer_id
        self.file_id = file_id
        self.host = host
        self.port = port

        self._piece_manager = piece_manager
        self._storage = storage or piece_manager.storage
        self._request_manager = RequestManager(REQUEST_TIMEOUT)
        self._uploaded = 0
        self._downloaded = 0
        self._downloaded_by_peer: dict[str, int] = {}

        self._state = PeerState(
            total_pieces=piece_manager.piece_count()
        )

        # Restore local state from pieces already stored on disk.
        # A stored piece is considered owned only if its hash is valid.
        for index in range(self._state.total_pieces):
            if not self._storage.has_piece(index):
                continue

            try:
                data = self._storage.load_piece(index)
            except OSError:
                continue

            piece_info = piece_manager.get_piece(index)

            if verify_piece(data, piece_info.expected_hash):
                piece_info.data = data
                piece_manager.mark_piece_complete(index)
                self._state.add_piece(index)

        # Gives peer access to network layer
        self._socket_manager = SocketManager()
        self._listen_socket = None
        self._threads: list[threading.Thread] = []
        self._stop_event = threading.Event()

        #Stores active connections to other peers
        self._connections = ConnectionPool(
            max_connections=max_connections
        )

        # Create download manager
        self._download_manager = DownloadManager(
            piece_manager=self._piece_manager,
            storage=self._storage,
            state=self._state,
            request_manager=self._request_manager,
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

        self._tracker_client = TrackerClient(
            DEFAULT_TRACKER_HOST,
            DEFAULT_TRACKER_PORT,
            self.peer_id,
            host,
            port,
            self.file_id,
        )

        self._choking_manager = ChokingManager(
            state=self._state,
            send_message=self._send_control_message,
            bytes_downloaded_from_peer=self._get_downloaded_from_peer,
        )

        # Gives this particular peer its own logger
        self._logger = get_logger(
            f"peer.{self.peer_id}"
        )

        self._running = False
        self._lock = threading.RLock()

    # Lifecycle

    def _get_downloaded_from_peer(self, peer_id: str) -> int:
        return self._downloaded_by_peer.get(peer_id, 0)

    def _send_control_message(self, peer_id: str, message_type: str) -> None:
        connection = self._connections.get(peer_id)
        if connection is None:
            return

        if message_type == "CHOKE":
            message = self.create_choke()
        elif message_type == "UNCHOKE":
            message = self.create_unchoke()
        else:
            raise ValueError(f"Unknown control message: {message_type}")

        connection.send_message(message)

    def _calculate_left(self) -> int:
        return sum(
            self._piece_manager.get_piece(index).size
            for index in self._state.get_missing_pieces()
        )

    def _start_listener(self) -> None:
        self._listen_socket = self._socket_manager.create_socket()
        self._socket_manager.bind(self._listen_socket, self.host, self.port)
        self._socket_manager.listen(self._listen_socket)

        thread = threading.Thread(
            target=self._accept_loop,
            daemon=True,
        )
        self._threads.append(thread)
        thread.start()

    def _accept_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                sock, _ = self._socket_manager.accept(self._listen_socket)
            except TimeoutError:
                continue
            except OSError:
                break

            connection = Connection(
                sock, self._socket_manager, direction="incoming"
            )
            connection.mark_connected()

            thread = threading.Thread(
                target=self._incoming_connection_loop,
                args=(connection,),
                daemon=True,
            )
            self._threads.append(thread)
            thread.start()

    def _incoming_connection_loop(self, connection: Connection) -> None:
        remote_peer_id = None

        try:
            message = connection.receive_message()

            if message.type != MessageType.HANDSHAKE:
                raise ValueError("First message must be HANDSHAKE")

            remote_peer_id = message.payload["peer_id"]

            if remote_peer_id == self.peer_id:
                raise ValueError("Peer cannot connect to itself")

            if not self._register_incoming_connection(remote_peer_id, connection):
                return

            response = self.handle_message(remote_peer_id, message)
            if response is not None:
                connection.send_message(response)

            self._receive_loop(remote_peer_id, connection)

        except Exception as exc:
            self._logger.warning("Connection failed: %s", exc)

            # Only remove the connection that failed. Do not remove an
            # already-established connection for the same peer.
            if remote_peer_id is not None:
                self.remove_connection(
                    remote_peer_id,
                    expected_connection=connection,
                )
            # remove_connection deliberately leaves a different, already
            # registered connection untouched; always close this failed socket.
            try:
                connection.close()
            except OSError:
                pass

    def _receive_loop(self, peer_id: str, connection: Connection) -> None:
        while self._running:
            try:
                message = connection.receive_message()
            except TimeoutError:
                # No data arrived within the socket's read timeout. This
                # is a normal idle period for a long-lived connection
                # (e.g. between choking rebalances), not a dead peer, so
                # keep the connection open and keep waiting.
                continue
            except Exception as exc:
                self._logger.info("Peer %s disconnected: %s", peer_id, exc)
                break

            try:
                response = self.handle_message(peer_id, message)
                if response is not None:
                    connection.send_message(response)
            except Exception as exc:
                self._logger.info("Peer %s disconnected: %s", peer_id, exc)
                break

        self.remove_connection(peer_id)

    def _tracker_loop(self) -> None:
        while not self._stop_event.is_set():
            try:
                peers = self._tracker_client.announce(
                    left=self._calculate_left(),
                    uploaded=self._uploaded,
                    downloaded=self._downloaded,
                    is_seeder=self._piece_manager.is_complete(),
                )
                for peer_data in peers:
                    if not isinstance(peer_data, dict):
                        continue
                    # A stale or unreachable tracker entry must not prevent us
                    # from attempting connections to the rest of the swarm.
                    try:
                        self.connect_to_peer(peer_data)
                    except Exception as exc:
                        self._logger.debug(
                            "Could not connect to advertised peer: %s", exc
                        )
            except Exception as exc:
                self._logger.warning("Tracker error: %s", exc)

            self._stop_event.wait(ANNOUNCE_INTERVAL)

    def _scheduler_loop(self) -> None:
        while not self._stop_event.is_set():
            expired = self._request_manager.expire()
            for request in expired:
                self._logger.info(
                    "Request timed out: piece=%s peer=%s",
                    request.piece_index,
                    request.peer_id,
                )
                self._state.clear_requested(request.piece_index)

            while self._request_manager.count() < MAX_PIPELINE_REQUESTS:
                if not self.schedule_next_request():
                    break

            self._stop_event.wait(0.2)

    def _broadcast_have(self, piece_index: int) -> None:
        message = self.create_have(piece_index)
        for peer_id, connection in self._connections.get_all_items():
            if connection.handshake_complete:
                try:
                    connection.send_message(message)
                except OSError:
                    self.remove_connection(peer_id)

    def start(self) -> None:
        """Start the peer."""

        with self._lock:
            if self._running:
                return

            self._running = True
            self._stop_event.clear()

        self._start_listener()
        self._choking_manager.start()

        tracker_thread = threading.Thread(
            target=self._tracker_loop,
            daemon=True,
        )
        self._threads.append(tracker_thread)
        tracker_thread.start()

        scheduler_thread = threading.Thread(
            target=self._scheduler_loop,
            daemon=True,
        )
        self._threads.append(scheduler_thread)
        scheduler_thread.start()

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
            self._stop_event.set()

        self._choking_manager.stop()

        if self._listen_socket is not None:
            try:
                self._listen_socket.close()
            except OSError:
                pass

        for peer_id, connection in list(self._connections.get_all_items()):
            try:
                connection.close()
            except OSError:
                pass
            self._connections.remove(peer_id)
            self._state.remove_peer(peer_id)

        # Use one bounded shutdown budget for the peer, rather than waiting
        # one full second for every historical connection thread. All active
        # sockets have been shut down above, so healthy receive loops should
        # wake promptly; any remaining worker is daemonized and cannot block
        # process exit indefinitely.
        join_deadline = time.monotonic() + 1.0
        for thread in list(self._threads):
            if thread is threading.current_thread() or not thread.is_alive():
                continue
            remaining = max(0.0, join_deadline - time.monotonic())
            if remaining == 0.0:
                break
            thread.join(timeout=remaining)

        self._logger.info(
            "Peer %s stopped",
            self.peer_id,
        )

    def _preferred_connection_direction(self, remote_peer_id: str) -> str:
        """Prefer one stable TCP direction for a pair of peers."""
        return "outgoing" if self.peer_id < remote_peer_id else "incoming"

    def _register_incoming_connection(
        self,
        remote_peer_id: str,
        connection: Connection,
    ) -> bool:
        """Register an inbound connection, resolving duplicate sockets safely."""
        connection.direction = "incoming"
        existing = self._connections.get(remote_peer_id)
        if existing is not None:
            preferred = self._preferred_connection_direction(remote_peer_id)

            if existing.direction == preferred:
                connection.close()
                return False
            if preferred != "incoming" or existing.direction != "outgoing":
                connection.close()
                return False

            self.remove_connection(
                remote_peer_id,
                expected_connection=existing,
            )

        try:
            self.add_connection(remote_peer_id, connection)
        except Exception:
            connection.close()
            raise
        return True

    def connect_to_peer(self, peer_info) -> None:
        if isinstance(peer_info, dict):
            peer_id = peer_info.get("peer_id")
            ip = peer_info.get("ip")
            port = peer_info.get("port")
        else:
            peer_id = getattr(peer_info, "peer_id", None)
            ip = getattr(peer_info, "ip", None)
            port = getattr(peer_info, "port", None)

        if not isinstance(peer_id, str) or not peer_id.strip():
            raise ValueError("Peer entry must contain a non-empty peer_id")
        if not isinstance(ip, str) or not ip.strip():
            raise ValueError("Peer entry must contain a non-empty ip")
        if type(port) is not int or not 1 <= port <= 65535:
            raise ValueError("Peer entry port must be an integer from 1 to 65535")
        if peer_id == self.peer_id:
            return

        existing = self._connections.get(peer_id)
        if existing is not None:
            preferred = self._preferred_connection_direction(peer_id)
            if existing.direction == preferred:
                return
            if preferred == "outgoing" and existing.direction == "incoming":
                self.remove_connection(peer_id, expected_connection=existing)
            else:
                return

        connection = Connection(
            self._socket_manager.create_socket(),
            self._socket_manager,
            direction="outgoing",
        )

        try:
            connection.connect(ip, port)
            self.add_connection(peer_id, connection)
            connection.send_message(self.create_handshake())
        except Exception:
            connection.close()
            raise

        thread = threading.Thread(
            target=self._outgoing_connection_loop,
            args=(peer_id, connection),
            daemon=True,
        )
        self._threads.append(thread)
        thread.start()

    def _outgoing_connection_loop(self, peer_id: str, connection: Connection) -> None:
        while self._running:
            try:
                message = connection.receive_message()
            except TimeoutError:
                continue
            except Exception as exc:
                self._logger.info("Peer %s disconnected: %s", peer_id, exc)
                break

            try:
                response = self.handle_message(peer_id, message)
                if response is not None:
                    connection.send_message(response)
            except Exception as exc:
                self._logger.info("Peer %s disconnected: %s", peer_id, exc)
                break

        current = self._connections.get(peer_id)
        if current is connection:
            self.remove_connection(peer_id, connection)

    # Connection management

    def add_connection(self, peer_id: str, connection) -> None:
        """Register an already-created connection."""

        if not self._running:
            raise RuntimeError("Peer is not running")

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

    def remove_connection(
        self,
        peer_id: str,
        expected_connection=None,
    ) -> None:
        """Remove and close a peer connection."""

        connection = self._connections.get(peer_id)

        if connection is not None and expected_connection is not None:
            if connection is not expected_connection:
                return

        if connection is not None:
            try:
                connection.close()
            except OSError:
                pass

        self._connections.remove(peer_id)
        self._state.remove_peer(peer_id)

        removed = self._request_manager.clear_peer(peer_id)
        for request in removed:
            self._state.clear_requested(request.piece_index)

    # Handshake

    def create_handshake(self) -> Message:
        return Handshake.create_handshake(
            self.peer_id,
            self.file_id,
        )

    def create_request(self, piece_index: int) -> Message:
        return Message(
            type=MessageType.REQUEST,
            payload={
                "piece_index": piece_index,
            },
        )

    def create_cancel(self, piece_index: int) -> Message:
        return Message(
            type=MessageType.CANCEL,
            payload={
                "piece_index": piece_index,
            },
        )

    def create_interested(self) -> Message:
        return Message(
            type=MessageType.INTERESTED,
            payload={},
        )

    def create_not_interested(self) -> Message:
        return Message(
            type=MessageType.NOT_INTERESTED,
            payload={},
        )

    def create_choke(self) -> Message:
        return Message(
            type=MessageType.CHOKE,
            payload={},
        )

    def create_unchoke(self) -> Message:
        return Message(
            type=MessageType.UNCHOKE,
            payload={},
        )

    def handle_handshake(
        self,
        peer_id: str,
        message: Message,
    ) -> bool:
        """Validate a remote handshake."""

        if not Handshake.validate_handshake(message):
            return False

        remote_peer_id = message.payload.get("peer_id")

        if remote_peer_id != peer_id:
            self._logger.warning(
                "Peer ID mismatch on connection to %s",
                peer_id,
            )
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

        # A bitfield must contain exactly one value for every piece.
        if len(pieces) != self._state.total_pieces:
            raise ValueError(
                "BITFIELD length does not match total piece count"
            )

        # Every value must be exactly 0 or 1.
        if any(
            isinstance(value, bool) or value not in (0, 1)
            for value in pieces
        ):
            raise ValueError(
                "BITFIELD values must be either 0 or 1"
            )

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

        piece_index = message.payload.get("piece_index")

        if (
            not isinstance(piece_index, int)
            or isinstance(piece_index, bool)
        ):
            raise ValueError(
                "HAVE piece_index must be an integer"
            )

        if not 0 <= piece_index < self._state.total_pieces:
            raise ValueError(
                "HAVE piece_index is outside the valid range"
            )

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

    # Interest
    # Compares our missing pieces against what a specific peer has and
    # sends INTERESTED / NOT_INTERESTED if our interest in them changed.
    # Without this, remote peers never learn we want anything from them,
    # so their ChokingManager never unchokes us and we can never request
    # pieces from them.
    def _update_interest(self, peer_id: str) -> None:
        connection = self._connections.get(peer_id)

        if connection is None or not connection.handshake_complete:
            return

        missing = set(self._state.get_missing_pieces())
        peer_pieces = self._state.get_peer_pieces(peer_id)
        should_be_interested = bool(missing & peer_pieces)
        currently_interested = self._state.am_interested(peer_id)

        if should_be_interested == currently_interested:
            return

        self._state.set_am_interested(peer_id, should_be_interested)

        message = (
            self.create_interested()
            if should_be_interested
            else self.create_not_interested()
        )

        try:
            connection.send_message(message)
        except OSError:
            self.remove_connection(peer_id)

    # Re-checks our interest in every connected peer. Used after we
    # complete a piece, since that can make us no longer interested in
    # peers who only had pieces we've since obtained elsewhere.
    def _update_interest_all(self) -> None:
        for peer_id in self._state.get_connected_peers():
            self._update_interest(peer_id)

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

            connection = self._connections.get(peer_id)

            if connection is None:
                raise ValueError(
                    f"No connection found for peer: {peer_id}"
                )

            was_already_complete = connection.handshake_complete

            # Receiving a valid handshake completes our side of the
            # handshake process.
            connection.handshake_complete = True

            # If we have not sent our handshake yet, send it now as our
            # response. If we already sent one, this is the response to
            # our handshake, so we do not send another one.
            if not connection.handshake_sent:
                connection.send_message(self.create_handshake())

            # The first time the handshake completes on this connection
            # (whether we initiated it or accepted it), tell the remote
            # peer which pieces we already have. Without this, a peer
            # that *initiated* the connection would never announce its
            # bitfield, since only the accepting side used to do this.
            if not was_already_complete:
                connection.send_message(self.create_bitfield())

            return None

        connection = self._connections.get(peer_id)

        if connection is None:
            raise ValueError(
                f"No connection found for peer: {peer_id}"
            )

        if not connection.handshake_complete:
            raise ValueError(
                f"Handshake not complete with peer: {peer_id}"
            )

        if message.type == MessageType.BITFIELD:
            self.handle_bitfield(peer_id, message)
            self._update_interest(peer_id)
            return None

        if message.type == MessageType.HAVE:
            self.handle_have(peer_id, message)
            self._update_interest(peer_id)
            return None

        if message.type == MessageType.REQUEST:
            piece_index = message.payload["piece_index"]

            connection = self._connections.get(peer_id)

            uploaded = 0
            if connection is not None:
                uploaded = self._upload_manager.handle_request(
                    peer_id,
                    connection,
                    piece_index,
                )

            self._uploaded += uploaded
            return None

        if message.type == MessageType.CANCEL:
            piece_index = message.payload["piece_index"]
            self._upload_manager.cancel_upload(peer_id, piece_index)
            self._state.clear_requested(piece_index)
            return None

        if message.type == MessageType.PIECE:
            valid = self._download_manager.handle_piece(peer_id, message)

            if valid:
                piece_index = message.payload["piece_index"]
                self._downloaded += len(message.payload["data"])
                self._downloaded_by_peer[peer_id] = self._downloaded_by_peer.get(peer_id, 0) + len(message.payload["data"])
                self._broadcast_have(piece_index)
                self._update_interest_all()

            return None

        if message.type == MessageType.CHOKE:
            self._state.set_choked(peer_id, True)
            return None

        if message.type == MessageType.UNCHOKE:
            self._state.set_choked(peer_id, False)
            return None

        if message.type == MessageType.INTERESTED:
            self._state.set_interested(peer_id, True)
            self._choking_manager.rebalance()
            return None

        if message.type == MessageType.NOT_INTERESTED:
            self._state.set_interested(peer_id, False)
            self._choking_manager.rebalance()
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
            peer_id,
        )

        return True

    # State access

    def get_state(self) -> PeerState:
        return self._state

    def get_connections(self) -> ConnectionPool:
        return self._connections

    def is_complete(self) -> bool:
        return self._piece_manager.is_complete()

    