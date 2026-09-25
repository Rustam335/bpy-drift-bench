"""Case bank: one question asked across several Blender versions.

`bpy_drift/data/cases.json` holds version-agnostic questions (package data, so the installed
wheel carries the bank). Each case names the API changes that
could trip a model on it; which of those are live traps depends on the target version
(`changedIn <= target`). The assert script can be overridden per version when the correct
end state itself differs between versions (e.g. the EEVEE engine id).
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from importlib import resources
from pathlib import Path
from typing import Iterable

import pandas as pd

VERSIONS = ("3.6", "4.2", "4.5", "5.0")


def version_key(v: str) -> tuple[int, ...]:
    """'4.2' -> (4, 2) so versions compare numerically, not as strings."""
    return tuple(int(p) for p in v.split("."))


@dataclass(frozen=True)
class ApiChange:
    id: str
    symbol: str
    kind: str  # removed | renamed | behavior | added
    changed_in: str
    replacement: str | None
    summary: str

    @property
    def is_trap(self) -> bool:
        # An "added" API is context; WATCH OUT is defined as deprecated/removed patterns.
        return self.kind != "added"


@dataclass(frozen=True)
class Case:
    id: str
    category: str
    question: str
    api_changes: tuple[str, ...]
    versions: tuple[str, ...]
    assert_script: str
    assert_by_version: dict[str, str] = field(default_factory=dict)
    notes: str = ""

    def assert_for(self, version: str) -> str:
        return self.assert_by_version.get(version, self.assert_script)


def load_api_changes() -> dict[str, ApiChange]:
    raw = json.loads(resources.files("bpy_drift").joinpath("data/api_changes.json").read_text("utf-8"))
    out = {}
    for c in raw:
        out[c["id"]] = ApiChange(
            id=c["id"], symbol=c["symbol"], kind=c["kind"], changed_in=c["changedIn"],
            replacement=c.get("replacement") or None, summary=c.get("summary", ""),
        )
    return out


def load_cases(path: str | Path | None = None) -> list[Case]:
    if path is None:
        raw = json.loads(resources.files("bpy_drift").joinpath("data/cases.json").read_text("utf-8"))
    else:
        raw = json.loads(Path(path).read_text("utf-8"))
    cases = []
    for c in raw:
        cases.append(Case(
            id=c["id"], category=c["category"], question=c["question"],
            api_changes=tuple(c.get("apiChanges", [])),
            versions=tuple(c.get("versions", VERSIONS)),
            assert_script=c["assert"],
            assert_by_version=dict(c.get("assertByVersion", {})),
            notes=c.get("notes", ""),
        ))
    _validate(cases)
    return cases


def _validate(cases: list[Case]) -> None:
    known = load_api_changes()
    ids = [c.id for c in cases]
    dupes = {i for i in ids if ids.count(i) > 1}
    if dupes:
        raise ValueError(f"duplicate case ids: {sorted(dupes)}")
    for c in cases:
        unknown = [a for a in c.api_changes if a not in known]
        if unknown:
            raise ValueError(f"case {c.id}: unknown apiChanges {unknown}")
        bad = [v for v in c.versions if v not in VERSIONS]
        if bad:
            raise ValueError(f"case {c.id}: unsupported versions {bad}")
        stray = [v for v in c.assert_by_version if v not in c.versions]
        if stray:
            raise ValueError(f"case {c.id}: assertByVersion for versions not run {stray}")


def expected_changes(case: Case, version: str) -> list[ApiChange]:
    """API changes that are live traps for this case at this target version."""
    known = load_api_changes()
    target = version_key(version)
    return [
        known[a] for a in case.api_changes
        if known[a].is_trap and version_key(known[a].changed_in) <= target
    ]


def expand(cases: Iterable[Case], versions: Iterable[str] = VERSIONS) -> pd.DataFrame:
    """One row per (case, version): the evaluation_data frame kbench iterates over."""
    wanted = set(versions)
    rows = []
    for c in cases:
        for v in c.versions:
            if v in wanted:
                rows.append({"case_id": c.id, "version": v, "category": c.category, "question": c.question})
    return pd.DataFrame(rows)
