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
