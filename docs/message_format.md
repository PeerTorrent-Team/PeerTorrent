# PeerTorrent Message Format

This document describes the peer-to-peer messages used by PeerTorrent. The tracker uses a separate HTTP/JSON API; its requests and responses are described in `protocol_specification.md`.

## 1. General Message Structure

A peer message has two main fields:

```text
Message
├── type
└── payload
```

- `type` identifies the message purpose.
- `payload` contains the data associated with that message.

Messages are serialized to bytes before transmission over a TCP connection.

## 2. Message Types

| Message | Purpose |
| --- | --- |
| `HANDSHAKE` | Identifies the peer and file being shared |
| `BITFIELD` | Reports which pieces the peer currently has |
| `HAVE` | Announces that a peer has obtained a piece |
| `REQUEST` | Requests a specific piece |
| `PIECE` | Carries requested piece data |
| `CANCEL` | Cancels a pending upload request for a piece |
| `INTERESTED` | Indicates that the sender needs pieces held by the receiver |
| `NOT_INTERESTED` | Indicates that the sender currently needs no pieces from the receiver |
| `CHOKE` | Temporarily prevents the receiver from making piece requests |
| `UNCHOKE` | Allows the receiver to make piece requests |

## 3. Wire Framing and Serialization

Peer-to-peer messages use this TCP framing format:

```text
[4-byte big-endian unsigned length][JSON payload bytes]
```

The length prefix specifies the number of bytes in the JSON payload that follows. The connection layer is responsible for reading the frame; the protocol decoder converts the payload into a message.

For `PIECE` messages, the binary `data` field is encoded as Base64 text inside JSON. The receiver decodes that field back to bytes before processing the piece.

Decoded messages must be validated before being accepted by peer logic.

## 4. Message Representation

Conceptually, a message is represented as:

```text
Message {
    type: <message_type>
    payload: <message_data>
}
```

For example:

```json
{
  "type": "REQUEST",
  "payload": {
    "piece_index": 4
  }
}
```

This is a format illustration; actual field validation and serialization are handled by the implementation.

## 5. HANDSHAKE

The handshake identifies the connecting peer and the file swarm:

```json
{
  "type": "HANDSHAKE",
  "payload": {
    "peer_id": "peer-1",
    "file_id": "<file-id>"
  }
}
```

- `peer_id` identifies the sender.
- `file_id` identifies the file being shared.

A peer should validate the handshake and confirm that the file ID matches the active file before continuing with normal piece exchange.

## 6. BITFIELD

The bitfield describes piece availability:

```json
{
  "type": "BITFIELD",
  "payload": {
    "pieces": [1, 0, 1, 1, 0, 1]
  }
}
```

Each entry corresponds to a piece index. `1` indicates that the piece is available; `0` indicates that it is not.

## 7. HAVE

Sent when a peer obtains a new piece successfully:

```json
{
  "type": "HAVE",
  "payload": {
    "piece_index": 4
  }
}
```

Other connected peers can use this information to update their view of the sender's piece availability.

## 8. REQUEST

Requests a specific piece:

```json
{
  "type": "REQUEST",
  "payload": {
    "piece_index": 7
  }
}
```

The receiving peer checks whether the requested piece is available before serving it.

## 9. PIECE

Carries the requested piece index and its data:

```json
{
  "type": "PIECE",
  "payload": {
    "piece_index": 7,
    "data": "<Base64-encoded piece bytes>"
  }
}
```

The `data` value shown here is a placeholder. On the wire, binary piece data is represented as Base64 text inside the JSON payload. After decoding, the receiver should verify the piece against the expected hash before treating it as valid.

## 10. CANCEL

Indicates that a peer no longer wants a particular piece to be uploaded:

```json
{
  "type": "CANCEL",
  "payload": {
    "piece_index": 4
  }
}
```

The upload manager updates its tracking state for the request associated with the sending peer and piece index. Receiving a cancellation does not necessarily interrupt data that is already being transmitted.

## 11. INTERESTED and NOT_INTERESTED

These messages have empty payloads.

```json
{
  "type": "INTERESTED",
  "payload": {}
}
```

`INTERESTED` indicates that the sender needs one or more pieces held by the receiver.

```json
{
  "type": "NOT_INTERESTED",
  "payload": {}
}
```

`NOT_INTERESTED` indicates that the sender currently does not need any pieces from the receiver.

## 12. CHOKE and UNCHOKE

These messages have empty payloads.

```json
{
  "type": "CHOKE",
  "payload": {}
}
```

`CHOKE` indicates that the receiver should temporarily stop making piece requests to the sender.

```json
{
  "type": "UNCHOKE",
  "payload": {}
}
```

`UNCHOKE` indicates that piece requests are allowed again.

## 13. Encoding Flow

```text
Message object
    ↓
Encoder
    ↓
JSON payload bytes
    ↓
4-byte length prefix + payload
    ↓
TCP connection
```

The encoder and decoder must agree on the message schema and serialization format.

## 14. Decoding Flow

```text
TCP connection
    ↓
Read length prefix and complete payload
    ↓
Parse JSON
    ↓
Decode Base64 piece data when applicable
    ↓
Validate message type and payload
    ↓
Pass valid message to peer logic
```

Incomplete frames, invalid JSON, unsupported message types, or invalid payloads should be rejected safely.

## 15. Example Piece Exchange

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

This illustrates a basic piece exchange. Actual message ordering depends on the peer's state and the implementation's connection and scheduling logic.

## 16. Design Rules

- Every message must have a recognized message type.
- The payload must match the message type.
- Messages must be framed and encoded before transmission.
- Receivers must read complete frames before decoding them.
- Piece data must be decoded from Base64 before integrity verification.
- Invalid messages must not be passed to peer logic.
- Received pieces must be verified before being treated as valid.
- The tracker HTTP API must not be confused with the peer wire protocol.