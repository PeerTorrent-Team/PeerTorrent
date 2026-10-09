"""Shared validation for PeerTorrent's peer-wire messages.

The encoder validates outbound messages as well as the decoder validating
inbound messages. This keeps local peers from emitting frames that a remote
peer would reject.
"""

from __future__ import annotations

from .message import Message
from .message_types import MessageType

_REQUIRED_FIELDS: dict[MessageType, set[str]] = {
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

_INDEXED_MESSAGES = {
    MessageType.HAVE,
    MessageType.REQUEST,
    MessageType.PIECE,
    MessageType.CANCEL,
}


def validate_message(message: Message) -> None:
    """Validate a decoded or in-memory protocol message.

    Raises:
        TypeError: when PIECE data is not bytes.
        ValueError: when the message shape or fields violate the wire schema.
    """

    if not isinstance(message, Message):
        raise TypeError("message must be a Message instance")

    if not isinstance(message.type, MessageType):
        raise ValueError("Message type must be a supported MessageType")

    payload = message.payload
    if not isinstance(payload, dict):
        raise ValueError("Message payload must be a JSON object")

    required_fields = _REQUIRED_FIELDS[message.type]
    missing_fields = required_fields - payload.keys()
    if missing_fields:
        raise ValueError(
            f"Missing required payload fields: {sorted(missing_fields)}"
        )

    if message.type == MessageType.HANDSHAKE:
        for field in ("peer_id", "file_id"):
            value = payload[field]
            if not isinstance(value, str) or not value.strip():
                raise ValueError(
                    f"HANDSHAKE {field} must be a non-empty string"
                )

    elif message.type == MessageType.BITFIELD:
        pieces = payload["pieces"]
        if not isinstance(pieces, list):
            raise ValueError("BITFIELD pieces must be a list")
        if any(type(value) is not int or value not in (0, 1) for value in pieces):
            raise ValueError("BITFIELD values must be integer 0 or 1")

    if message.type in _INDEXED_MESSAGES:
        piece_index = payload["piece_index"]
        if type(piece_index) is not int or piece_index < 0:
            raise ValueError("piece_index must be a non-negative integer")

    if message.type == MessageType.PIECE and not isinstance(payload["data"], bytes):
        raise TypeError("PIECE data must be bytes")
