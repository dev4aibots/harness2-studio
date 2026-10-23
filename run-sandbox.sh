#!/usr/bin/env bash
# Sandbox launcher for Harness² Studio.
#
# The sandbox is headless (no DISPLAY) and exports a NO_PROXY whose bracketed
# IPv6 entries crash httpx-based tools that talk to the local model proxy.
# This launcher fixes the environment, attaches a virtual display when none
# exists, and hands every argument through to run.py (including --check).
set -euo pipefail
cd "$(dirname "$0")"
export NO_PROXY="localhost,127.0.0.1" no_proxy="localhost,127.0.0.1"
export PYTHONUNBUFFERED=1
if [ -z "${DISPLAY:-}" ]; then
  exec xvfb-run -a -s "-screen 0 1600x1000x24" python3 run.py "$@"
fi
exec python3 run.py "$@"
