from __future__ import annotations

import base64
import json

from .message import Message
from .message_types import MessageType

class Encoder:
 # Converts a Message object into UTF-8 encoded JSON bytes.
 # TCP framing is NOT handled here. The SocketManager is responsible for adding the 4-byte message length before sending the bytes.


 def encode(self, message: Message) -> bytes:
    """
    Convert a Message into JSON bytes.

    PIECE messages contain binary data (bytes), which JSON cannot
    serialize directly. Therefore, PIECE data is converted to
    Base64 before being placed into the JSON payload.
    """

    # Copy the payload so that encoding does not modify the original
    # Message object's payload.
    payload = dict(message.payload)

    # PIECE data is binary bytes and must be converted to a string
    # before JSON serialization.
    if message.type == MessageType.PIECE:
        data = payload.get("data")

        if not isinstance(data, bytes):
            raise TypeError("PIECE data must be bytes")

        # Base64 converts arbitrary binary data into a JSON-safe string.
        payload["data"] = base64.b64encode(data).decode("ascii")

    # Create the JSON representation of the protocol message.
    data = {
        "type": message.type.value,
        "payload": payload,
    }

    # Convert the Python dictionary into a JSON string.
    serialized = json.dumps(data)

    # Convert the JSON string into UTF-8 bytes.
    #
    # IMPORTANT:
    # No length prefix is added here. TCP framing belongs to
    # SocketManager, not Encoder.
    return serialized.encode("utf-8")