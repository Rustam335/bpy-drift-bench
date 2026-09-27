from bpy_drift.prompt import build_user_prompt, is_truncated, output_cap


def test_user_prompt_names_the_version_and_the_task():
    assert build_user_prompt("4.2", "Do X") == "Target: Blender 4.2.\n\nTask: Do X"


def test_output_cap_gives_thinking_models_more_room():
    assert output_cap("qwen/qwen3-coder-480b-a35b-instruct") == 8192
    assert output_cap("anthropic/claude-sonnet-5@default") == 8192
    # gemini 3.x flash reached the 8192 cap on v6 (thinking counts against max_tokens through the proxy)
    assert output_cap("google/gemini-3.8-flash") == 16384
    assert output_cap("google/gemini-3.1-pro-preview") == 16384
    assert output_cap("deepseek-ai/deepseek-r1-0528") == 16384
    assert output_cap("openai/gpt-5.5-2026-04-23") == 16384
    assert output_cap("xai/grok-4.6") == 16384


def test_is_truncated_only_within_the_margin_of_the_cap():
    assert is_truncated(8188, 8192)
    assert is_truncated(8192, 8192)
    assert is_truncated(8200, 8192)  # the proxy may count a few tokens past the cap
    assert not is_truncated(8074, 8192)
    assert not is_truncated(None, 8192)
    assert not is_truncated(8188, 16384)
    # usage summed over a cut first call (16380) and a completed retry (18829), stored under the doubled cap
    assert not is_truncated(35209, 32768)
