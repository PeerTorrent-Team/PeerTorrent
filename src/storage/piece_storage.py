from pathlib import Path

_DEFAULT_STORAGE_DIR = Path("data") / "peer_storage"

class PieceStorage:
    def __init__(self, storage_dir: Path | str = _DEFAULT_STORAGE_DIR) -> None:
        self._storage_dir = Path(storage_dir)

    def save_piece(self, index: int, data: bytes) -> None:
        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._piece_path(index)
        path.write_bytes(data)

    def load_piece(self, index: int) -> bytes:

        path = self._piece_path(index)
        if not path.exists():
            raise FileNotFoundError(
                f"Piece {index} not found at {path}"
            )
        return path.read_bytes()

    def has_piece(self, index: int) -> bool:

        return self._piece_path(index).is_file()


    def _piece_path(self, index: int) -> Path:

        return self._storage_dir / f"piece_{index}.bin"
