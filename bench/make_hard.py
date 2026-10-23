"""Compose multi-bug tasks from the single-bug mutations.

One mutation is a warm-up: the failing test names point straight at the fix. Three
independent mutations in three files force the agent to hold several defects at once and keep
the suite green while fixing each, which is where a harness that demands verification should
separate from one that does not.
"""

from __future__ import annotations

import json
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import tasks as T

COMBOS = {
    "hard-three-files": ["blob-sha-length", "models-dedupe-lost", "env-template-overwrite"],
    "hard-installer-and-cli": ["include-everything", "run-argv-drops-k", "summary-status-filter"],
    "hard-quartet": [
        "blob-sha-length",
        "include-everything",
        "models-dedupe-lost",
        "run-argv-drops-k",
    ],
    "hard-cli-three": ["run-argv-drops-k", "summary-status-filter", "models-dedupe-lost"],
    "hard-installer-two": ["blob-sha-length", "include-everything"],
    "hard-env-and-cli": ["env-template-overwrite", "run-argv-drops-k", "summary-status-filter"],
    "hard-all-six": [
        "blob-sha-length",
        "include-everything",
        "models-dedupe-lost",
        "env-template-overwrite",
        "run-argv-drops-k",
        "summary-status-filter",
    ],
}


def main() -> int:
    by_id = {m["id"]: m for m in T.MUTATIONS}
    pristine = T.BENCH_PRISTINE = Path(__file__).resolve().parent / "tasks" / "_pristine"
    if not pristine.is_dir():
        T.snapshot(pristine)

    for name, ids in COMBOS.items():
        work = Path(__file__).resolve().parent / "tasks" / name
        T.snapshot(work)
        applied = []
        for mid in ids:
            spec = by_id[mid]
            target = work / spec["path"]
            source = target.read_text(encoding="utf-8")
            if spec["old"] not in source:
                raise SystemExit(f"{mid}: anchor missing")
            target.write_text(source.replace(spec["old"], spec["new"], 1), encoding="utf-8")
            applied.append(mid)
        result = T.pytest_run(work)
        failed = [ln.split(" - ")[0].strip() for ln in result.stdout.splitlines() if ln.startswith("FAILED ")]
        if result.returncode == 0 or not failed:
            print(f"[skip] {name}: suite stayed green")
            shutil.rmtree(work, ignore_errors=True)
            continue
        manifest = {
            "id": name,
            "issue": "Several independent defects were introduced across the package. "
                     "Each failing test points at one of them; all of them must be fixed.",
            "failed_tests": failed,
            "mutated_file": ", ".join(sorted({by_id[i]["path"] for i in applied})),
            "composed_of": applied,
        }
        (work / "TASK.json").write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        print(f"[task] {name}: {len(failed)} failing tests from {len(applied)} mutations")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
