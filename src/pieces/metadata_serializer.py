import json
from pathlib import Path

from src.common.types import FileMetadata, PieceInfo
from src.pieces.hash_utils import calculate_file_hash, calculate_hash


def build_metadata(file_path: str, piece_size: int) -> FileMetadata:
    if (
        not isinstance(piece_size, int)
        or isinstance(piece_size, bool)
        or piece_size <= 0
    ):
        raise ValueError("piece_size must be a positive integer")

    path = Path(file_path)
    if not path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    pieces = []
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(piece_size)
            if not chunk:
                break
            pieces.append(
                PieceInfo(
                    index=len(pieces),
                    hash=calculate_hash(chunk),
                    size=len(chunk),
                )
            )

    file_hash = calculate_file_hash(str(path))

    return FileMetadata(
        file_name=path.name,
        file_size=path.stat().st_size,
        piece_size=piece_size,
        piece_count=len(pieces),
        pieces=tuple(pieces),
        file_hash=file_hash,
    )


def save_metadata(metadata: FileMetadata, path: str) -> None:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    payload = {
        "file_name": metadata.file_name,
        "file_size": metadata.file_size,
        "piece_size": metadata.piece_size,
        "piece_count": metadata.piece_count,
        "file_hash": metadata.file_hash,
        "pieces": [
            {
                "index": piece.index,
                "hash": piece.hash,
                "size": piece.size,
            }
            for piece in metadata.pieces
        ],
    }

    destination.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_metadata(path: str) -> FileMetadata:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(f"Metadata not found: {path}")

    payload = json.loads(source.read_text(encoding="utf-8"))
    pieces = tuple(
        PieceInfo(
            index=item["index"],
            hash=item["hash"],
            size=item["size"],
        )
        for item in payload["pieces"]
    )

    return FileMetadata(
        file_name=payload["file_name"],
        file_size=payload["file_size"],
        piece_size=payload["piece_size"],
        piece_count=payload["piece_count"],
        pieces=pieces,
        file_hash=payload.get("file_hash"),
    )
