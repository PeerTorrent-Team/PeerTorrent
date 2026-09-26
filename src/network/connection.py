from protocol.decoder import Decoder
from protocol.encoder import Encoder
from protocol.message import Message
from .socket_manager import SocketManager


class Connection:

    def __init__(self, sock, socket_manager: SocketManager | None = None):
        self.socket = sock
        self.socket_manager = socket_manager or SocketManager()

        self.encoder = Encoder()
        self.decoder = Decoder()

        self.connected = False
        self.handshake_complete = False

    def connect(self, host: str, port: int) -> None:
        # Establish a TCP connection to the remote peer.
        self.socket_manager.connect(self.socket, host, port)
        self.connected = True

    def mark_connected(self) -> None:
        # An accepted socket is already connected by the time it reaches us.
        self.connected = True

    def send_message(self, message: Message) -> None:
        # Messages must be encoded into bytes before they can travel over TCP.
        data = self.encoder.encode(message)

        self.socket_manager.send(self.socket, data)

    def receive_message(self) -> Message:
        # Receive raw bytes from the TCP connection.
        data = self.socket_manager.receive(self.socket)

        # Convert the received bytes back into a protocol Message.
        return self.decoder.decode(data)

    def close(self) -> None:
        # Close the underlying TCP connection.
        self.socket_manager.close(self.socket)

        self.connected = False
        self.handshake_complete = False
