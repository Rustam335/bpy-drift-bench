import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))

from aggregate_runs import load_records  # noqa: E402


def write(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True)
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def test_load_records_skips_the_output_folder(tmp_path):
    write(tmp_path / "6" / "m" / "1" / "records.jsonl", [{"model": "m", "case_id": "c", "version": "4.2"}])
    write(tmp_path / "out" / "records.jsonl", [{"model": "stale", "case_id": "c", "version": "4.2"}])

    rows = load_records(tmp_path, skip=tmp_path / "out")

    assert [r["model"] for r in rows] == ["m"]


def test_regrade_aware_uses_the_current_parser_on_stored_answers():
    from aggregate_runs import regrade_aware

    answer = "```python\nimport bpy\n```\n- bpy.ops.export_scene.obj: removed in 4.0, use bpy.ops.wm.obj_export\n"
    stale = {"answer": answer, "expected": ["export-scene-obj"], "aware": False,
             "failures": ["No WATCH OUT block in the answer.", "Blender: AttributeError: x"]}

    (row,) = regrade_aware([stale])

    assert row["aware"] is True
    assert row["failures"] == ["Blender: AttributeError: x"]


def test_split_truncated_moves_answers_cut_at_the_output_cap():
    from aggregate_runs import split_truncated

    cut = {"model": "google/gemini-3.8-flash", "case_id": "auto-smooth", "version": "4.5", "output_tokens": 8188,
           "runs": False}
    whole = {"model": "google/gemini-3.8-flash", "case_id": "auto-smooth", "version": "5.0", "output_tokens": 8074,
             "runs": True}
    big_cap = {"model": "deepseek-ai/deepseek-r1-0528", "case_id": "auto-smooth", "version": "4.5",
               "output_tokens": 8188, "runs": True}  # v6 gave reasoning models 16384: not truncated
    stored = {"model": "google/gemini-3.8-flash", "case_id": "color-strip", "version": "5.0", "output_tokens": 16380,
              "output_cap": 16384, "runs": False}  # v7 records carry the cap that was used

    kept, truncated = split_truncated([cut, whole, big_cap, stored])

    assert kept == [whole, big_cap]
    assert truncated == [cut, stored]


def test_regrade_runs_reruns_only_answers_whose_script_changed_under_the_current_parser(monkeypatch):
    import aggregate_runs
    from aggregate_runs import regrade_runs

    calls = []

    def fake_run(binary, script, assert_script="", timeout_s=120):
        calls.append((binary, script, assert_script))
        return aggregate_runs.RunOutcome(passed=True, returncode=0, stdout="", stderr="", timed_out=False)

    monkeypatch.setattr(aggregate_runs, "run_script", fake_run)
    monkeypatch.setattr(aggregate_runs, "local_blender", lambda version: "blender-4.2")

    thinking = ("<think>\n```python\n<script>\n```\n</think>\n```python\nimport bpy\nx = 1\n```\nWATCH OUT\n- none\n")
    stale = {"model": "deepseek-ai/deepseek-r1-0528", "case_id": "array-modifier", "version": "4.2", "answer": thinking,
             "script": "<script>", "runs": False, "reason": "SyntaxError: invalid syntax", "stderr": "boom",
             "failures": ["Blender: SyntaxError: invalid syntax"]}
    same = {"model": "google/gemini-3.8-flash", "case_id": "array-modifier", "version": "4.2",
            "answer": "```python\nimport bpy\n```\nWATCH OUT\n- none\n", "script": "import bpy", "runs": True,
            "reason": "", "stderr": "", "failures": []}

    (fixed,), unchanged = regrade_runs([stale, same])

    assert unchanged == [same]
    assert len(calls) == 1 and calls[0][0] == "blender-4.2" and calls[0][1] == "import bpy\nx = 1"
    assert calls[0][2]  # the case's assert travels with the script
    assert fixed["runs"] is True and fixed["script"] == "import bpy\nx = 1"
    assert fixed["reason"] == "" and fixed["failures"] == [] and fixed["stderr"] == ""


def test_regrade_runs_keeps_the_record_when_no_local_blender_is_available(monkeypatch, capsys):
    import aggregate_runs
    from aggregate_runs import regrade_runs

    monkeypatch.setattr(aggregate_runs, "local_blender", lambda version: None)
    stale = {"model": "m", "case_id": "array-modifier", "version": "5.0",
             "answer": "<think>\n```python\n<script>\n```\n</think>\n```python\nimport bpy\n```\n",
             "script": "<script>", "runs": False, "reason": "SyntaxError", "stderr": "", "failures": []}

    fixed, unchanged = regrade_runs([stale])

    assert fixed == [stale] and unchanged == []
    assert "no local Blender 5.0" in capsys.readouterr().out
