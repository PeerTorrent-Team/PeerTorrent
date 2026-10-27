import os
import tempfile
from pathlib import Path

from src.storage.paths import resolve_storage_root


class PieceStorage:
    def __init__(
        self,
        storage_dir: Path | str | None = None,
        *,
        peer_id: str | None = None,
        file_id: str | None = None,
    ) -> None:
        base_dir = resolve_storage_root(storage_dir)

        if peer_id is not None:
            base_dir = base_dir / peer_id

        if file_id is not None:
            base_dir = base_dir / file_id

        self._storage_dir = base_dir

    def _validate_index(self, index: int) -> None:
        if not isinstance(index, int) or isinstance(index, bool):
            raise TypeError("piece index must be an integer")

        if index < 0:
            raise ValueError("piece index must be non-negative")

    def save_piece(self, index: int, data: bytes) -> None:
        self._validate_index(index)

        if not isinstance(data, bytes):
            raise TypeError("piece data must be bytes")

        self._storage_dir.mkdir(parents=True, exist_ok=True)
        path = self._piece_path(index)

        with tempfile.NamedTemporaryFile(
            mode="wb",
            dir=str(self._storage_dir),
            prefix=f"piece_{index}_",
            suffix=".tmp",
            delete=False,
        ) as handle:
            handle.write(data)
            temp_path = Path(handle.name)

        os.replace(temp_path, path)

    def load_piece(self, index: int) -> bytes:
        self._validate_index(index)

        path = self._piece_path(index)
        if not path.exists():
            raise FileNotFoundError(
                f"Piece {index} not found at {path}"
            )
        return path.read_bytes()

    def has_piece(self, index: int) -> bool:
        self._validate_index(index)
        return self._piece_path(index).is_file()

    def _piece_path(self, index: int) -> Path:
        return self._storage_dir / f"piece_{index}.bin"
