# Architecture

The PeerTorrent implementation is organized as a basic tracker-assisted peer-to-peer file distribution system. A tracker manages peer discovery, while individual peers coordinate connections, piece selection, verification, and file reconstruction.

## Current Project Structure

```text
PeerTorrent/
├── AI-USE.md
├── README.md
├── pyproject.toml
├── requirements.txt
├── data/
│   ├── downloads/
│   ├── input_files/
│   ├── metadata/
│   └── peer_storage/
├── docs/
│   ├── architecture.md
│   ├── Development_plan.txt
│   ├── experiment_design.md
│   ├── message_format.md
│   ├── module_interfaces.md
│   ├── protocol_specification.md
│   └── setup_guide.md
├── experiments/
├── src/
│   ├── main.py
│   ├── __init__.py
│   ├── common/
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── logger.py
│   │   └── types.py
│   ├── network/
│   │   ├── __init__.py
│   │   ├── connection.py
│   │   ├── connection_pool.py
│   │   └── socket_manager.py
│   ├── peer/
│   │   ├── __init__.py
│   │   ├── choking_manager.py
│   │   ├── download_manager.py
│   │   ├── peer.py
│   │   ├── peer_state.py
│   │   ├── request_manager.py
│   │   ├── scheduler.py
│   │   └── upload_manager.py
│   ├── pieces/
│   │   ├── __init__.py
│   │   ├── hash_utils.py
│   │   ├── metadata.py
│   │   ├── metadata_serializer.py
│   │   ├── piece.py
│   │   ├── piece_manager.py
│   │   └── verifier.py
│   ├── protocol/
│   │   ├── __init__.py
│   │   ├── decoder.py
│   │   ├── encoder.py
│   │   ├── handshake.py
│   │   ├── message.py
│   │   ├── message_types.py
│   │   └── ...
│   ├── selection/
│   │   ├── __init__.py
│   │   ├── random_selector.py
│   │   ├── rarest_first.py
│   │   ├── selector.py
│   │   └── sequential_selector.py
│   ├── storage/
│   │   ├── __init__.py
│   │   ├── file_manager.py
│   │   └── piece_storage.py
│   └── tracker/
│       ├── __init__.py
│       ├── peer_registry.py
│       ├── swarm_manager.py
│       ├── tracker.py
│       ├── tracker_client.py
│       ├── tracker_main.py
│       └── tracker_server.py
└── tests/
    ├── __init__.py
    ├── test_metadata.py
    ├── test_multi_peer.py
    ├── test_piece_manager.py
    ├── test_protocol.py
    └── test_tracker.py
```

## Runtime Components

- The entry point is [src/main.py](../src/main.py). It starts a peer with metadata, a peer ID, and a listening port.
- The peer runtime is implemented mainly in [src/peer/peer.py](../src/peer/peer.py) and coordinates connection lifecycle, protocol handling, scheduling, and state updates.
- Request tracking is handled by [src/peer/request_manager.py](../src/peer/request_manager.py), while choking policy logic lives in [src/peer/choking_manager.py](../src/peer/choking_manager.py).
- Piece metadata and hash-based verification are handled under [src/pieces](../src/pieces).
- Storage persistence is managed under [src/storage](../src/storage).
- Tracker discovery and peer registration are handled under [src/tracker](../src/tracker).

## Notes

The older placeholder `src/extensions/...` structure is not part of the current implementation and is not included in the active project layout.
│   ├── analyzer.py
│   │
│   └── plots/
│       ├── swarm_size.py
│       ├── strategy_compare.py
│       └── free_rider.py
│
│
├── tests/
│   ├── __init__.py
│   ├── test_metadata.py
│   ├── test_piece_manager.py
│   ├── test_protocol.py
│   ├── test_tracker.py
│   └── test_multi_peer.py
│
│
└── scripts/
    ├── run_tracker.sh
    ├── run_peer.sh
    └── run_experiment.sh