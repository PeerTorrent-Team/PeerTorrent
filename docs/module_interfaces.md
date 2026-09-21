# Module Interfaces

This document defines the main functions exposed by each module so that different team members can develop their components independently.

---

## 1. Common Types

### `PeerInfo`

* `peer_id` — Unique identifier of the peer.
* `ip` — IP address of the peer.
* `port` — Port used by the peer.

### `PieceInfo`

* `index` — Index of the piece in the file.
* `size` — Size of the piece in bytes.
* `hash` — Expected hash of the piece.

### `FileMetadata`

* `file_name` — Name of the original file.
* `file_size` — Size of the original file.
* `piece_size` — Size of each piece.
* `piece_count` — Total number of pieces.
* `pieces` — Hash information for all pieces.

---

## 2. Pieces & Storage

### `PieceManager`

```text
get_missing_pieces()
```

Returns the pieces that have not been downloaded yet.

```text
has_piece(index)
```

Checks whether the peer already has a particular piece.

```text
get_piece(index)
```

Returns information or data for the requested piece.

```text
mark_piece_complete(index)
```

Marks a piece as successfully downloaded.

```text
is_complete()
```

Checks whether all pieces have been downloaded.

### `PieceStorage`

```text
save_piece(index, data)
```

Stores the downloaded piece on disk.

```text
load_piece(index)
```

Loads a stored piece from disk.

```text
has_piece(index)
```

Checks whether a piece exists in local storage.

### `FileManager`

```text
split_file(file_path, piece_size)
```

Splits the input file into fixed-size pieces.

```text
reconstruct_file(pieces, output_path)
```

Combines the downloaded pieces to recreate the original file.

---

## 3. Tracker

### `PeerRegistry`

```text
register_peer(peer)
```

Adds a peer to the tracker's registry.

```text
remove_peer(peer_id)
```

Removes a peer from the registry.

```text
get_peer(peer_id)
```

Returns information about a specific peer.

```text
get_peers()
```

Returns the currently registered peers.

### `SwarmManager`

```text
add_peer(file_id, peer)
```

Adds a peer to the swarm for a particular file.

```text
remove_peer(file_id, peer_id)
```

Removes a peer from a file's swarm.

```text
get_peers(file_id)
```

Returns peers currently sharing the requested file.

### `TrackerServer`

```text
handle_request(request)
```

Processes tracker requests and returns the appropriate response.

---

## 4. Protocol

### `Message`

Represents a P2P message containing a message type and its payload.

```text
Message(type, payload)
```

Creates a message with the specified type and data.

### `Encoder`

```text
encode(message)
```

Converts a message into bytes for network transmission.

### `Decoder`

```text
decode(data)
```

Converts received bytes back into a message.

### `Handshake`

```text
create_handshake(peer_id, file_id)
```

Creates the initial handshake message between two peers.

```text
validate_handshake(handshake)
```

Checks whether a received handshake is valid.

---

## 5. Network

### `Connection`

```text
connect()
```

Establishes a TCP connection with another peer.

```text
send_message(message)
```

Sends an encoded message to the connected peer.

```text
receive_message()
```

Receives and decodes a message from the peer.

```text
close()
```

Closes the network connection.

### `ConnectionPool`

```text
add(connection)
```

Adds an active connection to the pool.

```text
remove(peer_id)
```

Removes a peer's connection from the pool.

```text
get(peer_id)
```

Returns the connection for a specific peer.

```text
get_all()
```

Returns all active peer connections.

---

## 6. Peer

### `DownloadManager`

```text
request_piece(peer, piece_index)
```

Requests a specific piece from another peer.

```text
handle_piece(piece)
```

Processes a received piece and updates local state.

### `UploadManager`

```text
handle_request(peer, piece_index)
```

Handles a request for a piece from another peer.

```text
send_piece(peer, piece_index)
```

Reads and sends the requested piece.

### `Scheduler`

```text
schedule()
```

Coordinates which peer and piece should be processed next.

### `Peer`

```text
start()
```

Starts the peer and its required components.

```text
stop()
```

Stops the peer and closes its connections.

---

## 7. Piece Selection

All piece-selection strategies should provide:

```text
select_piece(missing_pieces, availability)
```

Selects the next piece that should be downloaded.

### Inputs

*missing_pieces*

A collection of piece indices that the local peer still needs to download.

Example:

python
missing_pieces = [0, 2, 4, 7]


*availability*

A mapping where each piece index is associated with the number of connected peers that currently have that piece.

Example:

python
availability = {
    0: 3,
    2: 1,
    4: 4,
    7: 2
}


In this example, piece 2 is available from only one peer, while piece 4 is available from four peers.

The availability information is used by the RarestFirstSelector to select the least commonly available required piece.

### Return Value

select_piece() returns the selected piece index.

If there are no missing pieces available for selection, the selector should return None.

### Implementations

```text
SequentialSelector
```

Selects pieces in sequential order.

```text
RandomSelector
```

Selects an available piece randomly.

```text
RarestFirstSelector
```

Selects the least commonly available piece.

---

## 8. Module Dependencies

The main dependencies between modules are:

```text
Peer
 ├── Tracker
 ├── Network
 ├── Protocol
 ├── PieceManager
 ├── Storage
 └── Selection

Tracker
 ├── PeerRegistry
 └── SwarmManager

Network
 └── Protocol

PieceManager
 └── Storage
```

The interfaces above are kept intentionally small so that team members can implement their modules independently while following the same function names and responsibilities.
