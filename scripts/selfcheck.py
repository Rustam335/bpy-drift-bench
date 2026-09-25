"""Prove the case bank: every hand-written reference answer passes its assert in every version it lists.

    python scripts/selfcheck.py                 # all cases, all versions
    python scripts/selfcheck.py 4.5 5.0         # a subset of versions
    python scripts/selfcheck.py --case eevee-engine --case color-strip

Reference answers live in bpy_drift/reference/<case>.py, with <case>.<mm>.py overriding one
version (e.g. eevee-engine.42.py). A case without a reference for a version is a failure too:
the bank only ships questions that are proven answerable. Exit code is non-zero on any failure.

Locally the Blender builds come from BLENDER_BIN_<mm>; on Linux the pinned builds are downloaded.
"""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from bpy_drift.blender import RELEASES, ensure_blender, run_script, verify_build
from bpy_drift.cases import load_cases

REFERENCE_DIR = Path(__file__).resolve().parents[1] / "bpy_drift" / "reference"


def reference_for(case_id: str, version: str) -> Path | None:
    specific = REFERENCE_DIR / f"{case_id}.{version.replace('.', '')}.py"
    if specific.exists():
        return specific
    default = REFERENCE_DIR / f"{case_id}.py"
    return default if default.exists() else None


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("versions", nargs="*", default=list(RELEASES), help="versions to check (default: all)")
    parser.add_argument("--case", action="append", dest="cases", help="only these case ids (repeatable)")
    args = parser.parse_args(argv)

    cases = [c for c in load_cases() if not args.cases or c.id in args.cases]
    binaries = {v: ensure_blender(v) for v in args.versions}
    for v, binary in binaries.items():
        print(f"[{v}] {verify_build(binary, v)}")

    failures = 0
    checked = 0
    for case in cases:
        for version in case.versions:
            if version not in binaries:
                continue
            checked += 1
            ref = reference_for(case.id, version)
            if ref is None:
                failures += 1
                print(f"MISSING  {case.id:24s} {version}  no reference answer")
                continue
            t0 = time.time()
            outcome = run_script(binaries[version], ref.read_text("utf-8"), case.assert_for(version))
            status = "ok     " if outcome.passed else "FAIL   "
            failures += not outcome.passed
            detail = "" if outcome.passed else f"  {outcome.reason}"
            print(f"{status}  {case.id:24s} {version}  {ref.name:32s} {time.time() - t0:4.1f}s{detail}")
            if not outcome.passed and outcome.stderr:
                tail = [l for l in outcome.stderr.strip().splitlines() if l.strip()][-6:]
                print("         " + "\n         ".join(tail))
    print(f"\n{checked - failures}/{checked} reference answers pass")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
