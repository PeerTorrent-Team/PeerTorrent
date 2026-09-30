=============================
Rajneesh
=============================

I worked on the M1 Pieces and Storage module and used AI assistance for understanding the project architecture and module interfaces, implementing and reviewing `hash_utils.py`, `metadata.py`, `piece.py`, and `piece_storage.py`, and for debugging and testing support. I also used AI assistance for implementing and reviewing `verifier.py`, debugging the import-resolution issue, and functional verification/testing support. I also used AI assistance for planning, implementing, and reviewing `file_manager.py`, and for debugging and implementation verification/testing support. I also used AI assistance for planning, reviewing, debugging, and testing support for `src/pieces/piece_manager.py`, including alignment with the documented PieceManager interface and existing Piece/PieceStorage modules. The final implementations and changes were reviewed and verified according to the project requirements.



=============================
Debjyoti
=============================

-> src/common/ 

AI was utilized as an aid for learning and development during the implementation of the `common` module. It assisted in providing explanations of some of the Python programming elements such as dataclasses, frozen dataclasses, type annotations, logging, handlers, formatters, and duplicate handler avoidance.

The code for the `common` module was implemented manually by the team member. AI was used to provide explanations of the design choices, suggest implementation, and assist in the process of testing the code.

-> src/tracker/

I worked on the tracker module, including `peer_registry.py`, `swarm_manager.py`, `tracker_client.py`, `tracker_main.py`, and `tracker_server.py`. I used AI assistance for understanding the tracker architecture and module interfaces, peer registration, swarm management, tracker-client communication, and the overall flow of tracker operations.

AI was also used for implementation support, debugging, code review, and testing assistance. It helped explain Python concepts and design choices, identify and resolve implementation issues, and suggest temporary test cases for verifying the tracker components. The final implementations and changes were reviewed and verified according to the project requirements.


=============================
Aritri
=============================

I worked on the initial project documentation and configuration files and used AI for preparing the README.md, requirements.txt, pyproject.toml, and architecture.md, for summarizing the project overview, learning dependencies, Python project configuration, and generating overall system architecture.

I completed the selection folder and used AI to understand what exactly each algorithm is doing. I used AI to generate temporary test cases to see if my algorithms worked properly. I also used AI to update module_interfaces.md for availability data representation defination.

I completed the core peer folder modules, including peer.py, peer_state.py, scheduler.py, download_manager.py, and upload_manager.py. I implemented the core structure and logic of these modules myself, using the project documentation and interfaces as the basis for their design and integration, while using AI as a support tool to understand the responsibilities and flow of each module, particularly how peer state, piece scheduling, downloading, uploading, and protocol message handling interact with the other project components. AI was also used to explain unfamiliar code concepts, review the implementation, identify potential issues, and help me understand how the other modules are related to this folder.







=============================
Ankit
=============================

I used AI as a support tool while developing the project documentation, protocol module, and network module. It helped me organize documents such as `Development_plan.txt`, `message_format.md`, `module_interfaces.md`, and `protocol_specification.md`, as well as understand and implement parts of `src/protocol/`, including message types, message handling, encoding, decoding, and handshaking. I also used it to understand and implement `src/network/`, including TCP socket management, peer connections, message sending and receiving, connection state handling, and connection pooling. AI was also used to clarify Python concepts, debug issues, and design and run small tests for the implemented modules. The final code, structure, and decisions were reviewed, understood, tested, and adapted by me according to the project requirements.

=============================
Rajneesh — M1 Integration
=============================

I carried out the M1 integration pass to align the Pieces and Storage modules with the integration version supplied by a teammate. AI assistance (Antigravity) was used to review the supplied integration version, identify file-level differences, plan the integration order, generate implementation prompts, review changes, and perform compilation and compatibility verification.

The M1 files aligned with the supplied integration version were:
- src/common/types.py
- src/pieces/hash_utils.py
- src/pieces/metadata.py
- src/pieces/metadata_serializer.py
- src/pieces/piece.py
- src/pieces/piece_manager.py
- src/pieces/verifier.py
- src/storage/file_manager.py
- src/storage/piece_storage.py

The integration work preserved the supplied architecture and interfaces. The final versions of all nine M1 source files were compared byte-for-byte with the supplied integration archive using cmp and matched exactly.

AI assistance was used for review, planning, implementation guidance, and verification. No claim should be made that AI independently authored the complete core BitTorrent protocol implementation. The existing pytest suite collected zero tests during validation, so no test cases were reported as passing.