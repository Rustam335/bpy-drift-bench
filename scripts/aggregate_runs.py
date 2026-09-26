"""Merge the per-model outputs of the Kaggle benchmark runs into the cross-model tables and charts.

    kaggle benchmarks tasks download bpy_drift_runs -o runs/
    python scripts/aggregate_runs.py runs/bpy-drift-runs/6 runs/out/

Point it at ONE task version: `tasks download` keeps every version side by side, and the leaderboard
must come from a single version so every model saw the same notebook. Files under the output folder are
skipped, so re-running does not feed the previous merge back in.

Every model run writes records.jsonl (one graded answer per line, model name included) into its
working directory; `tasks download` puts each run in its own folder. This script finds every
records.jsonl below the input folder, concatenates them, and writes:

    out/records.jsonl        every graded answer, all models
    out/results.csv          the same without answer text and stderr
    out/runs_by_version.csv  run rate per model x version (+ all)
    out/aware_by_version.csv awareness rate per model x version
    out/gap.csv              runs-but-unaware / aware-but-breaks per model
    out/failure_reasons.csv  most common Blender failure lines
    out/drift_runs.png, out/drift_aware.png, out/heatmap_runs.png
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import pandas as pd  # noqa: E402

from bpy_drift import report  # noqa: E402


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
    out.mkdir(parents=True, exist_ok=True)
    df = report.records_frame(records)
    df = df.drop_duplicates(subset=["model", "case_id", "version"], keep="last")
    print(f"{len(df)} graded answers, {df['model'].nunique()} models")

    df.to_json(out / "records.jsonl", orient="records", lines=True)
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
