# bpy-drift-bench: Blender Python API drift, graded in real Blender

> **Question:** *When you ask an LLM for a Blender script for a specific version, does the script run in that version, and does the model know what changed?*
> **Event:** DEV x Kaggle Benchmarking Challenge (`#kagglechallenge`)
> **Benchmark:** [hoholalagaul/bpy-drift-runs](https://www.kaggle.com/benchmarks/tasks/hoholalagaul/bpy-drift-runs) on Kaggle Benchmarks

[![Kaggle Benchmarks](https://img.shields.io/badge/Kaggle-Benchmarks-20beff?logo=kaggle)](https://www.kaggle.com/benchmarks/tasks/hoholalagaul/bpy-drift-runs)
[![Blender](https://img.shields.io/badge/Blender-3.6%20%7C%204.2%20%7C%204.5%20%7C%205.0-e87d0d?logo=blender)](https://www.blender.org/)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-lightgrey)](#8-license)

---

## 1. Problem

The Blender Python API (`bpy`) changes on every major release: enums get renamed, attributes are removed, node
sockets move, operators are replaced. Most of the code a model learned from was written for Blender 2.8 to 3.x.
Ask for a Blender 5.0 script and the model often writes a 3.x script that fails on the first changed line.

Text-similarity grading cannot see this. A script that calls `mesh.use_auto_smooth = True` looks right and reads
right; it raises `AttributeError` in 4.1 and later. The only reliable judge is the Blender version the question was
asked for.

### Approach

- The same 30 scripting tasks are asked for Blender **3.6, 4.2, 4.5 and 5.0** (119 prompts per model; one task has no 3.6 form).
- Every answer is executed headless in that exact Blender build, then a per-task assert script checks the resulting scene.
- Every model gets the same system prompt, temperature 0, no tools, no retrieval.

Two verdicts per answer:

| axis | decided by |
|------|------------|
| **runs** | the generated script and the task's assert script both exit 0 in the target build (`blender -b --factory-startup --python`) |
| **aware** | the answer's `WATCH OUT` block names each API that changed for that version and its replacement |

The two axes come apart. A model can write code that runs while having no idea the API changed (it happened to
use a form that survived), and a model can describe the change correctly and still emit the old call.

---

## 2. Example tasks

### Render engine: a rename that was reverted
- **Task:** `Set the render engine to EEVEE and the render resolution to 640 by 480 pixels.`
- **Correct engine id:** `BLENDER_EEVEE` in 3.6, `BLENDER_EEVEE_NEXT` in 4.2 and 4.5, `BLENDER_EEVEE` again in 5.0.
- **Observed:** models write `BLENDER_EEVEE` for 4.2 and 4.5, or `BLENDER_EEVEE_NEXT` for 5.0. Both fail with an enum `TypeError`.

### Boolean solver: an enum that moved in 5.0
- **Task:** `Add a Boolean modifier in DIFFERENCE mode on 'Cube' using the fast (non-exact) solver.`
- **Correct:** `solver = 'FAST'` up to 4.5, `solver = 'FLOAT'` in 5.0 (`'FAST'` no longer exists; `'MANIFOLD'` is new).

### Control tasks
- Two tasks use APIs that did not change across the four versions. They check that the grader does not punish
  a model for writing ordinary, correct code.

---

## 3. Pipeline

```
 cases.json (30 tasks)  x  versions (3.6 / 4.2 / 4.5 / 5.0)
                    │
                    ▼
      ┌───────────────────────────────┐
      │  Prompt  (prompt.py)          │   one system prompt for every model,
      │  "Target: Blender 4.5 ..."    │   temperature 0, no tools
      └───────────────┬───────────────┘
                      │  kbench.llm (Kaggle Model Proxy)
                      ▼
      ┌───────────────────────────────┐
      │  Parse  (contract.py)         │   strip <think> blocks, take the
      │  script + WATCH OUT bullets   │   python fence, dedent, read bullets
      └───────────────┬───────────────┘
                      ▼
      ┌───────────────────────────────┐
      │  Run  (blender.py)            │   headless build of the target version,
      │  script, then assert script   │   factory startup, per-call timeout
      └───────────────┬───────────────┘
                      ▼
      ┌───────────────────────────────┐
      │  Grade  (grading.py)          │   runs  = both exit 0
      │                               │   aware = every expected change named
      └───────────────┬───────────────┘
                      ▼
        records.jsonl, per-version tables, charts (report.py)
```

The Blender builds come from a Kaggle dataset (four Linux tarballs plus the `bpy_drift` wheel), so the task runs
without internet access. Proxy errors (rate limits, quota) are retried with backoff and never counted as model
failures; a run with more than 10% lost prompts aborts instead of producing a score.

---

## 4. Results

Task version 7, 119 prompts per model, all 119 graded for every model. Aware is re-graded offline with the current
parser (`scripts/aggregate_runs.py`), so every model is judged the same way.

| model | runs | aware | runs but unaware |
|-------|-----:|------:|-----------------:|
| gpt-5.5-2026-04-23 | 95% | 71% | 26% |
| claude-sonnet-5 | 94% | 53% | 42% |
| gemini-3.8-flash | 92% | 77% | 17% |
| gemini-3.1-pro-preview | 92% | 76% | 18% |
| gemini-3.7-flash | 89% | 73% | 18% |
| grok-4.20-0309-reasoning | 82% | 29% | 57% |
| claude-haiku-4-5 | 72% | 31% | 48% |
| qwen3-coder-480b-a35b-instruct | 70% | 29% | 46% |
| deepseek-r1-0528 | 67% | 39% | 33% |
| gpt-oss-120b | 61% | 29% | 37% |

Runs by target version:

| model | 3.6 | 4.2 | 4.5 | 5.0 |
|-------|----:|----:|----:|----:|
| gpt-5.5-2026-04-23 | 97% | 97% | 100% | 87% |
| claude-sonnet-5 | 100% | 97% | 100% | 80% |
| gemini-3.8-flash | 97% | 90% | 97% | 87% |
| gemini-3.1-pro-preview | 97% | 90% | 97% | 83% |
| gemini-3.7-flash | 93% | 90% | 90% | 83% |
| grok-4.20-0309-reasoning | 86% | 83% | 87% | 70% |
| claude-haiku-4-5 | 79% | 77% | 73% | 60% |
| qwen3-coder-480b-a35b-instruct | 83% | 67% | 70% | 60% |
| deepseek-r1-0528 | 86% | 70% | 63% | 50% |
| gpt-oss-120b | 93% | 53% | 57% | 43% |

Notes on reading these numbers:

- **Every model is worst on 5.0.** The recurring 5.0 failures are `Action.fcurves` (slotted actions),
  `Scene.node_tree` (compositor), `SequenceEditor.sequences`, the `FAST` boolean solver and
  `new_effect(length=)`.
- **Temperature 0 is not deterministic through the proxy.** Four runs of gemini-3.7-flash on the same prompts
  scored 107, 107, 103 and 106 out of 119, so differences of 1 to 4 points between models are within noise.
- **The Kaggle leaderboard shows 62% for deepseek-r1**, not 67%. The proxy returns its reasoning inline as
  `<think>...</think>`, and the notebook version that ran it took a draft script from inside that block. The
  tables above re-extract the final answer and re-run the changed scripts in the same Blender builds.
- **grok-4.20-0309-reasoning has the widest gap of the ten**: 82% of its scripts run, but it writes `- none`
  under WATCH OUT in 110 of 119 answers, including for every 2.80-era change it silently gets right. Its
  awareness by version (69 / 23 / 13 / 10%) is identical to qwen3-coder's.
- **grok-4.6** is listed by the Model Proxy but every call returned `404 model not found`; its run is recorded as
  errored and it has no row here. grok-4.20-0309-reasoning is the xAI entry instead.
- The aware check matches identifiers by substring and quoted enum values exactly. It is a floor on awareness,
  not a proof of understanding.

---

## 5. Repository layout

```
bpy_drift/                 grading library (pip install -e .)
  cases.py                 case bank loader, expected API changes per version
  contract.py              answer parsing and the WATCH OUT check
  blender.py               locate / extract / run headless Blender per version
  prompt.py                the system prompt and per-model output caps
  grading.py               grade(answer, case, version) -> runs, aware, failures
  report.py                charts
  data/api_changes.json    33 verified API changes with the version they happened in
  data/cases.json          30 tasks + assert scripts, with per-version overrides
  reference/               a hand-written correct answer per task (and per version where it differs)
notebooks/task/            the Kaggle Benchmarks task (generated by scripts/build_notebook.py)
scripts/                   selfcheck.py · smoke_blender.py · aggregate_runs.py · make_dataset.py · build_notebook.py
tests/                     pytest
```

`scripts/selfcheck.py` runs every reference answer in every version it applies to and requires 119/119 to pass.
This is the evidence that each task is answerable in each version and that each assert is correct.

---

## 6. Quickstart

### Prerequisites
- Python 3.10 or newer
- Blender 3.6, 4.2, 4.5 and 5.0 portable builds (only for the Blender-backed scripts)

### Run locally
```bash
# 1. Install
pip install -e . pytest matplotlib

# 2. Unit tests
python -m pytest -q tests

# 3. Point at local Blender builds (one variable per version: 36, 42, 45, 50)
export BLENDER_BIN_45=/path/to/blender-4.5.14/blender

# 4. Check that each build starts and asserts work
python scripts/smoke_blender.py 4.5

# 5. Check every reference answer against its assert
python scripts/selfcheck.py

# 6. Aggregate downloaded Kaggle runs into cross-model tables and charts
python scripts/aggregate_runs.py runs/bpy-drift-runs/7 runs/out/
```

On Linux (including Kaggle) the pinned portable builds are extracted to `/tmp/bpy-drift/blender`.

---

## 7. Origin

The case bank, assert scripts and the WATCH OUT contract come from [bpy-compass](https://github.com/Rustam335/bpy-compass),
a version-aware bpy assistant built on a Sanity knowledge base. Its evaluation compared one model with and without
the knowledge base; this benchmark asks the broader question across models and versions.

## 8. License

MIT.
