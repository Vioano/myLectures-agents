# TTS Workflow

This route covers full TTS production for myLectures episodes. It does not rely on the original recording for final pacing. Instead, write a production narration script, synthesize the full audio, transcribe that synthesized result, then build the final timeline.

Current conclusion after episode 0001 experiments: use **IndexTTS2 MLX 8-bit with the Zaojian speaker and Takagi emotion audio**. VoxCPM2 produced attractive short anchors, but long generation drifted in timbre, noise, and pacing. The production route now favors IndexTTS2 stability over VoxCPM2 anchor charm.

Current production voice:

- Engine: IndexTTS2 MLX 8-bit.
- Voice/speaker: Zaojian speaker `.npz`.
- Emotion: Takagi reference audio.
- Review voice target: calm, lecture-like, close-mic, steady pacing.

Episode 0001 source example:

- Speaker: `videos/0001-mpm-1-complex_numbers_tts/draft/tts-tests/indextts/long-stability/zaojian_ref/mlx_8bit/speakers/zaojian_20s_indextts2_mlx_8bit_speaker.npz`
- Emotion audio: `/Users/nikolastar/Projects/AI-voice/references/takagi_emotion_ref_31p547_43p456.wav`
- Confirmed full audio: `videos/0001-mpm-1-complex_numbers_tts/exports/audio/mpm-1_tts_indextts2_zaojian_takagi_v4_mochang.wav`
- Confirmed SRT: `videos/0001-mpm-1-complex_numbers_tts/exports/subtitles/mpm-1_tts_indextts2_zaojian_takagi_v4_mochang.srt`

## Narration Script

Write the narration script before audio synthesis. The script is not final subtitles; it is the unit structure for synthesis and later timeline construction.

Before revising or synthesizing the script, run the script-authoring feedback
loop in `12-script-authoring-feedback-loop.md`. Human feedback about wording,
mathematical precision, AI-sounding narration, exposition order, or TTS
pronunciation is production data. It must be converted into tracked feedback
notes, issue JSON, a script-authoring preflight in `experiment-log.md`, and
episode-local lint checks when the failure can be detected mechanically.

For a new episode, initialize:

- `README.md` with source draft, route, voice profile, output names, and next commands.
- `script.md` split into `Sxxx` synthesis/timeline units.
- `tts-speaking-rules.md` with model-specific pronunciation hacks for this topic.
- `formula-manifest.md` so important screen formulas are tracked before audio exists.
- `storyboard.md` with mathematical objects, visual drivers, and anti-fabrication notes.
- `timeline.json` marked as `pre_audio_placeholder`, with no invented production timecodes.
- `experiment-log.md` from the first operation, not after the first render.
- `src/theme.py` and route scripts for full TTS render, normalization, stitching, and transcription.

Use:

- Source script: `MyLectures-vault/mpm-1-复数伸缩与旋转.md`
- Original vocal SRT as optional timing/reference only when the episode has one; pure TTS projects should not require an original recording.
- `script.md`
- `tts-speaking-rules.md`

Each `Sxxx` segment in `script.md` is a synthesis and timeline unit. Read only segment body text for synthesis, not headings.

Do not feed raw LaTeX formulas to TTS when they sound bad. Rewrite formulas into speakable Chinese/math narration according to `tts-speaking-rules.md`. Some formulas should be spoken; some should be shown visually.

Do not synthesize full audio while applicable human-review script issues remain
unconsumed. At minimum, run the local script lint and a TTS plan pass after
script edits, and update `storyboard.md`, `timeline.json`, and
`formula-manifest.md` when segment responsibilities or formula coverage change.

## Current Production Scheme

Use IndexTTS2 per chunk/segment batch, then normalize and stitch mechanically. Do not depend on a long hidden generation state to preserve timbre.

Recommended parameters:

- `engine`: IndexTTS2 MLX 8-bit.
- `voice`: Zaojian speaker `.npz`.
- `emotion_audio`: Takagi reference audio.
- `seed`: `3407`.
- `emo_alpha`: `0.9`.
- `diffusion_steps`: `25`.
- `cfg_rate`: `0.7`.
- `max_text_tokens`: `120`.
- `max_tokens`: `1500`.
- `interval_silence`: `200`.
- `speed`: `1.0`.
- chunking: keep chunks moderate; for episode 0001, 8 script segments / about 700 characters was stable.
- normalization: `I=-16`, `TP=-1.5`, `LRA=11`.

Use raw WAV as the archival model output. Use normalized WAV/MP3 for listening, stitching, preview, ASR, and animation review.

Important engineering rules:

- Run model inference in one main process unless a new engine-specific benchmark proves otherwise.
- Do not spawn multiple full IndexTTS2/MLX workers just because the machine has large memory; model load and Metal contention can erase the gain or destabilize the system.
- Parallelize cheap post-processing instead: ffprobe, loudness analysis, MP3 transcode, preview stitching, and manifest checks.
- Pass absolute output paths to `mlx-indextts` when the wrapper or CLI may run from a different current working directory. Relative output directories caused `soundfile.LibsndfileError` even when inference itself succeeded.
- Before blaming text, speaker files, or model checkpoints, smoke-test MLX/Metal visibility:

```text
/Users/nikolastar/Projects/AI-voice/mlx-indextts/.venv/bin/python -c 'import mlx.core as mx; print(mx.array([1,2,3]))'
```

If this fails with `mlx.core.metal.Device ... index 0 beyond bounds for empty array`, Metal is invisible to the process. Restore full-access/non-sandbox execution and rerun the smoke test before TTS debugging.

## TTS Input Is Not Final Text

The TTS input layer may use deliberate pronunciation spellings. These hacks must not pollute screen formulas, final subtitles, or mathematical prose.

Current rules from episode 0001:

- Greek letters for IndexTTS2: write `alpha`, `beta`, `theta`, `Delta theta` when the Greek glyph or combined glyphs sound wrong.
- `π`: use `pie` if `pi` is not read correctly.
- Trig functions: use `cosine` and `sine` instead of `cos` and `sin`.
- Logs: prefer semantic Chinese phrases such as "自然对数" or "以十为底的对数"; avoid unstable `log x`, `ln x`, or subscript forms in TTS input.
- Multi-pronunciation terms: write `模常` in TTS input when IndexTTS2 reads `模长` as `mo zhang`; final subtitles and screen formulas must be corrected back to `模长`.

Every pronunciation change requires the full repair loop: update `script.md`, regenerate the affected segments, normalize, patch or restitch full audio, update SRT/alignment, and update `timeline.json`. Text edits alone do not change existing audio.

## Historical Candidates

VoxCPM2 Takagi first3 anchor remains a useful historical reference for the desired soft rhythm:

- `draft/tts-tests/voxcpm2/mpm-1_first3_takagi_voxcpm2_10steps.wav`

It should not be treated as the current production route. Stateful continuation and fixed-anchor-per-segment both failed long-form listening QC: later segments could become noisier, faster, or subtly different in timbre.

Previous VoxCPM2 reference-clone candidates with Takagi voice, `cfg=2.0`, and 14 steps had decent single-segment clarity but did not solve segment drift.

8/10/12/14/16 steps were compared. 8 steps was worse than 10. 14 steps can sound good in reference-only mode but does not solve segment drift.

Zaojian VoxCPM2 needs female/style control and is not the current main voice.

## Execution Mode

Run the selected TTS model conservatively until the engine has been benchmarked on the current machine.

For IndexTTS2 MLX 8-bit:

- TTS inference: one main process by default.
- Model load: once per run.
- Generation chunks: moderate length; avoid whole-episode monoliths.
- Normalization, MP3 transcode, ffprobe checks, and preview stitching may run in parallel.
- Listen to replacement previews before accepting a patched full audio.
- If a segment fails, rerun only that segment or a local neighborhood and record seed, text, speaker, emotion, and parameters.

## Output Layout

- `draft/tts-tests/`: short engine, voice, emotion, quantization, and pronunciation tests.
- `draft/tts-renders/<route>/raw/`: raw model-generated segment or chunk audio.
- `draft/tts-renders/<route>/normalized/`: loudness-normalized audio for listening and stitching.
- `draft/tts-renders/<route>/previews/`: replacement and context-window preview sets.
- `draft/tts-renders/<route>/full/`: stitch manifests and mechanical timing manifests.
- `exports/audio/`: confirmed full TTS audio.
- `exports/subtitles/`: SRT/alignment for confirmed audio.

Normalize every segment. Default target: around `-16 LUFS`, true peak near `-1.5 dB`. Adjust globally later for Bilibili and BGM.

## SRT For TTS

TTS audio duration is not known until synthesis completes. Transcribe the synthesized audio to get real timing before timeline production.

Order:

1. Fix `script.md` segment text.
2. Synthesize full audio with the selected IndexTTS2 route.
3. Transcribe full audio to SRT/alignment.
4. Generate first `timeline.json`.
5. If audio is cut, update audio, SRT, and timeline together.
6. After final animation timing, transcribe final rendered audio again and manually correct formula/symbol text.

## Timeline For TTS Route

Timeline cannot reuse original-recording timecodes. It must be based on final TTS audio.

Before audio exists, a `timeline.json` may be initialized as a design placeholder only. It must clearly mark its status, keep `start`/`end` empty or null, and record visual/audio/character/sonification intent without pretending to be a timing contract. After full TTS audio, SRT, and alignment exist, regenerate or recompile the timeline from the real audio.

At minimum, timeline must support:

- `segments`: time range, narration text, script segment id, source script location.
- `visual`: screen objects, Manim scenes, formulas, axes, matrices, arrows, transitions.
- `audio`: TTS segment, anchor parameters, normalized files, sound effects, mix notes.
- `character`: character visibility, expression, position, and occlusion risk.
- `sonification`: mathematical event sound triggers.
- `bgm_suggestions`: exact BGM entry/exit points, energy, and speech avoidance.

## Animation Discipline In TTS Route

Inherit the animation discipline from the voice-conversion route:

- Do not make subtitle-style screens.
- Generate `formula-manifest.md` first.
- Write `storyboard.md` and `timeline.json` before Manim.
- For each shot, identify the mathematical object and display mapping before coding.
- Write `experiment-log.md` after each segment.
- Extract keyframes and inspect occlusion, overlap, formula hierarchy, color semantics, transitions, and whether objects start from correct positions.
- Use shared `src/theme.py`; do not invent per-scene styling.

Before Manim work, read `20-math-object-driven-animation.md`, `30-visual-language-and-style.md`, and production hard requirements.
