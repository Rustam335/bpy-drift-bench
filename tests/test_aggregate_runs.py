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
