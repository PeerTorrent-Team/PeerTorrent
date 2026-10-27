# PeerTorrent Experiment Design

## 1. Objective

The objective of these experiments is to evaluate the performance and reliability of PeerTorrent under different file-transfer and swarm conditions.

The experiments examine:

1. The effect of piece-selection strategies on download completion time.
2. The effect of swarm size on transfer performance.
3. The effect of the initial number of seeders.
4. The effect of a peer that does not contribute uploads.
5. The effect of limiting upload rates.

The experiments also validate that completed downloads can be reconstructed and checked against the metadata generated from the original files.

## 2. System Under Test

PeerTorrent is a peer-to-peer file-sharing system in which a tracker supports peer discovery and swarm management. Peers exchange file pieces directly.

The system includes:

- A tracker for peer registration and discovery.
- Peer processes for uploading and downloading pieces.
- Metadata describing the source file and its pieces.
- Piece storage for each peer and file.
- Piece-selection strategies.
- Experiment scripts for preparing swarms, executing transfers, recording results, and generating plots.

The tracker does not transfer the file pieces itself. The participating peers perform the actual piece exchange.

## 3. Experimental Environment

### 3.1 Project structure

The experiments are run from the PeerTorrent project root.

Relevant paths include:

```text
PeerTorrent/
├── configs/
│   ├── swarm_config.json
│   ├── swarm_config_3.json
│   ├── swarm_config_5.json
│   ├── swarm_config_7_peers_2_seeders.json
│   ├── swarm_config_original.json
│   └── swarm_7_peers_backup.json
├── data/
│   ├── input_files/
│   │   ├── 20MB_text_file.txt
│   │   ├── 50mb.txt
│   │   └── 15MB.mp4
│   ├── metadata/
│   │   ├── 20MB_text_file.json
│   │   ├── 50mb.json
│   │   └── 15MB.json
│   ├── peer_storage/
│   └── downloads/
├── experiments/
│   └── plots/
├── scripts/
│   ├── create_metadata.py
│   ├── prepare_swarm_data.py
│   ├── run_experiment.py
│   └── plot_results.py
└── src/
```

This is the intended layout for the experiment workflow. Confirm that the configuration files and directories exist before running the commands. A configuration file that has been renamed or moved must be referenced using its current path.

### 3.2 Python environment

Create and activate a virtual environment:

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Install the dependencies:

```bash
python -m pip install --upgrade pip setuptools wheel
python -m pip install -r requirements.txt
```

Create the experiment output directories if needed:

```bash
mkdir -p data/peer_storage
mkdir -p data/downloads
mkdir -p experiments/plots
```

Run the experiment commands from the project root.

### 3.3 Input files

The experiments use three source files.

| File workload | Source file | Metadata file |
|---|---|---|
| `file_20mb` | `data/input_files/20MB_text_file.txt` | `data/metadata/20MB_text_file.json` |
| `file_50mb` | `data/input_files/50mb.txt` | `data/metadata/50mb.json` |
| `video_mp4` | `data/input_files/15MB.mp4` | `data/metadata/15MB.json` |

The experiment's configured piece size is 262144 bytes, equivalent to 256 KiB.

Generate metadata from the source files:

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

The metadata must correspond to the actual source bytes. Do not reuse piece hashes or file identifiers generated for a different file.

## 4. Swarm Configuration and Storage

### 4.1 Configuration files

The canonical swarm configuration is:

```text
configs/swarm_config.json
```

The other configuration files support alternative swarm setups, including different peer counts and an initial distribution with two seeders.

The intended configurations include:

- `configs/swarm_config_3.json`
- `configs/swarm_config_5.json`
- `configs/swarm_config_7_peers_2_seeders.json`
- `configs/swarm_config_original.json`
- `configs/swarm_7_peers_backup.json`

Check each configuration before using it. In particular, verify the peer IDs, source-file paths, metadata paths, active workloads, and initial piece distributions.

Configuration paths are resolved relative to the configuration file. For files stored directly in `configs/`, paths pointing to project data will normally begin with `../data/`.

### 4.2 Peer assignments

The swarm configuration specifies the initial piece distribution for each configured peer and file.

Supported initial distributions used by the preparation workflow include:

- `all` — the peer initially has all pieces.
- `none` — the peer initially has no pieces.
- `even` — the peer initially has even-numbered piece indices.
- `quarter` — the peer initially has piece indices following the configured quarter distribution.
- An integer count — the first N pieces.
- An explicit list — the specified piece indices.

The precise assignments for an experiment must be taken from its configuration file.

A peer may have local piece storage for more than one file, but a running peer process participates in one active file swarm at a time. The configured workloads are evaluated separately.

### 4.3 Storage isolation

The default piece-storage root is:

```text
data/peer_storage/
```

Piece files are organized under a peer ID and canonical file ID:

```text
data/peer_storage/<peer_id>/<canonical_file_id>/
```

The preparation and experiment scripts must use the intended shared storage root.

The `--reset` option should be used when a clean initial distribution is required. It replaces the configured peer/file storage for the preparation operation; it should not be treated as permission to delete unrelated peer data.

A fresh initial state is important because pieces downloaded in a previous experiment can otherwise affect the next experiment's results.

## 5. General Experimental Procedure

The following procedure applies to each experiment unless a specific section defines an additional treatment.

1. Confirm that the source files and metadata exist.
2. Verify the configuration file and its paths.
3. Prepare the intended initial piece distribution.
4. Run the experiment with the selected settings.
5. Preserve the CSV output for that run.
6. Inspect run status and integrity-verification results.
7. Generate plots from the relevant CSV.
8. Compare the results under the conditions actually tested.

Prepare the default swarm using:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

The runner can then execute the configured strategy comparison:

```bash
python scripts/run_experiment.py \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --fresh-results
```

The commands use three repetitions, a timeout of 180 seconds, and a random seed of 42. Keep these settings consistent across paired experiments wherever possible.

The runner's actual timing boundaries and results schema should be determined from the implementation and output. Report measured completion times and other metrics using the definitions provided by the code.

## 6. Experiment 1: Piece-Selection Strategies

### 6.1 Objective

Compare the download performance of the supported piece-selection strategies.

### 6.2 Strategies

The experiment evaluates:

- **Sequential:** selects pieces in sequential order.
- **Random:** selects pieces randomly.
- **Rarest-first:** prioritizes pieces with lower availability among connected peers.

### 6.3 Independent variable

The independent variable is the piece-selection strategy.

### 6.4 Dependent variables

The primary dependent variable is download completion time.

Additional reported variables may include success status, integrity verification, and other fields recorded by the experiment runner.

### 6.5 Controlled variables

Where applicable, keep the following consistent:

- Input file and its metadata.
- Initial piece distribution.
- Peer assignments.
- Timeout.
- Number of repetitions.
- Random seed.
- Storage preparation.
- Experiment runner and result-processing procedure.

### 6.6 Procedure

Prepare the initial swarm:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Run all supported strategies:

```bash
python scripts/run_experiment.py \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --fresh-results
```

Generate the default comparison plot:

```bash
python scripts/plot_results.py
```

If the results need to be plotted from a specific CSV, use:

```bash
python scripts/plot_results.py \
    --input experiments/distribution_results.csv \
    --output-dir experiments/plots/strategy_comparison
```

Replace `experiments/distribution_results.csv` with the actual CSV produced by the run if the configured output path differs.

### 6.7 Expected outcome

The experiment should establish whether the measured completion times differ between strategies under the tested conditions.

No strategy should be declared universally fastest based on a single run or a single file workload.

## 7. Experiment 2: Swarm Size

### 7.1 Objective

Investigate how the number of participating peers affects transfer performance.

### 7.2 Independent variable

The independent variable is the configured swarm size.

The current configuration set includes three-peer and five-peer variants, along with the default and other alternative configurations. The actual peer count and file-workload assignments must be verified in each JSON configuration.

### 7.3 Dependent variables

The primary dependent variable is download completion time.

Run success and integrity-verification status should also be inspected.

### 7.4 Controlled variables

Keep the following consistent where possible:

- Input files and metadata.
- Piece-selection strategies.
- Initial distribution pattern, adjusted only as required by the experimental design.
- Timeout and repetition count.
- Random seed.
- Result-processing procedure.

### 7.5 Procedure: three-peer configuration

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

### 7.6 Procedure: five-peer configuration

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

### 7.7 Interpretation

Compare the measured results for each configuration. Differences may be affected by the number of uploaders, the initial distribution of pieces, peer connectivity, and other settings.

To attribute a difference specifically to swarm size, the other experimental conditions should be controlled as closely as possible.

## 8. Experiment 3: Initial Seeder Count

### 8.1 Objective

Evaluate transfer performance when a swarm starts with two seeders.

### 8.2 Independent variable

The independent variable is the initial seeder configuration.

The two-seeder configuration should be checked to confirm that two peers assigned to the relevant workload have the intended complete initial piece sets.

### 8.3 Dependent variables

The primary dependent variable is download completion time.

Successful completion and integrity verification are also important for determining whether a transfer was valid.

### 8.4 Procedure

Prepare the configured two-seeder swarm:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config_7_peers_2_seeders.json \
    --reset
```

Run the experiment:

```bash
python scripts/run_experiment.py \
    --config configs/swarm_config_7_peers_2_seeders.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/two_seeders_results.csv \
    --fresh-results
```

Generate plots:

```bash
python scripts/plot_results.py \
    --input experiments/two_seeders_results.csv \
    --output-dir experiments/plots/two_seeders
```

### 8.5 Interpretation

Compare the two-seeder condition with a suitable baseline whose initial distribution and other settings are documented.

A valid comparison must distinguish the effect of seeder count from other changes to peer assignments or initial piece availability.

## 9. Experiment 4: Free-Rider Behaviour

### 9.1 Objective

Evaluate how the presence of a peer that does not upload pieces affects transfer performance.

### 9.2 Independent variable

The independent variable is whether the designated peer participates normally or is configured as a free rider.

For the documented treatment, the designated peer is `peer8`.

### 9.3 Baseline procedure

Prepare the default swarm:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Run the baseline without the free-rider option:

```bash
python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/freerider_baseline.csv \
    --fresh-results
```

### 9.4 Free-rider treatment

Prepare the same initial state:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Run the treatment:

```bash
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

Confirm that `peer8` belongs to the relevant workload in the configuration.

### 9.5 Plotting

Plot the baseline:

```bash
python scripts/plot_results.py \
    --input experiments/freerider_baseline.csv \
    --output-dir experiments/plots/freerider_baseline
```

Plot the treatment:

```bash
python scripts/plot_results.py \
    --input experiments/freerider_peer8_results.csv \
    --output-dir experiments/plots/freerider_peer8
```

### 9.6 Interpretation

Compare the baseline and treatment using successful runs and the metrics recorded by the runner.

Verify from the implementation that the free-rider option disables uploading for the intended peer. Do not assume that the option changes any other peer behaviour unless the implementation confirms it.

## 10. Experiment 5: Upload-Rate Limiting

### 10.1 Objective

Investigate how an upload-rate limit affects file-transfer performance.

### 10.2 Independent variable

The independent variable is the upload-rate-limit condition:

- Baseline: no explicit upload-rate-limit option.
- Treatment: `--upload-rate-limit 262144`.

### 10.3 Baseline procedure

Prepare the default swarm:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Run the baseline:

```bash
python scripts/run_experiment.py \
    --config configs/swarm_config.json \
    --strategy all \
    --repeats 3 \
    --timeout 180 \
    --random-seed 42 \
    --output experiments/rate_limit_baseline.csv \
    --fresh-results
```

### 10.4 Rate-limit treatment

Prepare the same initial distribution:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json \
    --reset
```

Run the treatment:

```bash
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

### 10.5 Plotting

Baseline:

```bash
python scripts/plot_results.py \
    --input experiments/rate_limit_baseline.csv \
    --output-dir experiments/plots/rate_limit_baseline
```

Treatment:

```bash
python scripts/plot_results.py \
    --input experiments/rate_limit_256k_results.csv \
    --output-dir experiments/plots/rate_limit_256k
```

### 10.6 Implementation check

Before treating the numeric setting as a particular upload speed, inspect how the runner handles the option.

```bash
grep -n -C 5 \
    'upload.rate.limit\|upload_rate_limit' \
    scripts/run_experiment.py \
    scripts/run_peer.py
```

Confirm:

- Whether the runner supports `--upload-rate-limit`.
- The units expected by the option.
- Whether the limit is applied per peer or globally.
- Which component enforces the limit.
- Whether the treatment actually reaches the upload implementation.

If the option is not supported by the current code, the treatment cannot be considered executed simply because the command was documented. Check the runner's help output:

```bash
python scripts/run_experiment.py --help
```

### 10.7 Interpretation

Compare the baseline and treatment using the same input files, initial distributions, strategies, and repetition settings.

Report the configured numeric value and the verified units and scope of the limit. Do not infer these details from the value alone.

## 11. Result Recording and Validation

### 11.1 Results

Each experimental condition should have a distinct CSV output.

The recommended output files are:

| Experiment | Results file |
|---|---|
| Default strategy comparison | Runner's configured default output |
| Three-peer swarm | `experiments/swarm_config_3_results.csv` |
| Five-peer swarm | `experiments/swarm_config_5_results.csv` |
| Two-seeder swarm | `experiments/two_seeders_results.csv` |
| Free-rider baseline | `experiments/freerider_baseline.csv` |
| Free-rider treatment | `experiments/freerider_peer8_results.csv` |
| Upload-rate baseline | `experiments/rate_limit_baseline.csv` |
| Upload-rate treatment | `experiments/rate_limit_256k_results.csv` |

Use the actual CSV path produced by the runner if its defaults differ.

The `--fresh-results` option should be used when a new independent result set is required. Use separate output files for different experiment conditions so results are not accidentally mixed.

### 11.2 Integrity validation

A transfer should not be considered successful solely because a peer process terminated or a timer stopped.

Inspect the result status and integrity fields. Successful downloads should be reconstructed and checked against the expected metadata.

Failed runs should remain identifiable in the CSV and should not be silently counted as successful measurements.

### 11.3 Plot generation

Use the plot script with the correct input CSV:

```bash
python scripts/plot_results.py \
    --input <results.csv> \
    --output-dir <output-directory>
```

Replace the placeholders with a real CSV path and output directory.

Review the plot and its source CSV together. Confirm that failed runs are handled as intended and that any reported means or standard deviations are based on the appropriate successful observations.

## 12. Reproducibility Controls

The following practices should be followed across the experiments:

1. Run commands from the project root.
2. Use the intended configuration file for each condition.
3. Verify configuration paths before preparation.
4. Generate metadata from the actual source files.
5. Use a clean, known initial piece distribution for each independent run.
6. Run baseline and treatment sequentially.
7. Avoid running two experiments that modify the same peer/file storage at the same time.
8. Keep repetition counts, timeouts, and random seeds consistent across comparisons where possible.
9. Use a separate CSV output for each condition.
10. Preserve failed-run records.
11. Check integrity before accepting a result as successful.
12. Keep plots for separate conditions in separate output directories.
13. Record the command, configuration, and relevant implementation settings for each experiment.
14. Verify the implementation of optional features before interpreting their effects.

## 13. Limitations

Experimental results are specific to the tested environment and configuration.

Performance may be influenced by:

- Initial piece distribution.
- Number of peers and seeders.
- Peer connection behaviour.
- Piece-selection strategy.
- Upload behaviour and any configured limits.
- File size and number of pieces.
- Timeout and repetition settings.
- Runtime and operating-system scheduling.
- Failed or incomplete runs.

A small number of repetitions may not capture the full variability of the system. Conclusions should be based on multiple runs and should account for failed experiments.

The documented experiment commands describe the intended workflow; an experiment should only be reported as completed after the command has run successfully and its results have been checked.

## 14. Expected Deliverables

The experiment workflow should produce:

- Metadata files for each input file.
- Prepared peer piece stores.
- CSV result files for each experiment condition.
- Plots for strategy, swarm-size, seeder-count, free-rider, and upload-rate comparisons where the corresponding runs are supported and completed.
- A written analysis of the results, including unsuccessful runs and integrity-verification outcomes.

## 15. Conclusion

This experimental design provides a repeatable approach to evaluating PeerTorrent's file-transfer behaviour.

By comparing piece-selection strategies, swarm configurations, initial seeder counts, free-rider behaviour, and upload-rate limiting, the experiments can help identify how the tested conditions affect measured transfer performance.

The reliability of the conclusions depends on consistent initial conditions, verified configuration settings, separate result files, integrity checking, and transparent reporting of the actual measurements.