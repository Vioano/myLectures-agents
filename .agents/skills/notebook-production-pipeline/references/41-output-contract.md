# Output Contract

This file defines paths and source/generated boundaries for notebook work.

## Notebook Repository

```text
数学物理方法PowerPack-Notebooks/
  README.md
  pyproject.toml
  uv.lock
  notebooks/
    NNNN-slug.ipynb                   public production candidate
  episodes/
    NNNN-slug/
      README.md                       episode production/control notes
      draft/                          rejected/generated/temporary notebooks
      review/
        audits/
        gate/
        human-feedback/
        agent-feedback/
        issues/
      assets/                         small local assets for this notebook
      data/                           small notebook-specific data if needed
  handouts/
  data/
```

The exact review directories may be created when a notebook becomes a
production candidate. Draft-only attempts do not need full review scaffolding.

## Review Gate State

Hard review receipts live under:

```text
episodes/NNNN-slug/review/gate/<review_id>/
  state.json
  events.jsonl
  review.json
  fixes/
```

`state.json` and `review.json` are source-side review records and may be
committed with the notebook when the candidate is ready for user inspection.
Large executed exports, screenshots, and temporary conversions remain generated
artifacts unless the user explicitly requests them.

## Draft Naming

Use explicit draft directories:

```text
episodes/NNNN-slug/draft/qoder-YYYY-MM-DD/notebook.ipynb
episodes/NNNN-slug/draft/codex-YYYY-MM-DD-<short-purpose>/notebook.ipynb
```

If a draft is rejected because the production direction is wrong, add a short
`README.md` explaining why it is archived.

## Production Notebook

Only place public production notebooks directly under `notebooks/` as
`notebooks/NNNN-slug.ipynb`. Do not publish a generic
`notebooks/NNNN-slug/notebook.ipynb`; that path hides the student-facing entry
inside a production-control directory. A production candidate must:

- follow the current user direction;
- execute top-to-bottom;
- pass automatic audit or have explicit known blockers;
- have review status recorded when it is ready for user inspection;
- pass `scripts/review_gate.py status --require-pass` or clearly state why the
  gate is blocked.

The episode directory is backstage. It can contain README, contracts, drafts,
review receipts, issue JSON, small assets, and small data files, but it is not
the public notebook entry.

## Generated Outputs

Large executed outputs, exported HTML, screenshots, caches, and temporary
notebook conversions should not be committed unless the user asks for a
specific artifact.

Use `/tmp` for validation outputs by default.

## Git Hygiene

Run Git status inside the nested notebook repo:

```bash
git -C 数学物理方法PowerPack-Notebooks status --short --branch
```

On `/Volumes`, run `dot_clean` after bulk notebook moves or generated files.
Never stage `._*`, `.DS_Store`, `.ipynb_checkpoints/`, or `.venv/`.
