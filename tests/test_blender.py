import os

from bpy_drift.blender import RELEASES, archive_dirs, blender_reason, find_archive


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
    assert archive_dirs()[0].name == "input" and archive_dirs()[0].parent.name == "kaggle"


def test_archive_dirs_splits_on_pathsep(monkeypatch):
    monkeypatch.setenv("BPY_DRIFT_TARBALL_DIRS", os.pathsep.join(["dir-a", "dir-b", ""]))
    assert [p.name for p in archive_dirs()] == ["dir-a", "dir-b"]


def test_runtime_lib_table_matches_the_apt_package_list():
    from bpy_drift.blender import APT_PACKAGES, RUNTIME_LIBS, missing_runtime_libs
    assert set(RUNTIME_LIBS.values()) == set(APT_PACKAGES.split())
    if os.name == "nt":
        assert missing_runtime_libs() == []  # only Linux builds link against these


def test_blender_reason_prefers_the_exception_line_from_either_stream():
    # Blender 3.6 prints the traceback to stdout and only its own notice to stderr.
    stderr_36 = "Error: script failed, file: '/tmp/x/case.py', exiting.\n"
    stdout_36 = "Traceback (most recent call last):\n  File \"case.py\", line 2\nAssertionError: deliberate failure\n"
    assert blender_reason(stderr_36, stdout_36) == "AssertionError: deliberate failure"
    # 4.x puts everything on stderr; the exception line wins over the generic notice.
    stderr_42 = "Traceback (most recent call last):\nTypeError: bad enum\nError: script failed, file: 'x', exiting.\n"
    assert blender_reason(stderr_42, "") == "TypeError: bad enum"
    assert blender_reason("Error: script failed, file: 'x', exiting.", "nothing useful") == "Error: script failed, file: 'x', exiting."
    assert blender_reason("", "") == ""
