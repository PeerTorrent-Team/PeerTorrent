"""Factory for the supported PeerTorrent piece-selection strategies."""

from __future__ import annotations

from src.selection.random_selector import RandomSelector
from src.selection.rarest_first import RarestFirstSelector
from src.selection.sequential_selector import SequentialSelector
from src.selection.selector import Selector

DEFAULT_STRATEGY = "rarest-first"
SUPPORTED_STRATEGIES = ("rarest-first", "random", "sequential")


def normalize_strategy_name(name: str) -> str:
    """Normalize CLI and configuration spellings to a canonical strategy name."""
    if not isinstance(name, str):
        raise TypeError("strategy name must be a string")

    normalized = name.strip().lower().replace("_", "-")
    aliases = {
        "rarest": "rarest-first",
        "rarest-first": "rarest-first",
        "random": "random",
        "sequential": "sequential",
        "sequential-first": "sequential",
    }
    try:
        return aliases[normalized]
    except KeyError as exc:
        supported = ", ".join(SUPPORTED_STRATEGIES)
        raise ValueError(
            f"Unknown piece-selection strategy {name!r}; choose one of: {supported}"
        ) from exc


def create_selector(name: str = DEFAULT_STRATEGY) -> Selector:
    """Build a fresh selector instance for a supported strategy."""
    strategy = normalize_strategy_name(name)
    if strategy == "rarest-first":
        return RarestFirstSelector()
    if strategy == "random":
        return RandomSelector()
    return SequentialSelector()
