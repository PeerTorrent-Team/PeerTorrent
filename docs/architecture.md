## Architecture Design

                         ┌─────────────────────────┐
                         │                         │
                         │     USER / CLIENT       │
                         │                         │
                         │  - Select File          │
                         │  - Start Download       │
                         │  - View Status          │
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │   PEERTORRENT PEER      │
                         │                         │
                         │  - Peer Controller      │
                         │  - Download Manager     │
                         │  - Upload Manager       │
                         │  - Scheduler            │
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │ METADATA & PIECE MANAGER│
                         │                         │
                         │  - File Metadata        │
                         │  - Piece Management     │
                         │  - Piece Selection      │
                         │  - Hash Information     │
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │     TRACKER SERVER      │
                         │                         │
                         │  - Peer Registry        │
                         │  - Swarm Tracking       │
                         │  - Peer Discovery       │
                         │                         │
                         └────────────┬────────────┘
                                      │
                              Peer List / Metadata
                                      │
                                      ▼
                    ┌────────────────────────────────────┐
                    │                                    │
                    │          PEER-TO-PEER NETWORK      │
                    │                                    │
                    └────────────────┬───────────────────┘
                                     │
                         Connection / Handshake
                                     │
                                     ▼
              ┌─────────────────────────────────────────────┐
              │                                             │
              │              PIECE EXCHANGE                 │
              │                                             │
              │   ┌──────────────┐     ┌──────────────┐     │
              │   │    PEER 1    │     │    PEER 2    │     │
              │   │    SEEDER    │◄───►│   LEECHER    │     │
              │   │              │     │              │     │
              │   │ Complete File│     │Partial File  │     │
              │   └──────────────┘     └──────────────┘     │
              │                                             │
              │   ┌──────────────┐     ┌──────────────┐     │
              │   │    PEER 3    │◄───►│    PEER 4    │     │
              │   │   LEECHER    │     │   LEECHER    │     │
              │   │              │     │              │     │
              │   │Missing Pieces│     │Missing Pieces│     │
              │   └──────────────┘     └──────────────┘     │
              │                                             │
              └────────────────────┬────────────────────────┘
                                   │
                                   ▼
                         ┌─────────────────────────┐
                         │                         │
                         │    HASH VERIFICATION    │
                         │                         │
                         │  - Verify Piece Hash    │
                         │  - Reject Invalid Data  │
                         │                         │
                         └────────────┬────────────┘
                                      │
                              Verified Pieces
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │      PIECE STORAGE      │
                         │                         │
                         │  - Store Pieces         │
                         │  - Track Availability   │
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │   FILE RECONSTRUCTION   │
                         │                         │
                         │  Pieces → Original File │
                         │                         │
                         └────────────┬────────────┘
                                      │
                                      ▼
                         ┌─────────────────────────┐
                         │                         │
                         │     COMPLETED FILE      │
                         │                         │
                         └─────────────────────────┘


## Folder Structure

PeerTorrent/
│
├── README.md
├── AI-USE.md
├── requirements.txt
├── pyproject.toml
│
│
├── docs/
│   ├── architecture.md
|   ├── Development_plan.txt
│   ├── protocol_specification.md
│   ├── message_format.md
│   ├── module_interfaces.md
│   ├── experiment_design.md
│   └── setup_guide.md
│
│
├── src/
│   ├── __init__.py
│   ├── main.py
│   │
│   │
│   ├── common/                              # SHARED — All Members
│   │   ├── __init__.py
│   │   ├── constants.py
│   │   ├── types.py
│   │   └── logger.py
│   │
│   │
│   ├── tracker/                             # MEMBER 2
│   │   ├── __init__.py
│   │   ├── tracker_server.py
│   │   ├── peer_registry.py
│   │   ├── swarm_manager.py
│   │   └── tracker_main.py
│   │
│   │
│   ├── protocol/                            # MEMBER 3
│   │   ├── __init__.py
│   │   ├── message.py
│   │   ├── message_types.py
│   │   ├── encoder.py
│   │   ├── decoder.py
│   │   └── handshake.py
│   │
│   │
│   ├── network/                             # MEMBER 3
│   │   ├── __init__.py
│   │   ├── socket_manager.py
│   │   ├── connection.py
│   │   └── connection_pool.py
│   │
│   │
│   ├── pieces/                              # MEMBER 1
│   │   ├── __init__.py
│   │   ├── metadata.py
│   │   ├── piece.py
│   │   ├── piece_manager.py
│   │   ├── verifier.py
│   │   └── hash_utils.py
│   │
│   │
│   ├── storage/                             # MEMBER 1
│   │   ├── __init__.py
│   │   ├── file_manager.py
│   │   └── piece_storage.py
│   │
│   │
│   ├── peer/                                # MEMBER 4
│   │   ├── __init__.py
│   │   ├── peer.py
│   │   ├── peer_state.py
│   │   ├── download_manager.py
│   │   ├── upload_manager.py
│   │   └── scheduler.py
│   │
│   │
│   ├── selection/                           # MEMBER 4
│   │   ├── __init__.py
│   │   ├── selector.py
│   │   ├── rarest_first.py
│   │   ├── random_selector.py
│   │   └── sequential_selector.py
│   │
│   │
│   └── extensions/                          # STRETCH GOALS
│       ├── __init__.py
│       │
│       ├── choking/
│       │   ├── __init__.py
│       │   └── choking_manager.py
│       │
│       ├── optimistic_unchoke/
│       │   ├── __init__.py
│       │   └── optimistic.py
│       │
│       ├── endgame/
│       │   ├── __init__.py
│       │   └── endgame_manager.py
│       │
│       ├── dht/
│       │   ├── __init__.py
│       │   └── dht_node.py
│       │
│       └── super_seed/
│           ├── __init__.py
│           └── super_seed.py
│
│
├── data/
│   ├── input_files/
│   │   └── .gitkeep
│   │
│   ├── metadata/
│   │   └── .gitkeep
│   │
│   ├── downloads/
│   │   └── .gitkeep
│   │
│   └── peer_storage/
│       └── .gitkeep
│
│
├── experiments/
│   ├── logs/
│   │   └── .gitkeep
│   │
│   ├── experiment_runner.py
│   ├── metrics.py
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