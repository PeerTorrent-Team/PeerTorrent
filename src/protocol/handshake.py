from protocol import handshake

from .message import Message
from .message_types import MessageType

class Handshake:
    @staticmethod
    def create_handshake(peer_id: str, file_id: str) -> Message:
        # The handshake identifies both the peer and the file being shared
        return Message(
            type=MessageType.HANDSHAKE,
            payload={
                "peer_id": peer_id,
                "file_id": file_id,
            },
        )
    
    @staticmethod
    def validate_handshake(message: Message) -> bool:
        # A handshake must actually be a HANDSHAKE message
        if message.type != MessageType.HANDSHAKE:
            return False

        # Both identifiers are required to identify the peer and shared file
        if "peer_id" not in handshake.payload:
            return False
        if "file_id" not in handshake.payload:
            return False
        return True