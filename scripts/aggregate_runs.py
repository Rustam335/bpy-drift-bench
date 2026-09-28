"""Merge the per-model outputs of the Kaggle benchmark runs into the cross-model tables and charts.

    kaggle benchmarks tasks download bpy_drift_runs -o runs/
    python scripts/aggregate_runs.py runs/bpy-drift-runs/6 runs/out/

Point it at ONE task version: `tasks download` keeps every version side by side, and the leaderboard
must come from a single version so every model saw the same notebook. Files under the output folder are
skipped, so re-running does not feed the previous merge back in.

Every model run writes records.jsonl (one graded answer per line, model name included) into its
working directory; `tasks download` puts each run in its own folder. This script finds every
records.jsonl below the input folder, concatenates them, and writes:

    out/records.jsonl        every graded answer, all models (aware axis re-graded by the current parser; an
                             answer whose script the current parser extracts differently is re-run in the
                             local Blender named by BLENDER_BIN_<mm>, so the runs axis follows the parser too)
    out/truncated.csv        answers cut at the proxy output cap, excluded from every table (infrastructure, not model)
    out/results.csv          the same without answer text and stderr
    out/runs_by_version.csv  run rate per model x version (+ all)
    out/aware_by_version.csv awareness rate per model x version
    out/gap.csv              runs-but-unaware / aware-but-breaks per model
    out/failure_reasons.csv  most common Blender failure lines
    out/drift_runs.png, out/drift_aware.png, out/heatmap_runs.png
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from bpy_drift import report  # noqa: E402
from bpy_drift.blender import RunOutcome, env_var_for, run_script  # noqa: E402
from bpy_drift.cases import load_api_changes, load_cases  # noqa: E402
from bpy_drift.contract import check_watch_out, extract_script, split_blocks  # noqa: E402
from bpy_drift.prompt import MAX_OUTPUT_TOKENS, REASONING_OUTPUT_TOKENS, is_truncated  # noqa: E402

# Task versions up to v6 did not store the cap in the record and gave gemini the short cap.
LEGACY_REASONING_MARKERS = ("deepseek-r1", "thinking", "reasoning", "gpt-5", "gpt-6", "grok")


def record_cap(record: dict) -> int:
    """The max_tokens the notebook used for this answer: stored from v7 on, reconstructed for older records."""
    if record.get("output_cap"):
        return int(record["output_cap"])
    name = record["model"].lower()
    return REASONING_OUTPUT_TOKENS if any(m in name for m in LEGACY_REASONING_MARKERS) else MAX_OUTPUT_TOKENS


def split_truncated(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Separate answers that stopped at the proxy output cap. Notebook versions before v7 graded them as ordinary
    failures; they are an infrastructure limit and leave the denominator like errored prompts."""
    truncated = [r for r in records if is_truncated(r.get("output_tokens"), record_cap(r))]
    kept = [r for r in records if not is_truncated(r.get("output_tokens"), record_cap(r))]
    return kept, truncated


def regrade_aware(records: list[dict]) -> list[dict]:
    """Re-run the awareness check on the stored answers so every model, whichever notebook version
    graded it, is judged by the current parser. The runs axis is untouched: that needs Blender."""
    known = load_api_changes()
    out = []
    for r in records:
        expected = [known[i] for i in r.get("expected", []) if i in known]
        aware_failures = check_watch_out(split_blocks(r.get("answer") or "").watch_out, expected)
        blender_failures = [f for f in r.get("failures", []) if not f.startswith(("WATCH OUT", "No WATCH OUT"))]
        out.append({**r, "aware": not aware_failures, "failures": aware_failures + blender_failures})
    return out


def local_blender(version: str) -> str | None:
    """The local Blender binary for `version` (env BLENDER_BIN_<mm>), or None: the offline re-grade never downloads."""
    binary = os.environ.get(env_var_for(version))
    return binary if binary and Path(binary).is_file() else None


def regrade_runs(records: list[dict]) -> tuple[list[dict], list[dict]]:
    """Re-run the answers whose script the current parser extracts differently from what the notebook ran.

    The notebook version that graded deepseek-r1 took the first fence in the answer, which for that model
    sits inside its <think> block (a placeholder or a draft). Returns (re-graded records, untouched records);
    a record stays as it was when no local Blender for its version is configured, with a note.
    """
    cases = {c.id: c for c in load_cases()}
    fixed, unchanged = [], []
    for r in records:
        script = extract_script(r.get("answer") or "")
        if script == (r.get("script") or "") or r["case_id"] not in cases:
            unchanged.append(r)
            continue
        binary = local_blender(r["version"])
        if binary is None:
            print(f"script changed under the current parser but no local Blender {r['version']}: "
                  f"{r['model']} {r['case_id']} kept as graded")
            fixed.append(r)
            continue
        outcome: RunOutcome = run_script(binary, script, cases[r["case_id"]].assert_for(r["version"]))
        other = [f for f in r.get("failures", []) if not f.startswith("Blender:")]
        blender = [] if outcome.passed else [f"Blender: {outcome.reason}"]
        print(f"re-run {r['model']} {r['case_id']} {r['version']}: {r.get('runs')} -> {outcome.passed}")
        fixed.append({**r, "script": script, "runs": outcome.passed, "reason": "" if outcome.passed else outcome.reason,
                      "stderr": outcome.stderr[-4000:], "failures": other + blender, "regraded_locally": True})
    return fixed, unchanged


def load_records(root: Path, skip: Path | None = None) -> list[dict]:
    records: list[dict] = []
    for path in sorted(root.rglob("records.jsonl")):
        if skip is not None and skip.resolve() in path.resolve().parents:
            continue
        with path.open(encoding="utf-8") as fh:
            rows = [json.loads(line) for line in fh if line.strip()]
        print(f"{path}: {len(rows)} records, models {sorted({r['model'] for r in rows})}")
        records.extend(rows)
    return records


def main(src: str, dst: str) -> int:
    root, out = Path(src), Path(dst)
    records = load_records(root, skip=out)
    if not records:
        print(f"no records.jsonl under {root}")
        return 1
    records, truncated = split_truncated(records)
    for r in truncated:
        print(f"truncated at the output cap, excluded: {r['model']} {r['case_id']} {r['version']} ({r['output_tokens']} tokens)")
    fixed, unchanged = regrade_runs(records)
    print(f"runs re-graded in local Blender: {len(fixed)} answers whose script the current parser reads differently")
    records = fixed + unchanged
    before = sum(bool(r.get("aware")) for r in records)
    records = regrade_aware(records)
    print(f"aware re-graded with the current parser: {before} -> {sum(r['aware'] for r in records)} aware answers")
    out.mkdir(parents=True, exist_ok=True)
    df = report.records_frame(records)
    df = df.drop_duplicates(subset=["model", "case_id", "version"], keep="last")
    print(f"{len(df)} graded answers, {df['model'].nunique()} models")

    df.to_json(out / "records.jsonl", orient="records", lines=True)
    pd.DataFrame(truncated, columns=["model", "case_id", "version", "output_tokens"]).to_csv(out / "truncated.csv", index=False)
    df.drop(columns=["answer", "stderr"]).to_csv(out / "results.csv", index=False)
    report.rate_table(df, "runs").to_csv(out / "runs_by_version.csv")
    report.rate_table(df, "aware").to_csv(out / "aware_by_version.csv")
    report.gap_table(df).to_csv(out / "gap.csv")
    report.failure_reasons(df).reset_index().to_csv(out / "failure_reasons.csv", index=False)

    for metric in ("runs", "aware"):
        report.plot_drift_curves(df, metric)
        plt.tight_layout()
        plt.savefig(out / f"drift_{metric}.png", bbox_inches="tight")
        plt.close()
    report.plot_category_heatmap(df, "runs")
    plt.tight_layout()
    plt.savefig(out / "heatmap_runs.png", bbox_inches="tight")
    plt.close()

    print(report.rate_table(df, "runs").round(2).to_string())
    return 0


if __name__ == "__main__":
    if len(sys.argv) != 3:
        print(__doc__)
        sys.exit(2)
    sys.exit(main(sys.argv[1], sys.argv[2]))
