# TTS Pronunciation Registry

The machine-readable authority is `tts-pronunciation-registry.json`.

This is not a universal phonetic dictionary. IndexTTS behavior depends on the
engine, voice, surrounding sentence, and occurrence. The registry therefore
controls which spellings may enter a pre-TTS candidate; it never grants a human
listening pass for a new occurrence.

`routes.<route_id>.candidate_forms` is the executable allowlist. Candidate
forms are route-scoped: adding a new engine/voice/asset/parameter route grants
it no candidates until its own map is written and reviewed. The token-level
`documented_candidates` field is explanatory history only and is never an
authorization source. Production contracts and the compiler must bind this
one canonical Skill file; alternate per-episode registries are rejected.

Hard rules:

1. Start with the literal Latin or Greek name (`w`, `theta`, `f`) when the
   selected route can plausibly read it.
2. A non-literal spelling must be registered for the exact formal token and
   exact route before preflight. An unregistered form blocks TTS. Leading or
   trailing whitespace, line breaks, controls, and case variants not explicitly
   listed for the route are different forms and block TTS.
3. A form in `forbidden_forms` always blocks preflight. In particular, do not
   substitute Chinese approximations such as `西塔`, `达布留`, or `达布溜` for
   unreviewed English symbol names.
4. Prior evidence may nominate an audition candidate such as `thay-ta`; it does
   not pass a new sentence or occurrence. The final WAV still needs full
   playback and one recorded ear result per occurrence.
5. The pre-TTS receipt must hash-bind every nested TTS input. Editing a TTS
   input after preflight makes the receipt stale and blocks `phase-start` and
   the renderer.
6. Formal narration, subtitles, and screen formulae always keep standard
   mathematical notation.

Episode-level `tts-speaking-rules.md` may narrow the candidate set, but may not
add a spoken form that the canonical registry rejects.
