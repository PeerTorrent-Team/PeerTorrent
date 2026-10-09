from __future__ import annotations

import threading

from src.protocol.decoder import Decoder
from src.protocol.encoder import Encoder
from src.protocol.message import Message
from src.protocol.message_types import MessageType
from .socket_manager import SocketManager


class Connection:

    def __init__(
        self,
        sock,
        socket_manager: SocketManager | None = None,
        *,
        direction: str = "unknown",
    ):
        if direction not in {"incoming", "outgoing", "unknown"}:
            raise ValueError("direction must be incoming, outgoing, or unknown")
        self.socket = sock
        # Used by Peer to resolve simultaneous connections deterministically.
        self.direction = direction
        self.socket_manager = socket_manager or SocketManager()
        self._send_lock = threading.Lock()

        self.encoder = Encoder()
        self.decoder = Decoder()

        self.connected = False
        self.handshake_complete = False
        self.handshake_sent = False

    def connect(self, host: str, port: int) -> None:
        # Establish a TCP connection to the remote peer.
        self.socket_manager.connect(self.socket, host, port)
        self.connected = True

    def mark_connected(self) -> None:
        # An accepted socket is already connected by the time it reaches us.
        self.connected = True

    def send_message(self, message: Message) -> None:
        # Encode the message before sending it through the network.
        data = self.encoder.encode(message)

        with self._send_lock:
            # Send one complete framed protocol message.
            self.socket_manager.send(self.socket, data)

            # Remember that this connection has already sent its handshake.
            # This prevents the two peers from repeatedly responding to each
            # other's handshake messages.
            if message.type == MessageType.HANDSHAKE:
                self.handshake_sent = True

    def receive_message(self) -> Message:
        # SocketManager returns exactly one complete framed message.
        # It handles the 4-byte length prefix and partial TCP receives.
        data = self.socket_manager.receive(self.socket)

        # Convert the complete JSON message back into a protocol Message.
        return self.decoder.decode(data)

    def close(self) -> None:
        # Close the underlying TCP connection.
        self.socket_manager.close(self.socket)

        self.connected = False
        self.handshake_complete = False
        self.handshake_sent = False