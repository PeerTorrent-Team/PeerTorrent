from __future__ import annotations

import socket
import struct

from src.common.constants import MAX_MESSAGE_SIZE, SOCKET_TIMEOUT


class SocketManager:
    def __init__(self, timeout: float = SOCKET_TIMEOUT):
        if timeout <= 0:
            raise ValueError("timeout must be positive")

        self.timeout = timeout

    def create_socket(self) -> socket.socket:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(self.timeout)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
        return sock

    def send_all(self, sock: socket.socket, data: bytes) -> None:
        view = memoryview(data)

        while view:
            sent = sock.send(view)

            if sent == 0:
                raise ConnectionError("Socket connection closed during send")

            view = view[sent:]

    def receive_exact(self, sock: socket.socket, size: int) -> bytes:
        if size < 0:
            raise ValueError("size cannot be negative")

        chunks = bytearray()

        while len(chunks) < size:
            chunk = sock.recv(size - len(chunks))

            if not chunk:
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
        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message is too large: {len(data)} bytes "
                f"(maximum is {MAX_MESSAGE_SIZE} bytes)"
            )

        header = struct.pack("!I", len(data))
        self.send_all(sock, header + data)

    def receive(self, sock: socket.socket) -> bytes:
        header = self.receive_exact(sock, 4)
        message_length = struct.unpack("!I", header)[0]

        if message_length <= 0:
            raise ValueError("Invalid message length")

        if message_length > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Received message is too large: {message_length} bytes "
                f"(maximum is {MAX_MESSAGE_SIZE} bytes)"
            )

        return self.receive_exact(sock, message_length)

    def close(self, sock: socket.socket) -> None:
        sock.close()