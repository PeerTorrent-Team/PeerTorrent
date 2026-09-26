from .connection import Connection


class ConnectionPool:

    def __init__(self, max_connections: int | None = None):
        self.connections: dict[str, Connection] = {}
        self.max_connections = max_connections

    def add(self, peer_id: str, connection: Connection) -> None:
        # Avoid creating a second connection for the same peer.
        if peer_id in self.connections:
            raise ValueError(f"Connection already exists for peer: {peer_id}")

        # Respect the maximum number of active connections if one is configured.
        if (
            self.max_connections is not None
            and len(self.connections) >= self.max_connections
        ):
            raise RuntimeError("Connection pool is full")

        self.connections[peer_id] = connection

    def remove(self, peer_id: str) -> None:
        # Remove the connection if the peer is currently in the pool.
        self.connections.pop(peer_id, None)

    def get(self, peer_id: str) -> Connection | None:
        # Return the connection for this peer, if it exists.
        return self.connections.get(peer_id)

    def get_all(self) -> list[Connection]:
        # Return all currently managed connections.
        return list(self.connections.values())