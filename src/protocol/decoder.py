import base64
import json

from src.common.constants import MAX_MESSAGE_SIZE

from .message import Message
from .message_types import MessageType
from .validation import validate_message


class Decoder:
    def decode(self, data: bytes) -> Message:
        # The SocketManager has already removed the 4-byte TCP length
        # prefix before the decoder receives these bytes.
        # Therefore, Decoder only deals with JSON → Message conversion.
        if not isinstance(data, (bytes, bytearray)):
            raise TypeError("message data must be bytes")

        if len(data) > MAX_MESSAGE_SIZE:
            raise ValueError(
                f"Message is too large: {len(data)} bytes "
                f"(maximum is {MAX_MESSAGE_SIZE} bytes)"
            )

        try:
            serialized = data.decode("utf-8")

            def reject_duplicate_keys(pairs):
                result = {}
                for key, value in pairs:
                    if key in result:
                        raise ValueError(f"Duplicate JSON key: {key}")
                    result[key] = value
                return result

            raw = json.loads(
                serialized,
                object_pairs_hook=reject_duplicate_keys,
                parse_constant=lambda value: (_ for _ in ()).throw(
                    ValueError(f"Invalid JSON constant: {value}")
                ),
            )
        except (UnicodeDecodeError, json.JSONDecodeError, ValueError) as exc:
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

        message = Message(
            type=message_type,
            payload=payload,
        )
        validate_message(message)
        return message