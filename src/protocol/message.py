from dataclasses import dataclass
from .message_types import MessageType

@dataclass
class Message:
    # Every protocol message has a type and payload.
    type: MessageType
    payload: dict