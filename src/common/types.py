from dataclasses import dataclass


# Stores the basic network identity of a peer in the torrent swarm.
@dataclass(frozen=True)
class PeerInfo:
    peer_id: str
    ip: str
    port: int


# Represents one chunk of a file and its hash, used for validation and piece tracking.
@dataclass(frozen=True)
class PieceInfo:
    index: int
    hash: str
    size: int


# Describes the file being shared, including all piece metadata needed for download logic.
@dataclass(frozen=True)
class FileMetadata:
    file_name: str
    file_size: int
    piece_size: int
    piece_count: int
    pieces: list[PieceInfo]