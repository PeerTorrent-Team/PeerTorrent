import dataclasses
import re


@dataclasses.dataclass
class Piece:
    index: int
    size: int
    expected_hash: str
    data: bytes | None = None
    is_complete: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.index, int) or isinstance(self.index, bool):
            raise ValueError("index must be a non-negative integer")

        if self.index < 0:
            raise ValueError("index must be a non-negative integer")

        if not isinstance(self.size, int) or isinstance(self.size, bool):
            raise ValueError("size must be a positive integer")

        if self.size <= 0:
            raise ValueError("size must be a positive integer")

        if not isinstance(self.expected_hash, str):
            raise ValueError("expected_hash must be a string")

        if not re.fullmatch(r"[0-9a-fA-F]{64}", self.expected_hash):
            raise ValueError(
                "expected_hash must be a 64-character SHA-256 hexadecimal string"
            )
