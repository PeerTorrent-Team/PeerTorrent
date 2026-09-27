# Experiment Design

## Objective

The objective is to evaluate the PeerTorrent implementation for reliable peer discovery,
piece exchange, integrity verification, and file reconstruction.

## Experimental Setup

The experiment uses:

- One tracker
- Two or more PeerTorrent peers
- The same metadata file for participating peers
- A shared test file divided into pieces
- Separate listening ports for each peer

Example:

```text
Tracker
   |
   +---- Peer A
   |
   +---- Peer B
```

## Procedure

1. Start the tracker.
2. Start Peer A with the required metadata and listening port.
3. Start Peer B with the same metadata and a different listening port.
4. Allow the peers to register with the tracker.
5. Allow peers to discover and establish connections.
6. Exchange pieces between peers.
7. Verify the integrity of received pieces using their expected hashes.
8. Reconstruct the complete file.
9. Compare the reconstructed file with the original file.

## Measurements

Record the following:

* Peer registration success
* Peer discovery success
* Connection establishment
* Number of pieces transferred
* Piece verification success/failure
* File reconstruction success
* Transfer completion time
* Connection/request failures

## Expected Results

A successful experiment should demonstrate that:

* Peers can register with the tracker.
* Peers can discover other peers.
* Peers can establish connections.
* Required pieces can be requested and transferred.
* Received pieces pass integrity verification.
* The complete file can be reconstructed correctly.
* Previously stored pieces can be recovered after a peer restart.

## Reproducibility

The experiment should be repeated with the same metadata and test file while
keeping peer ports distinct. Results should be recorded using the measurements
listed above.
