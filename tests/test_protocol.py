import json
import socket
import struct

import pytest

from src.network.connection import Connection
from src.network.connection_pool import ConnectionPool
from src.network.socket_manager import SocketManager
from src.protocol.decoder import Decoder
from src.protocol.encoder import Encoder
from src.protocol.handshake import Handshake
from src.protocol.message import Message
from src.protocol.message_types import MessageType


@pytest.mark.parametrize(
    "message",
    [
        Message(MessageType.HANDSHAKE, {"peer_id": "peer-a", "file_id": "file-1"}),
        Message(MessageType.BITFIELD, {"pieces": [1, 0, 1]}),
        Message(MessageType.HAVE, {"piece_index": 2}),
        Message(MessageType.REQUEST, {"piece_index": 1}),
        Message(MessageType.PIECE, {"piece_index": 1, "data": b"\x00\x01payload\xff"}),
        Message(MessageType.CANCEL, {"piece_index": 1}),
        Message(MessageType.INTERESTED, {}),
        Message(MessageType.NOT_INTERESTED, {}),
        Message(MessageType.CHOKE, {}),
        Message(MessageType.UNCHOKE, {}),
    ],
)
def test_encoder_decoder_round_trip(message):
    wire = Encoder().encode(message)
    decoded = Decoder().decode(wire)

    assert decoded.type is message.type
    assert decoded.payload == message.payload


def test_piece_encoding_does_not_mutate_original_payload():
    message = Message(MessageType.PIECE, {"piece_index": 0, "data": b"hello"})

    Encoder().encode(message)

    assert message.payload["data"] == b"hello"


def test_piece_encoder_rejects_non_bytes_data():
    message = Message(MessageType.PIECE, {"piece_index": 0, "data": "hello"})

    with pytest.raises(TypeError, match="PIECE data must be bytes"):
        Encoder().encode(message)


@pytest.mark.parametrize(
    "wire",
    [
        b"not json",
        b"[]",
        json.dumps({"type": "HAVE"}).encode(),
        json.dumps({"type": "WHATEVER", "payload": {}}).encode(),
        json.dumps({"type": "HAVE", "payload": []}).encode(),
        json.dumps({"type": "HAVE", "payload": {}}).encode(),
        json.dumps({"type": "BITFIELD", "payload": {"pieces": [0, 2]}}).encode(),
        json.dumps({"type": "HANDSHAKE", "payload": {"peer_id": "p"}}).encode(),
        json.dumps({"type": "REQUEST", "payload": {"piece_index": -1}}).encode(),
        json.dumps({"type": "REQUEST", "payload": {"piece_index": True}}).encode(),
    ],
)
def test_decoder_rejects_malformed_or_invalid_messages(wire):
    with pytest.raises(ValueError):
        Decoder().decode(wire)


def test_decoder_rejects_invalid_base64_for_piece():
    wire = json.dumps(
        {
            "type": "PIECE",
            "payload": {"piece_index": 0, "data": "%%%not-base64%%%"},
        }
    ).encode()

    with pytest.raises(ValueError, match="Base64"):
        Decoder().decode(wire)


def test_handshake_creation_and_validation():
    handshake = Handshake.create_handshake("peer-a", "file-a")

    assert handshake.type is MessageType.HANDSHAKE
    assert handshake.payload == {"peer_id": "peer-a", "file_id": "file-a"}
    assert Handshake.validate_handshake(handshake)
    assert not Handshake.validate_handshake(Message(MessageType.CHOKE, {}))
    assert not Handshake.validate_handshake(
        Message(MessageType.HANDSHAKE, {"peer_id": "", "file_id": "file-a"})
    )


def test_socket_manager_frames_messages_over_tcp_socketpair():
    sender, receiver = socket.socketpair()
    manager = SocketManager(timeout=1)
    try:
        manager.send(sender, b"test payload")
        assert manager.receive(receiver) == b"test payload"
    finally:
        sender.close()
        receiver.close()


def test_socket_manager_receives_fragmented_frame():
    sender, receiver = socket.socketpair()
    manager = SocketManager(timeout=1)
    payload = b"fragmented message"
    frame = struct.pack("!I", len(payload)) + payload
    try:
        # Separate header and payload writes to exercise receive_exact().
        sender.sendall(frame[:2])
        sender.sendall(frame[2:5])
        sender.sendall(frame[5:])
        assert manager.receive(receiver) == payload
    finally:
        sender.close()
        receiver.close()


def test_socket_manager_rejects_zero_length_frame():
    sender, receiver = socket.socketpair()
    try:
        sender.sendall(struct.pack("!I", 0))
        with pytest.raises(ValueError, match="message length"):
            SocketManager(timeout=1).receive(receiver)
    finally:
        sender.close()
        receiver.close()


def test_socket_manager_rejects_oversized_frame_before_reading_body():
    sender, receiver = socket.socketpair()
    try:
        sender.sendall(struct.pack("!I", 16 * 1024 * 1024 + 1))
        with pytest.raises(ValueError, match="too large"):
            SocketManager(timeout=1).receive(receiver)
    finally:
        sender.close()
        receiver.close()


def test_connection_sends_and_receives_protocol_messages():
    local_socket, remote_socket = socket.socketpair()
    local = Connection(local_socket, SocketManager(timeout=1))
    remote = Connection(remote_socket, SocketManager(timeout=1))
    try:
        local.mark_connected()
        remote.mark_connected()
        outgoing = Message(MessageType.REQUEST, {"piece_index": 3})

        local.send_message(outgoing)
        received = remote.receive_message()

        assert received == outgoing
        assert local.connected
    finally:
        local.close()
        remote.close()


def test_connection_pool_lookup_remove_and_duplicate_guard():
    pool = ConnectionPool()
    sock_a, sock_b = socket.socketpair()
    connection = Connection(sock_a)
    try:
        pool.add("peer-a", connection)
        assert pool.get("peer-a") is connection
        assert pool.get_all() == [connection]
        with pytest.raises(ValueError, match="already exists"):
            pool.add("peer-a", connection)
        pool.remove("peer-a")
        assert pool.get("peer-a") is None
        assert pool.get_all() == []
    finally:
        sock_a.close()
        sock_b.close()


def test_connection_pool_enforces_max_connections():
    pool = ConnectionPool(max_connections=1)
    socket_pairs = [socket.socketpair(), socket.socketpair()]
    try:
        pool.add("peer-a", Connection(socket_pairs[0][0]))
        with pytest.raises(RuntimeError, match="full"):
            pool.add("peer-b", Connection(socket_pairs[1][0]))
    finally:
        for pair in socket_pairs:
            for sock in pair:
                sock.close()


def test_connection_pool_rejects_invalid_capacity():
    for invalid in (0, -1, True, 1.5):
        with pytest.raises(ValueError):
            ConnectionPool(max_connections=invalid)