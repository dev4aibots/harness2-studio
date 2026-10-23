# Verification log

Observed on 2026-10-21, Linux, `DISPLAY=:0`, Python 3.12.14 at
`/home/dev/.local/python312/bin/python3.12`, Harness² checkout at `/home/dev/harness2`.

Every result below is copied from the command that produced it; nothing is
inferred from reading the code.

## Static checks

```console
$ ruff check .
All checks passed!

$ python3.12 -m compileall -q h2studio run.py tools
$ echo $?
0
```

## Service and contract tests

```console
$ python3 -m pytest -q
44 passed, 1 skipped
```

The service suite covers:

- argv construction for all seven CLIs, every benchmark, subset, substrate,
  mode, split rule and the seed matrix;
- installer tree filtering, traversal rejection (including Windows drive and
  reserved-name escapes), git blob hashes, partial resume, complete-part
  promotion, HTTP 416 recovery, streamed resume after a dropped connection,
  short-body retention for resume, corrupt payload rejection, cancellation at
  phase boundaries, update backups, marker round-trips and optional-package
  commands;
- artifact discovery for all four known JSON kinds and all C1–C8 component
  paths;
- `.env` comment preservation, starter-template creation-once, 0600
  permissions and shell-over-file precedence;
- model-catalogue parsing.

The skip is `tests/test_gui_smoke.py`: the `/usr/bin/python3` running pytest has
no `tkinter`. GUI behaviour is covered by the scripts below under the Tk
interpreter.

## Entry point

```console
$ python3.12 run.py --check
GUI constructed and destroyed cleanly

$ /tmp/opencode/pkgvenv/bin/harness2-studio --check
Harness² Studio constructed and destroyed cleanly
```

## GUI smoke

```console
$ python3.12 tools/smoke.py
SMOKE OK: 9 views, theme toggle x2
```

## Button audit (all nine screens, disposable checkout)

```console
$ python3.12 tools/button_audit.py
...
9 views · 65 documented controls · 9 command stages
BUTTON AUDIT PASS
```

The audit walks every widget, asserts the exact label inventory and a callable
command for every Pill, then invokes the safe handlers with `run_action`
replaced by a recorder. It verifies setup/check/run/judge/report/demo/bridge
staging, WorkBuddy subset switching, argv preview, console filters/copy/clear,
artifact selection/copy, harness edit → save → backup → diff locking, `.env`
save/reload, install/check task start, every progress phase, guide search and
contextual topic, a real background task re-enabling every control afterwards,
and a raising callback not stopping the queue pump. Unknown or unbound controls
fail the audit.

## Behavioural self-test (real widgets, isolated state)

```console
$ python3.12 tools/selftest.py
[ok  ] non-numeric k stays in the error channel
[ok  ] missing checkout refuses to launch
[ok  ] missing checkout explains itself
[ok  ] read-only harness keeps Save disabled
[ok  ] diff mode marks component read-only
[ok  ] diff view never overwrites the file
[ok  ] console replays the log buffer
[ok  ] palette renders eight rows
[ok  ] zoom grows the type scale
[ok  ] unsaved model draft survives theme rebuild
[ok  ] palette filters actions
[ok  ] palette executes the action
[ok  ] model discovery completes off-thread — models: 591
SELFTEST PASS
```

## End-to-end demo through the GUI

```console
$ python3.12 tools/e2e.py
E2E OK: demo via GUI -> /home/dev/harness2/runs/ui-e2e/demo.json (2 tasks, 0 failed)
```

`tools/e2e.py` presses the Demo button, waits for the streamed process to finish,
and asserts `[exit 0]` plus a parsed `demo.json` with `failed == 0`. It is not a
mock: the harness executor and editor run for real.

## Auto-install from an empty folder

```console
$ python3.12 - <<'PY'   # h2studio.services.installer.install(...)
...
check        1/1 1cfe254e · 107 files
download     107/107 third_party/wb_runner/configs/.../Dockerfile
environment  1/1 Environment ready
verify       1/1 Import check passed
INSTALL DONE 107 files 0.1.0 /tmp/opencode/h2auto-install/.venv/bin/python 97.7s
PY
```

The tree API reported **107 installable files / 848,099 bytes**. Every file was
verified against its git blob SHA-1. Immediately afterwards, the new checkout
ran the real demo:

```console
$ cd /tmp/opencode/h2auto-install
$ .venv/bin/python -m harness2.cli.demo --k 1 --mode both --output runs/install-check
[accounting] 1/2 ok  ledger-1
[accounting] 2/2 ok  ledger-2
Local demo: 2 tasks completed; 0 failed.
```

A second run drove the same install **through the Install screen** (download,
progress, venv, import check), adopted the new checkout automatically, and
rebuilt all nine views against it. The status then read `Installed` with the
commit and version.

## Update, local-edit backup, resume/no-op

```console
$ python3.12 - <<'PY'   # edit harness2/demo.py, then installer.install(...)
updated 1 backed ['harness2/demo.py'] version 0.1.0 time 16.2
restored True
backup .../.harness2-studio-backups/20261021T144529Z/harness2/demo.py contains True
second 0 backed [] time 7.0
```

The edited file was preserved under `.harness2-studio-backups/<timestamp>/`,
the upstream copy was restored, and a second update downloaded **0 files**.

## Benchmark verification (real upstream failures, surfaced honestly)

Driving **Setup → Check environment** for JobBench through the GUI produced:

```console
FAIL: OpenCode checkout missing at .../dependencies/opencode ...
FAIL: job-bench-eval patch failed; run harness2-setup for this benchmark
FAIL: opencode patch failed; run harness2-setup for this benchmark
FAIL: OpenCode dependencies missing; run harness2-setup jb
FAIL: JobBench document and judge dependencies: FileNotFoundError; see README.md
FAIL: Set GOOGLE_CLOUD_PROJECT or HARNESS2_JUDGE_BASE_URL for JobBench judging
Setup incomplete: 9 issue(s). See docs/BENCHMARKS.md.
[exit 1]
```

The GUI parsed all nine issues and did not crash; this is the correct result on a
machine where the benchmark's pinned checkouts have not been installed.

## Packaging

```console
$ pip install --no-build-isolation -e .
Successfully installed harness2-studio-1.1.0

$ python -m pip wheel --no-build-isolation --no-deps -w /tmp/opencode/wheels .
Successfully built harness2_studio-1.1.0-py3-none-any.whl
```

The wheel contains 34 files, including `h2studio/guide_content.py`, all nine
views, `h2studio/assets/icon.png` and `icon.svg`. Build isolation needs PyPI for
`setuptools`; `--no-build-isolation` is the offline path documented in the
README.

## Desktop launcher

```console
$ HARNESS2_STUDIO_PYTHON=/home/dev/.local/python312/bin/python3.12 sh packaging/install-desktop.sh
Installed Harness² Studio launcher:
  desktop icon : /home/dev/Desktop/harness2-studio.desktop
  app grid     : ~/.local/share/applications/harness2-studio.desktop
  command      : "/home/dev/.local/python312/bin/python3.12" "/home/dev/harness2-studio/run.py"
  icon         : harness2-studio
$ desktop-file-validate ~/Desktop/harness2-studio.desktop   # clean
$ gio info -a metadata::trusted ~/Desktop/harness2-studio.desktop
  metadata::trusted: true
$ /home/dev/.local/python312/bin/python3.12 /home/dev/harness2-studio/run.py --check
  GUI constructed and destroyed cleanly
```

The launcher uses the verified Tk interpreter (`python3.12`), sets `StartupWMClass=harness2-studio` so GNOME groups the window with the app-grid entry, ships `Categories=Development;IDE;` (single main category), resolves its icon from the hicolor theme (128×128, 256×256, 512×512 PNG + scalable SVG), and marks the desktop file trusted so GNOME launches it without a confirmation dialog.

## Screenshots

```console
$ H2STUDIO_OFFLINE=1 python3.12 tools/shoot.py
captured .../home.png
captured .../install.png
captured .../setup.png
captured .../run.png
captured .../harness.png
captured .../runs.png
captured .../models.png
captured .../console.png
captured .../guide.png
captured .../run-wb.png
captured .../palette.png
captured .../home-light.png
captured .../run-light.png
captured .../harness-light.png
```

Captured from the real window with ImageMagick `import`; the palette capture is
an overlay inside the window, not a separately composited window.

## Independent reviews

Two read-only subagent passes reviewed the earlier build:

- **Python correctness** found 10 defects including a shadowed entry point,
  Save persisting rendered diffs, unguarded numeric parsing, a stale `recent`
  list, and a Tk-thread subprocess call. All 10 were fixed; the high-risk paths
  are asserted in `tools/selftest.py` and `tools/button_audit.py`.
- **Accessibility** measured every token pair (body text 14.8–16.4:1, focus ring
  5.5–11:1, field borders 4.1–5.4:1) and flagged keyboard traps, the palette
  contract, Esc killing jobs, and missing UI scaling. The blocking findings were
  fixed. The remaining exceptions are the toolkit's missing AT-SPI tree and a
  12 px scrollbar thumb (with wheel and keyboard scrolling as equivalents).

A **second review** of the installer/guide delta was started later and found
seven issues: terminal task handlers observing `task_running()` before the pop
(controls stayed disabled), a callback exception permanently killing the queue
pump, complete `.part` files being stranded, truncated bodies aborting the
install, cancel being ignored after downloads, Windows path escapes, and a
backup window. All seven were fixed and re-verified by the same reviewer; the
follow-up pass also found a medium truncation hole (a clean EOF shorter than the
announced size deleted resumable bytes), which is now fixed: short bodies keep
their bytes for Range resume, and only full-length hash mismatches are treated
as corruption. See "Service and contract tests" for the regression tests.

## Environment limits

- `harness2-setup jb` still needs git/codeload/dataset traffic that stalls on
  this network; the recorded end-to-end run uses the credential-free demo and
  reports the benchmark prerequisites verbatim.
- GitHub throughput varies from ~16 KB/s to under 2 KB/s on this network. A
  later live install attempt was still progressing after 15 minutes with 42/107
  files and zero errors, which is why the streamed-resume path exists; the
  completed 97.7 s run is the recorded baseline.
- LAB and WorkBuddy judging are Vertex-shaped upstream. JobBench accepts
  `HARNESS2_JUDGE_BASE_URL` plus a key, exposed in Models.
- No Roboto/Google Sans/Noto font is installed here, so the UI resolves to
  Liberation Sans (see `pick_family`); it never falls back to Tk's 10 px default.
