# Overview And Boundaries

This skill governs public-facing companion notebooks for the myLectures course
series. A notebook is part of the learning product, not production scratch.

## Role Of Notebooks

The notebook should extend the video after viewing:

- let students rerun the core construction;
- turn visual intuition into computation, derivation, or proof;
- provide exercises that reveal the same course object from another angle;
- keep optional extensions discoverable without overwhelming the main path.

It should not become:

- a second lecture script;
- a random widget gallery;
- a collection of solved exam drills with no course-object connection;
- a dumping ground for generated experiments.

## Repository Boundary

The video production repo is `/Volumes/bocchi/myLectures`.

The public notebook repo is:

```text
/Volumes/bocchi/myLectures/数学物理方法PowerPack-Notebooks/
```

This is a nested Git repository and is ignored by the outer production repo.
Run Git commands inside it when changing notebooks.

## Draft Versus Production

Use `draft/` for generated attempts, rejected directions, temporary experiments,
and reference candidates.

Use `notebook.ipynb` at the episode root only when the notebook is intended as
the current production candidate.

Do not present a `draft/` notebook as production unless the user explicitly asks
to inspect that draft.

## Course Source Boundary

Use the video script, storyboard, final episode intent, and user direction as
the source of truth. Learning-vault material can inspire content only when the
user asks for it or points to it. Do not copy personal learning vault state,
queues, Obsidian settings, or private scaffolding into the notebook repo.

## Lessons From The Animation Pipeline

The notebook workflow borrows these mechanisms from the animation pipeline:

- living skill references instead of one long monolithic instruction file;
- authoring preflight from human and accepted-agent feedback;
- abstract review standards before concrete regression cases;
- issue JSON as a repair queue;
- separate draft, production, review, and generated-output semantics;
- automatic checks plus independent/human review gates;
- promotion of only distilled reusable lessons into the skill.
