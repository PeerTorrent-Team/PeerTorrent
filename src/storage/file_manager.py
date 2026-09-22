from pathlib import Path

from src.common.types import PieceInfo
from src.pieces.hash_utils import calculate_hash


def split_file(file_path: str, piece_size: int) -> list[PieceInfo]:
    """Read *file_path* and split it into fixed-size chunks.

    Returns a list of PieceInfo objects (one per chunk), ordered by index.
    The final chunk may be smaller than *piece_size*.
    Hashes are computed with SHA-256 via calculate_hash().
    """
    if piece_size <= 0:
        raise ValueError("piece_size must be greater than 0")

    pieces: list[PieceInfo] = []
    index = 0

    with open(file_path, "rb") as f:
        while True:
            chunk = f.read(piece_size)
            if not chunk:
                break
            pieces.append(PieceInfo(
                index=index,
                hash=calculate_hash(chunk),
                size=len(chunk),
            ))
            index += 1

    return pieces


def reconstruct_file(pieces: list[tuple[int, bytes]], output_path: str) -> None:
    """Concatenate *pieces* in index order and write the result to *output_path*.

    *pieces* is a list of (index, data) tuples containing verified piece data.
    Hash verification is not performed here; that responsibility belongs to
    verifier.py.

    Raises ValueError if *pieces* is empty, contains duplicate indices, or
    has gaps in the index sequence.
    """
    if not pieces:
        raise ValueError("pieces must not be empty")

    indices = [index for index, _ in pieces]

    if len(indices) != len(set(indices)):
        raise ValueError("pieces contains duplicate indices")

    sorted_pieces = sorted(pieces, key=lambda t: t[0])
    expected = list(range(len(sorted_pieces)))
    actual = [index for index, _ in sorted_pieces]

    if actual != expected:
        raise ValueError(
            f"piece indices are not a complete sequence 0..{len(sorted_pieces) - 1}: "
            f"got {actual}"
        )

    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    with open(output, "wb") as f:
        for _, data in sorted_pieces:
            f.write(data)
