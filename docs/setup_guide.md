# Setup Guide

## Requirements

Python 3.10 or newer is recommended.

## Installation

Clone or extract the PeerTorrent project and enter the project directory:

```bash
cd PeerTorrent
```

Install the dependencies:

```bash
pip install -r requirements.txt
```

## Start the Tracker

Run:

```bash
python -m src.tracker.tracker_main
```

## Start a Peer

Run:

```bash
python -m src.main --peer-id peerA --metadata metadata.json --port 6881
```

For another peer, use a different peer ID and port:

```bash
python -m src.main --peer-id peerB --metadata metadata.json --port 6882
```

## Verify Installation

Run the test suite:

```bash
pytest
```

Compile-check the source:

```bash
python -m compileall src
```
