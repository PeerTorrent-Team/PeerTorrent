# Setup Guide

## Requirements

Python 3.10 or newer is recommended.

## Installation

Clone or extract the PeerTorrent project and enter the project directory:

```bash
cd PeerTorrent
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Create Metainfo and Prepare a Seeder

From the project root, create metainfo for the file you want to share:

```bash
python scripts/create_metadata.py data/input_files/sample.bin \
    --output data/metadata/sample.bin.json
```

Prepare the seeder's local piece storage from that exact source file. This checks
every piece hash and the optional whole-file hash before publishing the pieces to
the peer's permanent storage:

```bash
python scripts/seed_file.py \
    --file data/input_files/sample.bin \
    --metadata data/metadata/sample.bin.json \
    --peer-id seed1
```

## Start the Tracker and Seeder

Start the tracker in one terminal:

```bash
python -m src.tracker.tracker_main
```

Start the seeded peer in a second terminal:

```bash
python -m src.main --peer-id seed1 --metadata data/metadata/sample.bin.json --port 6881
```

Start each downloader with a unique peer ID and port, using the same metainfo.
For example, in another terminal:

```bash
python -m src.main --peer-id peer2 --metadata data/metadata/sample.bin.json --port 6882
```

After the downloader has received all pieces, reconstruct and verify its stored
pieces. Use the same `--storage` root used when starting that peer if you
customized the storage path:

```bash
python scripts/verify_download.py \
    --metadata data/metadata/sample.bin.json \
    --peer-id peer2 \
    --output data/downloads/sample.bin
```

The verifier checks each piece's size and SHA-256 hash, reconstructs the file,
checks the final size and whole-file hash, and only then writes the final output.

## Verify Installation

Run the test suite:

```bash
pytest
```

Compile-check the source:

```bash
python -m compileall src
```
