# Human observation checklist

The observer watches the live Web UI; the black-box Agent writes the separate
Agent experience report. Do not coach the Agent unless the run cannot continue.
Every coaching message counts as a human intervention.

## Before start

- [ ] Fresh episode selected; no human-recording branch or pressure event is visible.
- [ ] Initial all-TTS topology is understandable without opening every task.
- [ ] Overall completion and per-branch state are visible.
- [ ] Default graph shows a bounded release view, with minimap and zoom controls.
- [ ] Browser event stream is connected and the eight-minute timer is ready.

## During normal parallel release

- [ ] Contract approval visibly releases audio and visual work in parallel.
- [ ] Agent workstations show who owns which lease.
- [ ] Progress changes are event-derived, not a decorative timer.
- [ ] The observer can distinguish running, review, waiting and legal idle.
- [ ] A single click inspects; a double click changes topology depth.

## During the late recording request

- [ ] A new upload/replacement branch appears only after the user event.
- [ ] The old back-half TTS route remains visible as superseded/out-of-route.
- [ ] Front-half TTS remains active and is not invalidated.
- [ ] Only genuine descendants are rewired or invalidated.
- [ ] The data direction from recording to transcript/alignment/split/audio is inspectable.
- [ ] The five-second question can be answered: what changed, who is working,
      what is blocked, what was invalidated, and what releases next?

## During review return and recovery

- [ ] Review return does not steal focus from a live task.
- [ ] At the next boundary, the returned finding is exact and actionable.
- [ ] A duplicate semantic-work attempt is denied without creating a fake task.
- [ ] An idempotent retry does not duplicate artifacts/events.
- [ ] No sibling or parent scope is damaged by local rework.

## Media and Human gate

- [ ] Placeholder MP4/WAV plays directly in the browser.
- [ ] One annotation binds exact time and frame position.
- [ ] One annotation enters the episode draft and batch submission succeeds.
- [ ] Bubble/sidebar projection does not hide or duplicate player state.
- [ ] Fullscreen uses the bubble and keeps media/annotation access usable.
- [ ] Independent review is visibly distinct from Human authority.

## Archify-derived visual checks

- [ ] One obvious main route; side branches join at their semantic parent.
- [ ] Default release view contains roughly twelve or fewer primary nodes.
- [ ] Edge labels remain obtainable without forming a permanent label cloud.
- [ ] Lines do not cross unrelated opaque nodes or create ambiguous shared corridors.
- [ ] Active trace/motion is finite and static meaning remains complete.
- [ ] Reading depth is progressive: overview, focus passport, diagnostic whole graph.
- [ ] Minimap mirrors the graph and never disagrees with canonical state.
- [ ] Text remains readable; no panel solves crowding by tiny typography.
- [ ] No page-level horizontal overflow at 1440x900, 1600x1000, 1920x1080,
      or 2048x1320; desktop page-height overflow is recorded rather than hidden.

## Stop and result

- [ ] At 07:30 no new plot is introduced.
- [ ] At 08:00 mutation stops even if unfinished.
- [ ] Command transcript, event cursor and screenshots are frozen.
- [ ] Agent experience report exists and lists every non-capsule file read.
- [ ] Human interventions, ambiguities and unknown telemetry are recorded truthfully.
- [ ] No source patch or design optimization occurred during the timed round.
