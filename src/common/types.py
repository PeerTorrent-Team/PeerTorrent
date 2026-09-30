import re
from dataclasses import dataclass


# Stores the basic network identity of a peer in the torrent swarm.
@dataclass(frozen=True)
class PeerInfo:
    peer_id: str
    ip: str
    port: int

    def __post_init__(self) -> None:
        if not isinstance(self.peer_id, str) or not self.peer_id.strip():
            raise ValueError("peer_id must be a non-empty string")

        if not isinstance(self.ip, str) or not self.ip.strip():
            raise ValueError("ip must be a non-empty string")

        if (
            not isinstance(self.port, int)
            or isinstance(self.port, bool)
            or not 1 <= self.port <= 65535
        ):
            raise ValueError(
                "port must be an integer between 1 and 65535"
            )


# Represents one chunk of a file and its hash, used for validation and piece tracking.
@dataclass(frozen=True)
class PieceInfo:
    index: int
    hash: str
    size: int

    def __post_init__(self) -> None:
        if (
            not isinstance(self.index, int)
            or isinstance(self.index, bool)
            or self.index < 0
        ):
            raise ValueError(
                "piece index must be a non-negative integer"
            )

        if (
            not isinstance(self.size, int)
            or isinstance(self.size, bool)
            or self.size < 0
        ):
            raise ValueError(
                "piece size must be a non-negative integer"
            )

        if not isinstance(self.hash, str) or not self.hash.strip():
            raise ValueError(
                "piece hash must be a non-empty string"
            )

        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.hash):
            raise ValueError(
                "piece hash must be a 64-character SHA-256 hexadecimal string"
            )


# Describes the file being shared, including all piece metadata needed for download logic.
@dataclass(frozen=True)
class FileMetadata:
    file_name: str
    file_size: int
    piece_size: int
    piece_count: int
    pieces: tuple[PieceInfo, ...]
    file_hash: str | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.file_name, str) or not self.file_name.strip():
            raise ValueError("file_name must be a non-empty string")

        if (
            not isinstance(self.file_size, int)
            or isinstance(self.file_size, bool)
        ):
            raise ValueError(
                "file_size must be a non-negative integer"
            )

        if (
            not isinstance(self.piece_size, int)
            or isinstance(self.piece_size, bool)
        ):
            raise ValueError(
                "piece_size must be a positive integer"
            )

        if (
            not isinstance(self.piece_count, int)
            or isinstance(self.piece_count, bool)
        ):
            raise ValueError(
                "piece_count must be a non-negative integer"
            )

        if not isinstance(self.pieces, tuple):
            object.__setattr__(self, "pieces", tuple(self.pieces))

        if any(not isinstance(piece, PieceInfo) for piece in self.pieces):
            raise ValueError(
                "pieces must contain only PieceInfo objects"
            )

        if self.file_hash is not None:
            if not isinstance(self.file_hash, str) or not self.file_hash.strip():
                raise ValueError("file_hash must be a non-empty SHA-256 hex string")
            if not re.fullmatch(r"[0-9a-fA-F]{64}", self.file_hash):
                raise ValueError(
                    "file_hash must be a 64-character SHA-256 hexadecimal string"
                )

        if self.file_size < 0:
            raise ValueError("file_size must be non-negative")

        if self.piece_size <= 0:
            raise ValueError("piece_size must be greater than 0")

        if self.piece_count < 0:
            raise ValueError("piece_count must be non-negative")

        expected_piece_count = (
            0
            if self.file_size == 0
            else (self.file_size + self.piece_size - 1) // self.piece_size
        )

        if self.piece_count != expected_piece_count:
            raise ValueError(
                "piece_count does not match file_size and piece_size"
            )

        total_piece_bytes = sum(piece.size for piece in self.pieces)

        if total_piece_bytes != self.file_size:
            raise ValueError(
                "piece sizes do not match file_size"
            )

        for index, piece in enumerate(self.pieces):
            if piece.index != index:
                raise ValueError(
                    "pieces must have sequential indexes"
                )

            if piece.size <= 0:
                raise ValueError(
                    "piece size must be greater than 0"
                )

            if piece.size > self.piece_size:
                raise ValueError(
                    "piece size cannot exceed piece_size"
                )

        if len(self.pieces) != self.piece_count:
            raise ValueError(
                "piece_count must match the number of pieces"
            )