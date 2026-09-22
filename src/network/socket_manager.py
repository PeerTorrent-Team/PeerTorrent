import socket
from common.constants import SOCKET_TIMEOUT


class SocketManager:
    
    def __init__(self, timeout: float = SOCKET_TIMEOUT):
        self.timeout = timeout

    def create_socket(self) -> socket.socket:
        # Create an IPv4 TCP socket for peer-to-peer communication.
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # Prevent the socket from waiting forever on network operations.
        sock.settimeout(self.timeout)

        return sock

    def bind(self, sock: socket.socket, host: str, port: int) -> None:
        # Attach the socket to our local IP address and port.
        sock.bind((host, port))

    def listen(self, sock: socket.socket, backlog: int = 5) -> None:
        # Put the socket into server mode so it can accept peers.
        sock.listen(backlog)

    def connect(
        self,
        sock: socket.socket,
        host: str,
        port: int,
    ) -> None:
        # Establish a TCP connection to another peer.
        sock.connect((host, port))

    def accept(
        self,
        sock: socket.socket,
    ) -> tuple[socket.socket, tuple[str, int]]:
        # Wait for an incoming peer connection.
        return sock.accept()

    def send(self, sock: socket.socket, data: bytes) -> None:
        # Send the complete byte sequence through the TCP connection.
        sock.sendall(data)

    def receive(
        self,
        sock: socket.socket,
        buffer_size: int = 4096,
    ) -> bytes:
        # Receive bytes from the connected peer.
        return sock.recv(buffer_size)

    def close(self, sock: socket.socket) -> None:
        # Close the TCP socket when the connection is finished.
        sock.close()