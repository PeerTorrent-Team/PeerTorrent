from __future__ import annotations

import logging
import threading
from typing import Callable

from src.common.constants import CHOKING_INTERVAL, MAX_UNCHOKED_PEERS


class ChokingManager:
    """Apply a tit-for-tat-inspired choking policy with optimistic unchoking.

    Connected interested peers are ranked by bytes we have downloaded from
    them. Up to ``max_unchoked - 1`` top contributors are normally unchoked;
    one additional slot rotates optimistically so newcomers can prove useful.
    """

    def __init__(
        self,
        state,
        send_message: Callable[[str, str], None],
        bytes_downloaded_from_peer: Callable[[str], int],
        *,
        interval: float = CHOKING_INTERVAL,
        max_unchoked: int = MAX_UNCHOKED_PEERS,
    ) -> None:
        if isinstance(interval, bool) or not isinstance(interval, (int, float)) or interval <= 0:
            raise ValueError("interval must be a positive number")
        if (
            not isinstance(max_unchoked, int)
            or isinstance(max_unchoked, bool)
            or max_unchoked < 0
        ):
            raise ValueError("max_unchoked must be a non-negative integer")

        self._state = state
        self._send_message = send_message
        self._bytes_downloaded_from_peer = bytes_downloaded_from_peer
        self._interval = float(interval)
        self._max_unchoked = max_unchoked

        self._running = False
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.RLock()
        self._optimistic_peer: str | None = None
        self._stats = {
            "rebalances": 0,
            "choke_messages": 0,
            "unchoke_messages": 0,
            "optimistic_unchokes": 0,
        }
        self._peer_choke_events: dict[str, dict[str, int]] = {}
        self._logger = logging.getLogger(__name__)

    def start(self) -> None:
        with self._lock:
            if self._running:
                return
            self._running = True
            self._stop_event.clear()
            self._thread = threading.Thread(
                target=self._loop,
                name="peertorrent-choking-manager",
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            self._running = False
            self._stop_event.set()
            thread = self._thread

        if thread is not None and thread is not threading.current_thread():
            thread.join(timeout=2)

        with self._lock:
            self._thread = None

    def rebalance(self, *, rotate_optimistic: bool = False) -> list[str]:
        """Recalculate choking; return peer IDs that should be unchoked.

        Message-triggered calls do not rotate an already selected optimistic
        peer. The periodic loop opts into rotation, avoiding rapid optimistic
        slot changes whenever an INTERESTED message arrives.
        """
        with self._lock:
            connected = set(self._state.get_connected_peers())
            interested = sorted(
                peer_id
                for peer_id in self._state.get_interested_peers()
                if peer_id in connected
            )
            ranked = sorted(
                interested,
                key=lambda peer_id: (
                    -max(0, int(self._bytes_downloaded_from_peer(peer_id))),
                    peer_id,
                ),
            )

            if self._max_unchoked == 0 or not interested:
                selected: list[str] = []
                self._optimistic_peer = None
            else:
                normal_slots = self._max_unchoked - 1
                selected = ranked[:normal_slots]
                remaining = [peer for peer in interested if peer not in selected]

                if remaining:
                    if self._optimistic_peer not in remaining:
                        # Select the first eligible peer initially, then rotate
                        # only during scheduled rebalances.
                        self._optimistic_peer = remaining[0]
                    elif rotate_optimistic and len(remaining) > 1:
                        current_index = remaining.index(self._optimistic_peer)
                        self._optimistic_peer = remaining[
                            (current_index + 1) % len(remaining)
                        ]
                    selected.append(self._optimistic_peer)
                else:
                    self._optimistic_peer = None

            # Enforce the limit even if the normal/optimistic configuration is
            # changed later or an unusual state is supplied by a test harness.
            selected = selected[: self._max_unchoked]
            selected_set = set(selected)

            for peer_id in sorted(connected):
                should_unchoke = peer_id in selected_set
                currently_unchoked = not self._state.is_choking(peer_id)

                if should_unchoke and not currently_unchoked:
                    self._state.set_choking(peer_id, False)
                    self._send_message(peer_id, "UNCHOKE")
                    self._stats["unchoke_messages"] += 1

                    events = self._peer_choke_events.setdefault(
                        peer_id, {"choke": 0, "unchoke": 0}
                    )
                    events["unchoke"] += 1

                    if peer_id == self._optimistic_peer:
                        self._stats["optimistic_unchokes"] += 1

                elif not should_unchoke and currently_unchoked:
                    self._state.set_choking(peer_id, True)
                    self._send_message(peer_id, "CHOKE")
                    self._stats["choke_messages"] += 1

                    events = self._peer_choke_events.setdefault(
                        peer_id, {"choke": 0, "unchoke": 0}
                    )
                    events["choke"] += 1

            self._stats["rebalances"] += 1
            return selected

    def get_stats(self) -> dict[str, object]:
     """Return a detached snapshot useful for tests and experiments."""
     with self._lock:
        return {
            **self._stats,
            "optimistic_peer": self._optimistic_peer,
            "peer_choke_events": {
                peer_id: dict(events)
                for peer_id, events in self._peer_choke_events.items()},}

    def _loop(self) -> None:
        # Run one initial rebalance immediately, then rotate the optimistic
        # slot at the configured cadence.
        while not self._stop_event.is_set():
            try:
                self.rebalance(rotate_optimistic=True)
            except Exception:
                self._logger.exception("Choking rebalance failed")
            self._stop_event.wait(self._interval)
