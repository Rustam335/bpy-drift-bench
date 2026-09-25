"""Tables and charts for the notebook and the write-up.

One restrained visual system: a small fixed palette, no chart junk, every figure titled with the
claim it supports. Input is the records frame produced by the notebook (one row per model,
case, version) with boolean `runs` and `aware` columns.
"""

from __future__ import annotations

import pandas as pd

VERSION_ORDER = ["3.6", "4.2", "4.5", "5.0"]

# Muted, print-safe palette; one hue per model, greys for context.
PALETTE = ["#1f4e79", "#c0504d", "#4f6228", "#7f6000", "#5b3a8c", "#31859c", "#984807", "#404040"]
INK = "#262626"
MUTED = "#8c8c8c"
RULE = "#d9d9d9"


def records_frame(records: list[dict]) -> pd.DataFrame:
    df = pd.DataFrame(records)
    if df.empty:
        return df
    df["version"] = pd.Categorical(df["version"], VERSION_ORDER, ordered=True)
    df["runs"] = df["runs"].astype(bool)
    df["aware"] = df["aware"].astype(bool)
    df["runs_not_aware"] = df["runs"] & ~df["aware"]
    df["aware_not_runs"] = df["aware"] & ~df["runs"]
    return df


def rate_table(df: pd.DataFrame, metric: str, index: str = "model", columns: str = "version") -> pd.DataFrame:
    """Pass rate (0-1) of `metric` as index x columns, plus an `all` column over every row."""
    if df.empty:
        return df
    table = df.pivot_table(index=index, columns=columns, values=metric, aggfunc="mean", observed=False)
    table["all"] = df.groupby(index, observed=False)[metric].mean()
    return table.sort_values("all", ascending=False)


def gap_table(df: pd.DataFrame) -> pd.DataFrame:
    """Where the two axes disagree, per model: share of answers that run but are unaware, and vice versa."""
    if df.empty:
        return df
    g = df.groupby("model", observed=False)
    out = pd.DataFrame({
        "runs": g["runs"].mean(),
        "aware": g["aware"].mean(),
        "runs but unaware": g["runs_not_aware"].mean(),
        "aware but breaks": g["aware_not_runs"].mean(),
        "n": g.size(),
    })
    return out.sort_values("runs", ascending=False)


def failure_reasons(df: pd.DataFrame, top: int = 15) -> pd.DataFrame:
    """Most common Blender failure lines across all failed runs, with the versions they occur in."""
    failed = df[~df["runs"] & df["reason"].astype(bool)]
    if failed.empty:
        return failed
    grouped = failed.groupby("reason", observed=False).agg(
        count=("reason", "size"),
        versions=("version", lambda s: ", ".join(sorted(set(map(str, s)), key=VERSION_ORDER.index))),
        cases=("case_id", lambda s: ", ".join(sorted(set(s)))),
    )
    return grouped.sort_values("count", ascending=False).head(top)


def _style(ax, title: str, ylabel: str):
    ax.set_title(title, loc="left", color=INK, fontsize=12, pad=12)
    ax.set_ylabel(ylabel, color=MUTED)
    ax.tick_params(colors=INK, length=0)
    for side in ("top", "right"):
        ax.spines[side].set_visible(False)
    for side in ("left", "bottom"):
        ax.spines[side].set_color(RULE)
    ax.yaxis.grid(True, color=RULE, linewidth=0.6)
    ax.set_axisbelow(True)


def plot_drift_curves(df: pd.DataFrame, metric: str = "runs", ax=None):
    """Pass rate per model across Blender versions: the drift curve."""
    import matplotlib.pyplot as plt

    table = rate_table(df, metric).drop(columns="all")
    if ax is None:
        _, ax = plt.subplots(figsize=(7, 4), dpi=120)
    for i, (model, row) in enumerate(table.iterrows()):
        ax.plot(table.columns.astype(str), row.values, marker="o", markersize=4, linewidth=1.6,
                color=PALETTE[i % len(PALETTE)], label=str(model))
    ax.set_ylim(0, 1.02)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0%", "25%", "50%", "75%", "100%"])
    label = "scripts that run on the target version" if metric == "runs" else "answers that name the API change"
    _style(ax, f"Share of {label}, by Blender version", "")
    ax.set_xlabel("Blender version asked for", color=MUTED)
    ax.legend(frameon=False, fontsize=8, loc="lower left")
    return ax


def plot_category_heatmap(df: pd.DataFrame, metric: str = "runs", ax=None):
    """Category x version pass rate over all models: where exactly the API breaks."""
    import matplotlib.pyplot as plt
    import numpy as np

    table = df.pivot_table(index="category", columns="version", values=metric, aggfunc="mean", observed=False)
    table = table.loc[table.mean(axis=1).sort_values().index]
    if ax is None:
        _, ax = plt.subplots(figsize=(6, 0.45 * len(table) + 1.2), dpi=120)
    im = ax.imshow(table.values, cmap="Greys_r", vmin=0, vmax=1, aspect="auto")
    ax.set_xticks(range(table.shape[1]))
    ax.set_xticklabels(table.columns.astype(str))
    ax.set_yticks(range(table.shape[0]))
    ax.set_yticklabels(table.index)
    for i in range(table.shape[0]):
        for j in range(table.shape[1]):
            v = table.values[i, j]
            if not np.isnan(v):
                ax.text(j, i, f"{v:.0%}", ha="center", va="center", fontsize=8,
                        color=INK if v > 0.55 else "#f2f2f2")
    ax.set_title(f"{'Run' if metric == 'runs' else 'Awareness'} rate by change category and version, all models",
                 loc="left", color=INK, fontsize=12, pad=12)
    ax.tick_params(length=0, colors=INK)
    for s in ax.spines.values():
        s.set_visible(False)
    return ax
