# Voice Conversion Workflow

This route explores "original oral recording + vocal separation + voice conversion". It is separate from the TTS route in `videos/0001-mpm-1-complex_numbers_tts/`. The goal is to preserve the original lecture's pauses, emphasis, spontaneous adjustments, and timing while replacing the voice color.

## Route Positioning

The core advantage is that timing already exists. The original audio `mpm-1.m4a` contains real pauses, stress, temporary adjustments, and formula-reading rhythm. These are valuable for later animation editing.

Do not immediately rewrite the full narration. First process the original recording into usable production material:

- Original recording: `mpm-1.m4a`
- Separated vocals: `exports/audio/mpm-1_vocals_htdemucs_ft.wav`
- Transcript subtitles: `exports/subtitles/mpm-1_vocals_htdemucs_ft.srt`
- Alignment data: `exports/subtitles/mpm-1_vocals_htdemucs_ft_alignment.json`

`exports/` holds confirmed production intermediates. Trial voices, parameter comparisons, reference cuts, and short listening samples go into `draft/`.

## Original Oral Recording

The original oral recording is not the final subtitle text and may not exactly match the source script. Treat it as the real timing sample for this lesson.

Use these references:

- Source script, for content intent.
- Vocal SRT, for timing.

The source script contains the full intended information. The oral recording is one presentation of it. Some formulas are not read aloud and must be carried by visuals. Some sentences are improvised for natural speaking. Do not treat these differences as errors; separate "spoken information" from "visual information" in timeline design.

## Vocal Separation

First separate and clean vocals from `mpm-1.m4a`. Keep only useful vocals in `exports/audio/`. Do not keep `novocals`, accompaniment, or unused stems in `exports/`.

The separated vocals are used for:

- ASR transcription and timing.
- Voice conversion source audio, preserving original pacing while replacing timbre.

## SRT Transcription

The SRT is primarily a timing artifact, not final subtitle copy. Use it to estimate when each sentence starts and ends.

Editing audio, modifying SRT timecodes, and updating `timeline.json` must be done together. If one changes without the others, the timeline drifts.

After final video timing is settled, transcribe the final rendered audio again. That final SRT corresponds to the final cut and still needs manual correction for formulas, symbols, proper nouns, and mixed Chinese/English speech.

## Voice Conversion

The current direction is SeedVC-style voice conversion: keep the original vocal content and timing, migrate timbre to the target voice.

Existing tests live under:

- `draft/voice-conversion-tests/`
- `draft/voice-conversion-tests/compare-voices/`
- `draft/references/voice_refs/`
- `draft/references/`

The currently valuable sample is:

- `draft/voice-conversion-tests/compare-voices/mpm-1_first3_takagi_seedvc_25steps.wav`

Before converting a whole video, test short segments:

- Whether the timbre matches.
- Whether words are swallowed or smeared.
- Whether mathematical vocabulary and mixed Chinese/English remain stable.
- Whether pauses, emphasis, and speed preserve the original feel.
- Whether long formula-heavy sentences remain stable.

If short samples are stable, expand to 30 seconds, then one minute, then one section.

## Audio Organization

Use this layout:

- `mpm-1.m4a`: original recording in the video root.
- `exports/audio/`: production-worthy audio such as separated vocals and confirmed full converted audio.
- `exports/subtitles/`: SRT and alignment corresponding to production audio.
- `draft/source-clips/`: source clips cut from original audio or vocals.
- `draft/references/`: reference voice material.
- `draft/voice-conversion-tests/`: voice conversion test outputs.

All "listen to this sample" temporary files go into `draft/`. Only files entering the production chain go into `exports/`.

Normalize loudness for full converted audio. Model outputs can vary in loudness; without normalization, loudness shifts may be mistaken for timbre shifts. Prefer normalized audio for listening and editing; keep raw output only for backtracking.

## Timeline For Voice Conversion Route

This route still needs `timeline.json`. SRT only says what was said when; it does not describe visual intent.

At minimum, timeline must bind:

- `segments`: time range, subtitle text, source script location.
- `visual`: Manim scenes, formulas, axes, matrices, arrows, transitions.
- `audio`: original vocals, converted vocals, or replacement clips.
- `character`: character state, expression, and visibility if used.
- `sonification`: mathematical sound triggers and parameters.
- `bgm_suggestions`: exact suggested points, energy, fade, and speech-avoidance notes.

Timeline is not an SRT translation. It is the middle layer joining edit instructions, animation instructions, and audio instructions.

## Suggested Order

1. Test SeedVC parameters on first sentences and formula-heavy sentences.
2. Confirm a stable voice-conversion parameter set.
3. Process a short section, such as 30 seconds to one minute.
4. Normalize the section and re-transcribe SRT.
5. Build a minimal `timeline.json`.
6. Use timeline to drive one Manim segment and verify audio/subtitle/visual timing.
7. If stable, expand; if unstable, compare with the TTS route.
