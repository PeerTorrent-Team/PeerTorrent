import dataclasses

@dataclasses.dataclass
class Piece:
    index: int
    size: int
    expected_hash: str
    data: bytes | None = None
    is_complete: bool = False
