"""Grade one model answer for one (case, version)."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict

from .blender import ensure_blender, run_script, verify_build
from .cases import Case, expected_changes
from .contract import check_watch_out, extract_script, split_blocks


@dataclass
class GradeResult:
    case_id: str
    version: str
    runs: bool
    aware: bool
    script: str
    failures: list[str] = field(default_factory=list)
    reason: str = ""
    stderr: str = ""
    blender_build: str = ""
    expected: list[str] = field(default_factory=list)

    def as_dict(self) -> dict:
        d = asdict(self)
        d["stderr"] = d["stderr"][-4000:]
        return d


def grade(answer: str, case: Case, version: str, binary: str | None = None, timeout_s: int = 120) -> GradeResult:
    """Run the answer's script in Blender `version` and check its WATCH OUT block.

    `runs`  : script + the case's assert exit 0 in the verified Blender build.
    `aware` : WATCH OUT names every trap live in this version (vacuously true when there is none).
    """
    expected = expected_changes(case, version)
    blocks = split_blocks(answer)
    aware_failures = check_watch_out(blocks.watch_out, expected)
    script = extract_script(answer)

    if not script:
        return GradeResult(
            case.id, version, runs=False, aware=not aware_failures, script="",
            failures=["No python script found in answer.", *aware_failures],
            reason="no script", expected=[c.id for c in expected],
        )

    binary = binary or ensure_blender(version)
    build = verify_build(binary, version)
    outcome = run_script(binary, script, case.assert_for(version), timeout_s=timeout_s)
    failures = list(aware_failures)
    if not outcome.passed:
        failures.append(f"Blender: {outcome.reason}")
    return GradeResult(
        case.id, version, runs=outcome.passed, aware=not aware_failures, script=script,
        failures=failures, reason="" if outcome.passed else outcome.reason,
        stderr=outcome.stderr, blender_build=build, expected=[c.id for c in expected],
    )
