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
