"""High-level seeding and downloaded-file verification workflows.

This module joins the existing metainfo, piece storage, and reconstruction
components without coupling them to CLI argument parsing.
"""

from __future__ import annotations

import hashlib
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from src.common.types import FileMetadata
from src.pieces.hash_utils import calculate_file_hash
from src.pieces.metadata import calculate_file_id
from src.pieces.verifier import verify_piece
from src.storage.file_manager import reconstruct_file
from src.storage.paths import resolve_project_path, resolve_storage_root
from src.storage.piece_storage import PieceStorage


def seed_source_file(
    source_path: str | Path,
    metadata: FileMetadata,
    peer_id: str,
    storage_root: str | Path | None = None,
) -> PieceStorage:
    """Validate a source file against metainfo and populate a seeder's store.

    The input is first checked and staged in a temporary directory. No pieces
    are copied into the peer's permanent storage until every piece and the
    optional whole-file hash have passed verification.
    """
    if not isinstance(peer_id, str) or not peer_id.strip():
        raise ValueError("peer_id must be a non-empty string")

    source = resolve_project_path(source_path)
    if not source.is_file():
        raise FileNotFoundError(f"Source file not found: {source}")

    if source.stat().st_size != metadata.file_size:
        raise ValueError(
            "Source file size does not match metainfo: "
            f"expected {metadata.file_size}, got {source.stat().st_size}"
        )

    root = resolve_storage_root(storage_root)
    root.mkdir(parents=True, exist_ok=True)

    # Stage validated pieces outside the permanent peer store. This prevents a
    # mismatched source file from leaving a partially initialized seeder.
    with TemporaryDirectory(prefix=".peertorrent-seed-", dir=root) as staging_dir:
        staging = PieceStorage(staging_dir)
        digest = hashlib.sha256()
        bytes_read = 0

        with source.open("rb") as handle:
            for info in metadata.pieces:
                data = handle.read(info.size)
                if len(data) != info.size:
                    raise ValueError(
                        f"Source ended while reading piece {info.index}: "
                        f"expected {info.size} bytes, got {len(data)}"
                    )
                if not verify_piece(data, info.hash):
                    raise ValueError(
                        f"Source piece {info.index} does not match metainfo hash"
                    )

                staging.save_piece(info.index, data)
                digest.update(data)
                bytes_read += len(data)

            if handle.read(1):
                raise ValueError("Source contains more bytes than metainfo describes")

        if bytes_read != metadata.file_size:
            raise ValueError(
                f"Source byte count does not match metainfo: "
                f"expected {metadata.file_size}, got {bytes_read}"
            )

        if metadata.file_hash is not None:
            actual_file_hash = digest.hexdigest()
            if actual_file_hash.lower() != metadata.file_hash.lower():
                raise ValueError(
                    "Source file hash does not match metainfo: "
                    f"expected {metadata.file_hash}, got {actual_file_hash}"
                )

        file_id = calculate_file_id(metadata)
        destination = PieceStorage(
            storage_dir=root,
            peer_id=peer_id,
            file_id=file_id,
        )
        for info in metadata.pieces:
            destination.save_piece(info.index, staging.load_piece(info.index))

    return destination


def verify_downloaded_file(
    metadata: FileMetadata,
    storage: PieceStorage,
    output_path: str | Path,
) -> Path:
    """Verify every stored piece and reconstruct the complete output file.

    Reconstruction is performed to a temporary file first. The requested
    output path is replaced only after piece hashes, the total file size, and
    the optional whole-file hash all pass.
    """
    verified_pieces: list[tuple[int, bytes]] = []

    for info in metadata.pieces:
        try:
            data = storage.load_piece(info.index)
        except FileNotFoundError as exc:
            raise FileNotFoundError(
                f"Cannot verify download: piece {info.index} is missing"
            ) from exc

        if len(data) != info.size:
            raise ValueError(
                f"Piece {info.index} has the wrong size: "
                f"expected {info.size}, got {len(data)}"
            )
        if not verify_piece(data, info.hash):
            raise ValueError(f"Piece {info.index} failed SHA-256 verification")

        verified_pieces.append((info.index, data))

    output = resolve_project_path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    # Keep the temporary file in the destination directory so os.replace is
    # atomic on the same filesystem and any previous output survives failure.
    with TemporaryDirectory(
        prefix=".peertorrent-verify-", dir=output.parent
    ) as temporary_dir:
        candidate = Path(temporary_dir) / output.name
        reconstruct_file(verified_pieces, str(candidate))

        actual_size = candidate.stat().st_size
        if actual_size != metadata.file_size:
            raise ValueError(
                f"Reconstructed file size mismatch: expected "
                f"{metadata.file_size}, got {actual_size}"
            )

        if metadata.file_hash is not None:
            actual_hash = calculate_file_hash(str(candidate))
            if actual_hash.lower() != metadata.file_hash.lower():
                raise ValueError(
                    "Reconstructed file hash mismatch: "
                    f"expected {metadata.file_hash}, got {actual_hash}"
                )

        os.replace(candidate, output)

    return output
