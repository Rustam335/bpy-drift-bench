"""bpy-drift: grade LLM-written Blender Python against the exact Blender version it was asked for.

Two verdicts per (case, version, model):
  runs   - the generated script executes in headless Blender <version> and the case's assert passes
  aware  - the WATCH OUT block names every API change that is a trap in that version
"""

from .cases import Case, load_cases, expand, expected_changes, version_key
from .contract import split_blocks, extract_script, check_watch_out, mentions
from .blender import RELEASES, ensure_blender, verify_build, run_script, blender_reason, RunOutcome
from .prompt import SYSTEM_PROMPT, build_user_prompt
from .grading import grade, GradeResult

__all__ = [
    "Case", "load_cases", "expand", "expected_changes", "version_key",
    "split_blocks", "extract_script", "check_watch_out", "mentions",
    "RELEASES", "ensure_blender", "verify_build", "run_script", "blender_reason", "RunOutcome",
    "SYSTEM_PROMPT", "build_user_prompt",
    "grade", "GradeResult",
]
