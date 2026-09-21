# Re-export canonical shared types so that existing M1 code can still
# import PieceInfo and FileMetadata from src.pieces.metadata.
from src.common.types import PieceInfo, FileMetadata

__all__ = ["PieceInfo", "FileMetadata"]
