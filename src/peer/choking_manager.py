from __future__ import annotations

import threading
import time

from src.common.constants import CHOKING_INTERVAL, MAX_UNCHOKED_PEERS


class ChokingManager:
    def __init__(
        self,
        state,
        send_message,
        bytes_downloaded_from_peer,
        *,
        interval=CHOKING_INTERVAL,
        max_unchoked=MAX_UNCHOKED_PEERS,
    ):
        self._state = state
        self._send_message = send_message
        self._bytes_downloaded_from_peer = bytes_downloaded_from_peer

        self._interval = interval
        self._max_unchoked = max_unchoked

        self._running = False
        self._thread = None
        self._stop_event = threading.Event()

        self._lock = threading.RLock()
        self._optimistic_peer = None

    def start(self):
        with self._lock:
            if self._running:
                return

            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(target=self._loop, daemon=True)
            self._thread.start()

    def stop(self):
        with self._lock:
            self._running = False
            self._stop_event.set()

        if self._thread:
            self._thread.join(timeout=2)

        self._thread = None

    def rebalance(self):
        connected = set(self._state.get_connected_peers())

        interested = [
            peer
            for peer in self._state.get_interested_peers()
            if peer in connected
        ]

        ranked = sorted(
            interested,
            key=self._bytes_downloaded_from_peer,
            reverse=True,
        )

        normal_slots = max(0, self._max_unchoked - 1)
        selected = ranked[:normal_slots]

        remaining = [
            peer for peer in interested if peer not in selected
        ]

        if remaining:
            if self._optimistic_peer not in remaining:
                self._optimistic_peer = remaining[0]
            else:
                index = remaining.index(self._optimistic_peer)
                self._optimistic_peer = remaining[(index + 1) % len(remaining)]

            selected.append(self._optimistic_peer)

        for peer_id in connected:
            should_unchoke = peer_id in selected
            currently_unchoked = not self._state.is_choking(peer_id)

            if should_unchoke and not currently_unchoked:
                self._state.set_choking(peer_id, False)
                self._send_message(peer_id, "UNCHOKE")
            elif not should_unchoke and currently_unchoked:
                self._state.set_choking(peer_id, True)
                self._send_message(peer_id, "CHOKE")

    def _loop(self):
        while not self._stop_event.is_set():
            try:
                self.rebalance()
            except Exception:
                pass

            self._stop_event.wait(self._interval)
