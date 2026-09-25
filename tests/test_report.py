import matplotlib

matplotlib.use("Agg")

from bpy_drift.report import failure_reasons, gap_table, plot_category_heatmap, plot_drift_curves, rate_table, records_frame


def sample():
    rows = []
    for model, ok in (("a", True), ("b", False)):
        for version in ("3.6", "4.2", "4.5", "5.0"):
            for case, cat in (("eevee-engine", "render-engine"), ("link-object", "scene-object-api")):
                rows.append({
                    "model": model, "case_id": case, "category": cat, "version": version,
                    "runs": ok or version == "4.5", "aware": not ok,
                    "reason": "" if ok else "TypeError: bpy_struct: item.attr = val: enum \"BLENDER_EEVEE\" not found",
                })
    return records_frame(rows)


def test_rate_table_has_versions_and_all_column():
    t = rate_table(sample(), "runs")
    assert list(t.columns) == ["3.6", "4.2", "4.5", "5.0", "all"]
    assert t.loc["a", "all"] == 1.0
    assert t.loc["b", "4.5"] == 1.0 and t.loc["b", "3.6"] == 0.0


def test_gap_table_reports_disagreements():
    g = gap_table(sample())
    assert g.loc["a", "runs but unaware"] == 1.0
    assert g.loc["b", "aware but breaks"] == 0.75


def test_failure_reasons_groups_by_line():
    f = failure_reasons(sample())
    assert len(f) == 1 and f.iloc[0]["count"] == 6


def test_plots_render_without_error():
    df = sample()
    assert plot_drift_curves(df) is not None
    assert plot_category_heatmap(df) is not None
