"""Automated experiment runner for PeerTorrent swarms.

Orchestrates multi-peer distribution experiments across piece-selection
strategies, measures distribution times, verifies reconstructed downloads,
and records results to experiments/distribution_results.csv.

Example:
    python scripts/run_experiment.py --strategy rarest-first --repeats 3 --timeout 180
    python scripts/run_experiment.py --strategy sequential --repeats 3 --timeout 180
    python scripts/run_experiment.py --strategy random --repeats 3 --timeout 180
"""

from __future__ import annotations

import argparse
import csv
import json
import random
import socket
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen
from urllib.error import URLError

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_swarm_data import (
    DEFAULT_CONFIG_PATH,
    _piece_indices,
    prepare_from_config,
)
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.selection.selector_factory import SUPPORTED_STRATEGIES
from src.storage.file_workflow import verify_downloaded_file
from src.storage.paths import (
    DEFAULT_DOWNLOAD_ROOT,
    DEFAULT_STORAGE_ROOT,
    resolve_project_path,
    resolve_storage_root,
)
from src.storage.piece_storage import PieceStorage

STORAGE_ROOT = DEFAULT_STORAGE_ROOT
DOWNLOAD_ROOT = DEFAULT_DOWNLOAD_ROOT
DEFAULT_RESULTS_CSV = PROJECT_ROOT / "experiments" / "distribution_results.csv"

DEFAULT_PEER_STATS_CSV = PROJECT_ROOT / "experiments" / "peer_statistics.csv"

PEER_STATS_FIELDNAMES = [
    "run_id",
    "repeat",
    "strategy",
    "swarm",
    "peer_id",
    "is_free_rider",
    "upload_enabled",
    "uploaded_bytes",
    "downloaded_bytes",
    "rejected_upload_requests",
    "complete",
    "downloaded_by_peer",
    "rebalances",
    "choke_messages",
    "unchoke_messages",
    "optimistic_unchokes",
    "optimistic_peer",
    "peer_choke_events",
]

CSV_FIELDNAMES = [
    "run_id",
    "repeat",
    "strategy",
    "swarm",
    "file_name",
    "file_size_bytes",
    "piece_count",
    "peer_count",
    "initial_seeder_count",
    "random_seed",
    "distribution_seconds",
    "integrity",
    "status",
    "error",
]
ALL_STRATEGIES = (*SUPPORTED_STRATEGIES, "all")


def load_swarm_configs(config_path: Path = DEFAULT_CONFIG_PATH) -> list[dict]:
    """Build one experiment workload per file from the shared assignments."""
    config_file = resolve_project_path(config_path)
    payload = json.loads(config_file.read_text(encoding="utf-8"))
    files = payload.get("files")
    peers = payload.get("peers")
    if not isinstance(files, dict) or not isinstance(peers, list):
        raise ValueError("Experiment config must contain 'files' and 'peers'")
    workloads = {
        file_name: {
            "name": file_name,
            "metadata_path": resolve_project_path(
                config_file.parent / file_config["metadata"]
            ),
            "peers": [],
            "assignments": {},
        }
        for file_name, file_config in files.items()
    }
    seen_pairs: set[tuple[str, str]] = set()
    for peer_config in peers:
        peer_id = peer_config["peer_id"]
        for file_name, distribution in peer_config["files"].items():
            pair = (peer_id, file_name)
            if pair in seen_pairs:
                raise ValueError(f"Duplicate configured peer/file assignment: {pair}")
            seen_pairs.add(pair)
            if file_name not in workloads:
                raise ValueError(f"Unknown configured file: {file_name}")
            workloads[file_name]["peers"].append({"id": peer_id})
            workloads[file_name]["assignments"][peer_id] = distribution
    return [workload for workload in workloads.values() if workload["peers"]]


def stop_process(proc: subprocess.Popen, timeout: float = 3.0) -> None:
    """Terminate and wait for a subprocess, killing if unresponsive."""
    if proc.poll() is not None:
        return
    try:
        proc.terminate()
        proc.wait(timeout=timeout)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def allocate_free_port(host: str = "127.0.0.1") -> int:
    """Ask the OS for an currently unused TCP port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.bind((host, 0))
        return listener.getsockname()[1]


def wait_for_tracker(
    host: str = "127.0.0.1",
    port: int = 6969,
    timeout: float = 5.0,
    process: subprocess.Popen | None = None,
) -> bool:
    """Poll tracker health until ready, timeout, or tracker process failure."""
    deadline = time.monotonic() + timeout
    url = f"http://{host}:{port}/health"
    while time.monotonic() < deadline:
        if process is not None and process.poll() is not None:
            return False
        try:
            with urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except (OSError, URLError):
            time.sleep(0.1)
    return False


def verify_peer_download(
    metadata_path: Path,
    peer_id: str,
    output_path: Path,
    storage_root: Path = STORAGE_ROOT,
) -> bool:
    """Reconstruct and verify one peer's actual stored pieces and file hash."""
    metadata = load_metadata(metadata_path)
    storage = PieceStorage(
        storage_root,
        peer_id=peer_id,
        file_id=calculate_file_id(metadata),
    )
    try:
        verify_downloaded_file(metadata, storage, output_path)
    except (OSError, ValueError) as exc:
        print(f"Verification failed for {peer_id}: {exc}")
        return False
    return True


def validate_initial_distribution(
    workload: dict,
    metadata,
    storage_root: Path,
) -> None:
    """Fail before networking if scoped preparation differs from config."""
    file_id = calculate_file_id(metadata)
    for peer_id, distribution in workload["assignments"].items():
        expected = _piece_indices(distribution, metadata.piece_count)
        storage = PieceStorage(storage_root, peer_id=peer_id, file_id=file_id)
        actual = [
            index
            for index in range(metadata.piece_count)
            if storage.has_piece(index)
        ]
        if actual != expected:
            raise RuntimeError(
                f"Initial storage validation failed for {peer_id}/"
                f"{workload['name']}: expected {len(expected)} configured pieces, "
                f"found {len(actual)}"
            )


def run_single_iteration(
    run_id: str,
    repeat_idx: int,
    strategy: str,
    timeout: float,
    free_rider_peer: str | None = None,
    config_path: Path = DEFAULT_CONFIG_PATH,
    storage_root: Path = STORAGE_ROOT,
    download_root: Path = DOWNLOAD_ROOT,
    random_seed: int | None = None,
    upload_rate_limit: int | None = None,
) -> list[dict]:
    """Run every configured file workload once, returning a row per workload."""
    print(f"\n{'='*70}")
    print(f"Starting Run {run_id} | Repeat {repeat_idx} | Strategy: {strategy}")
    print(f"{'='*70}")
    config_path = resolve_project_path(config_path)
    storage_root = resolve_storage_root(storage_root)
    download_root = resolve_project_path(download_root)
    workloads = load_swarm_configs(config_path)
    results: list[dict] = []

    for workload_index, workload in enumerate(workloads):
        metadata = load_metadata(workload["metadata_path"])
        file_id = calculate_file_id(metadata)
        peer_ids = [peer["id"] for peer in workload["peers"]]
        seeds = [
            peer_id
            for peer_id, distribution in workload["assignments"].items()
            if distribution == "all"
        ]
        seed_for_run = (
            random_seed + repeat_idx * 1009 + workload_index
            if random_seed is not None
            else random.SystemRandom().randrange(0, 2**32)
        )
        stats_dir = (
            PROJECT_ROOT
            / "experiments"
            / "peer_stats"
            / f"{run_id}_{workload['name']}"
        )
        stats_dir.mkdir(parents=True, exist_ok=True)

        record = {
            "run_id": run_id,
            "repeat": repeat_idx,
            "strategy": strategy,
            "swarm": workload["name"],
            "file_name": metadata.file_name,
            "file_size_bytes": metadata.file_size,
            "piece_count": metadata.piece_count,
            "peer_count": len(peer_ids),
            "initial_seeder_count": len(seeds),
            "random_seed": seed_for_run if strategy == "random" else "",
            "distribution_seconds": "",
            "integrity": "not_checked",
            "status": "preparation_failure",
            "error": "",
        }

        tracker_proc = None
        peer_procs: list[subprocess.Popen] = []
        phase = "preparation_failure"
        try:
            # Each workload and repetition begins with an explicitly reset copy
            # of the configured distribution; no prior strategy can warm it.
            prepare_from_config(
                config_path,
                storage_root=storage_root,
                download_root=download_root,
                reset_peer_files={
                    (peer_id, workload["name"])
                    for peer_id in peer_ids
                },
                only_peer_files={
                    (peer_id, workload["name"])
                    for peer_id in peer_ids
                },
            )
            validate_initial_distribution(workload, metadata, storage_root)

            phase = "tracker_failure"
            tracker_port = allocate_free_port()
            tracker_proc = subprocess.Popen(
                [
                    sys.executable,
                    "-m",
                    "src.tracker.tracker_main",
                    "--host",
                    "127.0.0.1",
                    "--port",
                    str(tracker_port),
                ],
                cwd=str(PROJECT_ROOT),
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            if not wait_for_tracker(port=tracker_port, process=tracker_proc):
                record["status"] = "tracker_failure"
                raise RuntimeError("HTTP tracker failed to become ready")

            phase = "process_failure"
            ports: set[int] = set()
            started_at = time.monotonic()
            for peer_id in peer_ids:
                peer_port = allocate_free_port()
                while peer_port in ports or peer_port == tracker_port:
                    peer_port = allocate_free_port()
                ports.add(peer_port)
                peer_seed = seed_for_run + int(peer_id[4:]) if peer_id.startswith("peer") and peer_id[4:].isdigit() else seed_for_run
                command = [
                    sys.executable,
                    "-m",
                    "src.main",
                    "--peer-id",
                    peer_id,
                    "--metadata",
                    str(workload["metadata_path"]),
                    "--port",
                    str(peer_port),
                    "--tracker-port",
                    str(tracker_port),
                    "--storage",
                    str(storage_root),
                    "--strategy",
                    strategy,
                    "--random-seed",
                    str(peer_seed),
                    "--stats-output",
                    str(stats_dir / f"{peer_id}.json"),
                ]
                if upload_rate_limit is not None:
                  command.extend(["--upload-rate-limit",str(upload_rate_limit),])
                if free_rider_peer == peer_id:
                    command.append("--no-upload")
                peer_procs.append(
                    subprocess.Popen(
                        command,
                        cwd=str(PROJECT_ROOT),
                        stdout=subprocess.DEVNULL,
                        stderr=subprocess.DEVNULL,
                    )
                )

            deadline = started_at + timeout
            while time.monotonic() < deadline:
                failed = [process for process in peer_procs if process.poll() is not None]
                if failed:
                    record["status"] = "process_failure"
                    raise RuntimeError(
                        "Peer process exited unexpectedly with code "
                        + ", ".join(str(process.returncode) for process in failed)
                    )
                if tracker_proc.poll() is not None:
                    record["status"] = "tracker_failure"
                    raise RuntimeError("Tracker process exited during workload")
                complete = all(
                    all(
                        PieceStorage(
                            storage_root,
                            peer_id=peer_id,
                            file_id=file_id,
                        ).has_piece(index)
                        for index in range(metadata.piece_count)
                    )
                    for peer_id in peer_ids
                )
                if complete:
                    record["distribution_seconds"] = f"{time.monotonic() - started_at:.6f}"
                    record["status"] = "integrity_failure"
                    record["error"] = ""
                    record["integrity"] = "failed"
                    safe_name = Path(metadata.file_name.replace("\\", "/")).name
                    verification_errors = []
                    for peer_id in peer_ids:
                        output = download_root / peer_id / safe_name
                        if not verify_peer_download(
                            workload["metadata_path"],
                            peer_id,
                            output,
                            storage_root=storage_root,
                        ):
                            verification_errors.append(peer_id)
                    if verification_errors:
                        record["error"] = "Integrity verification failed for: " + ", ".join(verification_errors)
                    else:
                        record["integrity"] = "passed"
                        record["status"] = "success"
                    break
                time.sleep(0.2)
            else:
                record["status"] = "timeout"
                record["integrity"] = "not_checked"
                record["error"] = f"Not all {len(peer_ids)} peers completed within {timeout} seconds"
        except KeyboardInterrupt:
            record["status"] = "process_failure"
            record["error"] = "Interrupted by user"
            results.append(record)
            raise
        except Exception as exc:
            if record["status"] not in {"tracker_failure", "process_failure"}:
                record["status"] = phase
            record["error"] = str(exc)
        finally:
            for process in reversed(peer_procs):
                stop_process(process)

            peer_stat_rows = []
            for peer_id in peer_ids:
                stats_path = stats_dir / f"{peer_id}.json"
                if not stats_path.is_file():
                    continue
                try:
                    stats = json.loads(stats_path.read_text(encoding="utf-8"))
                except (OSError, json.JSONDecodeError) as exc:
                    print(f"Could not read peer stats for {peer_id}: {exc}")
                    continue

                choking = stats.get("choking", {})
                peer_stat_rows.append({
                    "run_id": run_id,
                    "repeat": repeat_idx,
                    "strategy": strategy,
                    "swarm": workload["name"],
                    "peer_id": peer_id,
                    "is_free_rider": peer_id == free_rider_peer,
                    "upload_enabled": stats.get("upload_enabled", ""),
                    "uploaded_bytes": stats.get("uploaded_bytes", ""),
                    "downloaded_bytes": stats.get("downloaded_bytes", ""),
                    "rejected_upload_requests": stats.get(
                        "rejected_upload_requests", ""
                    ),
                    "complete": stats.get("complete", ""),
                    "downloaded_by_peer": json.dumps(
                        stats.get("downloaded_by_peer", {}),
                        sort_keys=True,
                    ),
                    "rebalances": choking.get("rebalances", ""),
                    "choke_messages": choking.get("choke_messages", ""),
                    "unchoke_messages": choking.get("unchoke_messages", ""),
                    "optimistic_unchokes": choking.get("optimistic_unchokes", ""),
                    "optimistic_peer": choking.get("optimistic_peer", ""),
                    "peer_choke_events": json.dumps(
                        choking.get("peer_choke_events", {}),
                        sort_keys=True,
                    ),
                })

            if peer_stat_rows:
                record_peer_stats_to_csv(
                    peer_stat_rows,
                    DEFAULT_PEER_STATS_CSV,
                )

            if tracker_proc is not None:
                stop_process(tracker_proc)

        print(
            f"[{workload['name']}] {record['status']} "
            f"integrity={record['integrity']} "
            f"time={record['distribution_seconds'] or 'n/a'} "
            f"error={record['error'] or 'none'}"
        )
        results.append(record)

    return results


def record_results_to_csv(results: list[dict], csv_path: Path) -> None:
    """Append result dictionaries to the CSV file, creating headers if needed."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    if not write_header:
        with csv_path.open("r", newline="", encoding="utf-8") as existing:
            header = next(csv.reader(existing), [])
        if header != CSV_FIELDNAMES:
            raise ValueError(
                f"Existing results schema in {csv_path} differs; use --fresh-results"
            )

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        for r in results:
            writer.writerow(r)


def record_peer_stats_to_csv(rows: list[dict], csv_path: Path) -> None:
    """Append peer transfer and choking statistics to their own CSV."""
    if not rows:
        return

    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    if not write_header:
        with csv_path.open("r", newline="", encoding="utf-8") as existing:
            header = next(csv.reader(existing), [])
        if header != PEER_STATS_FIELDNAMES:
            raise ValueError(
                f"Existing peer stats schema in {csv_path} differs. "
                "Back up the file before changing its schema."
            )

    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=PEER_STATS_FIELDNAMES)
        if write_header:
            writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run automated PeerTorrent swarm distribution experiments."
    )
    parser.add_argument(
        "--strategy",
        choices=ALL_STRATEGIES,
        default="all",
        help="Strategy to run, or 'all' for rarest-first, sequential, and random.",
    )
    parser.add_argument(
        "--repeats",
        type=int,
        default=3,
        help="Number of experimental repetitions (default: 3).",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=180.0,
        help="Maximum seconds to wait for swarm completion (default: 180.0).",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_RESULTS_CSV,
        help="Path to CSV output file (default: experiments/distribution_results.csv).",
    )
    parser.add_argument(
        "--free-rider-peer",
        default=None,
        help="Optional peer ID configured with --no-upload for free-rider tests.",
    )
    parser.add_argument(
     "--upload-rate-limit",
     type=int,
     default=None,
     help="Simulated upload rate limit in bytes per second (default: unlimited).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=DEFAULT_CONFIG_PATH,
        help=f"Peer/file assignment config (default: {DEFAULT_CONFIG_PATH}).",
    )
    parser.add_argument(
        "--storage",
        type=Path,
        default=None,
        help=f"Canonical peer storage root (default: {DEFAULT_STORAGE_ROOT}).",
    )
    parser.add_argument(
        "--random-seed",
        type=int,
        default=0,
        help="Base seed for reproducible random-selector runs (default: 0).",
    )
    parser.add_argument(
        "--fresh-results",
        action="store_true",
        help="Truncate the selected CSV before this benchmark.",
    )

    args = parser.parse_args()
    if args.repeats < 1:
        parser.error("--repeats must be at least 1")
    if args.timeout <= 0:
        parser.error("--timeout must be greater than 0")
    if args.upload_rate_limit is not None and args.upload_rate_limit <= 0:
        parser.error("--upload-rate-limit must be greater than 0")
    
    result_path = resolve_project_path(args.output)
    storage_root = resolve_storage_root(args.storage)
    if args.fresh_results:
        result_path.parent.mkdir(parents=True, exist_ok=True)
        result_path.write_text("", encoding="utf-8")
    elif result_path.exists() and result_path.stat().st_size:
        with result_path.open("r", newline="", encoding="utf-8") as existing:
            header = next(csv.reader(existing), [])
        if header != CSV_FIELDNAMES:
            parser.error("Existing CSV has a different schema; pass --fresh-results")

    strategies = SUPPORTED_STRATEGIES if args.strategy == "all" else (args.strategy,)
    print(f"Starting experiments with strategies: {', '.join(strategies)}")
    print(f"Repetitions: {args.repeats}")
    print(f"Timeout: {args.timeout}s")
    print(f"Storage root: {storage_root}")
    print(f"Results CSV: {result_path}")

    all_succeeded = True
    for strategy in strategies:
        for repeat_index in range(1, args.repeats + 1):
            run_id = uuid.uuid4().hex[:8]
            try:
                results = run_single_iteration(
                    run_id=run_id,
                    repeat_idx=repeat_index,
                    strategy=strategy,
                    timeout=args.timeout,
                    free_rider_peer=args.free_rider_peer,
                    config_path=args.config,
                    storage_root=storage_root,
                    download_root=DOWNLOAD_ROOT,
                    random_seed=args.random_seed,
                    upload_rate_limit=args.upload_rate_limit,
                )
            except KeyboardInterrupt:
                print("Experiment interrupted; started child processes were stopped.")
                return 130
            except Exception as exc:
                print(f"{strategy} repeat {repeat_index} could not be initialized: {exc}")
                all_succeeded = False
                continue
            record_results_to_csv(results, result_path)
            if any(result["status"] != "success" for result in results):
                all_succeeded = False
            print(
                f"{strategy} repeat {repeat_index}/{args.repeats} "
                f"recorded to {result_path}"
            )

    print("\nExperiment repetitions finished.")
    return 0 if all_succeeded else 1


if __name__ == "__main__":
    raise SystemExit(main())