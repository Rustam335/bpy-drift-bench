import os

from bpy_drift.blender import RELEASES, archive_dirs, find_archive


def test_find_archive_prefers_attached_dataset(tmp_path, monkeypatch):
    ds = tmp_path / "blender-linux-builds" / "nested"
    ds.mkdir(parents=True)
    name = f"blender-{RELEASES['4.5']}-linux-x64.tar.xz"
    (ds / name).write_bytes(b"not really a tarball")
    monkeypatch.setenv("BPY_DRIFT_TARBALL_DIRS", str(tmp_path))
    assert find_archive("4.5") == ds / name
    assert find_archive("5.0") is None


def test_archive_dirs_default_is_kaggle_input(monkeypatch):
    monkeypatch.delenv("BPY_DRIFT_TARBALL_DIRS", raising=False)
    assert [str(p) for p in archive_dirs()] == [os.path.join(os.sep, "kaggle", "input")] or archive_dirs()[0].name == "input"


def test_archive_dirs_splits_on_pathsep(monkeypatch):
    monkeypatch.setenv("BPY_DRIFT_TARBALL_DIRS", os.pathsep.join(["dir-a", "dir-b", ""]))
    assert [p.name for p in archive_dirs()] == ["dir-a", "dir-b"]
