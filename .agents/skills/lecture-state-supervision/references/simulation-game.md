# Eight-minute simulation game

This is a bounded, black-box rehearsal of one lecture-production run. It is not
a short unit fixture and it is not the Episode 13 shadow run. Its purpose is to
make the Human UI visibly move while a fresh Agent experiences the public
interface, exact context delivery, review return, a late route change and final
feedback.

The round has a hard wall-clock limit of eight minutes. At 07:30 the game
master stops introducing work and starts freezing evidence. At 08:00 all
mutation stops even if the episode is unfinished. An unfinished but truthful
state is a valid test result.

## Initial truth

Initialization represents the production plan as it existed before any
surprise:

- narration for both the front half (S01-S02) and back half (S03-S05) uses TTS;
- front/back animation work can proceed independently of audio;
- integration consumes the two narration outputs and the two animation outputs;
- no human recording, hybrid route, planned review rejection, worker failure or
  duplicate-work probe exists in state;
- every task is unstarted and the only initially runnable task is the production
  contract.

The hidden pressure script is game-master evidence, not system context. The
black-box Agent must not read it.

## Eight-minute run sheet

| Window | Visible production action | Pressure or assertion | Placeholder work only |
| --- | --- | --- | --- |
| 00:00-00:40 | Open the fresh episode and complete T001 production contract. | Confirm the UI begins from the original all-TTS plan. | One short Markdown contract. |
| 00:40-01:40 | Release T010/T012 audio and T020/T022 animation in parallel. The black-box Agent claims T010; game-master actors advance visual work. | Human UI must show multiple live lanes and independent progress, not a phase barrier. | TTS draft plus a tiny valid WAV; Python source containing one simulation sentence; minimal timeline JSON. |
| 01:40-02:20 | T010 submits its front-half TTS candidate, then immediately claims another available task before review finishes. | Independent review returns `revise` after the Agent has moved on. The current lease must not be interrupted. | Review finding: pronunciation/timing marker is missing for one simulated beat. |
| 02:20-03:20 | The user unexpectedly supplies a recording for S03-S05 and requests TTS for S01-S02 but human speech for S03-S05. | Add the upload at runtime, then route-switch only T012 to the human-recording route. The initial system had no foreknowledge. | A tiny WAV stands for the upload. Replacement work emits a transcript excerpt, alignment JSON, segment map and narration WAV. |
| 03:20-04:15 | The black-box Agent completes the human-recording replacement while the T010 return remains deferred. | Its capsule must contain the new recording instruction and omit obsolete back-half TTS rules. A spare actor attempts duplicate semantic work and must receive a structured denial. | Four tiny placeholder artifacts; no ASR or real cutting. |
| 04:15-05:05 | At the next attention boundary the Agent receives and repairs T010. | The exact review finding must be present once, with a legal repair action; unrelated visual work must remain valid. Retry one command with the same request ID to verify idempotency. | Change one line in the TTS draft/time marker and resubmit. |
| 05:05-06:15 | Finish visual candidates and build T040 integration. | Route lineage must show front TTS + back human recording. Hard artifact checks remain required. | A short playable review MP4 and WAV; no real rendering or edit. |
| 06:15-07:10 | Review the media in the browser. Add one immediate time/position annotation and one episode-draft annotation, then submit the batch. | The annotation time and optional normalized frame position must survive; Human gate remains explicit. | Findings are deliberately simulated and clearly labelled as such. |
| 07:10-07:30 | Resolve the Human gate and expose T900. | A fresh Agent should be able to identify final authority without chat history. | No release or publishing. |
| 07:30-08:00 | Freeze command transcript, events, Human observations and the Agent experience report. | Stop on time. Do not patch the system during the round. | Feedback only. |

The scheduled review wording is intentionally concrete but synthetic:

> 模拟审查了 S01-S02 的 TTS 稿与时间标记，发现“theta”虽然按绑定规则保留英文读法，但 00:02.400-00:03.100 没有对应的分镜时间锚点。请补齐该锚点后重新提交。

The visual-source placeholder is equally bounded. The Agent creates a Python
file containing a single assignment or comment such as “模拟完成 S01-S02 的
Manim 分镜代码”，plus a tiny timeline JSON. Review never claims that this is a
real animation.

## Deliberately omitted

- real TTS synthesis, voice conversion, ASR, forced alignment or audio cutting;
- real Manim authoring, rendering, layout QC, mathematical-quality review or
  beginner-causality review;
- full-resolution 4K media, subtitle burn-in, release-wide loudness checks,
  packaging, publishing, Git merge or final video approval;
- destructive corruption, database edits, network faults, plugin hot update,
  long lease expiry, multi-hour budget behavior or comprehensive failure-state
  traversal;
- optimization or source patches during the timed round.

Those are long-shadow-run or focused regression concerns. The game tests
whether state, attention and projections stay coherent while the story changes.

## Pressure that is included

The round combines five stressors without turning into an exhaustive suite:

1. a late partial route switch from TTS to human recording;
2. an attention-safe review return while the author holds another lease;
3. dynamic insertion of an upload/replacement path that was absent at startup;
4. one duplicate-work attempt and one idempotent retry;
5. exact media annotation plus the explicit Human authority gate.

If time remains, the game master may briefly disconnect/reload the Web page and
verify cursor recovery. No additional production plot is introduced.

## Black-box boundary

The test Agent receives only its generated `MISSION.md`, `environment.json`,
the public operator wrapper/help, task capsules and task-bound references. It
must not read:

- this run sheet or any hidden pressure/oracle file;
- `references/architecture.md`;
- `scripts/runtime/supervision/`, `static/`, `tests/` or SQLite files;
- earlier reports, transcripts or implementation commits.

If stuck, the Agent uses `help`, `next`, `explain`, structured denials and
`observe`; a human hint is counted as an intervention. This is cognitive
blinding enforced by the task contract and transcript audit, not an OS security
sandbox.

At launch, create the evaluator Agent with no inherited conversation turns
(`fork_turns="none"`). Its first message contains only the absolute generated
`MISSION.md` path, the actor ID `blind-operator`, the eight-minute stop rule and
the instruction to use the recorded operator wrapper. Do not paste this README,
the pressure schedule or implementation commentary into that message. Audit its
tool reads before accepting `source_contamination: false`.

## Archify-derived visual acceptance

The Human UI is judged with the following reader-facing disciplines:

- one obvious current main route; side branches leave the nearest relevant node;
- no more than roughly twelve primary nodes in the default release view;
- semantic relationship labels remain available on focus instead of becoming a
  permanent text cloud;
- current-event motion is finite and optional; the static graph still carries
  complete meaning;
- progressive reading depth: overview first, exact task passport on focus, full
  diagnostic graph only by explicit choice;
- minimap/radar mirrors the canonical graph and never becomes separate state;
- node focus has upstream/downstream truth and exact artifact/context passports;
- desktop containment and legibility are checked at 1440x900, 1600x1000,
  1920x1080 and 2048x1320 without solving overflow by shrinking text into
  unreadability.

The practical five-second test is whether the observer can answer: what changed,
who is working, what is blocked, what was invalidated, and what releases next.
