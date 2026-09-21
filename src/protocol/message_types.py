from enum import Enum

class MessageType(Enum):
    # These are the message types our peers can exchange with each other.
    HANDSHAKE="HANDSHAKE"
    BITFIELD="BITFIELD"
    HAVE="HAVE"
    REQUEST="REQUEST"
    PIECE="PIECE"
    INTERESTED="INTERESTED"
    NOT_INTERESTED="NOT_INTERESTED"
    CHOKE="CHOKE"
    UNCHOKE="UNCHOKE"