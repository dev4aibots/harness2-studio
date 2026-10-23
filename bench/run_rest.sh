#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
M=nvidia/nemotron-3-ultra-550b-a55b
python3 bench/run_eval.py --model "$M" --harness ours --k 2 --cap 25
python3 bench/run_eval.py --model "$M" --harness baseline --k 2 --tasks blob-sha-length,summary-status-filter --cap 25
python3 bench/run_eval.py --model "$M" --harness baseline --k 2 --tasks hard-three-files,hard-installer-and-cli,hard-quartet --cap 25
python3 bench/run_eval.py --model "$M" --harness ours --k 2 --tasks hard-three-files,hard-installer-and-cli,hard-quartet --cap 25
