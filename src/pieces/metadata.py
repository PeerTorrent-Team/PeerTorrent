import hashlib
import json

from src.common.types import FileMetadata, PieceInfo

__all__ = ["PieceInfo", "FileMetadata", "calculate_file_id"]


def calculate_file_id(metadata: FileMetadata) -> str:
    payload = json.dumps(
        {
            "file_name": metadata.file_name,
            "file_size": metadata.file_size,
            "piece_size": metadata.piece_size,
            "piece_count": metadata.piece_count,
            "pieces": [
                {"index": piece.index, "hash": piece.hash, "size": piece.size}
                for piece in metadata.pieces
            ],
        },
        sort_keys=True,
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()
