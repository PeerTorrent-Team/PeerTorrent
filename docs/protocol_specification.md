# Protocol Specification

This document defines how peers communicate in PeerTorrent during file sharing.

---

## 1. Protocol Overview

PeerTorrent uses TCP connections for communication between peers.

The basic protocol flow is:

```text id="k2q8qf"
Start Peer
    ↓
Connect to Tracker
    ↓
Get Peer List
    ↓
Connect to Other Peers
    ↓
Handshake
    ↓
Exchange Piece Availability
    ↓
Select Required Piece
    ↓
Request Piece
    ↓
Receive Piece
    ↓
Verify Piece
    ↓
Store Piece
    ↓
Repeat Until Complete
    ↓
Reconstruct File
```

---

## 2. Tracker Communication

The tracker is used for peer discovery. It does not transfer file pieces.

When a peer starts, it contacts the tracker and provides basic information about itself.

```text id="m1qv5b"
Peer → Tracker
    Register / Request Peers

Tracker → Peer
    List of Available Peers
```

The tracker maintains information about which peers are participating in a file's swarm.

---

## 3. Peer Connection

After receiving the peer list, the peer attempts to establish TCP connections with other peers.

```text id="wq6y6s"
Peer A ───────── TCP Connection ───────── Peer B
```

Each active connection is managed by the network module.

If a connection fails, the peer should continue operating and may attempt another connection.

---

## 4. Handshake

After establishing a connection, the peers exchange handshake messages.

```text id="5atxrl"
Peer A                         Peer B
  │                              │
  │────── HANDSHAKE ────────────>│
  │<───── HANDSHAKE ─────────────│
```

The handshake contains:

```text id="u5h4tq"
peer_id
file_id
```

A peer should verify that the received `file_id` corresponds to the file being shared before continuing.

---

## 5. Piece Availability

After the handshake, peers exchange their current piece availability.

```text id="qf1a5g"
Peer A                         Peer B
  │                              │
  │────── BITFIELD ─────────────>│
  │<───── BITFIELD ──────────────│
```

The bitfield indicates which pieces each peer currently has.

For example:

```text id="e8v9ki"
Peer A: 1 1 0 0 1 0
Peer B: 0 1 1 1 0 1
```

Peer A can request pieces `2`, `3`, or `5` from Peer B.

---

## 6. Interest

A peer compares the remote peer's available pieces with its own missing pieces.

If the remote peer has something it needs:

```text id="7klj9w"
Peer A → Peer B
INTERESTED
```

Otherwise:

```text id="5n3e9u"
Peer A → Peer B
NOT_INTERESTED
```

---

## 7. Choking and Unchoking

A peer may temporarily prevent another peer from requesting pieces using `CHOKE`.

```text id="6u2qla"
Peer A → Peer B
CHOKE
```

When requests are allowed again:

```text id="7n4z0d"
Peer A → Peer B
UNCHOKE
```

The initial implementation may keep this behavior simple. More advanced choking strategies can be added later through the `extensions/choking` module.

---

## 8. Piece Request

After a peer is interested and allowed to request pieces, it selects a required piece using the configured selection strategy.

It then sends:

```text id="a4g1ot"
REQUEST {
    piece_index
}
```

Example:

```text id="f3l6jh"
Peer A → Peer B
REQUEST {
    piece_index: 4
}
```

---

## 9. Piece Transfer

The receiving peer checks whether it has the requested piece.

If available, it sends:

```text id="0m6r5x"
PIECE {
    piece_index
    data
}
```

The basic exchange is:

```text id="1u9lrv"
Peer A                         Peer B
  │                              │
  │────── REQUEST(4) ───────────>│
  │                              │
  │<───── PIECE(4, data) ────────│
```

---

## 10. Piece Verification

After receiving a piece, the peer verifies its data using the expected piece hash stored in the metadata.

```text id="1j7r8p"
Received Data
     ↓
Calculate Hash
     ↓
Compare With Expected Hash
     ↓
 ┌───────────────┐
 │               │
Match          Mismatch
 │               │
 ↓               ↓
Store          Reject
Piece          Piece
```

A successfully verified piece is marked as complete.

If verification fails, the piece should not be stored as a valid piece.

---

## 11. Have Message

After successfully receiving and verifying a piece, the peer informs connected peers.

```text id="5k0q2v"
HAVE {
    piece_index
}
```

Example:

```text id="q0p4r9"
Peer A → Peer B
HAVE {
    piece_index: 4
}
```

This allows other peers to update their piece availability information.

---

## 12. Download Loop

The peer repeats the following process until all pieces are obtained:

```text id="s8k1cz"
Check Missing Pieces
       ↓
Check Peer Availability
       ↓
Select Piece
       ↓
Send REQUEST
       ↓
Receive PIECE
       ↓
Verify
       ↓
Store
       ↓
Send HAVE
       ↓
Repeat
```

The piece-selection strategy can be changed without changing the basic network protocol.

---

## 13. File Reconstruction

When all pieces have been successfully downloaded:

```text id="1x6jtc"
All Pieces Available
       ↓
Order Pieces by Index
       ↓
Combine Piece Data
       ↓
Reconstruct Original File
```

The reconstructed file is written to the configured download location.

---

## 14. Upload Flow

When another peer requests a piece, the upload process is:

```text id="v5d2lp"
Receive REQUEST
       ↓
Check Piece Exists
       ↓
Read Piece From Storage
       ↓
Create PIECE Message
       ↓
Encode Message
       ↓
Send to Peer
```

If the requested piece is unavailable, the peer should not send invalid piece data.

---

## 15. Connection Failure

If a peer connection is lost:

```text id="x0s5ge"
Connection Lost
      ↓
Remove Connection
      ↓
Update Peer State
      ↓
Continue With Other Peers
```

A single failed connection should not terminate the entire download.

---

## 16. Message Handling

All incoming messages follow this basic process:

```text id="j2c8wk"
Receive Bytes
     ↓
Decode Message
     ↓
Identify Message Type
     ↓
Validate Payload
     ↓
Handle Message
     ↓
Update Peer State
```

Invalid messages should be rejected safely.

---

## 17. Complete Communication Example

A simplified complete interaction is:

```text id="4h6z3s"
Peer A                         Tracker
  │                              │
  │──── Register / Request ─────>│
  │<────── Peer List ────────────│
  │                              │
  │
  │                         Peer B
  │                              │
  │────── HANDSHAKE ────────────>│
  │<───── HANDSHAKE ─────────────│
  │                              │
  │────── BITFIELD ─────────────>│
  │<───── BITFIELD ──────────────│
  │                              │
  │────── INTERESTED ───────────>│
  │<───── UNCHOKE ───────────────│
  │                              │
  │────── REQUEST ──────────────>│
  │<───── PIECE ─────────────────│
  │                              │
  │────── HAVE ─────────────────>│
  │                              │
  │       Repeat until complete  │
```

---

## 18. Protocol Rules

1. TCP is used for peer-to-peer communication.
2. A handshake must occur before normal piece exchange.
3. Peers must identify the file they are sharing.
4. Piece availability should be exchanged before selecting pieces.
5. A peer should request only pieces it does not already have.
6. Received pieces must be verified before being stored.
7. Successfully obtained pieces should be announced using `HAVE`.
8. Invalid messages or corrupted pieces should not crash the peer.
9. A failed peer connection should not stop the entire download.
10. The tracker is used for peer discovery and does not transfer file pieces.

---

## 19. Relationship With Other Modules

```text id="3a8f6v"
Tracker
   ↓
Peer Discovery

Network
   ↓
TCP Connections

Protocol
   ↓
Handshake + Message Encoding/Decoding

Piece Manager
   ↓
Piece State

Selection
   ↓
Next Piece

Storage
   ↓
Save / Load Pieces

Peer
   ↓
Coordinates Everything
```

The protocol defines **how peers communicate**, while `message_format.md` defines **what each message contains** and `module_interfaces.md` defines **how the software modules interact internally**.
