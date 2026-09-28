import hashlib
from typing import Union


def calculate_hash(data: bytes) -> str:
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.hexdigest()


def calculate_hash_bytes(data: bytes) -> bytes:
    hasher = hashlib.sha256()
    hasher.update(data)
    return hasher.digest()


def calculate_file_hash(file_path: str, chunk_size: int = 65536) -> str:
    if chunk_size <= 0:
        raise ValueError("chunk_size must be greater than 0")

    hasher = hashlib.sha256()
    with open(file_path, 'rb') as f:
        for chunk in iter(lambda: f.read(chunk_size), b''):
            hasher.update(chunk)
    return hasher.hexdigest()


def verify_hash(data: bytes, expected_hash: Union[str, bytes]) -> bool:
    if isinstance(expected_hash, bytes):
        return calculate_hash_bytes(data) == expected_hash
    elif isinstance(expected_hash, str):
        return calculate_hash(data).lower() == expected_hash.lower()
    else:
        raise TypeError("expected_hash must be either a string or bytes")
