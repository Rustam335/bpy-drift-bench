"""Day-1 gate: prove every target Blender build starts headless and runs an assert script.

    python scripts/smoke_blender.py            # all versions
    python scripts/smoke_blender.py 4.5 5.0    # a subset

Locally it uses BLENDER_BIN_<mm> env vars; on Linux (Kaggle) it downloads the pinned builds.
Exit code is non-zero if any version fails, so this can gate the notebook before any LLM call.
"""

from __future__ import annotations

import sys
import time

from bpy_drift.blender import RELEASES, ensure_blender, run_script, verify_build

PROBE = "import bpy\nprint('objects:', [o.name for o in bpy.data.objects])\nbpy.data.objects['Cube'].location.x = 1.0"
ASSERT = "import bpy\nassert bpy.data.objects['Cube'].location.x == 1.0"
FAILING_ASSERT = "import bpy\nassert bpy.data.objects['Cube'].location.x == 2.0, 'deliberate failure'"


def main(versions: list[str]) -> int:
    failed = False
    for v in versions:
        t0 = time.time()
        try:
            binary = ensure_blender(v)
            build = verify_build(binary, v)
            ok = run_script(binary, PROBE, ASSERT)
            bad = run_script(binary, PROBE, FAILING_ASSERT)
        except Exception as e:  # noqa: BLE001 - report every failure, keep probing the rest
            print(f"[{v}] ERROR {e}")
            failed = True
            continue
        good = ok.passed and not bad.passed and "deliberate failure" in bad.reason
        failed |= not good
        print(f"[{v}] {'OK ' if good else 'BAD'} {build}  pass={ok.passed} fail-detected={not bad.passed} "
              f"reason={bad.reason!r}  {time.time() - t0:.1f}s")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:] or list(RELEASES)))
