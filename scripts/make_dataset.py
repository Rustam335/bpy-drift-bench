"""Assemble the Kaggle dataset the notebook attaches instead of downloading anything.

Contents: the four pinned Linux Blender tarballs (see bpy_drift.blender.RELEASES) and a wheel of this
package, so a run needs no internet: `pip install --no-index <wheel>` and `ensure_blender()` finds
the archives under /kaggle/input.

    python scripts/make_dataset.py D:/Tools/blender/linux-tarballs          # builds dist/kaggle-dataset/
    kaggle datasets create -p dist/kaggle-dataset                            # first time
    kaggle datasets version -p dist/kaggle-dataset -m "bpy-drift 0.1.x"      # afterwards

Tarballs are linked/copied from the given directory; download them once with curl from
https://download.blender.org/release/Blender<minor>/blender-<full>-linux-x64.tar.xz.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path

from bpy_drift.blender import RELEASES

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "dist" / "kaggle-dataset"
DATASET_ID = "hoholalagaul/bpy-drift-blender-builds"
TITLE = "bpy-drift-blender-builds"  # Kaggle requires the title to slugify to the id


def main(tarball_dir: str) -> int:
    src = Path(tarball_dir)
    OUT.mkdir(parents=True, exist_ok=True)
    for stale in OUT.glob("*.whl"):
        stale.unlink()

    missing = []
    for version, full in RELEASES.items():
        name = f"blender-{full}-linux-x64.tar.xz"
        archive = src / name
        if not archive.is_file():
            missing.append(name)
            continue
        target = OUT / name
        if not target.exists() or target.stat().st_size != archive.stat().st_size:
            print(f"copying {name} ({archive.stat().st_size / 1e6:.0f} MB)")
            shutil.copyfile(archive, target)
    if missing:
        print("missing tarballs:", *missing, sep="\n  ")
        return 1

    print("building wheel")
    subprocess.run([sys.executable, "-m", "pip", "wheel", str(ROOT), "--no-deps", "-q", "-w", str(OUT)], check=True)

    meta = {
        "title": TITLE,
        "id": DATASET_ID,
        "licenses": [{"name": "other"}],
        "subtitle": "Pinned headless Blender 3.6/4.2/4.5/5.0 Linux builds plus the bpy-drift grading package",
        "description": (
            "Official Blender Foundation Linux x64 release archives (GPL-2.0-or-later, unmodified) for the four "
            "versions bpy-drift-bench grades against, and a wheel of the grading package. Attached to the benchmark "
            "notebook so every run uses exactly these binaries and needs no network access. "
            "Source: https://download.blender.org/release/ and https://github.com/Rustam335/bpy-drift-bench"
        ),
    }
    (OUT / "dataset-metadata.json").write_text(json.dumps(meta, indent=2) + "\n", "utf-8")
    total = sum(p.stat().st_size for p in OUT.iterdir()) / 1e6
    print(f"dataset folder ready: {OUT} ({total:.0f} MB)")
    for p in sorted(OUT.iterdir()):
        print(f"  {p.name:48s} {p.stat().st_size / 1e6:7.1f} MB")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1] if len(sys.argv) > 1 else "D:/Tools/blender/linux-tarballs"))
