"""Locate, download and drive headless Blender builds, one per target version.

Resolution order for a target `major.minor`:
  1. env `BLENDER_BIN_<major><minor>` (e.g. BLENDER_BIN_45=D:/Tools/blender/.../blender.exe)
  2. an already-extracted portable build under the cache root
  3. a pinned tar.xz found under the archive directories (env `BPY_DRIFT_TARBALL_DIRS`, os.pathsep
     separated, default `/kaggle/input`, searched recursively): a Kaggle dataset attached to the
     notebook, so a run needs no internet
  4. download the pinned Linux x64 tar.xz from download.blender.org and extract it

The cache root is env `BPY_DRIFT_BLENDER_ROOT`, else `/tmp/bpy-drift/blender` on Linux
(Kaggle: outside /kaggle/working so ~5 GB of binaries never become notebook output).
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import sys
import tarfile
import tempfile
from dataclasses import dataclass
from pathlib import Path

import requests

# Pinned builds: same patch versions as the local Windows builds used in bpy-compass,
# 3.6.23 is the final 3.6 LTS release. URLs verified 2026-09-25.
RELEASES = {
    "3.6": "3.6.23",
    "4.2": "4.2.23",
    "4.5": "4.5.14",
    "5.0": "5.0.1",
}
DOWNLOAD_URL = "https://download.blender.org/release/Blender{minor}/blender-{full}-linux-x64.tar.xz"

# Shared libraries a headless Linux Blender still links against (X11/GL stubs).
APT_PACKAGES = "libxi6 libxxf86vm1 libxfixes3 libxrender1 libgl1 libegl1 libsm6 libxkbcommon0"

DEFAULT_TIMEOUT_S = 120
_verified: dict[str, str] = {}


def cache_root() -> Path:
    env = os.environ.get("BPY_DRIFT_BLENDER_ROOT")
    if env:
        return Path(env)
    if platform.system() == "Windows":
        return Path(tempfile.gettempdir()) / "bpy-drift" / "blender"
    return Path("/tmp/bpy-drift/blender")


def env_var_for(version: str) -> str:
    return "BLENDER_BIN_" + version.replace(".", "")


def _extracted_binary(version: str) -> Path:
    full = RELEASES[version]
    return cache_root() / f"blender-{full}-linux-x64" / "blender"


def archive_dirs() -> list[Path]:
    env = os.environ.get("BPY_DRIFT_TARBALL_DIRS")
    if env is None:
        return [Path("/kaggle/input")]
    return [Path(part) for part in env.split(os.pathsep) if part.strip()]


def find_archive(version: str) -> Path | None:
    """The pinned tar.xz for `version` inside an archive directory (an attached Kaggle dataset), if any."""
    name = f"blender-{RELEASES[version]}-linux-x64.tar.xz"
    for root in archive_dirs():
        if not root.is_dir():
            continue
        direct = root / name
        if direct.is_file():
            return direct
        found = next(root.rglob(name), None)
        if found is not None:
            return found
    return None


def download(version: str, log=print) -> Path:
    """Download and extract the pinned Linux build; returns the binary path."""
    if platform.system() != "Linux":
        raise RuntimeError(
            f"Automatic download only ships Linux builds. Set {env_var_for(version)} to a local Blender {version}."
        )
    binary = _extracted_binary(version)
    if binary.exists():
        return binary
    full = RELEASES[version]
    url = DOWNLOAD_URL.format(minor=version, full=full)
    root = cache_root()
    root.mkdir(parents=True, exist_ok=True)
    archive = root / f"blender-{full}-linux-x64.tar.xz"
    local = find_archive(version)
    if local is not None:
        log(f"using attached archive {local}")
        archive = local
    elif not archive.exists():
        log(f"downloading {url}")
        with requests.get(url, stream=True, timeout=60) as r:
            r.raise_for_status()
            tmp = archive.with_suffix(".part")
            with open(tmp, "wb") as f:
                for chunk in r.iter_content(chunk_size=1 << 20):
                    f.write(chunk)
            tmp.rename(archive)
    log(f"extracting {archive.name}")
    with tarfile.open(archive, "r:xz") as tar:
        tar.extractall(root, filter="data") if sys.version_info >= (3, 12) else tar.extractall(root)
    if local is None:
        archive.unlink(missing_ok=True)  # attached datasets are read-only and stay where they are
    if not binary.exists():
        raise RuntimeError(f"extraction finished but {binary} is missing")
    return binary


def ensure_blender(version: str, log=print) -> str:
    """Path to a Blender binary for `version`, downloading if needed. Does not verify; see verify_build."""
    if version not in RELEASES:
        raise ValueError(f"unsupported version {version}; known: {sorted(RELEASES)}")
    explicit = os.environ.get(env_var_for(version))
    if explicit:
        return explicit
    binary = _extracted_binary(version)
    if binary.exists():
        return str(binary)
    return str(download(version, log=log))


def verify_build(binary: str, version: str) -> str:
    """Run `blender --version` and check the runtime is the requested major.minor. Returns the build line."""
    cached = _verified.get(binary)
    if cached:
        return cached
    out = subprocess.run([binary, "--version"], capture_output=True, text=True, timeout=60)
    # Some builds print allocator notices first (4.2 on Windows), so take the first line that names the build.
    lines = [l.strip() for l in (out.stdout or "").splitlines()]
    first = next((l for l in lines if l.startswith("Blender ")), "")
    m = re.match(r"^Blender (\d+\.\d+)", first)
    if not m:
        raise RuntimeError(f"{binary} did not report a Blender version: {out.stdout!r} {out.stderr!r}")
    if m.group(1) != version:
        raise RuntimeError(f"{binary} is Blender {m.group(1)}, but target {version} needs a {version} build")
    _verified[binary] = first
    return first


@dataclass(frozen=True)
class RunOutcome:
    passed: bool
    returncode: int | None
    stdout: str
    stderr: str
    timed_out: bool

    @property
    def reason(self) -> str:
        if self.timed_out:
            return "timeout"
        return blender_reason(self.stderr)


def blender_reason(stderr: str) -> str:
    """The Python exception line from a failed run, else the first stderr line."""
    lines = [l.strip() for l in (stderr or "").splitlines() if l.strip()]
    for line in reversed(lines):
        if re.match(r"^[A-Za-z_.]*(Error|Exception)\b", line) and not line.startswith("Error: script failed"):
            return line
    return lines[0] if lines else ""


def run_script(binary: str, script: str, assert_script: str = "", timeout_s: int = DEFAULT_TIMEOUT_S) -> RunOutcome:
    """Run `script` then `assert_script` in one headless, factory-startup Blender process.

    Exit code 0 means both ran without an exception. Each run gets a scratch directory that
    is removed afterwards; cases that write files read BPY_OUT_OBJ instead of inventing a path.
    """
    scratch = Path(tempfile.mkdtemp(prefix="bpy-drift-"))
    try:
        case_file = scratch / "case.py"
        case_file.write_text("\n".join([script, "", "# ---- assertions ----", assert_script or ""]), "utf-8")
        env = {**os.environ, "BPY_OUT_OBJ": str(scratch / "out.obj")}
        try:
            out = subprocess.run(
                [binary, "-b", "--factory-startup", "--python-exit-code", "1", "--python", str(case_file)],
                capture_output=True, text=True, timeout=timeout_s, env=env,
            )
        except subprocess.TimeoutExpired as e:
            return RunOutcome(False, None, _text(e.stdout), _text(e.stderr), timed_out=True)
        return RunOutcome(out.returncode == 0, out.returncode, out.stdout, out.stderr, timed_out=False)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)


def _text(b) -> str:
    if b is None:
        return ""
    return b if isinstance(b, str) else b.decode("utf-8", "replace")
