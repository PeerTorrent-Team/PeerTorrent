"""Generate PeerTorrent experiment plots from result CSV files."""

from __future__ import annotations

import argparse
from pathlib import Path

import matplotlib
matplotlib.use("Agg")

import matplotlib.pyplot as plt
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RESULT_COLUMNS = {
    "strategy",
    "swarm",
    "distribution_seconds",
    "integrity",
    "status",
}
STRATEGIES = ("rarest-first", "sequential", "random")
COLORS = {
    "rarest-first": "#315f8c",
    "sequential": "#3b8066",
    "random": "#c17a35",
}


def find_csvs() -> list[Path]:
    """Find experiment result CSVs without modifying them."""
    directories = [
        PROJECT_ROOT / "experiments",
        PROJECT_ROOT,
    ]
    found = {}

    for directory in directories:
        if not directory.is_dir():
            continue

        for path in directory.glob("*.csv"):
            if path.name == "peer_statistics.csv":
                continue

            try:
                header = set(pd.read_csv(path, nrows=0).columns)
            except Exception as exc:
                print(f"Skipping unreadable CSV {path}: {exc}")
                continue

            if RESULT_COLUMNS.issubset(header):
                found[str(path.resolve())] = path

    return sorted(found.values(), key=lambda path: path.name)


def plot_results(source: Path, output_dir: Path) -> Path | None:
    """Plot verified completion times from one result CSV."""
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        print(f"Could not read {source}: {exc}")
        return None

    missing = RESULT_COLUMNS - set(frame.columns)
    if missing:
        print(f"Skipping {source.name}; missing columns: {sorted(missing)}")
        return None

    frame["distribution_seconds"] = pd.to_numeric(
        frame["distribution_seconds"], errors="coerce"
    )

    valid = (
        frame["status"].astype(str).str.strip().str.lower().eq("success")
        & frame["integrity"].astype(str).str.strip().str.lower().eq("passed")
        & frame["distribution_seconds"].notna()
        & (frame["distribution_seconds"] >= 0)
    )
    successful = frame.loc[valid].copy()
    excluded = len(frame) - len(successful)

    print(f"\n{source.name}: {len(successful)} verified runs; "
          f"{excluded} excluded")

    if successful.empty:
        print("No verified successful timings; no plot generated.")
        return None

    summary = (
        successful.groupby(["swarm", "strategy"], dropna=False)
        ["distribution_seconds"]
        .agg(mean="mean", std="std", count="count")
        .reset_index()
    )

    swarms = summary["swarm"].drop_duplicates().tolist()
    fig, axes = plt.subplots(
        1, len(swarms), figsize=(max(6, 5 * len(swarms)), 5),
        squeeze=False
    )

    for ax, swarm in zip(axes[0], swarms):
        subset = summary[summary["swarm"] == swarm].copy()
        present = subset["strategy"].astype(str).tolist()
        ordered = [s for s in STRATEGIES if s in present]
        ordered += sorted(s for s in present if s not in ordered)

        subset["strategy"] = subset["strategy"].astype(str)
        subset = subset.set_index("strategy").reindex(ordered).dropna(
            subset=["mean"]
        )

        labels = subset.index.tolist()
        means = subset["mean"].tolist()
        errors = [
            row["std"]
            if row["count"] > 1 and pd.notna(row["std"])
            else 0
            for _, row in subset.iterrows()
        ]
        colors = [COLORS.get(label, "#777777") for label in labels]

        bars = ax.bar(
            labels, means, yerr=errors, capsize=4, color=colors
        )
        ax.set_title(f"Swarm: {swarm}")
        ax.set_xlabel("Piece-selection strategy")
        ax.set_ylabel("Completion time (seconds)")
        ax.tick_params(axis="x", rotation=20)
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)

        for bar, (_, row) in zip(bars, subset.iterrows()):
            ax.annotate(
                f'{bar.get_height():.2f}s (n={int(row["count"])})',
                (bar.get_x() + bar.get_width() / 2, bar.get_height()),
                xytext=(0, 4),
                textcoords="offset points",
                ha="center",
                va="bottom",
                fontsize=8,
            )

    fig.suptitle(f"PeerTorrent completion times\n{source.stem}")
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    output_dir.mkdir(parents=True, exist_ok=True)
    destination = output_dir / f"{source.stem}_comparison.png"
    fig.savefig(destination, dpi=160, bbox_inches="tight")
    plt.close(fig)

    print(f"Saved: {destination}")
    return destination


def plot_peer_statistics(source: Path, output_dir: Path) -> None:
    """Generate separate upload/download and free-rider statistics plots."""
    try:
        frame = pd.read_csv(source)
    except Exception as exc:
        print(f"Could not read peer statistics: {exc}")
        return

    required = {"uploaded_bytes", "downloaded_bytes"}
    if not required.issubset(frame.columns):
        print(f"Skipping peer statistics: expected columns {required}")
        return

    for column in ("uploaded_bytes", "downloaded_bytes"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")

    usable = frame.dropna(subset=["uploaded_bytes", "downloaded_bytes"])
    if usable.empty:
        print("No usable peer transfer statistics.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)

    if "is_free_rider" in usable.columns:
        usable["free_rider_group"] = (
            usable["is_free_rider"].astype(str).str.strip().str.lower()
            .map({
                "true": "Free rider",
                "1": "Free rider",
                "yes": "Free rider",
                "false": "Regular peer",
                "0": "Regular peer",
                "no": "Regular peer",
            })
            .fillna("Unknown")
        )
        grouped = usable.groupby("free_rider_group")[
            ["uploaded_bytes", "downloaded_bytes"]
        ].mean()

        if not grouped.empty:
            ax = grouped.plot(kind="bar", figsize=(8, 5))
            ax.set_title("Average peer upload and download by peer type")
            ax.set_xlabel("Peer type")
            ax.set_ylabel("Bytes")
            ax.grid(axis="y", linestyle="--", alpha=0.35)
            ax.set_axisbelow(True)
            plt.xticks(rotation=0)
            plt.tight_layout()
            destination = output_dir / "peer_transfer_by_type.png"
            plt.savefig(destination, dpi=160, bbox_inches="tight")
            plt.close()
            print(f"Saved: {destination}")

    grouped = usable.groupby("peer_id")[
        ["uploaded_bytes", "downloaded_bytes"]
    ].sum() if "peer_id" in usable.columns else pd.DataFrame()

    if not grouped.empty:
        ax = grouped.plot(kind="bar", figsize=(max(8, len(grouped) * 0.7), 5))
        ax.set_title("Peer upload and download totals")
        ax.set_xlabel("Peer")
        ax.set_ylabel("Bytes")
        ax.grid(axis="y", linestyle="--", alpha=0.35)
        ax.set_axisbelow(True)
        plt.xticks(rotation=45, ha="right")
        plt.tight_layout()
        destination = output_dir / "peer_transfer_totals.png"
        plt.savefig(destination, dpi=160, bbox_inches="tight")
        plt.close()
        print(f"Saved: {destination}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        help="Plot one result CSV instead of discovering all result CSVs.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=PROJECT_ROOT / "experiments" / "plots",
        help="Directory in which to save PNG files.",
    )
    parser.add_argument(
        "--peer-statistics",
        type=Path,
        help="Optional peer_statistics.csv path.",
    )
    args = parser.parse_args()

    output_dir = args.output_dir
    if not output_dir.is_absolute():
        output_dir = PROJECT_ROOT / output_dir

    if args.input:
        source = args.input
        if not source.is_absolute():
            source = PROJECT_ROOT / source
        if not source.is_file():
            parser.error(f"Input CSV does not exist: {source}")
        plot_results(source, output_dir)
    else:
        files = find_csvs()
        if not files:
            print("No result CSVs with the expected columns were found.")
            return 1
        print(f"Found {len(files)} result CSV(s).")
        for source in files:
            plot_results(source, output_dir)

    stats = args.peer_statistics
    if stats is None:
        candidates = [
            PROJECT_ROOT / "experiments" / "peer_statistics.csv",
            PROJECT_ROOT / "peer_statistics.csv",
        ]
        stats = next((p for p in candidates if p.is_file()), None)

    elif not stats.is_absolute():
        stats = PROJECT_ROOT / stats

    if stats is not None and stats.is_file():
        plot_peer_statistics(stats, output_dir)
    elif args.peer_statistics:
        print(f"Peer statistics CSV not found: {stats}")

    print(f"\nPlot output directory: {output_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
