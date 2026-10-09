# PeerTorrent

A Lightweight Peer-to-Peer File Sharing System Inspired by BitTorrent

## Overview

PeerTorrent is a modular peer-to-peer file sharing system that demonstrates BitTorrent-style distributed file transfer.

Files are divided into pieces. Peers exchange pieces directly, while a tracker is used only for peer discovery and swarm management.

## Core Features

-   File metadata generation
-   File piece splitting
-   Hash-based verification
-   Tracker-based peer discovery
-   Peer-to-peer communication
-   Upload and download management
-   Piece selection strategies
-   Performance experiments

## Architecture

                     Tracker
                        |
                Peer Discovery
                        |
         +--------------+--------------+
         |              |              |
       Peer A <------> Peer B <------> Peer C

              Direct Piece Exchange

## Main Modules

### Tracker

Handles peer registration, swarm management, and discovery through a threaded
HTTP/JSON API. The default listener is `http://127.0.0.1:6969`.

- `POST /announce` — register/update a peer and return other peers in its swarm.
- `GET /peers?peer_id=...&file_id=...` — fetch peers in a file's swarm.
- `GET /stats` — return peer, seeder, leecher, and transfer counters.
- `GET /health` — basic health check.

The tracker is for discovery only; file pieces are transferred directly between
peers over the peer wire protocol.

### Protocol and Network

Handles messages, encoding, decoding, handshake, sockets, and connections.

### Pieces and Storage

Handles metadata, pieces, hashing, verification, storage, and reconstruction.

### Peer System

Handles downloading, uploading, scheduling, selection, and integration.

## Team Responsibilities

Member 1: Pieces and Storage

Member 2: Tracker and Peer Discovery

Member 3: Protocol and Network Communication

Member 4: Peer Logic and System Integration

## Installation

``` bash
pip install -r requirements.txt
```

Developer installation:

``` bash
pip install .[dev]
```

## Running

Create metainfo and prepare the seeder's piece store first:

```bash
python scripts/create_metadata.py data/input_files/sample.bin \
    --output data/metadata/sample.bin.json
python scripts/seed_file.py \
    --file data/input_files/sample.bin \
    --metadata data/metadata/sample.bin.json \
    --peer-id seed1
```

Start the tracker in one terminal:

```bash
python -m src.tracker.tracker_main
```

Start the seeder in a second terminal, then start downloaders with different peer
IDs and ports:

```bash
python -m src.main --peer-id seed1 --metadata data/metadata/sample.bin.json --port 6881
python -m src.main --peer-id peer2 --metadata data/metadata/sample.bin.json --port 6882
```

After a downloader has acquired all pieces, reconstruct and verify its output:

```bash
python scripts/verify_download.py \
    --metadata data/metadata/sample.bin.json \
    --peer-id peer2 \
    --output data/downloads/sample.bin
```

## Testing

``` bash
pytest
```

## Experiments

Experiments evaluate:

-   Download completion time
-   Upload contribution
-   Swarm size
-   Piece selection strategies

Strategies:

-   Sequential
-   Random
-   Rarest-first

## Development Workflow

    Design Interfaces
            |
    Parallel Development
            |
    Module Testing
            |
    Integration
            |
    Multi-peer Testing
            |
    Experiment Analysis

## AI Usage

AI usage is documented in AI-USE.md. AI is used only for documentation, debugging support, explanations, and testing assistance.

## Future Extensions

-   Choking mechanism
-   Optimistic unchoking
-   End-game mode
-   DHT
-   Super seeding

## Conclusion

PeerTorrent demonstrates the fundamentals of distributed peer-to-peer file sharing by allowing peers to cooperate in transferring files efficiently.
