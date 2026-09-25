"""Output-contract checks (Python port of bpy-compass `lib/eval-contract.ts`).

The model must answer with a fenced python block and a `WATCH OUT` section. Running the
script proves the code; this module checks the second axis: does WATCH OUT name every API
change that is a trap in the target version, plus its replacement when there is one?

Matching is keyword-based on purpose: a symbol such as `bpy.types.Scene.objects.link` is
reduced to its last identifier (`link`) or, when it quotes a value (`solver == "FLOAT"`),
to that quoted value. Alternatives written as `a / b`, `a and b` or `a via b` count if any
is mentioned. Case, spaces and punctuation are ignored.
"""

from __future__ import annotations

import re
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


def split_blocks(text: str) -> Blocks:
    m = re.search(r"^\s*(?:#+\s*)?(?:\*\*)?WATCH OUT\b", text, re.M)
    if not m:
        return Blocks(answer=text, watch_out=None)
    return Blocks(answer=text[: m.start()], watch_out=text[m.start():])


def extract_script(text: str) -> str:
    """The python script in the answer: first fenced block, else a 4-space indented block."""
    m = FENCED.search(text)
    if m:
        return m.group(1).rstrip()
    answer = split_blocks(text).answer
    indented = [line[4:] for line in answer.split("\n") if line.startswith("    ")]
    return "\n".join(indented).strip()


def normalize(text: str) -> str:
    return re.sub(r"[^a-z0-9@*]", "", text.lower())


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
