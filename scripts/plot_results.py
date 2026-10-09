"""Generate comparison plots from experiments/distribution_results.csv.

Usage:
    python scripts/plot_results.py
"""

from __future__ import annotations

import sys
from pathlib import Path
import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

input_path = PROJECT_ROOT / "experiments" / "distribution_results.csv"
output_path = PROJECT_ROOT / "experiments" / "distribution_time_comparison.png"


def main() -> None:
    if not input_path.exists():
        raise SystemExit(f"Results file not found: {input_path}")

    df = pd.read_csv(input_path)
    df = df[
        (df["status"] == "success")
        & (df["integrity"] == "passed")
    ]

    if df.empty:
        raise SystemExit("No successful, verified experiment results found.")

    # Convert distribution_seconds to float
    df["distribution_seconds"] = df["distribution_seconds"].astype(float)

    summary = (
        df.groupby(["swarm", "strategy"])["distribution_seconds"]
        .agg(["mean", "std"])
        .reset_index()
    )

    strategies = ["rarest-first", "sequential", "random"]
    swarms = sorted(summary["swarm"].unique())

    fig, axes = plt.subplots(
        1,
        len(swarms),
        figsize=(6 * len(swarms), 5),
        squeeze=False,
    )

    for ax, swarm in zip(axes[0], swarms):
        subset = summary[summary["swarm"] == swarm].set_index("strategy")
        means = [
            subset.loc[s, "mean"] if s in subset.index else 0
            for s in strategies
        ]
        errors = [
            (
                subset.loc[s, "std"]
                if s in subset.index and pd.notna(subset.loc[s, "std"])
                else 0
            )
            for s in strategies
        ]
        bars = ax.bar(strategies, means, yerr=errors, capsize=4, color=["#2563eb", "#10b981", "#f59e0b"])
        ax.set_title(swarm, fontsize=12, fontweight="bold")
        ax.set_ylabel("Distribution time (seconds)", fontsize=10)
        ax.set_xlabel("Piece-selection strategy", fontsize=10)
        ax.tick_params(axis="x", rotation=15)
        ax.grid(axis="y", linestyle="--", alpha=0.5)

        # Label bars with value
        for bar in bars:
            height = bar.get_height()
            if height > 0:
                ax.annotate(
                    f"{height:.2f}s",
                    xy=(bar.get_x() + bar.get_width() / 2, height),
                    xytext=(0, 3),
                    textcoords="offset points",
                    ha="center",
                    va="bottom",
                    fontsize=9,
                )

    fig.tight_layout()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output_path, dpi=160)
    print(f"Saved graph: {output_path}")


if __name__ == "__main__":
    main()
