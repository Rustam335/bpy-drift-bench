from bpy_drift.cases import ApiChange
from bpy_drift.contract import check_watch_out, extract_script, mentions, split_blocks


def change(symbol, replacement=None, kind="removed", changed_in="4.0"):
    return ApiChange(id="x", symbol=symbol, kind=kind, changed_in=changed_in, replacement=replacement, summary="")


def test_split_blocks_finds_watch_out_heading_variants():
    for heading in ("WATCH OUT", "## WATCH OUT", "**WATCH OUT**"):
        text = f"```python\nimport bpy\n```\n\n{heading}\n- none\n"
        blocks = split_blocks(text)
        assert blocks.watch_out is not None
        assert "import bpy" in blocks.answer


def test_split_blocks_without_watch_out():
    assert split_blocks("```python\nx=1\n```").watch_out is None
    assert split_blocks("```python\nx=1\n```\nThat is all.").watch_out is None


def test_split_blocks_takes_bare_bullets_after_the_fence_as_watch_out():
    text = "```python\nx=1\n```\n\n- bpy.ops.export_scene.obj: 3.6: replaced by bpy.ops.wm.obj_export\n"
    blocks = split_blocks(text)
    assert blocks.watch_out.strip().startswith("- bpy.ops.export_scene.obj")
    assert blocks.answer.endswith("```")
    assert split_blocks("```python\nx=1\n```\n- none").watch_out.strip() == "- none"


def test_extract_script_prefers_fenced_block():
    text = "Here you go:\n```python\nimport bpy\nprint(1)\n```\nWATCH OUT\n- none"
    assert extract_script(text) == "import bpy\nprint(1)"


def test_extract_script_dedents_a_fenced_block_indented_as_a_whole():
    # Gemini 3 Flash indented the entire fenced block by four spaces; Blender raised IndentationError.
    text = "    ```python\n    import bpy\n\n    if True:\n        x = 1\n    ```\n    WATCH OUT\n    - none"
    assert extract_script(text) == "import bpy\n\nif True:\n    x = 1"


def test_extract_script_falls_back_to_indented_block():
    text = "ANSWER\n\n    import bpy\n    print(2)\n\nWATCH OUT\n- none"
    assert extract_script(text) == "import bpy\nprint(2)"


def test_mentions_uses_last_identifier_and_ignores_punctuation():
    assert mentions("scene.objects.link was removed; use collection.objects.link", "bpy.types.Scene.objects.link")
    assert mentions("call Select-Set instead", "bpy.types.Object.select_set / select_get")
    assert not mentions("nothing relevant", "bpy.types.Scene.objects.link")


def test_mentions_uses_quoted_value_when_symbol_quotes_one():
    assert mentions("use 'FLOAT' now", 'bpy.types.BooleanModifier.solver == "FAST"') is False
    assert mentions("FAST was renamed", 'bpy.types.BooleanModifier.solver == "FAST"')


def test_mentions_quoted_value_is_direction_aware():
    # 5.0 renamed BLENDER_EEVEE_NEXT back to BLENDER_EEVEE: naming only the old id must not count as the new one.
    assert not mentions("BLENDER_EEVEE_NEXT is the id since 4.2", '"BLENDER_EEVEE"')
    assert mentions("use BLENDER_EEVEE, not BLENDER_EEVEE_NEXT", '"BLENDER_EEVEE"')
    assert mentions("set engine = 'BLENDER_EEVEE_NEXT'", 'RenderSettings.engine == "BLENDER_EEVEE_NEXT"')
    assert not mentions("the FASTER path", 'solver == "FAST"')


def test_mentions_quoted_phrase_matches_whole_phrase():
    assert mentions('use inputs["Emission Color"] now', 'inputs["Emission Color"] and inputs["Emission Strength"]')
    assert mentions("the Emission Strength socket", 'inputs["Emission Color"] and inputs["Emission Strength"]')
    assert not mentions("the Emission socket was split", 'inputs["Emission Color"]')


def test_mentions_dunder_operator_maps_to_symbol():
    assert mentions("use the @ operator", "mathutils.Matrix.__matmul__")
    assert mentions("the * operator no longer multiplies matrices", "mathutils.Matrix.__mul__")
    assert mentions("replaced by @ (PEP 465)", "@ operator (PEP 465)")


def test_check_watch_out_requires_symbol_and_replacement():
    expected = [change("bpy.ops.export_scene.obj", "bpy.ops.wm.obj_export")]
    assert check_watch_out("- export_scene.obj removed in 4.0, use wm.obj_export", expected) == []
    failures = check_watch_out("- export_scene.obj removed in 4.0", expected)
    assert len(failures) == 1 and "replacement" in failures[0]


def test_check_watch_out_ignores_added_changes_and_missing_block_when_no_traps():
    assert check_watch_out(None, [change("x", kind="added")]) == []
    assert check_watch_out(None, []) == []
    assert check_watch_out(None, [change("bpy.types.Scene.update")]) == ["No WATCH OUT block in the answer."]


def test_no_replacement_marker_is_not_required():
    expected = [change("bpy.types.Mesh.calc_normals", "(none) normals are computed lazily")]
    assert check_watch_out("- calc_normals was removed in 4.0", expected) == []
