"""Regenerate notebooks/bpy_drift_bench.ipynb from the cell sources below.

The notebook is the artefact Kaggle runs; keeping its source here makes diffs readable and
keeps prose and code out of a hand-edited JSON file.

    python scripts/build_notebook.py
"""

from __future__ import annotations

import json
from pathlib import Path

REPO = "https://github.com/Rustam335/bpy-drift-bench"
# pip installs from the tarball: the Kaggle worker could not `git clone` (exit 128) in the day-1 gate.
TARBALL = f"{REPO}/archive/refs/heads/main.tar.gz"
OUT = Path(__file__).resolve().parents[1] / "notebooks" / "bpy_drift_bench.ipynb"


def md(s: str) -> dict:
    return {"cell_type": "markdown", "metadata": {}, "source": s.strip("\n")}


def code(s: str) -> dict:
    return {"cell_type": "code", "metadata": {}, "execution_count": None, "outputs": [], "source": s.strip("\n")}


CELLS = [
    md(f"""
# Blender Python API drift across language models

Blender's Python API (`bpy`) changes with every release: `scene.objects.link` disappeared in 2.80, context override
dicts in 4.0, `use_auto_smooth` in 4.1, the EEVEE engine id was renamed in 4.2 and renamed back in 5.0, the fast
boolean solver became `FLOAT` in 5.0. Models trained on a mix of tutorials from every era tend to answer with whatever
version was most common in their data.

This benchmark asks the same scripting question for Blender **3.6, 4.2, 4.5 and 5.0** and grades each answer two ways:

| axis | verdict |
|------|---------|
| **runs** | the script, followed by a case-specific assert, exits 0 inside that exact Blender build (`blender -b --factory-startup --python`) |
| **aware** | the answer's `WATCH OUT` section names every API that was removed, renamed or changed for that version, and its replacement |

The primary leaderboard task is **runs**. Awareness is reported alongside it because the two come apart:
code can work while the model has no idea the API moved, and a model can describe the change and still emit the old call.

Grading code, case bank and the list of verified API changes: [bpy-drift-bench]({REPO}).
"""),

    md("## 1. Setup\n\nInstalls the grading library and the shared libraries a headless Linux Blender still links against."),
    code(f"""
import os, sys, subprocess, platform, pathlib, glob

ON_KAGGLE = pathlib.Path("/kaggle").exists()
PACKAGE_URL = "{TARBALL}"

if ON_KAGGLE:
    # The attached dataset carries a wheel of the grading package and the four Blender archives, so a run
    # needs no network. The GitHub tarball is only the fallback for a notebook without the dataset.
    wheels = sorted(glob.glob("/kaggle/input/*/bpy_drift-*.whl"))
    target = ["--no-index", "--no-deps", wheels[-1]] if wheels else ["--no-cache-dir", PACKAGE_URL]
    subprocess.run([sys.executable, "-m", "pip", "install", "-q", *target], check=True)
    subprocess.run("apt-get install -y -qq libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libsm6 libxkbcommon0 > /dev/null 2>&1",
                   shell=True, check=False)

import pandas as pd
import kaggle_benchmarks as kbench
from bpy_drift import (RELEASES, ensure_blender, verify_build, run_script, load_cases, expand,
                       SYSTEM_PROMPT, build_user_prompt, grade)
from bpy_drift import report

pd.set_option("display.max_colwidth", 120)
print("platform:", platform.platform())
"""),

    md("## 2. Gate: every target Blender build starts headless\n\nNothing below runs until all four builds are downloaded, report the expected version, and can both pass and fail an assert. Roughly 350 MB per version."),
    code("""
PROBE = "import bpy\\nbpy.data.objects['Cube'].location.x = 1.0"
PASSING = "import bpy\\nassert bpy.data.objects['Cube'].location.x == 1.0"
FAILING = "import bpy\\nassert False, 'deliberate failure'"

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
"""),

    md("## 3. Case bank\n\nEach case is one question, asked for every version it applies to. Which API changes are live traps for a case depends on the version (`changedIn <= target`). Where the correct end state itself differs between versions (EEVEE id, solver name, Principled socket names, sequencer strips, compositor output) the assert script is overridden per version.\n\nEvery case has a hand-written reference answer in the repository, and `scripts/selfcheck.py` runs each one in every Blender version it lists: a question only ships if it is provably answerable in that version. Two `control` cases use APIs that have not changed since 2.80; failures there measure general bpy competence, not drift."),
    code("""
CASES = {c.id: c for c in load_cases()}
eval_df = expand(CASES.values())
print(f"{len(CASES)} cases x versions = {len(eval_df)} prompts per model")
display(eval_df.pivot_table(index="category", columns="version", values="case_id", aggfunc="count", fill_value=0, observed=False))
display(eval_df[["case_id", "category", "question"]].drop_duplicates("case_id").set_index("case_id"))
"""),

    md("## 4. The prompt\n\nEvery model gets the same system prompt and the same user message; only the version number changes. No tools, no retrieval, temperature 0."),
    code("""
print(SYSTEM_PROMPT)
print("-" * 60)
print(build_user_prompt("4.2", CASES["eevee-engine"].question))
"""),

    md("## 5. Task definition\n\nThe task returns `runs`. Every graded answer, with its script, failure line and awareness verdict, is kept in `RECORDS` for the analysis below."),
    code("""
RECORDS = []

def ask(llm, version, question):
    with kbench.chats.new(name=f"bpy {version}", system_instructions=SYSTEM_PROMPT):
        return llm.prompt(build_user_prompt(version, question), temperature=0)

@kbench.task(
    name="bpy_drift_runs",
    description="Does the model's Blender Python script run in the exact Blender version it was asked for?",
)
def bpy_drift_runs(llm, case_id: str, version: str) -> bool:
    case = CASES[case_id]
    answer = ask(llm, version, case.question)
    result = grade(answer, case, version, binary=BLENDER[version])
    RECORDS.append({"model": llm.name, "category": case.category, "answer": answer, **result.as_dict()})
    return result.runs
"""),

    md("## 6. Dry run: one case, one model"),
    code("""
run = bpy_drift_runs.run(llm=kbench.llm, case_id="eevee-engine", version="5.0")
last = RECORDS[-1]
print("runs:", last["runs"], "| aware:", last["aware"], "| build:", last["blender_build"])
print("failures:", last["failures"])
print(last["script"])
"""),

    md("## 7. Models\n\nThe models available to this notebook. The list is fixed before the full run and reported in the write-up; aim for a spread of vendors and sizes."),
    code("""
print("\\n".join(sorted(kbench.llms)))
MODELS = [kbench.llm]  # replace with an explicit list, e.g. [kbench.llms["google/gemini-2.5-flash"], ...]
"""),

    md("## 8. Full evaluation\n\n`n_jobs=1`: every grade launches a Blender process. The response cache means a re-run after a grading fix does not re-prompt the models."),
    code("""
RECORDS.clear()
with kbench.client.enable_cache():
    runs = bpy_drift_runs.evaluate(
        llm=MODELS,
        evaluation_data=eval_df[["case_id", "version"]],
        on_failure="continue",
        max_attempts=2,
        n_jobs=1,
    )
print(f"completed: {len(runs.completed_runs)}  errored: {len(runs.errored_runs)}")
"""),

    md("## 9. Results"),
    code("""
df = report.records_frame(RECORDS)
df.drop(columns=["answer", "stderr"]).to_csv("results.csv", index=False)
df.to_json("records.jsonl", orient="records", lines=True)

pct = "{:.0%}"
print("Run rate by model and version")
display(report.rate_table(df, "runs").style.format(pct))
print("Awareness rate by model and version")
display(report.rate_table(df, "aware").style.format(pct))
print("Where the two axes disagree")
display(report.gap_table(df).style.format({c: pct for c in ["runs", "aware", "runs but unaware", "aware but breaks"]}))
print("Most common failure lines")
display(report.failure_reasons(df))
"""),
    code("""
import matplotlib.pyplot as plt

for metric in ("runs", "aware"):
    report.plot_drift_curves(df, metric)
    plt.tight_layout(); plt.savefig(f"drift_{metric}.png", bbox_inches="tight"); plt.show()
report.plot_category_heatmap(df, "runs")
plt.tight_layout(); plt.savefig("heatmap_runs.png", bbox_inches="tight"); plt.show()
"""),

    md("## 10. Publish\n\nKeeps only the primary task's files in the working directory, so the Kaggle benchmark is built from `bpy_drift_runs`."),
    code("%choose bpy_drift_runs"),
]


def main() -> None:
    for i, cell in enumerate(CELLS):
        cell["id"] = f"cell-{i:02d}"
    nb = {
        "cells": CELLS,
        "metadata": {
            "kernelspec": {"display_name": "Python 3", "language": "python", "name": "python3"},
            "language_info": {"name": "python"},
        },
        "nbformat": 4,
        "nbformat_minor": 5,
    }
    OUT.write_text(json.dumps(nb, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    print(f"wrote {OUT} ({len(CELLS)} cells)")


if __name__ == "__main__":
    main()
