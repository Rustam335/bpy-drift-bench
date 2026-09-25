# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

# %% [markdown]
# # Blender Python API drift across language models
#
# Blender's Python API (`bpy`) changes with every release: `scene.objects.link` disappeared in 2.80, context override
# dicts in 4.0, `use_auto_smooth` in 4.1, the EEVEE engine id was renamed in 4.2 and renamed back in 5.0, the fast
# boolean solver became `FLOAT` in 5.0, the compositor became a node group in 5.0. Models trained on a mix of tutorials
# from every era tend to answer with whatever version was most common in their data.
#
# This benchmark asks the same scripting question for Blender **3.6, 4.2, 4.5 and 5.0** and grades each answer two ways:
#
# | axis | verdict |
# |------|---------|
# | **runs** | the script, followed by a case-specific assert, exits 0 inside that exact Blender build (`blender -b --factory-startup --python`) |
# | **aware** | the answer's `WATCH OUT` section names every API that was removed, renamed or changed for that version, and its replacement |
#
# The leaderboard task is **runs**: how many of the (question, version) prompts produce a script that works in the
# Blender it was asked for. Awareness is reported alongside because the two come apart: code can work while the model
# has no idea the API moved, and a model can describe the change and still emit the old call.
#
# Grading code, case bank, reference answers and the list of verified API changes: [bpy-drift-bench](https://github.com/Rustam335/bpy-drift-bench).
# The attached dataset holds the four official Blender Linux builds and a wheel of the grading package, so a run
# downloads nothing and every model is graded by the same binaries.

# %% [markdown]
# ## 1. Setup
#
# Installs the grading library from the attached dataset, which also holds the four pinned Blender archives. Nothing is downloaded: the run is reproducible offline.

# %%
import os, sys, subprocess, platform, pathlib, glob, socket

ON_KAGGLE = pathlib.Path("/kaggle").exists()
PACKAGE_URL = "https://github.com/Rustam335/bpy-drift-bench/archive/refs/heads/main.tar.gz"

if ON_KAGGLE:
    # Datasets mount at /kaggle/input/<slug> in notebooks and /kaggle/input/datasets/<owner>/<slug> in benchmark tasks.
    wheels = sorted(glob.glob("/kaggle/input/**/bpy_drift-*.whl", recursive=True))
    target = ["--no-index", "--no-deps", wheels[-1]] if wheels else ["--no-cache-dir", PACKAGE_URL]
    print("installing", target[-1])
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *target], check=True)
    try:
        import matplotlib  # noqa: F401
    except ImportError:  # the benchmark image ships without it; charts are optional, the tables are not
        subprocess.run([sys.executable, "-m", "pip", "install", "-q", "matplotlib"], check=False)

import pandas as pd
import kaggle_benchmarks as kbench
from bpy_drift import (RELEASES, ensure_blender, ensure_runtime_libs, verify_build, run_script, load_cases, expand,
                       SYSTEM_PROMPT, build_user_prompt, grade)
from bpy_drift import report

if ON_KAGGLE:
    # Headless Blender still dlopens a few X11/GL stubs; the benchmark image lacks libXxf86vm. apt first, and if
    # that fails the .deb files are unpacked into the cache and handed to Blender through LD_LIBRARY_PATH.
    still_missing = ensure_runtime_libs()
    assert not still_missing, f"shared libraries Blender needs are unavailable: {still_missing}"

pd.set_option("display.max_colwidth", 120)
os.environ.setdefault("RENDER_SUBRUNS", "False")
try:
    display
except NameError:  # running the percent-format .py locally, outside IPython
    display = print
print("platform:", platform.platform())

# %% [markdown]
# ## 2. Gate: every target Blender build starts headless
#
# Nothing below runs until all four builds are extracted from the attached archives, report the expected version, and can both pass and fail an assert.

# %%
PROBE = "import bpy\nbpy.data.objects['Cube'].location.x = 1.0"
PASSING = "import bpy\nassert bpy.data.objects['Cube'].location.x == 1.0"
FAILING = "import bpy\nassert False, 'deliberate failure'"

BLENDER = {}
rows = []
for version in RELEASES:
    binary = ensure_blender(version)
    build = verify_build(binary, version)
    ok, bad = run_script(binary, PROBE, PASSING), run_script(binary, PROBE, FAILING)
    BLENDER[version] = binary
    rows.append({"target": version, "build": build, "assert passes": ok.passed,
                 "assert failure detected": not bad.passed, "failure line": bad.reason})
gate = pd.DataFrame(rows).set_index("target")
display(gate)
assert gate["assert passes"].all() and gate["assert failure detected"].all(), "a Blender build is not usable; stop here"

# %% [markdown]
# ## 3. Case bank
#
# Each case is one question, asked for every version it applies to. Which API changes are live traps for a case depends on the version (`changedIn <= target`). Where the correct end state itself differs between versions (EEVEE id, solver name, Principled socket names, sequencer strips, compositor output) the assert script is overridden per version.
#
# Every case has a hand-written reference answer in the repository, and `scripts/selfcheck.py` runs each one in every Blender version it lists: a question only ships if it is provably answerable in that version. Two `control` cases use APIs that have not changed since 2.80; failures there measure general bpy competence, not drift.

# %%
CASES = {c.id: c for c in load_cases()}
eval_df = expand(CASES.values())
LIMIT = int(os.environ.get("BPY_DRIFT_LIMIT", "0"))  # local smoke runs only; 0 = the whole bank
if LIMIT:
    eval_df = eval_df.head(LIMIT)
print(f"{len(CASES)} cases x versions = {len(eval_df)} prompts per model")
display(eval_df.pivot_table(index="category", columns="version", values="case_id", aggfunc="count", fill_value=0, observed=False))
display(eval_df[["case_id", "category", "question"]].drop_duplicates("case_id").set_index("case_id"))

# %% [markdown]
# ## 4. The prompt
#
# Every model gets the same system prompt and the same user message; only the version number changes. No tools, no retrieval, temperature 0.

# %%
print(SYSTEM_PROMPT)
print("-" * 60)
print(build_user_prompt("4.2", CASES["eevee-engine"].question))

# %% [markdown]
# ## 5. Task definition
#
# One sub-task per (case, version) prompt, and the leaderboard task that evaluates the whole bank for one model and returns the run rate with a 95% confidence interval. Every graded answer, with its script, failure line and awareness verdict, is kept in `RECORDS` for the analysis below.
#
# The model proxy occasionally answers `429 heavy load` for a whole batch, and kbench forces `max_attempts=1` inside a nested evaluation, so the prompt call retries with backoff here. A prompt that still fails is an infrastructure error, not a model error: it is reported and left out of the denominator, and if more than a tenth of the bank is lost the run aborts instead of recording a misleading score.

# %%
import time

RECORDS = []
RETRY_DELAYS = (5, 10, 20, 40, 60, 90)  # seconds between attempts; about four minutes in total
MAX_ERROR_SHARE = 0.10


def prompt_with_retry(llm, message: str) -> str:
    for attempt, delay in enumerate(RETRY_DELAYS + (None,)):
        try:
            return llm.prompt(message, temperature=0)
        except Exception as exc:  # noqa: BLE001 - the proxy raises its own error types; the message carries the status
            if delay is None:
                raise
            print(f"  prompt attempt {attempt + 1} failed ({str(exc)[:120]}); retrying in {delay}s")
            time.sleep(delay)


@kbench.task(store_task=False)
def bpy_drift_case(llm, case_id: str, version: str) -> dict:
    """Ask one question for one Blender version and grade the answer inside that Blender."""
    case = CASES[case_id]
    with kbench.chats.new(name=f"{case_id} @ {version}", system_instructions=SYSTEM_PROMPT):
        answer = prompt_with_retry(llm, build_user_prompt(version, case.question))
    result = grade(answer, case, version, binary=BLENDER[version])
    RECORDS.append({"model": llm.name, "category": case.category, "answer": answer, **result.as_dict()})
    return {"case_id": case_id, "version": version, "runs": result.runs, "aware": result.aware,
            "reason": result.reason, "expected": result.expected}


@kbench.task(
    name="bpy_drift_runs",
    description="How many Blender Python scripts run in the exact Blender version they were written for (3.6, 4.2, 4.5, 5.0).",
)
def bpy_drift_runs(llm, df) -> tuple[float, float]:
    """Run rate over the graded prompts with a 95% normal-approximation CI; prompts lost to proxy errors are excluded."""
    with kbench.client.enable_cache():
        runs = bpy_drift_case.evaluate(
            llm=[llm], evaluation_data=df, on_failure="continue", max_attempts=1,
            n_jobs=1, remove_run_files=True,  # every grade launches a Blender process
        )
    print(f"completed: {len(runs.completed_runs)}  errored: {len(runs.errored_runs)}")
    for run in runs.errored_runs:
        last_line = (run.error_message or "").strip().splitlines()[-1:] or ["(no message)"]
        print("  errored:", run.params.get("case_id"), run.params.get("version"), "|", last_line[0][:300])
    if len(runs.errored_runs) > MAX_ERROR_SHARE * df.shape[0]:
        raise RuntimeError(f"{len(runs.errored_runs)} of {df.shape[0]} prompts errored: infrastructure problem, not a score")
    done = runs.completed_runs.as_dataframe()
    passed = int(done["result"].str.get("runs").sum()) if len(done) else 0
    total = int(len(done))
    rate = passed / total if total else 0.0
    ci95 = 1.96 * (rate * (1 - rate) / total) ** 0.5
    print(f"runs: {passed} of {total} prompts")
    return rate, ci95

# %% [markdown]
# ## 6. Dry run: one case, one version
#
# A smoke test of the grading path against the model under test; its record is discarded before the measurement.

# %%
run = bpy_drift_case.run(llm=kbench.llm, case_id="eevee-engine", version="5.0")
last = RECORDS[-1]
print("runs:", last["runs"], "| aware:", last["aware"], "| build:", last["blender_build"])
print("failures:", last["failures"])
print(last["script"])
RECORDS.clear()  # the dry run is a smoke test, not part of the measurement

# %% [markdown]
# ## 7. Model under test
#
# The task is written for `kbench.llm`, so the same code runs once per model; models are scheduled from the task page or with `kaggle benchmarks tasks run bpy_drift_runs -m <model>`. The models available to this notebook are listed for the record.

# %%
print("model under test:", kbench.llm.name)
print("available:", ", ".join(sorted(kbench.llms)))

# %% [markdown]
# ## 8. Full evaluation
#
# `n_jobs=1` because every grade launches a Blender process. The response cache means a re-run after a grading fix does not re-prompt the model.

# %%
run = bpy_drift_runs.run(kbench.llm, eval_df[["case_id", "version"]])
print("passed, total:", run.result)

# %% [markdown]
# ## 9. Results for this model
#
# The cross-model comparison is built from the downloaded run outputs of every scheduled model (`kaggle benchmarks tasks download`); this section is the per-model view.

# %%
df = report.records_frame(RECORDS)
df.drop(columns=["answer", "stderr"]).to_csv("results.csv", index=False)
df.to_json("records.jsonl", orient="records", lines=True)

pct = "{:.0%}"
print("Run rate by version")
display(report.rate_table(df, "runs").style.format(pct))
print("Awareness rate by version")
display(report.rate_table(df, "aware").style.format(pct))
print("Where the two axes disagree")
display(report.gap_table(df).style.format({c: pct for c in ["runs", "aware", "runs but unaware", "aware but breaks"]}))
print("Most common failure lines")
display(report.failure_reasons(df))

# %%
try:
    import matplotlib.pyplot as plt
except ImportError:  # charts are a convenience here; the cross-model figures come from scripts/aggregate_runs.py
    plt = None
    print("matplotlib is not available in this image; skipping the per-model charts")

if plt is not None:
    for metric in ("runs", "aware"):
        report.plot_drift_curves(df, metric)
        plt.tight_layout(); plt.savefig(f"drift_{metric}.png", bbox_inches="tight"); plt.show()
    report.plot_category_heatmap(df, "runs")
    plt.tight_layout(); plt.savefig("heatmap_runs.png", bbox_inches="tight"); plt.show()

# %% [markdown]
# ## 10. Publish
#
# Keeps only the leaderboard task's files in the working directory, so the Kaggle benchmark is built from `bpy_drift_runs`.

# %%
# %choose bpy_drift_runs
