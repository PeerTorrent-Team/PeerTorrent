import base64
import json

from .message import Message
from .message_types import MessageType


class Decoder:
    def decode(self, data: bytes) -> Message:
        # The SocketManager has already removed the 4-byte TCP length
        # prefix before the decoder receives these bytes.
        # Therefore, Decoder only deals with JSON → Message conversion.
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

        # PIECE data is Base64-encoded on the wire because JSON
        # cannot directly represent Python bytes. Decode it back to
        # bytes before handing the message to the peer layer.
        if message_type == MessageType.PIECE:
            encoded_data = payload.get("data")

            if not isinstance(encoded_data, str):
                raise ValueError("PIECE data must be a Base64 string")

            try:
                payload["data"] = base64.b64decode(
                    encoded_data,
                    validate=True,
                )
            except (ValueError, TypeError) as exc:
                raise ValueError("Invalid Base64 PIECE data") from exc

        # Validate the fields required by each message type.
        required_fields = {
            MessageType.HANDSHAKE: {"peer_id", "file_id"},
            MessageType.BITFIELD: {"pieces"},
            MessageType.HAVE: {"piece_index"},
            MessageType.REQUEST: {"piece_index"},
            MessageType.PIECE: {"piece_index", "data"},
            MessageType.CANCEL: {"piece_index"},
            MessageType.INTERESTED: set(),
            MessageType.NOT_INTERESTED: set(),
            MessageType.CHOKE: set(),
            MessageType.UNCHOKE: set(),
        }

        missing_fields = required_fields[message_type] - payload.keys()

        if missing_fields:
            raise ValueError(
                f"Missing required payload fields: {sorted(missing_fields)}"
            )

        if message_type == MessageType.HANDSHAKE:
            peer_id = payload["peer_id"]
            file_id = payload["file_id"]

            if (
                not isinstance(peer_id, str)
                or not peer_id.strip()
            ):
                raise ValueError("HANDSHAKE peer_id must be a non-empty string")

            if (
                not isinstance(file_id, str)
                or not file_id.strip()
            ):
                raise ValueError("HANDSHAKE file_id must be a non-empty string")

        if message_type == MessageType.BITFIELD:
            pieces = payload["pieces"]

            if not isinstance(pieces, list):
                raise ValueError("BITFIELD pieces must be a list")

            if any(
                isinstance(value, bool) or value not in (0, 1)
                for value in pieces
            ):
                raise ValueError(
                    "BITFIELD values must be either 0 or 1"
                )

        # Piece indexes must be non-negative integers.
        if message_type in {
            MessageType.HAVE,
            MessageType.REQUEST,
            MessageType.PIECE,
            MessageType.CANCEL,
        }:
            piece_index = payload["piece_index"]

            # Check that piece_index is a non-negative integer.
            if not isinstance(piece_index, int) or isinstance(piece_index, bool):
                raise ValueError("piece_index must be a non-negative integer")

            if piece_index < 0:
                raise ValueError("piece_index must be a non-negative integer")

        return Message(
            type=message_type,
            payload=payload,
        )