# Member 1 Handoff: Pieces and Storage

## Scope

This change set covers the Member 1 responsibility listed in the project README:

- Preparing a seeder's piece storage from the original file.
- Verifying downloaded pieces and reconstructing the final output.
- Documenting the commands for those operations.

It intentionally does not change tracker transport, piece-selection defaults, choking policy, protocol message definitions, or `CANCEL` behavior.

## Files changed

- `src/storage/file_workflow.py` — adds the reusable `seed_source_file()` and `verify_downloaded_file()` workflows.
- `scripts/seed_file.py` — checks an original file against metainfo and populates the selected peer's piece store.
- `scripts/verify_download.py` — verifies each stored piece, reconstructs the output, checks the final size and whole-file hash, and only then replaces the destination file.
- `scripts/create_metadata.py` — supports direct execution from the project root without requiring an editable install.
- `tests/test_file_workflow.py` — covers valid seeding, metadata mismatches, reconstruction, corrupt/missing pieces, empty files, and peer startup from seeded storage.
- `README.md` and `docs/setup_guide.md` — document the workflow.

## Commands

Run these from the repository root.

Create metainfo:

```bash
python scripts/create_metadata.py path/to/original.bin \
    --output data/metadata/original.bin.json
```

Prepare the seeder's piece storage:

```bash
python scripts/seed_file.py \
    --file path/to/original.bin \
    --metadata data/metadata/original.bin.json \
    --peer-id seed1
```

Start the tracker and seed peer in separate terminals:

```bash
python -m src.tracker.tracker_main
python -m src.main --peer-id seed1 --metadata data/metadata/original.bin.json --port 6881
```

Start downloaders with the same metainfo, distinct peer IDs and distinct ports. Once a downloader has received all pieces, reconstruct and verify its stored data:

```bash
python scripts/verify_download.py \
    --metadata data/metadata/original.bin.json \
    --peer-id peer2 \
    --output data/downloads/original.bin
```

Use the same `--storage` root for seeding, running a peer, and verifying its stored pieces if you override the default `data/peer_storage` directory.

## Checks run

- `python -m pytest -q` — 91 tests passed.
- `python -m compileall -q src scripts` — passed.
- CLI round trip — created metainfo, seeded six pieces, reconstructed the file, verified its SHA-256 hash, and byte-compared the output with the source.

## Merge note

Review and merge this change set as the Member 1 pieces/storage contribution. Keep the existing `CANCEL` message definitions and handling untouched. The tracker and experiment changes should remain separate follow-up contributions.
