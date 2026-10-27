from __future__ import annotations

from pathlib import Path

from src.storage.paths import (
    DEFAULT_STORAGE_ROOT,
    PROJECT_ROOT,
    resolve_storage_root,
)
from src.storage.piece_storage import PieceStorage


def test_default_storage_root_reuses_existing_project_tree() -> None:
    assert DEFAULT_STORAGE_ROOT == PROJECT_ROOT / "data" / "peer_storage"
    assert DEFAULT_STORAGE_ROOT.is_dir()
    assert resolve_storage_root() == DEFAULT_STORAGE_ROOT.resolve()


def test_environment_and_relative_roots_are_resolved_consistently(
    tmp_path: Path, monkeypatch
) -> None:
    custom_root = tmp_path / "peerstorage"
    (custom_root / "peer1").mkdir(parents=True)
    marker = custom_root / "peer1" / "keep.txt"
    marker.write_text("existing peer folder", encoding="utf-8")
    monkeypatch.setenv("PEERTORRENT_STORAGE_ROOT", str(custom_root))

    store = PieceStorage(peer_id="peer1", file_id="file-id")
    store.save_piece(0, b"piece")

    assert resolve_storage_root() == custom_root.resolve()
    assert (custom_root / "peer1" / "keep.txt").read_text(encoding="utf-8") == "existing peer folder"
    assert (custom_root / "peer1" / "file-id" / "piece_0.bin").read_bytes() == b"piece"
    assert not (PROJECT_ROOT / "data" / "data" / "peer_storage").exists()


def test_explicit_relative_storage_path_is_project_root_relative(
    tmp_path: Path, monkeypatch
) -> None:
    monkeypatch.chdir(tmp_path)

    assert resolve_storage_root("data/peer_storage") == DEFAULT_STORAGE_ROOT.resolve()
