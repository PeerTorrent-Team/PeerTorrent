import json

from .message import Message
from .message_types import MessageType


class Decoder:
    def decode(self, data: bytes) -> Message:
        # Convert the bytes received from the network back into JSON data.
        try:
            serialized = data.decode("utf-8")
            raw = json.loads(serialized)
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("Invalid message data") from exc

        # A protocol message must be represented as a JSON object.
        if not isinstance(raw, dict):
            raise ValueError("Message must be a JSON object")

        # Every message needs both a type and a payload.
        if "type" not in raw or "payload" not in raw:
            raise ValueError("Message must contain both 'type' and 'payload'")

        # Convert the wire-level string back into the MessageType enum.
        try:
            message_type = MessageType(raw["type"])
        except (ValueError, TypeError) as exc:
            raise ValueError("Unknown message type") from exc

        # The Message class expects the payload to be a dictionary.
        payload = raw["payload"]

        if not isinstance(payload, dict):
            raise ValueError("Message payload must be a JSON object")

        # Validate the fields required by each message type.
        required_fields = {
            MessageType.HANDSHAKE: {"peer_id", "file_id"},
            MessageType.BITFIELD: {"pieces"},
            MessageType.HAVE: {"piece_index"},
            MessageType.REQUEST: {"piece_index"},
            MessageType.PIECE: {"piece_index", "data"},
            MessageType.INTERESTED: set(),
            MessageType.NOT_INTERESTED: set(),
            MessageType.CHOKE: set(),
            MessageType.UNCHOKE: set(),
        }

        missing_fields = required_fields[message_type] - payload.keys()

        if missing_fields:
            raise ValueError(f"Missing required payload fields: {sorted(missing_fields)}")

        # Piece indexes must be non-negative integers.
        if message_type in {
            MessageType.HAVE,
            MessageType.REQUEST,
            MessageType.PIECE,
        }:
            piece_index = payload["piece_index"]

            # Check that piece_index is a non-negative integer
            if not isinstance(piece_index, int) or isinstance(piece_index, bool):
                raise ValueError("piece_index must be a non-negative integer")

            if piece_index < 0:
                raise ValueError("piece_index must be a non-negative integer")

        return Message(
            type=message_type,
            payload=payload,
        )