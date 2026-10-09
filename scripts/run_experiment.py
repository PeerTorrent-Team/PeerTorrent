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
import subprocess
import sys
import time
import uuid
from pathlib import Path
from urllib.request import urlopen

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from scripts.prepare_swarm_data import SWARMS, prepare_all_swarms
from src.pieces.metadata import calculate_file_id
from src.pieces.metadata_serializer import load_metadata
from src.selection.selector_factory import DEFAULT_STRATEGY, SUPPORTED_STRATEGIES
from src.storage.piece_storage import PieceStorage

STORAGE_ROOT = PROJECT_ROOT / "data" / "peer_storage"
DOWNLOAD_ROOT = PROJECT_ROOT / "data" / "downloads"
DEFAULT_RESULTS_CSV = PROJECT_ROOT / "experiments" / "distribution_results.csv"

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
    "distribution_seconds",
    "integrity",
    "status",
]

SWARM_CONFIGS = [
    {
        "name": "20MB swarm",
        "metadata_path": PROJECT_ROOT / "data" / "metadata" / "20MB_text_file.json",
        "peers": [
            {"id": "peer 1", "port": 6881},
            {"id": "peer 2", "port": 6882},
            {"id": "peer 3", "port": 6883},
            {"id": "peer 4", "port": 6884},
        ],
    },
    {
        "name": "50MB swarm",
        "metadata_path": PROJECT_ROOT / "data" / "metadata" / "50mb.json",
        "peers": [
            {"id": "peer 5", "port": 6885},
            {"id": "peer 6", "port": 6886},
            {"id": "peer 7", "port": 6887},
            {"id": "peer 8", "port": 6888},
        ],
    },
]


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


def wait_for_tracker(host: str = "127.0.0.1", port: int = 6969, timeout: float = 5.0) -> bool:
    """Poll the tracker health endpoint until ready or timeout expires."""
    deadline = time.time() + timeout
    url = f"http://{host}:{port}/health"
    while time.time() < deadline:
        try:
            with urlopen(url, timeout=0.5) as resp:
                if resp.status == 200:
                    return True
        except Exception:
            time.sleep(0.1)
    return False


def verify_peer_download(
    metadata_path: Path,
    peer_id: str,
    output_path: Path,
) -> bool:
    """Run verify_download.py for a peer and return True if verification succeeded."""
    cmd = [
        sys.executable,
        str(PROJECT_ROOT / "scripts" / "verify_download.py"),
        "--metadata",
        str(metadata_path),
        "--peer-id",
        peer_id,
        "--output",
        str(output_path),
    ]
    res = subprocess.run(cmd, cwd=str(PROJECT_ROOT), capture_output=True, text=True)
    if res.returncode != 0:
        print(f"Verification failed for {peer_id}:\n{res.stderr}\n{res.stdout}")
        return False
    return True


def run_single_iteration(
    run_id: str,
    repeat_idx: int,
    strategy: str,
    timeout: float,
    free_rider_peer: str | None = None,
) -> list[dict]:
    """Execute one full iteration of the 8-peer experiment across both swarms."""
    print(f"\n{'='*70}")
    print(f"Starting Run {run_id} | Repeat {repeat_idx} | Strategy: {strategy}")
    print(f"{'='*70}")

    # 1. Reset and prepare peer storage
    prepare_all_swarms()

    # Preload swarm metadata
    swarm_meta = []
    for sc in SWARM_CONFIGS:
        meta = load_metadata(sc["metadata_path"])
        file_id = calculate_file_id(meta)
        swarm_meta.append({
            "config": sc,
            "metadata": meta,
            "file_id": file_id,
            "peers": [p["id"] for p in sc["peers"]],
        })

    # 2. Launch HTTP tracker
    tracker_cmd = [sys.executable, "-m", "src.tracker.tracker_main"]
    tracker_proc = subprocess.Popen(
        tracker_cmd,
        cwd=str(PROJECT_ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )

    if not wait_for_tracker():
        stop_process(tracker_proc)
        raise RuntimeError("HTTP tracker failed to start within timeout.")

    # 3. Launch all peers
    peer_procs: list[subprocess.Popen] = []
    try:
        for item in swarm_meta:
            meta_path = item["config"]["metadata_path"]
            for peer_info in item["config"]["peers"]:
                pid = peer_info["id"]
                port = peer_info["port"]
                peer_cmd = [
                    sys.executable,
                    "-m",
                    "src.main",
                    "--peer-id",
                    pid,
                    "--metadata",
                    str(meta_path),
                    "--port",
                    str(port),
                    "--strategy",
                    strategy,
                ]
                if free_rider_peer and pid == free_rider_peer:
                    peer_cmd.append("--no-upload")

                proc = subprocess.Popen(
                    peer_cmd,
                    cwd=str(PROJECT_ROOT),
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.DEVNULL,
                )
                peer_procs.append(proc)

        # 4. Measure time until all peers in each swarm have all pieces
        t_start = time.time()
        completion_times: dict[str, float | None] = {item["config"]["name"]: None for item in swarm_meta}

        while time.time() - t_start < timeout:
            now = time.time()
            all_swarms_finished = True

            for item in swarm_meta:
                swarm_name = item["config"]["name"]
                if completion_times[swarm_name] is not None:
                    continue

                all_peers_complete = True
                fid = item["file_id"]
                total_pieces = item["metadata"].piece_count

                for pid in item["peers"]:
                    st = PieceStorage(STORAGE_ROOT, peer_id=pid, file_id=fid)
                    for idx in range(total_pieces):
                        if not st.has_piece(idx):
                            all_peers_complete = False
                            break
                    if not all_peers_complete:
                        break

                if all_peers_complete:
                    elapsed = now - t_start
                    completion_times[swarm_name] = elapsed
                    print(f"[{swarm_name}] All peers completed distribution in {elapsed:.2f}s")
                else:
                    all_swarms_finished = False

            if all_swarms_finished:
                break

            time.sleep(0.2)

        # Check for timeouts
        for sname, ctime in completion_times.items():
            if ctime is None:
                print(f"[{sname}] Timed out after {timeout} seconds.")

    finally:
        # 5. Cleanly stop all peer processes and tracker
        for p in peer_procs:
            stop_process(p)
        stop_process(tracker_proc)
        time.sleep(1.0)  # Brief pause for OS sockets to clear

    # 6. Verify downloads and assemble results
    results: list[dict] = []
    for item in swarm_meta:
        swarm_name = item["config"]["name"]
        meta = item["metadata"]
        elapsed = completion_times[swarm_name]
        is_timeout = elapsed is None

        integrity_passed = True
        if not is_timeout:
            # Verify reconstructed files for all peers in swarm
            safe_fname = Path(meta.file_name.replace("\\", "/")).name
            for pid in item["peers"]:
                out_path = DOWNLOAD_ROOT / pid / safe_fname
                verified = verify_peer_download(
                    metadata_path=item["config"]["metadata_path"],
                    peer_id=pid,
                    output_path=out_path,
                )
                if not verified:
                    integrity_passed = False
                    break
        else:
            integrity_passed = False

        status = "success" if (not is_timeout and integrity_passed) else ("timeout" if is_timeout else "failed")
        integrity = "passed" if integrity_passed else "failed"
        dist_seconds = f"{elapsed:.2f}" if status == "success" else ""

        row = {
            "run_id": run_id,
            "repeat": repeat_idx,
            "strategy": strategy,
            "swarm": swarm_name,
            "file_name": meta.file_name,
            "file_size_bytes": meta.file_size,
            "piece_count": meta.piece_count,
            "peer_count": len(item["peers"]),
            "initial_seeder_count": 1,
            "distribution_seconds": dist_seconds,
            "integrity": integrity,
            "status": status,
        }
        results.append(row)
        print(f"Swarm: {swarm_name} | Status: {status} | Integrity: {integrity} | Distribution time: {dist_seconds}s")

    return results


def record_results_to_csv(results: list[dict], csv_path: Path) -> None:
    """Append result dictionaries to the CSV file, creating headers if needed."""
    csv_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not csv_path.exists() or csv_path.stat().st_size == 0

    with csv_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDNAMES)
        if write_header:
            writer.writeheader()
        for r in results:
            writer.writerow(r)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run automated PeerTorrent swarm distribution experiments."
    )
    parser.add_argument(
        "--strategy",
        choices=SUPPORTED_STRATEGIES,
        default=DEFAULT_STRATEGY,
        help=f"Piece selection strategy (default: {DEFAULT_STRATEGY}).",
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

    args = parser.parse_args()

    print(f"Starting experiments with strategy: {args.strategy}")
    print(f"Repetitions: {args.repeats}")
    print(f"Timeout: {args.timeout}s")
    print(f"Results CSV: {args.output}")

    for i in range(1, args.repeats + 1):
        run_id = uuid.uuid4().hex[:8]
        results = run_single_iteration(
            run_id=run_id,
            repeat_idx=i,
            strategy=args.strategy,
            timeout=args.timeout,
            free_rider_peer=args.free_rider_peer,
        )
        record_results_to_csv(results, args.output)
        print(f"Repeat {i}/{args.repeats} recorded to {args.output}")

    print("\nAll experiment repeats finished.")


if __name__ == "__main__":
    main()