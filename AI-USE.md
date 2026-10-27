# AI-USE.md

This file explains how each team member used AI tools during the development of the PeerTorrent project. We used AI mainly to understand concepts, debug errors, improve code, write tests, and review our implementation. We checked the generated suggestions and modified them according to our project requirements.

## 1. Rajneesh — Pieces and Storage

I worked mainly on the pieces and storage part of the project. I used AI tools to understand the implementation, debug errors, write unit tests, and check whether the modules were working correctly.

### Files and modules

- `src/pieces/hash_utils.py`
- `src/pieces/metadata.py`
- `src/pieces/piece.py`
- `src/pieces/piece_storage.py`
- `src/pieces/verifier.py`
- `src/pieces/piece_manager.py`
- `src/storage/file_manager.py`

I also worked on fixing import-resolution issues and making sure the modules could work together properly.

### Integration with Antigravity

I used Antigravity to help with integration and verification. I compared the following nine files with the integration archive using `cmp`:

- `src/common/types.py`
- `src/pieces/hash_utils.py`
- `src/pieces/metadata.py`
- `src/pieces/metadata_serializer.py`
- `src/pieces/piece.py`
- `src/pieces/piece_manager.py`
- `src/pieces/verifier.py`
- `src/storage/file_manager.py`
- `src/storage/piece_storage.py`

All nine files matched the integration archive byte-for-byte. During one integration check, pytest collected zero tests, so further testing was needed.

### Unit testing

I used AI assistance while developing and reviewing tests for:

- `tests/test_metadata.py`
- `tests/test_piece_manager.py`

The test suite for this work had 12 passing tests.

### File seeding and verification

I also worked on the file seeding and verification workflow.

In `src/storage/file_workflow.py`, I implemented:

- `seed_source_file`
- `verify_downloaded_file`

I worked on the following CLI scripts:

- `scripts/seed_file.py`
- `scripts/verify_download.py`
- `scripts/create_metadata.py`

I used AI assistance to debug the `mock_storage` fixture in `tests/test_piece_manager.py` and to write tests in `tests/test_file_workflow.py`. These tests covered piece staging, rollback of corrupted pieces, hash verification, and peer startup.

I also updated the documentation in:

- `README.md`
- `docs/setup_guide.md`
- `docs/member1_pieces_storage_handoff.md`

AI helped me understand errors and review the implementation, but I checked and adjusted the code to fit the project's requirements.

## 2. Debjyoti — Common Modules and Tracker

I worked mainly on the common modules and the tracker part of the project. I used AI tools to understand the code structure, improve implementation, and help with testing and debugging.

### Common modules

I worked in the `src/common/` directory. AI helped me understand and use:

- Dataclasses and frozen dataclasses
- Type annotations
- Logging
- Log handlers and formatters
- How to avoid adding duplicate logging handlers

I reviewed the suggestions and adjusted them to match the project's existing structure.

### Tracker modules

I worked on the following tracker files:

- `peer_registry.py`
- `swarm_manager.py`
- `tracker_client.py`
- `tracker_main.py`
- `tracker_server.py`

AI helped me understand the tracker workflow, debug problems, and review how peers register and communicate with the tracker.

### Testing

I also worked with `tests/test_tracker.py`. AI assistance helped me review test cases, understand failures, and check whether the tracker modules behaved as expected.

I used AI as a support tool for learning, debugging, and reviewing the code. I checked the final implementation against the project requirements.

## 3. Aritri — Project Setup and Peer Management

I worked on the initial project setup, documentation, configuration, and peer-management modules. I used AI tools to understand the architecture, organize the project, and review the implementation.

### Project setup and documentation

I worked on the following files:

- `README.md`
- `requirements.txt`
- `pyproject.toml`
- `architecture.md`

AI helped me organize the initial project structure, understand dependencies, and improve the documentation.

### Module selection and interfaces

I worked on the selection folder and temporary tests during development. I also worked on `module_interfaces.md`, especially the representation of availability data between modules.

AI helped me understand how the modules should communicate and how the interfaces could be kept consistent.

### Peer-management modules

I worked on the following peer-related files:

- `peer.py`
- `peer_state.py`
- `scheduler.py`
- `download_manager.py`
- `upload_manager.py`

I implemented the main structure and logic of these modules, using AI support to understand concepts, review code, and debug problems.

AI suggestions were useful for learning and checking my approach, but I reviewed and adapted the implementation to fit the project's design.

## 4. Ankit — Protocol and Network

I worked mainly on the protocol and network parts of PeerTorrent. I used AI tools to understand protocol concepts, debug implementation issues, and test the communication between peers.

### Documentation

I worked on the following documentation files:

- `Development_plan.txt`
- `message_format.md`
- `module_interfaces.md`
- `protocol_specification.md`

AI helped me organize technical information and understand how the protocol and network modules should interact.

### Protocol modules

I worked in `src/protocol/`, focusing on:

- Message types and message handling
- Message encoding and decoding
- Peer handshaking

AI helped me understand the message format and review the implementation for consistency with the protocol specification.

### Network modules

I worked in `src/network/`, focusing on:

- TCP socket management
- Peer connections
- Sending and receiving messages
- Connection state management
- Connection pooling

I used AI assistance to understand networking concepts, debug errors, and create small tests to check specific behaviours.

I reviewed and adapted the generated suggestions before using them in the project. The final implementation was checked against the project's protocol and networking requirements.

## General Note

All four members used AI as a supporting tool during development. It helped us learn unfamiliar concepts, understand errors, review code, and develop tests. We checked the suggestions and modified them where necessary to match our project requirements.

AI assistance did not replace our responsibility for understanding, reviewing, and integrating our work. Each member was responsible for their assigned modules and for checking the code they contributed.