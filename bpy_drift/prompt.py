"""The prompt every model gets. Same wording for every model and version; only the version changes.

No tools, no retrieval, no hints about what changed: the benchmark measures what the model
knows about the bpy API of a given version on its own.
"""

SYSTEM_PROMPT = """You write Blender Python (bpy) scripts for a specific Blender version.
The script runs in headless Blender started with --factory-startup, so the scene contains the default
Cube, Light and Camera. Every API you use must exist and behave as described in the requested version.

Respond in exactly this structure:

```python
<the complete script>
```

WATCH OUT
- <one bullet per bpy API used here that was removed, renamed or changed behaviour in or before the requested version: old form, the version it changed in, and the replacement>
(write "- none" if nothing relevant changed)
"""


def build_user_prompt(version: str, question: str) -> str:
    return f"Target: Blender {version}.\n\nTask: {question}"


# The model proxy reserves quota for the worst case output before every call (its default is the model maximum,
# which produced 403 "estimated cost exceeds quota" against the daily inference budget), so max_tokens is capped.
# Answers are a short script plus a few bullets, under 600 visible tokens for every model seen so far, but thinking
# counts against the same budget through the proxy: gemini-3.8-flash reached the 8192 cap on one answer.
MAX_OUTPUT_TOKENS = 8192
REASONING_OUTPUT_TOKENS = 16384
REASONING_MARKERS = ("deepseek-r1", "thinking", "reasoning", "gpt-5", "gpt-6", "grok", "gemini")
CAP_MARGIN = 32  # tokens; a model does not stop this close to the cap by itself


def output_cap(model_name: str) -> int:
    name = model_name.lower()
    return REASONING_OUTPUT_TOKENS if any(m in name for m in REASONING_MARKERS) else MAX_OUTPUT_TOKENS


def is_truncated(output_tokens: int | None, cap: int, margin: int = CAP_MARGIN) -> bool:
    """True when the answer stopped at the output cap: an infrastructure limit, not a model error."""
    return output_tokens is not None and output_tokens >= cap - margin
