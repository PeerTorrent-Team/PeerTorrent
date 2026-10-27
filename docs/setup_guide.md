# PeerTorrent Setup Guide

This guide covers installing PeerTorrent, preparing a source file, starting the tracker and peers, and verifying a downloaded file.

Run commands from the project root unless otherwise stated.

## Requirements

- Python 3.10 or newer.
- The project dependencies listed in `requirements.txt`.

## 1. Install Dependencies

Install the standard dependencies:

```bash
python -m pip install -r requirements.txt
```

For development tools such as Black and Flake8, install the project with its development extra:

```bash
python -m pip install ".[dev]"
```

## 2. Create Metadata

Place the source file in the project or choose an existing file. This example assumes the source is `data/input_files/sample.bin`.

```bash
python scripts/create_metadata.py data/input_files/sample.bin \
    --output data/metadata/sample.bin.json
```

Generate metadata from the exact file you intend to share. If the source file changes, regenerate its metadata.

## 3. Prepare the Seeder

Prepare the seeder's persistent piece storage:

```bash
python scripts/seed_file.py \
    --file data/input_files/sample.bin \
    --metadata data/metadata/sample.bin.json \
    --peer-id seed1
```

The source file and metadata must correspond. The preparation workflow checks the source data against the metadata before publishing pieces to the peer's storage.

## 4. Start the Tracker

In the first terminal, run:

```bash
python -m src.tracker.tracker_main
```

The default HTTP tracker address is `http://127.0.0.1:6969`.

The documented endpoints include:

- `GET /health` — liveness check.
- `GET /stats` — tracker statistics.
- `GET /peers` — retrieve peers for a file swarm.
- `POST /announce` — register/update a peer and retrieve discovered peers.

You can check the default health endpoint in a browser or with a command-line HTTP client:

```text
http://127.0.0.1:6969/health
```

## 5. Start the Seeder

In a second terminal, run:

```bash
python -m src.main \
    --peer-id seed1 \
    --metadata data/metadata/sample.bin.json \
    --port 6881
```

Keep the tracker and seeder running while a downloader is joining the swarm.

## 6. Start a Downloader

In a third terminal, use the same metadata but a different peer ID and listening port:

```bash
python -m src.main \
    --peer-id peer2 \
    --metadata data/metadata/sample.bin.json \
    --port 6882
```

Each peer process should use a unique peer ID and listening port. Additional downloaders can be started in separate terminals in the same way.

The tracker is responsible for discovery; peers transfer pieces directly to one another over TCP.

## 7. Reconstruct and Verify the Download

After the downloader has acquired all pieces, run:

```bash
python scripts/verify_download.py \
    --metadata data/metadata/sample.bin.json \
    --peer-id peer2 \
    --output data/downloads/sample.bin
```

If you started the peer with a custom storage root, pass the corresponding storage option supported by the verifier so it reads the correct piece store.

The verification workflow checks piece sizes and SHA-256 hashes, reconstructs the file, and checks the resulting file against the metadata before writing the final output.

A successful peer startup does not prove that a transfer completed. Confirm that all pieces have been obtained and that reconstruction and verification succeed.

## 8. Run the Tests

From the project root:

```bash
python -m pytest
```

Compile-check the source:

```bash
python -m compileall src
```

## Troubleshooting

- **Tracker connection fails:** confirm the tracker is running and that the peer uses the correct tracker host and port.
- **Peer discovery returns no peers:** confirm that another peer is running, has announced the same file ID, and uses compatible metadata.
- **A piece is rejected:** regenerate metadata from the actual source file and verify that the source and metadata match.
- **The final file cannot be reconstructed:** check whether the download has all required pieces and whether the verifier is pointed at the correct peer storage root.
- **A port is already in use:** choose another available listening port for the peer.

For multi-file swarm preparation and interactive file switching, see `dynamic_files.md`. For the overall architecture and protocol details, see `architecture.md` and `protocol_specification.md`.