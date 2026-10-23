"""Plain-language guide content.

Written for a smart person who has never run a research harness. Every claim
here maps to a real CLI flag or file in google-research/harness2; no invented
features. The Guide view renders these blocks and links each topic to the screen
that performs the work.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Topic:
    key: str
    kicker: str
    title: str
    summary: str
    steps: tuple[str, ...]
    note: str
    action: str
    view: str


TOPICS: tuple[Topic, ...] = (
    Topic(
        key="overview",
        kicker="Start here",
        title="What Harness² does — in plain language",
        summary=(
            "Harness² is Google Research's open-source system for improving the “harness” "
            "around a frozen language model. The harness is everything except the model: "
            "instructions, guardrails, memory, tool descriptions, sub-agents, skills, scripts "
            "and plugins.\n\n"
            "It runs a loop. An executor tries benchmark tasks using the current harness. An "
            "improver reads what happened and edits the harness. The next round uses the edited "
            "harness, so the system can get better without retraining the model. A judge then "
            "scores the artifacts, and a report turns those scores into tables.\n\n"
            "Studio is a desktop control room for that loop. It runs the same seven command-line "
            "tools that the research repo ships, shows the exact command before it runs, streams "
            "the real output, and lets you inspect or edit the eight harness components."
        ),
        steps=(
            "Install or locate the official source on the Install screen.",
            "Connect a model for the executor, improver and judge on Models.",
            "Run the free demo to prove the pipeline works.",
            "Install a benchmark on Setup, then run a small sweep.",
            "Judge the results, generate a report, and inspect the artifacts.",
        ),
        note=(
            "The demo is local and free. Real benchmark sweeps call a model and can cost money; "
            "start with one task and a dry run."
        ),
        action="Open Home",
        view="home",
    ),
    Topic(
        key="install",
        kicker="Setup · step 1",
        title="Install or update Harness² without git",
        summary=(
            "The Install screen downloads the current main branch of google-research/harness2 "
            "straight from GitHub into a folder you choose. It does not need git, and it does "
            "not install anything globally.\n\n"
            "Every file is checked against the SHA-1 hash GitHub publishes for that exact file. "
            "If a download is interrupted, the partial file is kept and the next attempt resumes "
            "it. Updates only replace files that actually changed, and any local edits are copied "
            "into .harness2-studio-backups before they are replaced.\n\n"
            "Finally Studio creates a private .venv in the checkout (the same interpreter you use "
            "for this app) and runs the demo's --help to prove the package imports."
        ),
        steps=(
            "Open Install. Choose an empty folder, or leave the default ~/harness2.",
            "Press Check for updates. The latest commit and date appear.",
            "Press Install latest (or Update). Watch the phase, progress bar and detail line.",
            "When it finishes, press Verify to run the import check again.",
            "If you already have a checkout, type its path and press Use this folder.",
        ),
        note=(
            "Needs an internet connection to GitHub. A full install is roughly 850 KB of source, "
            "not the multi-megabyte demo assets. The source stays Apache-2.0 licensed and local."
        ),
        action="Open Install",
        view="install",
    ),
    Topic(
        key="models",
        kicker="Setup · step 2",
        title="Connect any coding agent or model",
        summary=(
            "Harness² uses three roles. The executor does the benchmark work. The improver reads "
            "the results and rewrites harness components. The judge scores the finished artifacts. "
            "They can be the same model or three different ones — a separate judge is less likely "
            "to favour its own work.\n\n"
            "Models are configured in the checkout's .env file, never inside this app's state. "
            "Studio writes the file atomically, keeps your comments, masks keys on screen and sets "
            "permissions to owner-only. You can point at a hosted provider or a local "
            "OpenAI-compatible gateway by supplying a base URL and key."
        ),
        steps=(
            "Open Models.",
            "Enter the executor model, then its base URL and key if your gateway needs them.",
            "Repeat for the improver and the judge.",
            "Press Save .env, then Discover models to verify the endpoint answers. If no .env exists yet, press Create template first.",
            "Run Check environment on Setup to confirm the harness sees the values.",
        ),
        note=(
            "The demo needs no model. A benchmark sweep fails fast when HARNESS2_SOLVER_MODEL is "
            "missing — that is the most common first error, and the Models screen fixes it."
        ),
        action="Open Models",
        view="models",
    ),
    Topic(
        key="demo",
        kicker="First proof",
        title="Run the free demo",
        summary=(
            "The demo is a real run of the Harness² recursion and library code with deterministic "
            "local editors instead of a language model. It needs no credentials, makes no network "
            "calls and costs nothing. It proves that the checkout, interpreter, CLI wiring and "
            "artifact writer all work on this machine.\n\n"
            "It writes a small library of harness variants and a demo.json summary under "
            "runs/demo. You can open every file from the Runs screen."
        ),
        steps=(
            "Open Run and choose the Demo tab.",
            "Keep k at 2 and press Start demo.",
            "Watch the Console; the last line reports tasks completed and failed.",
            "Open Runs, select the demo artifact, and inspect demo.json.",
        ),
        note=(
            "A green demo does not prove a benchmark's dataset or Docker dependencies are "
            "installed. It proves the harness itself runs."
        ),
        action="Open Run",
        view="run",
    ),
    Topic(
        key="benchmarks",
        kicker="Benchmarks",
        title="Install a benchmark and check its prerequisites",
        summary=(
            "Harness² ships three benchmark adapters. JobBench (jb) is software-engineering work "
            "and needs its dataset checkout. LAB (lab) is a research-agent benchmark that also "
            "needs pandoc and poppler. WorkBuddy (wb) runs office, web or code tasks and needs "
            "Docker plus workbuddy-bench.\n\n"
            "The Setup screen shows a live prerequisite checklist for the selected benchmark. "
            "“Install benchmark” runs the real harness2-setup command, which downloads that "
            "benchmark's pinned runner, overlays and data. “Dry run” prints the plan without "
            "changing the machine. “Check environment” runs harness2-check and shows every "
            "FAIL, WARN and OK line verbatim."
        ),
        steps=(
            "Open Setup and pick JobBench, LAB or WorkBuddy.",
            "Read the prerequisite card; fix anything marked MISSING.",
            "Press Dry run install to see the plan.",
            "Press Install benchmark and let it finish.",
            "Press Check environment until the failures you care about are explained.",
        ),
        note=(
            "Benchmark installs use git, uv, Node.js and sometimes Docker. They are separate from "
            "the Harness² source install and can take a long time. A failure here does not break "
            "the app or the demo."
        ),
        action="Open Setup",
        view="setup",
    ),
    Topic(
        key="sweep",
        kicker="Core workflow",
        title="Run a sweep (the actual experiment)",
        summary=(
            "A sweep runs benchmark tasks through several rounds of harness improvement. k is how "
            "many recursion rounds to run. Parallel mode explores variants at the same level "
            "together; sequential mode carries one line of improvement forward. A seed makes task "
            "selection reproducible. Split, domains, workers and a task cap let you start small.\n\n"
            "Every command is staged in the Run form, validated, and shown as the exact argv before "
            "you start it. Output streams into Console and is written to runs/. Stopping with Esc "
            "sends SIGTERM to the whole process group, then SIGKILL after three seconds; finished "
            "task artifacts stay on disk and the same command can be resumed."
        ),
        steps=(
            "Open Run → Sweep and choose the benchmark.",
            "Set k=1, one worker, and a small max-tasks value for the first real run.",
            "Optionally press Dry run to validate the dataset and wiring.",
            "Press Start sweep and watch the first task end to end.",
            "Stop with Esc if the output is wrong; fix the model or harness, then resume.",
        ),
        note=(
            "Real sweeps consume model tokens and time. Cost grows with tasks × k × modes. Always "
            "prove one task before launching a full benchmark."
        ),
        action="Open Run",
        view="run",
    ),
    Topic(
        key="judge",
        kicker="Score",
        title="Judge the artifacts",
        summary=(
            "The judge is a separate model call that reads each finished task and assigns a score "
            "using the benchmark's rubric. It uses HARNESS2_JUDGE_MODEL, or a separate "
            "HARNESS2_JUDGE_BASE_URL and HARNESS2_JUDGE_API_KEY so a stronger model can grade a "
            "cheaper executor.\n\n"
            "The --bases option also judges the baseline harness, which is what makes “did the "
            "recursion actually help?” answerable. Judging can fail independently of the sweep: a "
            "missing judge key, rate limit or malformed artifact will stop it without deleting the "
            "run."
        ),
        steps=(
            "Connect the judge role on Models.",
            "Open Run → Judge, choose the same benchmark, k and mode as the sweep.",
            "Enable Include baselines if you want the comparison.",
            "Press Start judge; wait for the per-task scores in Console.",
            "Open Runs to see the judged artifacts and scores.",
        ),
        note=(
            "Use a different model family for the judge when possible. A model grading its own "
            "output tends to be optimistic."
        ),
        action="Open Run",
        view="run",
    ),
    Topic(
        key="report",
        kicker="Summarise",
        title="Turn scores into a report",
        summary=(
            "The report command aggregates judged artifacts into tables: score by benchmark, by "
            "recursion depth k, by mode, and by harness variant, plus the selections that produced "
            "the best result. It reads existing judged data and writes report files under runs/.\n\n"
            "Reporting is cheap because it does not call a model, but it needs judged artifacts. "
            "If you point it at a k or mode that was never judged, it will say so."
        ),
        steps=(
            "Finish a judged run first.",
            "Open Run → Report and enter the k values you judged, for example 1,2.",
            "Pick the same benchmark and mode.",
            "Press Generate report, then open the report path from Console or Runs.",
        ),
        note=(
            "Reports are only as honest as the judge. Read a few individual scores before quoting "
            "an aggregate."
        ),
        action="Open Run",
        view="run",
    ),
    Topic(
        key="harness",
        kicker="The eight components",
        title="Inspect and edit C1–C8",
        summary=(
            "Harness² stores a harness as files. C1 is the system prompt, C2 guardrails, C3 "
            "long-term memory, C4 tool guidance, C5 sub-agents, C6 skills, C7 scripts and C8 "
            "plugins. The Harness screen reads a real task's final harness, shows each component, "
            "and marks files that were truncated for display.\n\n"
            "You can edit a component directly. Studio writes a timestamped backup first, saves "
            "atomically, keeps the original line endings, and shows a unified diff so you can see "
            "exactly what changed. Editing is blocked while a command is running, and read-only "
            "when the file is truncated or you are viewing a diff."
        ),
        steps=(
            "Open Harness and choose a task with artifacts.",
            "Pick a component from C1–C8.",
            "Read it, or press Edit and change the text.",
            "Press Save; the backup path is written to Console.",
            "Press Diff to compare with the pre-edit copy, or Reload to discard.",
        ),
        note=(
            "These edits change the artifact you are inspecting, not the upstream source and not "
            "the model. To change how future runs behave, edit the library or let the improver do "
            "it during a sweep."
        ),
        action="Open Harness",
        view="harness",
    ),
    Topic(
        key="runs",
        kicker="Artifacts",
        title="Read what a run actually produced",
        summary=(
            "A real run writes runs/<run>/<task>/harnesses/<variant>/. A task exists only when a "
            "harnesses/base directory exists. Inside are the harness components, execution logs, "
            "scores and sometimes patches. The Runs screen scans this layout, groups by run and "
            "task, and shows sizes, scores and component coverage.\n\n"
            "Nothing is hidden behind a database: every row is a real directory you can open in "
            "your file manager. “Open folder” and “Copy path” are the fastest way to inspect raw "
            "output."
        ),
        steps=(
            "Open Runs and select a run.",
            "Filter or scroll to the task you care about.",
            "Read the score and component coverage.",
            "Open the folder or copy the path for deeper inspection.",
            "Use Harness to read the components of that exact task.",
        ),
        note=(
            "Do not rename run directories while a sweep is writing to them. Runs accumulate; "
            "archive or delete old runs deliberately."
        ),
        action="Open Runs",
        view="runs",
    ),
    Topic(
        key="bridge",
        kicker="Codex executor",
        title="Serve Vertex AI to the Codex executor",
        summary=(
            "Some workflows use OpenAI Codex as the executor. Codex expects an OpenAI Responses "
            "API, while Harness² calls Vertex AI. The bridge is a local LiteLLM server that "
            "translates between them and prints the .env settings Codex needs.\n\n"
            "It is only needed for the Codex substrate (cx) with Vertex AI. OpenCode workflows do "
            "not need it. The bridge requires the bridge extra packages, a Google Cloud project "
            "and Application Default Credentials; it binds to 127.0.0.1 by default. Use 0.0.0.0 "
            "only when a WorkBuddy container must reach it."
        ),
        steps=(
            "Install the bridge extra in the checkout: uv pip install -e '.[render,bridge]'.",
            "Set GOOGLE_CLOUD_PROJECT and GOOGLE_CLOUD_LOCATION in .env.",
            "Run gcloud auth application-default login.",
            "Open Models → Bridge, keep the default host, press Start bridge.",
            "Copy the printed settings into .env before running a cx workflow.",
        ),
        note=(
            "The bridge is a long-running foreground server, not a background daemon. It stops "
            "when you press Stop or quit Studio. Never expose it to the public internet."
        ),
        action="Open Models",
        view="models",
    ),
    Topic(
        key="troubleshooting",
        kicker="When something breaks",
        title="Troubleshooting, error by error",
        summary=(
            "Studio shows the real error from the real process. The most useful first move is "
            "always Console: it keeps the exact argv, working directory, stderr and exit code.\n\n"
            "The messages below account for nearly every first-run failure."
        ),
        steps=(
            (
                "“checkout missing” — Install has not completed, or the path is wrong. Open Install, "
                "choose the folder that contains pyproject.toml, press Use this folder."
            ),
            (
                "“No module named harness2” — the interpreter is outside the checkout. Use the "
                ".venv Python shown on Home, or press Verify on Install to rebuild the environment."
            ),
            (
                "“HARNESS2_SOLVER_MODEL is required” — connect the executor on Models, then run Check "
                "environment on Setup."
            ),
            (
                "HTTP 401/403 — the key is wrong, expired, or sent to the wrong base URL. Save it "
                "again on Models; keys are masked but never truncated."
            ),
            (
                "Network timeout during install — retry. Downloads resume from the partial file and "
                "every file is hash-checked. A proxy must allow github.com and raw.githubusercontent.com."
            ),
            (
                "“venv unusable” — install the venv module for Python 3.12 (Debian/Ubuntu: sudo apt "
                "install python3.12-venv), then Install again."
            ),
            (
                "Docker errors on WorkBuddy — start Docker Engine and make sure your user can run "
                "docker info without sudo."
            ),
            "pandoc/poppler missing on LAB — install both, then re-run Check environment.",
            (
                "Judge stops alone — the judge model is missing or rate-limited. The sweep artifacts "
                "are intact; fix Models and run Judge again."
            ),
        ),
        note=(
            "If a screen looks stale, press F5. If a command is stuck, press Esc once and confirm; "
            "it is stopped politely, then forcibly after three seconds."
        ),
        action="Open Console",
        view="console",
    ),
    Topic(
        key="glossary",
        kicker="Reference",
        title="Glossary",
        summary=(
            "Harness — the prompts, tools, memory and code around a model. Improving the harness "
            "is the point of Harness².\n\n"
            "Executor — the agent that attempts benchmark tasks using the current harness.\n\n"
            "Improver — the model role that proposes edits to harness components after a round.\n\n"
            "Judge — a separate model role that scores finished artifacts against a rubric.\n\n"
            "Substrate — which coding agent runs the tasks: OpenCode (oc) or Codex (cx).\n\n"
            "k — recursion depth, the number of improvement rounds.\n\n"
            "Mode — parallel explores variants at one level; sequential carries one line forward.\n\n"
            "Split — which benchmark partition to use, such as all, train or test.\n\n"
            "Component C1–C8 — the eight editable parts of a harness (prompt, guardrails, memory, "
            "tool guidance, sub-agents, skills, scripts, plugins).\n\n"
            "Artifact — any real file a run leaves under runs/, including harness files, logs, "
            "scores and reports.\n\n"
            ".env — the checkout's local configuration file. Studio treats it as the source of "
            "truth for model wiring and never uploads it."
        ),
        steps=(
            "Use the search box above to jump to a topic.",
            "Every screen also has a Guide button in the top bar; it opens the matching topic.",
            "The Console keeps history even when you switch views.",
        ),
        note="No accounts, telemetry or cloud storage are built into Studio. Your checkout and runs stay on this machine.",
        action="Open Overview",
        view="home",
    ),
)


def by_key(key: str) -> Topic:
    for topic in TOPICS:
        if topic.key == key:
            return topic
    return TOPICS[0]
