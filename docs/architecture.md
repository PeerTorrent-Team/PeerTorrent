# PeerTorrent Architecture

PeerTorrent is a tracker-assisted, peer-to-peer file distribution system inspired by BitTorrent. The tracker supports peer discovery and swarm membership. Peers connect directly to one another to exchange file pieces.

The system is divided into modules for peer coordination, networking, protocol messages, piece selection, integrity verification, and storage.

## 1. Architecture Diagram

```text
                      +---------------------------+
                      |         User / CLI        |
                      +---------------------------+
                                   |
                                   v
                      +---------------------------+
                      |        src/main.py        |
                      +---------------------------+
                                   |
                                   v
                      +---------------------------+
                      |   src/peer/peer.py        |
                      |       Peer Runtime        |
                      +---------------------------+
                                   |
              +--------------------+--------------------+
              |                    |                    |
              v                    v                    v
 +------------------------+ +---------------------+ +----------------------+
 | Tracker Communication  | | Network Connections | | Piece Selection      |
 | src/tracker/            | | src/network/         | | src/selection/       |
 | tracker_main.py         | |                     | |                      |
 +------------------------+ +---------------------+ +----------------------+
              |                    |                    |
              v                    v                    v
 +------------------------+ +---------------------+ +----------------------+
 | HTTP Tracker API       | | Protocol Handling   | | scheduler.py         |
 | Peer Registry          | | src/protocol/       | | request_manager.py   |
 | Swarm Manager           | |                     | |                      |
 +------------------------+ +---------------------+ +----------------------+
                                   |
                        +----------+----------+
                        |                     |
                        v                     v
             +----------------------+ +----------------------+
             | Download Manager     | | Upload Manager       |
             | download_manager.py   | | upload_manager.py    |
             +----------------------+ +----------------------+
                        |                     |
                        v                     v
             +----------------------+ +----------------------+
             | Piece Manager         | | Piece Storage        |
             | src/pieces/           | | src/storage/         |
             +----------------------+ +----------------------+
                        |
                        v
             +----------------------+
             | Hash Verification    |
             | src/pieces/          |
             +----------------------+
                        |
                        v
             +----------------------+
             | Verified Piece       |
             | Storage              |
             +----------------------+
                        |
                        v
             +----------------------+
             | File Reconstruction  |
             | src/storage/         |
             +----------------------+
                        |
                        v
             +----------------------+
             |   Completed File     |
             |   data/downloads/    |
             +----------------------+


                  PEER-TO-PEER COMMUNICATION

        +---------------------+       +---------------------+
        |       Peer A        |<----->|       Peer B        |
        | src/peer/peer.py    |  TCP  | src/peer/peer.py    |
        +---------------------+       +---------------------+
                   |                            |
                   +-------------+--------------+
                                 |
                                 v
                    +--------------------------+
                    |       HTTP Tracker       |
                    | src/tracker/             |
                    | tracker_main.py          |
                    +--------------------------+
```

The diagram shows the main responsibilities and communication paths. It is a conceptual view; individual calls and control flow may involve additional module interactions.

## 2. Main Components

### 2.1 Entry Point

`src/main.py` starts a peer using its peer ID, listening port, and either a metadata file or a catalog entry, depending on the selected startup mode.

The peer runtime coordinates connections, protocol handling, peer state, piece selection, downloading, and uploading.

### 2.2 Tracker

The tracker implementation lives under `src/tracker/`. It provides peer registration and discovery and maintains file-specific swarm membership.

The tracker exposes an HTTP/JSON API. The documented endpoints include:

- `GET /health` — basic health check.
- `GET /stats` — tracker statistics.
- `GET /peers` — retrieve peers for a file swarm.
- `POST /announce` — register or update a peer and retrieve peers in its swarm.

The default tracker address is `http://127.0.0.1:6969`.

The tracker does **not** transfer file pieces. Once peers discover one another, piece data is exchanged directly between peer processes.

### 2.3 Peer Runtime

The peer implementation is centered on `src/peer/peer.py`.

The peer coordinates:

- Tracker communication and peer discovery.
- Peer connections and protocol messages.
- Peer state and request tracking.
- Download and upload management.
- Piece selection and scheduling.
- Piece availability updates.

Related modules include `download_manager.py`, `upload_manager.py`, `request_manager.py`, `scheduler.py`, `peer_state.py`, and `choking_manager.py`.

### 2.4 Network and Protocol

The `src/network/` package handles socket operations, peer connections, and connection pooling.

The `src/protocol/` package defines the peer message representation, message types, handshake, encoding, and decoding.

The documented peer protocol uses TCP connections. Messages include `HANDSHAKE`, `BITFIELD`, `HAVE`, `REQUEST`, `PIECE`, `CANCEL`, `INTERESTED`, `NOT_INTERESTED`, `CHOKE`, and `UNCHOKE`.

The peer wire protocol and the tracker's HTTP API are separate communication paths.

### 2.5 Piece Selection

The `src/selection/` package provides alternative strategies for choosing the next piece to request:

- **Sequential** — selects pieces in sequential order.
- **Random** — selects an available required piece randomly.
- **Rarest-first** — prioritizes required pieces that are available from fewer connected peers.

The selection strategy determines which piece to request; the peer and download-management components handle the surrounding transfer process.

### 2.6 Pieces, Verification, and Storage

The `src/pieces/` package handles piece and metadata representations, hashing, piece management, and verification.

The `src/storage/` package manages persistent piece storage and file operations.

The general data flow is:

1. Metadata describes the source file, piece size, and expected piece hashes.
2. A peer identifies pieces it needs and pieces available from other peers.
3. The peer requests a piece from another peer.
4. The received data is checked against the expected hash.
5. Verified pieces are stored and peer availability is updated.
6. Once all required pieces are available, the pieces can be reconstructed into the original file.

A completed download should be verified against its metadata and, where configured, the whole-file hash.

## 3. End-to-End Communication Flow

```text
        DOWNLOADING PEER                 TRACKER
       +----------------+          +----------------+
       |    Peer A      |--------->|  HTTP API      |
       +----------------+ Announce +----------------+
               ^                           |
               |                           v
               |                    +----------------+
               +--------------------| Peer Discovery |
                     Peer List      +----------------+

       +----------------+             +----------------+
       |    Peer A      |<----------->|     Peer B     |
       +----------------+    TCP      +----------------+
               |                              |
               | REQUEST(piece_index) ------->|
               |                              |
               |<------- PIECE(piece, data) ---|
               |
               v
       +----------------+
       | Verify Piece   |
       +----------------+
               |
               v
       +----------------+
       | Store Piece    |
       +----------------+
```

This sequence illustrates the expected protocol flow. Actual message ordering depends on peer state, piece availability, and connection behavior.

## 4. Repository Layout

The principal directories and files are:

```text
PeerTorrent/
├── README.md
├── pyproject.toml
├── requirements.txt
├── configs/
│   ├── file_catalog.json
│   └── swarm_config.json
├── data/
│   ├── downloads/
│   ├── input_files/
│   ├── metadata/
│   └── peer_storage/
├── docs/
│   ├── architecture.md
│   ├── dynamic_files.md
│   ├── experiment_design.md
│   ├── message_format.md
│   ├── module_interfaces.md
│   ├── protocol_specification.md
│   ├── setup_guide.md
│   └── Development_plan.txt
├── experiments/
├── scripts/
├── src/
│   ├── main.py
│   ├── common/
│   ├── network/
│   ├── peer/
│   ├── pieces/
│   ├── protocol/
│   ├── selection/
│   ├── storage/
│   └── tracker/
└── tests/
```

This is a high-level layout, not an exhaustive listing of every file. The repository may also contain additional experiment outputs, helper scripts, and test modules.

## 5. Key Design Boundaries

- **Tracker vs. peer transfer:** the tracker provides discovery and swarm membership; peers exchange pieces directly.
- **Protocol vs. transport:** the protocol defines peer messages, while the network layer manages TCP connections and message transport.
- **Selection vs. downloading:** a selector chooses a piece; download management coordinates requesting and processing it.
- **Verification vs. persistence:** piece data should be verified before it is treated as valid downloaded content.
- **Runtime vs. experiments:** peer execution is implemented under `src/`; experiment scripts and results are organized separately.

## 6. Scope Notes

PeerTorrent is a BitTorrent-inspired implementation, not a claim of compatibility with the full BitTorrent protocol.

For detailed message fields and wire framing, see `message_format.md` and `protocol_specification.md`. For installation and runnable examples, see `setup_guide.md` and the repository `README.md`. For the experiment configuration and file-swapping workflow, see `dynamic_files.md`.