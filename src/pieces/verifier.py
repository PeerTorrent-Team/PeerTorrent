from .hash_utils import verify_hash


def verify_piece(data: bytes, expected_hash: str) -> bool:
    """Return True if the SHA-256 hash of *data* matches *expected_hash*."""
    return verify_hash(data, expected_hash)
