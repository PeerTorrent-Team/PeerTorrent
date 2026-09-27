from .message import Message
from .message_types import MessageType


class Handshake:
    @staticmethod
    def create_handshake(peer_id: str, file_id: str) -> Message:
        # The handshake identifies both the peer and the file being shared.
        return Message(
            type=MessageType.HANDSHAKE,
            payload={
                "peer_id": peer_id,
                "file_id": file_id,
            },
        )

    @staticmethod
    def validate_handshake(message: Message) -> bool:
        if message.type != MessageType.HANDSHAKE:
            return False

        peer_id = message.payload.get("peer_id")
        file_id = message.payload.get("file_id")

        if not isinstance(peer_id, str) or not peer_id.strip():
            return False

        if not isinstance(file_id, str) or not file_id.strip():
            return False

        return True