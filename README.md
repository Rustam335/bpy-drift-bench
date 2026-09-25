# bpy-drift-bench

A Kaggle benchmark that measures how badly language models suffer from **Blender Python API drift**:
the same scripting question asked for Blender 3.6, 4.2, 4.5 and 5.0, graded by running the model's
script inside that exact Blender version, headless.

Two verdicts per answer:

| axis | how it is decided |
|------|-------------------|
| **runs** | the generated script and the case's assert script exit 0 in the target Blender build (`blender -b --factory-startup --python`) |
| **aware** | the answer's `WATCH OUT` block names every API that was removed, renamed or changed for that version, and its replacement |

The two come apart in practice: code can run while the model has no idea the API changed, and a model can
describe the change correctly and still emit the old call.

## Layout

```
bpy_drift/        grading library (pip install -e .)
  cases.py        case bank loader, per-version expected API changes
  contract.py     WATCH OUT check (keyword match on symbol + replacement)
  blender.py      download / locate / verify / run headless Blender per version
  prompt.py       the one prompt every model gets
  grading.py      grade(answer, case, version) -> runs, aware, failures
  data/api_changes.json   32 verified changes with the version they happened in
  data/cases.json         version-agnostic questions + assert scripts (overrides per version where the correct state differs)
  reference/              hand-written answers per case (and per version where they differ), proven by scripts/selfcheck.py
notebooks/        the Kaggle notebook and its kernel-metadata.json
scripts/          smoke_blender.py (every target build starts and asserts work) · selfcheck.py (every reference answer passes its assert in every version)
tests/            pytest
```

## Local use

```
pip install -e . pytest
pytest
set BLENDER_BIN_45=D:/path/to/blender-4.5.14/blender.exe   # one per target: 36, 42, 45, 50
python scripts/smoke_blender.py 4.5
```

On Linux (including Kaggle) the pinned portable builds are downloaded automatically to `/tmp/bpy-drift/blender`.

## Origin

The case bank, assert scripts and the WATCH OUT contract come from [bpy-compass](https://github.com/Rustam335/bpy-compass),
a version-aware bpy assistant built on a Sanity knowledge base. Its evaluation compared one model with and without the
knowledge base; this benchmark asks the broader question across models and versions.

## License

MIT.
