# PeerTorrent

A Lightweight Peer-to-Peer File Sharing System Inspired by BitTorrent

## Overview

PeerTorrent is a modular peer-to-peer file-sharing system that demonstrates BitTorrent-style distributed file transfer.

Files are divided into pieces. Peers exchange pieces directly, while a tracker is used for peer discovery and swarm management.

The project includes file metadata generation, piece storage and verification, tracker-based peer discovery, peer-to-peer communication, multiple piece-selection strategies, and repeatable performance experiments.

## Core Features

- File metadata generation
- File piece splitting
- Hash-based piece verification
- Tracker-based peer discovery
- Peer-to-peer communication
- Upload and download management
- Piece-selection strategies
- Configurable initial piece distributions
- Multi-file swarm preparation
- Experiment results recorded in CSV format
- Performance plots for comparing experiment results
- Free-rider and upload-rate-limit experiments

## Architecture

```text
                     Tracker
                        |
                  Peer Discovery
                        |
             +----------+----------+
             |          |          |
           Peer A <--> Peer B <--> Peer C
             |          |          |
             +---- Direct Piece Exchange ----+
```

The tracker handles peer discovery and swarm management. File pieces are transferred directly between peers.

## Main Modules

### Tracker

Handles peer registration, swarm management, and discovery through a threaded HTTP/JSON API. The default listener is `http://127.0.0.1:6969`.

- `POST /announce` — register or update a peer and return other peers in its swarm.
- `GET /peers?peer_id=...&file_id=...` — fetch peers in a file's swarm.
- `GET /stats` — return peer, seeder, leecher, and transfer counters.
- `GET /health` — basic health check.

The tracker is used for discovery; file pieces are transferred directly between peers over the peer wire protocol.

### Protocol and Network

Handles messages, encoding, decoding, handshakes, sockets, and connections.

### Pieces and Storage

Handles metadata, pieces, hashing, verification, storage, and reconstruction.

### Peer System

Handles downloading, uploading, scheduling, piece selection, and integration.

## Team Responsibilities

- Member 1: Pieces and Storage
- Member 2: Tracker and Peer Discovery
- Member 3: Protocol and Network Communication
- Member 4: Peer Logic and System Integration

## Installation

From the project root, create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the project dependencies:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

For development dependencies, if the project defines them in `pyproject.toml`, install:

```bash
python -m pip install ".[dev]"
```

Run the commands below from the project root unless otherwise stated.

## Running a Basic Transfer

### 1. Create metadata and prepare the seeder

Create metadata for a source file:

```bash
python scripts/create_metadata.py data/input_files/sample.bin \
    --output data/metadata/sample.bin.json
```

Prepare the seeder's piece store:

```bash
python scripts/seed_file.py \
    --file data/input_files/sample.bin \
    --metadata data/metadata/sample.bin.json \
    --peer-id seed1
```

Replace `sample.bin` with a source file that exists in your project.

### 2. Start the tracker

In one terminal:

```bash
source .venv/bin/activate
python -m src.tracker.tracker_main
```

### 3. Start peers

Start the seeder and downloader in separate terminals, using different peer IDs and ports.

Seeder:

```bash
source .venv/bin/activate
python -m src.main \
    --peer-id seed1 \
    --metadata data/metadata/sample.bin.json \
    --port 6881
```

Downloader:

```bash
source .venv/bin/activate
python -m src.main \
    --peer-id peer2 \
    --metadata data/metadata/sample.bin.json \
    --port 6882
```

### 4. Verify the downloaded file

After the downloader has acquired all pieces, reconstruct and verify its output:

```bash
python scripts/verify_download.py \
    --metadata data/metadata/sample.bin.json \
    --peer-id peer2 \
    --output data/downloads/sample.bin
```

## Storage

The default shared storage root for peer piece data is:

```text
data/peer_storage/
```

The storage layout is:

```text
data/peer_storage/
└── <peer_id>/
    └── <canonical_file_id>/
        ├── piece_0.bin
        ├── piece_1.bin
        └── ...
```

The storage root can be overridden using the `PEERTORRENT_STORAGE_ROOT` environment variable or the relevant command's `--storage` option.

The experiment preparation and runner should use the same storage root. Do not manually delete unrelated peer directories. Use the preparation script's `--reset` option when you intend to replace the configured initial piece stores.

Create common output directories if needed:

```bash
mkdir -p data/peer_storage
mkdir -p data/downloads
mkdir -p experiments/plots
```

## Testing

Run the test suite from the project root:

```bash
pytest
```

## Experiments

### Experiment overview

The experiment workflow evaluates PeerTorrent's file-transfer performance under different conditions.

The principal experiments are:

1. Piece-selection strategy comparison
2. Swarm-size comparison
3. Initial seeder-count comparison
4. Free-rider behaviour
5. Upload-rate limiting

The canonical swarm configuration is:

```text
configs/swarm_config.json
```

Additional configuration files are stored in `configs/`, including:

```text
configs/swarm_config_3.json
configs/swarm_config_5.json
configs/swarm_config_7_peers_2_seeders.json
configs/swarm_config_original.json
configs/swarm_7_peers_backup.json
```

Use a configuration only after confirming that its peer assignments, file IDs, and input/metadata paths match the intended experiment. Configuration paths should point to the project's `data/` directory; for configs in `configs/`, paths to data files normally begin with `../data/`.

### Input files and metadata

The experiment uses these input files:

| Experiment file | Input file | Metadata file |
|---|---|---|
| 20 MB text file | `data/input_files/20MB_text_file.txt` | `data/metadata/20MB_text_file.json` |
| 50 MB text file | `data/input_files/50mb.txt` | `data/metadata/50mb.json` |
| MP4 video | `data/input_files/15MB.mp4` | `data/metadata/15MB.json` |

The piece size used in the documented experiment commands is 262144 bytes (256 KiB).

Generate metadata from the actual input files:

```bash
python scripts/create_metadata.py \
    data/input_files/20MB_text_file.txt \
    --output data/metadata/20MB_text_file.json \
    --piece-size 262144

python scripts/create_metadata.py \
    data/input_files/50mb.txt \
    --output data/metadata/50mb.json \
    --piece-size 262144

python scripts/create_metadata.py \
    data/input_files/15MB.mp4 \
    --output data/metadata/15MB.json \
    --piece-size 262144
```

Metadata must be generated from the corresponding source file. Do not reuse hashes or file IDs from a different input file.

### 1. Prepare the default swarm

Prepare the initial piece distributions:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Use `--reset` when you want the preparation script to replace the configured initial peer/file stores. This is useful before a fresh experiment. Avoid running competing experiment processes at the same time.

The default configuration defines peer assignments across the `file_20mb`, `file_50mb`, and `video_mp4` workloads. Each peer process participates in one active file swarm at a time. The runner evaluates the configured file workloads separately, using the peers assigned to each workload.

Consult `configs/swarm_config.json` for the exact peer count and piece distribution. Do not assume the total number of peer entries is the same as the number of peers participating in every individual file workload.

### 2. Compare piece-selection strategies

Run all supported strategies for all configured workloads:

```bash
python scripts/run_experiment.py \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --fresh-results
```

The supported strategies are:

- `rarest-first`
- `sequential`
- `random`

To run one strategy independently, replace `all` with the desired strategy. For example:

```bash
python scripts/run_experiment.py \
    --strategy rarest-first \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --fresh-results
```

The runner records experiment results in CSV format. The timer covers the runner's configured transfer interval, and the completed stores are reconstructed and checked against metadata. Failed runs should remain identifiable in the results rather than being silently treated as successful measurements.

`--fresh-results` starts a new results file instead of mixing new rows with an existing benchmark. Check the runner's help output if you need to confirm the default results path or any available options:

```bash
python scripts/run_experiment.py --help
```

Generate the default comparison plot:

```bash
python scripts/plot_results.py
```

For an explicit input CSV and output directory, use:

```bash
python scripts/plot_results.py \
    --input experiments/distribution_results.csv \
    --output-dir experiments/plots/default_strategy_comparison
```

Replace the input path with the actual CSV produced by your run. The plot script uses the supplied result file and writes plots to the selected directory.

### 3. Compare swarm sizes

Use the configuration file corresponding to the intended swarm size.

For a three-peer configuration:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config_3.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config_3.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/swarm_config_3_results.csv \
    --fresh-results

python scripts/plot_results.py \
    --input experiments/swarm_config_3_results.csv \
    --output-dir experiments/plots/swarm_config_3
```

For a five-peer configuration:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config_5.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config_5.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/swarm_config_5_results.csv \
    --fresh-results

python scripts/plot_results.py \
    --input experiments/swarm_config_5_results.csv \
    --output-dir experiments/plots/swarm_config_5
```

Before running these commands, verify that the named config files exist and that their peer assignments represent the intended swarm sizes. Keep the strategy, repetition count, timeout, random seed, file workloads, and measurement method consistent across comparisons wherever possible.

### 4. Compare a swarm with two seeders

Use the configuration intended for the two-seeder experiment:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config_7_peers_2_seeders.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config_7_peers_2_seeders.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/two_seeders_results.csv \
    --fresh-results

python scripts/plot_results.py \
    --input experiments/two_seeders_results.csv \
    --output-dir experiments/plots/two_seeders
```

Confirm in the configuration that exactly two of the peers assigned to each relevant workload start with the intended complete file or seeder state. A filename alone does not guarantee that the configuration has the expected distribution.

### 5. Free-rider experiment

The free-rider experiment compares a normal baseline with a run in which the selected peer does not upload pieces.

First prepare the default swarm and run the baseline without a free-rider option:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/freerider_baseline.csv \
    --fresh-results
```

Then prepare the same initial swarm again and run the treatment with `peer8` configured as the free rider:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --free-rider-peer peer8 \
    --output experiments/freerider_peer8_results.csv \
    --fresh-results
```

Plot the results separately:

```bash
python scripts/plot_results.py \
    --input experiments/freerider_baseline.csv \
    --output-dir experiments/plots/freerider_baseline

python scripts/plot_results.py \
    --input experiments/freerider_peer8_results.csv \
    --output-dir experiments/plots/freerider_peer8
```

Confirm that `peer8` is assigned to the workload being tested. The free-rider option should be interpreted according to the implementation in the experiment runner; verify that it disables uploading for the intended peer and does not unintentionally change other experiment settings.

### 6. Upload-rate-limit experiment

This experiment compares a baseline run with a treatment that applies an upload-rate limit.

Run the baseline without the limit:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/rate_limit_baseline.csv \
    --fresh-results
```

Prepare the same initial state again, then run with the configured value of `262144`:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset

python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --upload-rate-limit 262144 \
    --output experiments/rate_limit_256k_results.csv \
    --fresh-results
```

Plot the baseline and treatment separately:

```bash
python scripts/plot_results.py \
    --input experiments/rate_limit_baseline.csv \
    --output-dir experiments/plots/rate_limit_baseline

python scripts/plot_results.py \
    --input experiments/rate_limit_256k_results.csv \
    --output-dir experiments/plots/rate_limit_256k
```

**Important:** Before describing this treatment as a specific rate in a report, check the implementation of `--upload-rate-limit` to establish its units and whether the limit is applied per peer or globally. The command's numeric value alone is not enough to establish that scope.

If your current runner does not recognize `--upload-rate-limit`, check:

```bash
python scripts/run_experiment.py --help
```

Do not report this experiment as completed unless the runner supports the option and the run finishes with results recorded.

### Experiment hygiene and reproducibility

For meaningful comparisons:

- Run the baseline and treatment sequentially.
- Start each comparison from the intended initial piece distribution.
- Use a separate CSV output for each experiment condition.
- Keep the input files and generated metadata unchanged between paired runs.
- Use consistent strategy settings, repetition counts, timeouts, and random seeds.
- Check each CSV for failed or incomplete runs before interpreting averages.
- Compare integrity-verified successful transfers separately from failures.
- Keep plot output directories separate so one experiment does not overwrite another's figures.
- Record the exact configuration file and command used for each result.
- Do not infer a performance improvement from a single repetition.

### Measurements

The experiments can be used to evaluate:

- Transfer completion time
- Successful and failed runs
- File and piece integrity
- Effects of piece-selection strategy
- Effects of swarm size
- Effects of initial seeder count
- Effects of a peer that does not upload
- Effects of an upload-rate limit

Interpret the measurements in light of the experiment setup and the fields actually recorded in the CSV. Do not claim that a metric was measured if it is not present in the output or otherwise collected by the implementation.

## Development Workflow

```text
Design Interfaces
       |
Parallel Development
       |
Module Testing
       |
Integration
       |
Multi-peer Testing
       |
Experiment Analysis
```

## AI Usage

AI usage is documented in `AI-USE.md`. AI is used for documentation, debugging support, explanations, and testing assistance.

## Future Extensions

- Choking mechanism
- Optimistic unchoking
- End-game mode
- Distributed hash table (DHT)
- Super seeding

## Conclusion

PeerTorrent demonstrates the fundamentals of distributed peer-to-peer file sharing by allowing peers to discover one another, exchange pieces, verify received data, and reconstruct files. Its experiment workflow supports repeatable comparisons of piece-selection strategies and configurable swarm conditions.