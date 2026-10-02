import json
import socket

from src.common.constants import DEFAULT_TRACKER_HOST, DEFAULT_TRACKER_PORT, ENCODING


class TrackerClient:
    def __init__(
        self,
        host: str = DEFAULT_TRACKER_HOST,
        port: int = DEFAULT_TRACKER_PORT,
        peer_id: str = "",
        ip: str = "127.0.0.1",
        peer_port: int = 0,
        file_id: str = "",
        timeout: float = 5.0,
    ) -> None:
        self.host = host
        self.port = port
        self.peer_id = peer_id
        self.ip = ip
        self.peer_port = peer_port
        self.file_id = file_id
        self.timeout = timeout

    def _request(self, payload: dict) -> dict:
        with socket.create_connection((self.host, self.port), timeout=self.timeout) as sock:
            sock.sendall((json.dumps(payload) + "\n").encode(ENCODING))
            response = sock.makefile("r", encoding=ENCODING)
            line = response.readline()

        if not line:
            raise ConnectionError("Tracker returned no data")

        parsed = json.loads(line)
        if not parsed.get("ok", False):
            raise RuntimeError(parsed.get("error", "TRACKER_ERROR"))

        return parsed

    def announce(
        self,
        *,
        left: int,
        uploaded: int,
        downloaded: int,
        is_seeder: bool,
    ) -> list[dict]:
        response = self._request(
            {
                "type": "ANNOUNCE",
                "peer_id": self.peer_id,
                "ip": self.ip,
                "port": self.peer_port,
                "file_id": self.file_id,
                "left": left,
                "uploaded": uploaded,
                "downloaded": downloaded,
                "is_seeder": is_seeder,
            }
        )

        return response.get("peers", [])

    def get_peers(self) -> list[dict]:
        response = self._request(
            {
                "type": "GET_PEERS",
                "peer_id": self.peer_id,
                "file_id": self.file_id,
            }
        )

        return response.get("peers", [])
