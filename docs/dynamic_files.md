# Dynamic File Selection and Swarm Preparation

This guide describes the configurable multi-file swarm workflow.

The canonical assignment file is `configs/swarm_config.json`. It defines the source files, metadata paths, peer IDs, and each peer's initial piece distribution. `configs/file_catalog.json` maps the runtime names `file_20mb`, `file_50mb`, and `video_mp4` to their metadata.

## 1. Generate Metadata

Generate metadata from each actual input file before preparing peer storage. The documented piece size is 262144 bytes (256 KiB).

```bash
python scripts/create_metadata.py data/input_files/20MB_text_file.txt \
    --output data/metadata/20MB_text_file.json --piece-size 262144

python scripts/create_metadata.py data/input_files/50mb.txt \
    --output data/metadata/50mb.json --piece-size 262144

python scripts/create_metadata.py data/input_files/15MB.mp4 \
    --output data/metadata/15MB.json --piece-size 262144
```

These commands calculate metadata from the actual source bytes. Do not copy file IDs or piece hashes from metadata generated for a different file.

Configuration paths are resolved relative to the JSON configuration file, not the shell's current working directory.

## 2. Prepare Initial Pieces

Run the preparation script:

```bash
python scripts/prepare_swarm_data.py \
    --config configs/swarm_config.json
```

The script defaults to `configs/swarm_config.json` when `--config` is omitted.

Assignments support:

- `all` — all pieces.
- `none` — no pieces.
- `even` — even-numbered piece indices (`0`, `2`, `4`, ...).
- `quarter` — indices `1`, `5`, `9`, and so on.
- An integer count — the first N pieces.
- An explicit list — the specified piece indices.

The `even` assignment initializes approximately half the pieces. Storage is scoped to peer ID and canonical file ID.

Use `--reset` only when you intend to clear the configured peer/file stores and matching output files. Without it, a conflicting existing piece set causes the script to stop. Source bytes are checked against metadata before configured storage is changed.

## 3. Start the Tracker and a Peer

Start the tracker:

```bash
python -m src.tracker.tracker_main
```

Start a peer using a catalog entry:

```bash
python -m src.main \
    --peer-id peer7 \
    --catalog configs/file_catalog.json \
    --request-file video_mp4 \
    --port 6887 \
    --interactive
```

The example assumes that the configured input files, metadata, and initial storage have already been prepared.

## 4. Switch the Active File

At the interactive prompt, the documented commands are:

```text
request file_20mb
request file_50mb
request video_mp4
status
help
quit
```

Switching files stops the old peer session and starts a new session with the same peer ID and listening port. Its next tracker announcement moves that peer ID to the newly requested file swarm. Invalid catalog names leave the current swarm running.

A peer process has one active file ID and one network session. Although `peer7` can have local storage for all three files, it cannot serve all three swarms concurrently in the current architecture. Run or switch the peer to one catalog entry at a time; its other file stores remain on disk.

Direct startup with `--metadata` remains supported for existing workflows.

## 5. Verify a Transfer

For a real transfer, start a seeder for the selected file before requesting that file from a downloader.

After the downloader has obtained all pieces, reconstruct and verify the output using the project's verification script. A successful storage-preparation run or session unit test does not, by itself, prove that a live file transfer completed.