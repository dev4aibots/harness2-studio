#!/usr/bin/env bash
set -u
cd "$(dirname "$0")/.."
MODEL=nvidia/nemotron-3-ultra-550b-a55b
for arm in baseline ours; do
  python3 bench/run_eval.py --model "$MODEL" --harness "$arm" --k 2 --cap 25
done
