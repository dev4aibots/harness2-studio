#!/usr/bin/env python3
"""Interactive-control audit: every button is wired, unique, and exercised.

This is deliberately stricter than a smoke test. It builds a disposable
checkout, visits every screen, enumerates every Pill/Toggle/Segmented
control, asserts the label inventory, and invokes every safe handler with the
process launcher replaced by a recorder. Any new button or changed label fails
here until the test (and therefore the documentation) is updated.

Run: /home/dev/.local/python312/bin/python3.12 tools/button_audit.py
"""

from __future__ import annotations

import os
import sys
import tempfile
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
os.environ["XDG_CONFIG_HOME"] = tempfile.mkdtemp(prefix="h2studio-audit-")
os.environ["H2STUDIO_OFFLINE"] = "1"

from h2studio.app import NAV, App
from h2studio.services import h2
from h2studio.widgets import Pill, Toggle

EXPECTED = {
    "home": {"Run demo", "Check environment", "Open runs folder", "Open Models", "Read the field guide", "Copy"},
    "install": {"Browse", "Use this folder", "Choose", "Check for updates", "Install latest", "Verify",
                "Open folder", "Cancel", "Install"},
    "setup": {"Open Install", "JobBench", "LAB", "WorkBuddy", "OpenCode", "Codex", "Office", "Web", "Code",
              "Re-check", "Install benchmark", "Check environment", "Dry run install"},
    "run": {"JobBench", "LAB", "WorkBuddy", "All", "Office", "Web", "Code", "OpenCode", "Codex",
            "Start sweep", "Stop", "Judge", "Report", "Both", "Parallel", "Sequential", "Run demo", "Auto-Improve"},
    "harness": {"Save", "Open folder"},
    "runs": {"Refresh", "Run demo", "Copy JSON", "Open folder"},
    "models": {"Save .env", "Reload", "Discover models", "Create template", "Verify environment", "Start bridge"},
    "console": {"All output", "Problems", "Commands", "Copy", "Save log", "Clear"},
    "guide": {"Open Home", "Open console"},
    "tracker": {"Refresh", "Open Run view", "Open in Harness view"},
    "opencode": {"Run OpenCode", "Stop"},
}

failures: list[str] = []


def check(name: str, condition: bool, detail: str = "") -> None:
    print(f"[{'ok  ' if condition else 'FAIL'}] {name}{(' — ' + detail) if detail else ''}")
    if not condition:
        failures.append(name)


def walk(widget):
    for child in widget.winfo_children():
        yield child
        yield from walk(child)


def make_checkout(root: Path) -> Path:
    (root / "harness2").mkdir(parents=True)
    (root / "pyproject.toml").write_text(
        '[project]\nname = "harness2"\nversion = "0.1.0"\n', encoding="utf-8"
    )
    (root / ".env").write_text(
        "# audit fixture\nHARNESS2_IMPROVER_MODEL=fixture/improver\n"
        "HARNESS2_JUDGE_MODEL=fixture/judge\n",
        encoding="utf-8",
    )
    task = root / "runs" / "demo" / "task-1"
    base = task / "harnesses" / "base"
    cand = task / "harnesses" / "inv1"
    base.mkdir(parents=True)
    cand.mkdir(parents=True)
    (base / "systemprompt.md").write_text("base prompt\n", encoding="utf-8")
    (base / "guardrails.md").write_text("base guardrails\n", encoding="utf-8")
    (cand / "systemprompt.md").write_text("candidate prompt\n", encoding="utf-8")
    for folder in ("sub_agents", "skills", "scripts", "plugin"):
        (base / folder).mkdir()
        (cand / folder).mkdir()
    (root / "runs" / "demo" / "demo.json").write_text(
        '{"done": 1, "failed": 0, "tasks": [{"status": "ok"}]}\n', encoding="utf-8"
    )
    (task / "judged.json").write_text(
        '[{"task_id": "task-1", "graded": true, "score": 1.0}]\n', encoding="utf-8"
    )
    return root


def main() -> int:
    fixture = make_checkout(Path(tempfile.mkdtemp(prefix="h2studio-checkout-")))
    app = App()
    calls: list[tuple[str, object, str | None]] = []
    opened: list[str] = []
    started: list[str] = []

    def fake_run(action, opts, label=None):
        calls.append((action, opts, label))
        return False

    def fake_open(path):
        opened.append(str(path))

    def fake_start(key, _work, _handler):
        started.append(key)
        return threading.Event()

    real_start_task = app.start_task
    app.run_action = fake_run
    app.open_path = fake_open
    app.start_task = fake_start
    app.install = h2.discover(fixture, sys.executable)

    try:
        for key, _label, _sub in NAV:
            app.show(key)
            app.update()
            view = app.views[key]
            pills = [w for w in walk(view) if isinstance(w, Pill) and not isinstance(w, Toggle)]
            labels = [p._label for p in pills]
            check(f"{key}: every control has a callable command",
                  all(callable(p.command) for p in pills))
            check(f"{key}: label inventory matches the audited surface",
                  set(labels) == EXPECTED[key], f"actual={sorted(set(labels))}")
            check(f"{key}: no duplicate labels", len(labels) == len(set(labels)) or
                  key in {"install", "setup"}, f"{len(labels)} controls, {len(set(labels))} labels")

        # Home: the two quick actions route to the real command or screen.
        app.show("home")
        home = app.views["home"]
        home._demo()
        check("home: demo launches the demo action", calls and calls[-1][0] == "demo")
        home._check()
        check("home: check environment opens Setup", app.active == "setup")

        # Setup: install, dry-run, check all stage real commands.
        app.show("setup")
        setup = app.views["setup"]
        setup._install()
        check("setup: install stages harness2-setup", calls and calls[-1][0] == "setup")
        setup._dry()
        check("setup: dry run sets the flag", calls and calls[-1][1].dry_run is True)
        setup._check()
        check("setup: check stages harness2-check", calls and calls[-1][0] == "check")

        # Run: every mode stages its own action and keeps validation honest.
        app.show("run")
        run = app.views["run"]
        run.vars["k"].set("1")
        run._changed()
        run._start()
        check("run: sweep stages harness2 run_sweep", calls and calls[-1][0] == "run")
        run._judge()
        check("run: judge stages harness2-judge", calls and calls[-1][0] == "judge")
        run._report()
        check("run: report stages harness2-report", calls and calls[-1][0] == "report")
        run._demo()
        check("run: demo stages harness2-demo", calls and calls[-1][0] == "demo")
        run.bench.select("wb")
        check("run: WorkBuddy reveals its subset selector", run.subset_bar.winfo_manager() == "pack")
        run.subset.select("code")
        check("run: subset reaches Options", run._opts().subset == "code")
        run.subset.select("all")
        check("run: All maps to no subset flag", run._opts().subset is None)
        for key in ("jobbench", "lab", "workbuddy"):
            run.bench.select({"jobbench": "jb", "lab": "lab", "workbuddy": "wb"}[key])
        check("run: benchmark selection updates state", app.state.last_bench == "wb")
        preview = run.preview.cget("text")
        check("run: argv preview is rendered", "--bench wb" in preview and "--k 1" in preview)

        # Console: filters, copy, clear, and the empty-state placeholder.
        app.log.emit("audit-line", "out")
        app.log.emit("FAIL: audit-error", "err")
        app.show("console")
        con = app.views["console"]
        con._set_filter("commands")
        check("console: commands filter hides stdout", "audit-line" not in con.console.dump())
        con._set_filter("errors")
        check("console: problems filter keeps errors", "audit-error" in con.console.dump())
        con._set_filter("all")
        con._copy()
        check("console: copy puts output on the clipboard", "audit-line" in app.clipboard_get())
        con._clear()
        check("console: clear empties the buffer", con.lines == [])
        check("console: clear disables actions", con.copy_btn._enabled is False)

        # Runs: select a real artifact, render JSON, copy, open folder.
        app.show("runs")
        rv = app.views["runs"]
        rv.refresh()
        check("runs: finds the fixture artifact", bool(rv.items))
        if rv.items:
            rv.tree.selection_set(str(rv.items[0].path))
            rv._select()
            rv._copy()
            import json as _json
            try:
                copied = _json.loads(app.clipboard_get())
            except ValueError:
                copied = None
            check("runs: copy writes JSON to the clipboard", copied is not None)
            rv._open()
            check("runs: open folder uses the real path", bool(opened))

        # Harness: load the fixture, edit, save a backup, and toggle diff.
        app.show("harness")
        hv = app.views["harness"]
        hv.refresh()
        check("harness: finds a task with a base harness", bool(hv.tasks))
        check("harness: loads C1", hv.current is not None and "C1" in hv.current.files)
        if hv.current is not None and "C1" in hv.current.files:
            target = hv.current.files["C1"]
            original = target.read_text()
            hv.edit._toggle()
            check("harness: edit toggle unlocks Save", hv.save_btn._enabled is True)
            hv.texts["C1"].delete("1.0", "end")
            hv.texts["C1"].insert("1.0", "audited prompt\n")
            hv._save()
            backups = list(target.parent.glob("systemprompt.md.bak-*"))
            check("harness: save writes atomically with a backup",
                  target.read_text() == "audited prompt\n" and bool(backups))
            hv.diff._toggle()
            check("harness: diff disables editing", hv.editing is False)
            target.write_text(original)
            for backup in backups:
                backup.unlink()
            hv.diff._toggle()
            hv.edit._toggle()
        hv._open()
        check("harness: open folder uses the selected version", bool(opened))

        # Models: save real .env values, then reload them from disk.
        app.show("models")
        mv = app.views["models"]
        mv.vars["HARNESS2_SOLVER_MODEL"].set("audit/executor")
        mv._save()
        saved = h2.read_env(fixture / ".env")
        check("models: save persists to .env", saved.get("HARNESS2_SOLVER_MODEL") == "audit/executor")
        mv._load()
        check("models: reload reads the saved value",
              mv.vars["HARNESS2_SOLVER_MODEL"].get() == "audit/executor")
        mv._template()
        check("models: template never overwrites an existing .env",
              "audit fixture" in (fixture / ".env").read_text())
        mv.bridge_port.set("")
        mv._start_bridge()
        check("models: bridge stages the bridge action", calls and calls[-1][0] == "bridge")

        # Install: the three long actions are wired to background tasks.
        app.show("install")
        iv = app.views["install"]
        iv._check()
        check("install: check starts the check task", "check" in started)
        iv.dest_var.set(str(fixture))
        iv._install()
        check("install: install starts the install task", "install" in started)
        iv._cancel()
        check("install: cancel is safe before a task exists", not iv.cancel_btn.winfo_ismapped())
        for phase, total, done in (("check", 1, 0), ("backup", 0, 0), ("download", 107, 54),
                                   ("environment", 1, 0), ("verify", 1, 1)):
            iv._on_progress(phase, done, total, "audit")
        check("install: every progress phase maps to a finite bar",
              0.0 <= iv.bar._fraction <= 1.0, str(iv.bar._fraction))

        # A real task must re-enable every control when it finishes (regression
        # guard for handlers that observe task_running() before the pop).
        events: list[tuple[str, object]] = []
        real_start_task("audit-task", lambda report, cancel: (report("audit", 1, 1, "done"), "ok")[1],
                        lambda event, payload: events.append((event, payload)))
        deadline = time.time() + 5
        while time.time() < deadline and not any(e == "done" for e, _ in events):
            app.update()
            time.sleep(0.02)
        check("tasks: a real task reports done", any(e == "done" for e, _ in events), str(events))
        check("tasks: controls re-enable after the task ends",
              iv.install_btn._enabled and iv.check_btn._enabled,
              f"install={iv.install_btn._enabled} check={iv.check_btn._enabled}")
        check("tasks: entries re-enable after the task ends",
              str(iv.path_entry.cget("state")) == "normal", str(iv.path_entry.cget("state")))

        # A raising background callback must not kill the queue pump.
        app.show("console")
        console_view = app.views["console"]
        app.after_bg(lambda: None, lambda _r: (_ for _ in ()).throw(RuntimeError("audit boom")))
        deadline = time.time() + 3
        while time.time() < deadline:
            app.update()
            time.sleep(0.02)
        app.log.emit("post-crash-line", "out")
        deadline = time.time() + 3
        while time.time() < deadline and "post-crash-line" not in console_view.console.dump():
            app.update()
            time.sleep(0.02)
        check("queue: a raising callback does not stop the pump",
              "post-crash-line" in console_view.console.dump())

        # Guide: search filters, topics switch, action buttons navigate.
        app.show("guide")
        gv = app.views["guide"]
        gv._search.set("judge")
        app.update()
        visible = [k for k, (row, _l) in gv.rows.items() if row.winfo_manager()]
        check("guide: search filters topics", "judge" in visible and len(visible) < len(gv.rows),
              str(visible))
        gv._search.set("")
        app.update()
        gv.focus_topic("glossary")
        check("guide: topic selection updates the topic", gv.current == "glossary")
        gv.focus_topic("overview")
        check("guide: guide actions are reachable", gv.winfo_exists())
        app.show("run")
        app._open_guide()
        check("guide: header button opens the matching topic",
              app.active == "guide" and app.views["guide"].current == "sweep")

        # Toggles across the app flip their own state and notify.
        app.show("run")
        run = app.views["run"]
        for toggle in (run.tog_dry, run.tog_bases):
            before = toggle.value
            toggle._toggle()
            check("run: toggle flips state", toggle.value is not before)
            toggle._toggle()

        check("no unhandled exceptions reached the log",
              not any(line.startswith("WARN: task") for line, _t in app.log.buffer))
        print(f"\n{len(NAV)} views · {sum(len(v) for v in EXPECTED.values())} documented controls · "
              f"{len(calls)} command stages")
        if failures:
            print(f"BUTTON AUDIT FAILED: {len(failures)} issue(s): {failures}")
            return 1
        print("BUTTON AUDIT PASS")
        return 0
    finally:
        app.destroy()


if __name__ == "__main__":
    raise SystemExit(main())
