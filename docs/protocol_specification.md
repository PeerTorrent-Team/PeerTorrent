# Message Format

This document defines the basic structure and format of messages exchanged between peers in PeerTorrent.

---

## 1. General Message Structure

Every P2P message contains two main parts:

```text
Message
├── type
└── payload
```

* `type` — Identifies what the message is used for.
* `payload` — Contains the data required for that message.

Messages are converted into bytes before being sent through a TCP connection.

---

## 2. Message Types

The main message types are:

| Message          | Purpose                                            |
| ---------------- | -------------------------------------------------- |
| `HANDSHAKE`      | Establishes communication between two peers        |
| `BITFIELD`       | Tells a peer which pieces are available            |
| `HAVE`           | Announces that a peer has obtained a new piece     |
| `REQUEST`        | Requests a specific piece from another peer        |
| `PIECE`          | Sends the requested piece data                     |
| `INTERESTED`     | Indicates interest in pieces held by another peer  |
| `NOT_INTERESTED` | Indicates that no required pieces are available    |
| `CHOKE`          | Temporarily prevents a peer from requesting pieces |
| `UNCHOKE`        | Allows a peer to request pieces                    |

---

## 3. Message Representation

A message can be represented internally as:

```text
Message {
    type: <message_type>
    payload: <message_data>
}
```

For example:

```text
Message {
    type: REQUEST
    payload: {
        piece_index: 4
    }
}
```

The exact Python representation can be implemented by the protocol module.

---

## 4. Handshake Message

The handshake is the first message exchanged between two peers.

```text
HANDSHAKE {
    peer_id
    file_id
}
```

* `peer_id` identifies the sending peer.
* `file_id` identifies the file being shared.

A peer should validate the handshake before continuing with normal communication.

---

## 5. Bitfield Message

The bitfield tells another peer which pieces are currently available.

```text
BITFIELD {
    pieces: [0, 1, 0, 1, 1, 0]
}
```

Here, `1` means the peer has the piece and `0` means it does not.

For example:

```text
Piece:    0 1 2 3 4 5
Available:1 0 1 1 0 1
```

---

## 6. Have Message

Sent when a peer successfully obtains a new piece.

```text
HAVE {
    piece_index
}
```

Example:

```text
HAVE {
    piece_index: 4
}
```

This allows connected peers to update their knowledge of piece availability.

---

## 7. Request Message

Used when a peer wants to download a particular piece.

```text
REQUEST {
    piece_index
}
```

Example:

```text
REQUEST {
    piece_index: 7
}
```

The receiving peer checks whether it has the requested piece before sending it.

---

## 8. Piece Message

Contains the actual requested piece data.

```text
PIECE {
    piece_index
    data
}
```

Example:

```text
PIECE {
    piece_index: 7
    data: <piece bytes>
}
```

The receiver verifies the piece before storing it.

---

## 9. Interested / Not Interested

### `INTERESTED`

Indicates that the peer has discovered pieces it needs from the other peer.

```text
INTERESTED {
}
```

### `NOT_INTERESTED`

Indicates that the peer currently does not need any pieces from the other peer.

```text
NOT_INTERESTED {
}
```

These messages contain no additional data.

---

## 10. Choke / Unchoke

### `CHOKE`

Indicates that the receiving peer should temporarily stop requesting pieces.

```text
CHOKE {
}
```

### `UNCHOKE`

Indicates that the receiving peer may continue requesting pieces.

```text
UNCHOKE {
}
```

These messages contain no additional data.

---

## 11. Encoding

Before transmission:

```text
Message
   ↓
Encoder
   ↓
Bytes
   ↓
TCP Connection
```

The `Encoder` converts the message into a byte representation suitable for network transmission.

The exact serialization method should be consistent across all peers.

---

## 12. Decoding

When a message is received:

```text
TCP Connection
   ↓
Bytes
   ↓
Decoder
   ↓
Message
```

The `Decoder` reconstructs the original message type and payload.

Invalid or incomplete messages should be rejected rather than passed to the peer logic.

---

## 13. Message Flow Example

A simple piece-download interaction looks like:

```text
Peer A                         Peer B
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
```

This represents the basic communication needed for one peer to obtain a piece from another.

---

## 14. Design Rules

* Every message must have a valid message type.
* Payload fields must match the message type.
* Messages must be encoded before being sent.
* Received messages must be decoded before processing.
* Invalid messages should be rejected safely.
* Both peers must use the same message definitions.
* Piece data should be verified after receiving it.
