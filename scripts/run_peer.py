"""
Start a PeerTorrent peer.

Example:
    python scripts/run_peer.py \
        --peer-id peer1 \
        --metadata data/metadata/file.json \
        --port 6881
"""

from src.main import main


if __name__ == "__main__":
    main()