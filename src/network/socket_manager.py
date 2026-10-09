from __future__ import annotations

import socket
import struct

from src.common.constants import MAX_MESSAGE_SIZE, SOCKET_TIMEOUT


class SocketManager:
    """TCP socket helpers with bounded, length-prefixed message framing."""

    def __init__(self, timeout: float = SOCKET_TIMEOUT):
        if (
            not isinstance(timeout, (int, float))
            or isinstance(timeout, bool)
            or timeout <= 0
        ):
            raise ValueError("timeout must be a positive number")
        self.timeout = float(timeout)

    def create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        sock.settimeout(self.timeout)
        return sock

    def send_all(self, sock: socket.socket, data: bytes) -> None:
        view = memoryview(data)
        while view:
            try:
                sent = sock.send(view)
            except InterruptedError:
                continue
            if sent == 0:
                raise ConnectionError("Socket connection closed during send")
            view = view[sent:]

    def receive_exact(self, sock: socket.socket, size: int) -> bytes:
        if not isinstance(size, int) or isinstance(size, bool) or size < 0:
            raise ValueError("size must be a non-negative integer")

        chunks = bytearray()
        while len(chunks) < size:
            try:
                chunk = sock.recv(size - len(chunks))
            except TimeoutError as exc:
                if chunks:
                    raise ConnectionError(
                        "Socket receive timed out in the middle of a frame"
                    ) from exc
                raise

            if not chunk:
                if chunks:
                    raise ConnectionError(
                        "Socket connection closed in the middle of a frame"
                    )
                raise ConnectionError("Socket connection closed")
            chunks.extend(chunk)
        return bytes(chunks)

    def bind(self, sock: socket.socket, host: str, port: int) -> None:
        sock.bind((host, port))

    def listen(self, sock: socket.socket, backlog: int = 16) -> None:
        sock.listen(backlog)

    def connect(self, sock: socket.socket, host: str, port: int) -> None:
        sock.connect((host, port))

    def accept(self, sock: socket.socket):
        return sock.accept()

    def send(self, sock: socket.socket, data: bytes) -> None:
        if not isinstance(data, bytes):
            raise TypeError("message data must be bytes")
        if not data:
            raise ValueError("Cannot send an empty frame")
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message is too large: {len(data)} bytes "
                f"(maximum is {MAX_MESSAGE_SIZE} bytes)"
            )

        header = struct.pack("!I", len(data))
        self.send_all(sock, header + data)

    def receive(self, sock: socket.socket) -> bytes:
        # A timeout waiting for the first header byte is safe to retry. Once
        # the header has been consumed, a body timeout is fatal because the
        # next receive cannot start at a frame boundary.
        header = self.receive_exact(sock, 4)
        message_length = struct.unpack("!I", header)[0]

        if message_length <= 0:
            raise ValueError("Invalid message length")
        if message_length > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Received message is too large: {message_length} bytes "
                f"(maximum is {MAX_MESSAGE_SIZE} bytes)"
            )

        try:
            return self.receive_exact(sock, message_length)
        except TimeoutError as exc:
            raise ConnectionError(
                "Socket receive timed out while reading a frame body"
            ) from exc

    def close(self, sock: socket.socket) -> None:
        # shutdown() wakes a thread blocked in recv() on this socket. A plain
        # close() from another thread does not reliably interrupt that recv on
        # every platform, which can make Peer.stop() wait for socket timeouts.
        try:
            sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            pass
        sock.close()