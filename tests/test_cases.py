from bpy_drift.cases import VERSIONS, expand, expected_changes, load_cases, version_key


def test_version_key_orders_numerically():
    assert version_key("4.10") > version_key("4.2") > version_key("3.6")


def test_case_bank_loads_and_validates():
    cases = load_cases()
    assert len(cases) >= 10
    assert all(c.versions for c in cases)


def test_expected_changes_depend_on_target_version():
    by_id = {c.id: c for c in load_cases()}
    eevee = by_id["eevee-engine"]
    assert [c.id for c in expected_changes(eevee, "3.6")] == []
    assert [c.id for c in expected_changes(eevee, "4.2")] == ["render-engine-eevee-next"]
    assert "render-engine-eevee-50" in [c.id for c in expected_changes(eevee, "5.0")]

    override = by_id["boolean-apply"]
    # override dict was removed in 4.0: a live trap from 4.2 on, and "added" MANIFOLD never counts.
    assert [c.id for c in expected_changes(override, "3.6")] == []
    assert [c.id for c in expected_changes(override, "4.5")] == ["bpy-ops-context-override-dict"]


def test_assert_override_falls_back_to_default():
    by_id = {c.id: c for c in load_cases()}
    solver = by_id["boolean-fast-solver"]
    assert "'FAST'" in solver.assert_for("4.5")
    assert "'FLOAT'" in solver.assert_for("5.0")


def test_expand_yields_one_row_per_case_and_version():
    cases = load_cases()
    df = expand(cases)
    assert set(df.columns) >= {"case_id", "version", "category", "question"}
    assert len(df) == sum(len(c.versions) for c in cases)
    assert set(df["version"]) <= set(VERSIONS)
    assert len(expand(cases, versions=["5.0"])) == sum("5.0" in c.versions for c in cases)
