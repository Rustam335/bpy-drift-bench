"""Output-contract checks (Python port of bpy-compass `lib/eval-contract.ts`).

The model must answer with a fenced python block and a `WATCH OUT` section. Running the
script proves the code; this module checks the second axis: does WATCH OUT name every API
change that is a trap in the target version, plus its replacement when there is one?

Matching is keyword-based on purpose: a symbol such as `bpy.types.Scene.objects.link` is
reduced to its last identifier (`link`) and matched as a substring of the punctuation-free
text. A symbol that quotes a value (`solver == "FLOAT"`, `inputs["Emission Color"]`) is
matched as that whole word or phrase, so naming `BLENDER_EEVEE_NEXT` does not count as
naming `BLENDER_EEVEE`: for renamed enum values the direction matters. Alternatives written
as `a / b`, `a and b` or `a via b` count if any is mentioned. Case and punctuation are ignored.
"""

from __future__ import annotations

import re
import textwrap
from dataclasses import dataclass

STOP_WORDS = {"bpy", "types", "ops", "none", "and", "the", "via", "attribute", "operator", "pep"}
ALTERNATIVE_SEPARATORS = re.compile(r"\s+/\s+|\s+and\s+|\s+via\s+")
NO_REPLACEMENT = re.compile(r"^\s*\(none\)", re.I)
DUNDER_OPERATORS = {"mul": "*", "matmul": "@"}
OPERATOR_CHARS = re.compile(r"[@*]")
IDENTIFIER = re.compile(r"[A-Za-z_][A-Za-z0-9_]*")
QUOTED = re.compile(r"[\"']([^\"']+)[\"']")
FENCED = re.compile(r"```(?:python|py)?\s*\n(.*?)```", re.S)


@dataclass(frozen=True)
class Blocks:
    answer: str
    watch_out: str | None


BULLET = re.compile(r"^\s*[-*]\s+\S", re.M)


def split_blocks(text: str) -> Blocks:
    """The WATCH OUT section: from its heading to the end, or, when the heading is missing, the
    bullet list that follows the last closing fence (some models drop the heading and answer
    `- none` or `- <change>` bare; the axis grades what they know, not whether they wrote the word)."""
    m = re.search(r"^\s*(?:#+\s*)?(?:\*\*)?WATCH OUT\b", text, re.M)
    if m:
        return Blocks(answer=text[: m.start()], watch_out=text[m.start():])
    head, sep, tail = text.rpartition("```")
    if sep and BULLET.search(tail):
        return Blocks(answer=head + sep, watch_out=tail)
    return Blocks(answer=text, watch_out=None)


def extract_script(text: str) -> str:
    """The python script in the answer: first fenced block, else a 4-space indented block.

    A fenced block that the model indented as a whole (markdown list style) is dedented, so the
    grade reflects the bpy calls and not the chat formatting.
    """
    m = FENCED.search(text)
    if m:
        return textwrap.dedent(m.group(1)).strip("\n").rstrip()
    answer = split_blocks(text).answer
    indented = [line[4:] for line in answer.split("\n") if line.startswith("    ")]
    return "\n".join(indented).strip()


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9@*]", "", text.lower())


WORD = re.compile(r"[A-Za-z0-9_]+")


def words(text: str) -> str:
    """Lower-case words separated by single spaces, underscores removed inside a word.

    `inputs["Emission Color"]` -> `inputs emission color`; `BLENDER_EEVEE_NEXT` -> `blendereeveenext`.
    """
    return " ".join(w.replace("_", "").lower() for w in WORD.findall(text))


def mentions_phrase(text: str, phrase: str) -> bool:
    """Whole-word match of a quoted value: 'BLENDER_EEVEE' is not found inside 'BLENDER_EEVEE_NEXT'."""
    needle = words(phrase)
    return bool(needle) and re.search(rf"(?<![a-z0-9]){re.escape(needle)}(?![a-z0-9])", words(text)) is not None


def _key_tokens(alternative: str) -> list[str]:
    quoted = QUOTED.findall(alternative)
    if quoted:
        return [quoted[-1]]
    identifiers = [
        i.strip("_") for i in IDENTIFIER.findall(alternative)
        if len(i.strip("_")) >= 3 and i.strip("_").lower() not in STOP_WORDS
    ]
    tokens: list[str] = []
    if identifiers:
        last = identifiers[-1]
        tokens.append(last)
        if last.lower() in DUNDER_OPERATORS:
            tokens.append(DUNDER_OPERATORS[last.lower()])
    tokens.extend(OPERATOR_CHARS.findall(alternative))
    return tokens


def mentions(text: str, symbol_or_replacement: str) -> bool:
    haystack = normalize(text)
    for alternative in ALTERNATIVE_SEPARATORS.split(symbol_or_replacement):
        quoted = QUOTED.findall(alternative)
        if quoted:
            if mentions_phrase(text, quoted[-1]):
                return True
            continue
        tokens = _key_tokens(alternative)
        if tokens and any(normalize(t) in haystack for t in tokens):
            return True
    return False


def check_watch_out(watch_out: str | None, expected) -> list[str]:
    """Failures for the awareness axis; empty list means aware. `expected` = list[ApiChange]."""
    traps = [c for c in expected if c.is_trap]
    if not traps:
        return []
    if watch_out is None:
        return ["No WATCH OUT block in the answer."]
    failures = []
    for change in traps:
        if not mentions(watch_out, change.symbol):
            failures.append(f"WATCH OUT does not mention {change.symbol}.")
        replacement = (change.replacement or "").strip()
        if replacement and not NO_REPLACEMENT.match(replacement) and not mentions(watch_out, replacement):
            failures.append(f"WATCH OUT does not name the replacement for {change.symbol} ({replacement}).")
    return failures
