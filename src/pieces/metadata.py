import dataclasses
from typing import List

@dataclasses.dataclass
class PieceInfo:
    index: int
    size: int
    hash: str

@dataclasses.dataclass
class FileMetadata:
    file_name: str
    file_size: int
    piece_size: int
    piece_count: int
    pieces: List[PieceInfo]
