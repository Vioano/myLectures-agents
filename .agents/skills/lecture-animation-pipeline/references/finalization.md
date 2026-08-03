# Approved Episode Finalization

Read this file completely when the user says `可以收尾了`, asks for the final
4K episode, requests embedded subtitles or series sprites, or approves the
whole-episode candidate for finishing.

## Authority And Preconditions

`可以收尾了` means:

- the user approves the exact currently presented episode candidate;
- native final rendering, final assembly, subtitle burn-in, the established
  BGM mix, series sprite overlays, final QC, receipts, and a scoped
  source/control commit may proceed without another options questionnaire;
- push, platform upload, destructive cleanup, worktree removal, and deletion
  of prior candidates remain unauthorized.

`可以四K导出整集了` authorizes render, assembly, and QC, but not a commit unless
the same message also says `提交`, `commit`, or `可以收尾了`.

Before rendering, require:

- one durable human-pass outcome for every scene;
- current hash-bound review manifests after the last repair;
- distinct author/reviewer identities and the current hashed human or
  independent-review authority behind every semantic and pronunciation pass;
- a closed supervisor session for parallel production;
- authoritative scene order and approved scene slots;
- exact full audio, reader SRT, word/token alignment, and timeline offsets;
- no open issue whose scope affects final pixels, audio, subtitles, or ending.

Run the episode readiness gate at `post_tts` again if narration, timing,
terminology, or the ending changed after scene approval. Pass its fresh
hash-bound receipt to
`finalize-episode`; a stale narration, alignment, TTS pronunciation input, or
ear-evidence/reviewer hash blocks completion, and the receipt scene set must
exactly equal `progressive_production.json`. Then preflight font availability and glyph
coverage, subtitle renderer, BGM source/recipe, sprite sources, audio channel
layout, the series sprite rhythm, the mandatory spoken-identity Sumino cue,
and all output directories before starting any native 4K render. Episode
wrappers may supply paths and scene-class mappings,
but must call this standard route and must not retain temporary-worktree
absolute paths.

If an old output exists, never select it by filename alone. Freeze absolute
paths and SHA-256 values for the approved review MP4, scene manifests, source
packages, audio, reader SRT, word alignment, timeline, font, sprite assets, and
BGM.

## Native 4K And Timing

Render approved Manim sources at `3840x2160`, 30 fps through `uv run manim`.
Use native scene source packages; do not upscale 720p or 1080p review MP4s and
call the result a 4K master. If native rendering is genuinely impossible, stop
and obtain explicit approval for an `upscaled_delivery_workaround` recorded in
the manifest and experiment log.

The approved review candidate remains the timing and audio authority. Normalize
each native visual to its approved scene slot only by terminal trim or cloned
final-frame padding. Do not speed-change, internally retime, repeat narration,
or move scene boundaries. Concatenate in the sealed scene order and verify all
boundaries again from the assembled episode.

## Publication Subtitles

Use reader SRT for viewers and word/token alignment for anchors. Word-level SRT
is diagnostic evidence, not the burned subtitle product.

Before burn-in:

1. require continuous indices, nonempty cues, monotonic non-overlapping reader
   windows, positive durations, and final-candidate bounds;
2. compare concept-bearing wording against the approved script and timeline;
   normalize adjacent cue text as well as individual cues so a wrong term split
   across a cue boundary cannot evade correction or banned-text checks;
3. restore formal mathematics, names, Greek letters, and terminology instead
   of preserving ASR homophones or TTS pronunciation spellings;
4. reject creator-intent text, Markdown/LaTeX delimiters not meant for viewers,
   and production vocabulary;
5. reflow to at most two centered lines inside the safe width;
6. prove font glyph coverage and reserve the bottom 16 percent;
7. write a proofread audit, burned-overlay hash, and corrected reader SRT
   sidecar.

The upload MP4 carries subtitles as pixels and normally contains no subtitle
stream. Deliver the corrected reader SRT anyway for platform search,
accessibility, and later repair. Extract cue-midpoint frames for high-risk math
terms, repaired cues, and the ending; prove the burned pixels exist and stay in
the subtitle lane.

## Series Audio Mix

Resolve the latest approved series recipe from live episode manifests or
experiment logs; never approximate from chat memory. The current established
Satie source is `assets/bgm/埃里克萨蒂-玄秘曲.mp4`. Unless a later approved
manifest supersedes it, reuse the source and recipe below by default. Only an
explicit user request for a different BGM or different mix configuration may
override this default; silence or a new balance is not an implicit option.

- BGM gain `4.8`;
- compressor `threshold=0.125:ratio=3:attack=20:release=400:makeup=2` when the
  current series precedent includes it;
- voice sidechain `threshold=0.025:ratio=8:attack=80:release=900`;
- final loudness `I=-17.0:TP=-1.5:LRA=11.0`;
- explicit stereo AAC at 48 kHz in the upload MP4.

After any audio repair or remux, verify the final MP4 contains the BGM layer and
measure the final mix. Do not validate only an intermediate WAV.

## Series Characters And Editorial Sprites

Search the repository and Git history for the latest approved sprite action,
size, side, margins, fade, and frame rate. Keep sprites editorial: they may
support pacing but cannot cover subtitles, formulas, axes, active diagrams, or
the last mathematical hold.

The current series precedent is a restrained semantic rhythm, not a decorative
ending sticker. Before final composition, resolve three episode-level roles
from the final word alignment:

- `confused` at a genuine motivating contradiction or unresolved obstacle;
- `aha` when the central organizing relation becomes visible;
- `thinking` at the main transfer, generalization, or consequence.

The character need not always be Sumino. Approved Bocchi, Nijika, Ryo, Kita,
and Sumino actions may be selected by semantic fit. One carefully staged
two-character reaction is allowed when both reactions share the same exact
mathematical word window, occupy disjoint protected regions, and clarify a
collective recognition or comparison. Multiple characters are a series visual
signature, but they remain supporting actors: never place more than twelve
overlay records in a standard episode without a hash-bound human-approved
density override, never stack reactions merely to fill empty space, and never
let a character become the primary focal object while new mathematics is
landing.

Resolve every cue from the current episode's narration and mathematical stage
rather than copying old timestamps. Each manifest row records character,
action, semantic anchor, exact word window, global overlay window, clip and
asset hashes, side, size, protected rectangle, and subtitle-occlusion policy.
For a directional action such as `point_left` or `point_right`, the action name
is not evidence that the rendered character faces the intended target. Record
the asset's intrinsic facing direction, any horizontal mirror, the resulting
screen direction, and a protected target rectangle belonging to the active
mathematical object. The finalization gate must derive the rendered direction
from the asset direction and mirror flag, then reject a target rectangle that
does not lie inward along that direction. Independent QC must inspect exact
on/late frames and reject a gesture that points toward the frame edge or away
from its declared mathematical target.
For each of the three standard semantic roles, either provide a real cue or a
role-specific omission with collision evidence and a reason. A generic
“optional” flag is not an omission contract.

The fixed screen ending remains a learner-facing mathematical conclusion or
question. Separately, when the approved spoken series sign-off contains
`我是结束乐队的键盘手`, exactly one `sumino` overlay is mandatory. Its action is
not fixed to `talking`: choose any nonempty action registered in the bound
Sumino asset metadata that is semantically appropriate for the narration and
passes the same clip/asset, timing, protected-region, and pixel-QC checks.
It must already be visible before the aligned word `我`, remain visible through
`键盘手`, and may continue through `下个视频见`. The spoken sign-off stays in
audio, but the identity and farewell text must not appear in burned subtitles
or any other on-screen text. This mandatory identity carrier cannot be omitted
for layout convenience: move or resize it within a proven safe region while
preserving the final mathematical hold.

## Final Media And Independent QC

The main agent owns assembly and acceptance. A separate reviewer freezes the
candidate MP4, publication SRT, manifest, and relevant audits by SHA-256 before
review. The reviewer reports exact CLI commands and may not grant a pass from
screenshots alone.

Require all of the following:

- exactly one H.264 `3840x2160`, `30/1`, `yuv420p` video stream;
- exactly one AAC stereo 48 kHz audio stream and no subtitle stream for a
  burned-subtitle upload;
- duration drift no greater than `0.12 s` from the sealed assembly duration;
- independently probe decoded video and audio endpoints: both must reach the
  final aligned word, their endpoints must agree within one output frame, and
  decoded video frames must exist on both sides of every promoted scene
  boundary; an audit that reaches decoder EOF before its narration window is
  blocked even when it reports zero findings;
- full `ffmpeg` video/audio decode with no error;
- loudness/true-peak evidence from the final MP4;
- terminal visual hold, no clipped voice, and stereo-channel integrity; when
  BGM is present, validate the tail as BGM-only rather than demanding digital
  silence;
- all scene boundaries plus opening and ending QC frames, extracted from the
  exact final episode bytes rather than standalone scene candidates;
- publication-subtitle structure, formal-text, glyph, line-count, safe-zone,
  and burned-pixel checks;
- every editorial character cue bound to an exact word anchor and semantic
  role, with clip/asset hashes, a protected rectangle, before/on/late frames,
  and no subtitle or mathematical-object collision;
- when the spoken identity line is present, exactly one hash-bound Sumino cue
  using a nonempty, registered, semantically appropriate action and covering
  the complete `我是结束乐队的键盘手` word window,
  plus a positive final-vs-baseline pixel-difference check inside its protected
  rectangle and a zero-difference check immediately before it;
- spoken identity/farewell absent from burned subtitles and screen text while
  remaining present in the diagnostic word alignment and final audio;
- manifest hashes matching every native render contract, normalized segment,
  subtitle overlay/SRT, sprite asset/overlay, mixed audio, BGM, final MP4, and
  QC contact sheet;
- no AppleDouble `._*` files in either the delivery tree or the complete
  episode `review/` evidence tree; the machine report must enumerate both
  scoped roots and contain a failing
  cleanliness assertion rather than relying on a later manual `find`.

Write the final output under `exports/final/`, with a versioned 2160p30/upload
name, corrected reader SRT, finalization manifest, subtitle audit, QC frames,
and contact sheet. Generated media remains ignored by Git.

Before declaring the package durable, run `audit-portability --require-clean`
over current source, scripts, rebuild manifests, and required final assets.
The six core roles are decoded or parsed, not accepted by filename: lecture
text, executable source, WAV scene audio, final MP4, valid SRT cues, and a
manifest binding the final video/subtitle hashes.
Historical manifests may keep old absolute provenance, but one current
repo-relative rebuild receipt must supersede them. Promote any accepted
generated assets that exist only in a temporary producer worktree before that
worktree is eligible for removal.

## Commit And Handoff

After a clean finishing review triggered by `可以收尾了`, stage only approved
episode source/control changes, human/agent feedback, issue closures,
finalization scripts, manifests or receipts intended for tracking, and the
Skill change when it belongs to the task. Do not stage ignored media, caches,
other episodes, or unrelated worktree changes. Commit once with a concise
message; do not push.

The final report gives direct choices, not a process dump:

- upload MP4 absolute path and SHA-256;
- corrected reader SRT absolute path and SHA-256;
- manifest and contact-sheet paths;
- resolution/fps/audio/loudness/decode/subtitle, character-rhythm, and
  mandatory-Sumino-sign-off verdicts;
- whether source/control was committed and the commit hash;
- any remaining upload or push action that still requires authority.
