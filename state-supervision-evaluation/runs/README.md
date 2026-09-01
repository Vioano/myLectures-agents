# Episode long shadow runs

Each child directory is an immutable-at-handoff evaluation pack for one real production run.

Recommended name:

```text
<episode-id>-<slug>-<started-at-utc>
```

The Episode Session may append observations and update the draft retrospective while production is active. Once `evaluation-handoff.json` is marked `evaluation_ready`, do not rewrite raw observations or telemetry. Corrections must be additive and identify the superseded statement.

Episode 13 should use the templates under `../templates/` and the policy in `../README.md`.
