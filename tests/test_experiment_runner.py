from __future__ import annotations

import csv
from pathlib import Path

import pytest

import scripts.run_experiment as runner
from src.selection.random_selector import RandomSelector
from src.pieces.metadata_serializer import build_metadata, save_metadata


def test_load_swarm_configs_has_three_seven_peer_workloads() -> None:
    groups = runner.load_swarm_configs()

    assert [(group["name"], len(group["peers"])) for group in groups] == [
        ("file_20mb", 7),
        ("file_50mb", 7),
        ("video_mp4", 7),
    ]
    assert set(groups[0]["assignments"]) == {
        "peer1", "peer4", "peer7", "peer8", "peer9", "peer10", "peer11"
    }


def test_record_results_to_csv_preserves_failed_runs_and_rejects_old_schema(
    tmp_path: Path,
) -> None:
    result_path = tmp_path / "results.csv"
    row = {field: "" for field in runner.CSV_FIELDNAMES}
    row.update({"strategy": "random", "status": "timeout", "error": "deadline"})

    runner.record_results_to_csv([row], result_path)

    with result_path.open(newline="", encoding="utf-8") as handle:
        rows = list(csv.DictReader(handle))
    assert rows[0]["status"] == "timeout"
    assert rows[0]["error"] == "deadline"
    result_path.write_text("old,header\n", encoding="utf-8")
    with pytest.raises(ValueError, match="differs"):
        runner.record_results_to_csv([row], result_path)


def test_strategy_cli_rejects_unknown_strategy(monkeypatch) -> None:
    monkeypatch.setattr("sys.argv", ["run_experiment.py", "--strategy", "greedy"])

    with pytest.raises(SystemExit) as error:
        runner.main()

    assert error.value.code == 2


class FakeProcess:
    def __init__(self, *, returncode: int | None = None) -> None:
        self.returncode = returncode
        self.terminated = False
        self.killed = False

    def poll(self) -> int | None:
        return self.returncode

    def terminate(self) -> None:
        self.terminated = True
        self.returncode = 0

    def wait(self, timeout: float | None = None) -> int:
        return self.returncode or 0

    def kill(self) -> None:
        self.killed = True
        self.returncode = -9


def test_runner_records_peer_launch_failure_and_cleans_children(
    tmp_path: Path, monkeypatch
) -> None:
    source = tmp_path / "fixture.bin"
    source.write_bytes(b"fixture data")
    metadata_path = tmp_path / "fixture.json"
    save_metadata(build_metadata(str(source), piece_size=3), str(metadata_path))
    workload = {
        "name": "fixture",
        "metadata_path": metadata_path,
        "peers": [{"id": "peer1"}, {"id": "peer2"}],
        "assignments": {"peer1": "all", "peer2": "none"},
    }
    monkeypatch.setattr(runner, "load_swarm_configs", lambda _path: [workload])
    monkeypatch.setattr(runner, "prepare_from_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "validate_initial_distribution", lambda *args: None)
    monkeypatch.setattr(runner, "wait_for_tracker", lambda **kwargs: True)
    ports = iter((41001, 41002, 41003))
    monkeypatch.setattr(runner, "allocate_free_port", lambda: next(ports))
    children: list[FakeProcess] = []
    calls = 0

    def fake_popen(*args, **kwargs):
        nonlocal calls
        calls += 1
        if calls == 3:
            raise OSError("simulated peer launch failure")
        process = FakeProcess()
        children.append(process)
        return process

    monkeypatch.setattr(runner.subprocess, "Popen", fake_popen)

    rows = runner.run_single_iteration(
        run_id="test-run",
        repeat_idx=1,
        strategy="sequential",
        timeout=1,
        config_path=tmp_path / "unused.json",
        storage_root=tmp_path / "storage",
        download_root=tmp_path / "downloads",
    )

    assert rows[0]["status"] == "process_failure"
    assert "simulated peer launch failure" in rows[0]["error"]
    assert len(children) == 2
    assert all(child.terminated for child in children)


def test_runner_timeout_stops_all_started_processes(tmp_path: Path, monkeypatch) -> None:
    source = tmp_path / "fixture.bin"
    source.write_bytes(b"fixture data")
    metadata_path = tmp_path / "fixture.json"
    save_metadata(build_metadata(str(source), piece_size=3), str(metadata_path))
    workload = {
        "name": "fixture",
        "metadata_path": metadata_path,
        "peers": [{"id": "peer1"}, {"id": "peer2"}],
        "assignments": {"peer1": "all", "peer2": "none"},
    }
    monkeypatch.setattr(runner, "load_swarm_configs", lambda _path: [workload])
    monkeypatch.setattr(runner, "prepare_from_config", lambda *args, **kwargs: None)
    monkeypatch.setattr(runner, "validate_initial_distribution", lambda *args: None)
    monkeypatch.setattr(runner, "wait_for_tracker", lambda **kwargs: True)
    ports = iter((42001, 42002, 42003))
    monkeypatch.setattr(runner, "allocate_free_port", lambda: next(ports))
    children: list[FakeProcess] = []
    monkeypatch.setattr(
        runner.subprocess,
        "Popen",
        lambda *args, **kwargs: children.append(FakeProcess()) or children[-1],
    )

    rows = runner.run_single_iteration(
        run_id="timeout-run",
        repeat_idx=1,
        strategy="rarest-first",
        timeout=0,
        config_path=tmp_path / "unused.json",
        storage_root=tmp_path / "storage",
        download_root=tmp_path / "downloads",
    )

    assert rows[0]["status"] == "timeout"
    assert len(children) == 3
    assert all(child.terminated for child in children)


def test_random_selector_is_reproducible_with_seed() -> None:
    pieces = list(range(20))
    availability = {piece: 1 for piece in pieces}
    first = RandomSelector(seed=17)
    second = RandomSelector(seed=17)

    assert [first.select_piece(pieces, availability) for _ in range(10)] == [
        second.select_piece(pieces, availability) for _ in range(10)
    ]


def test_plot_handles_empty_failed_and_verified_csv(tmp_path: Path, capsys) -> None:
    from scripts.plot_results import create_plot

    csv_path = tmp_path / "results.csv"
    graph_path = tmp_path / "graph.png"
    csv_path.write_text("", encoding="utf-8")
    assert create_plot(csv_path, graph_path) is None
    assert not graph_path.exists()

    fields = ["strategy", "swarm", "distribution_seconds", "integrity", "status"]
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerow({"strategy": "random", "swarm": "video_mp4", "distribution_seconds": "", "integrity": "not_checked", "status": "timeout"})
    assert create_plot(csv_path, graph_path) is None
    assert "timeout: 1" in capsys.readouterr().out

    with csv_path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writerow({"strategy": "sequential", "swarm": "video_mp4", "distribution_seconds": "2.5", "integrity": "passed", "status": "success"})
    assert create_plot(csv_path, graph_path) == graph_path
    assert graph_path.is_file()
