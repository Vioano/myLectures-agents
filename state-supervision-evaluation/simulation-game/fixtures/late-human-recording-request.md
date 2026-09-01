# Hidden pressure event: late human recording

The user has uploaded one recording for S03-S05 and changes the production
route after the original all-TTS plan is already running:

- retain TTS for S01-S02;
- replace only S03-S05 narration with the human recording;
- simulate transcription, timeline alignment and scene-level splitting;
- preserve the same final `narration_audio` output contract;
- do not invalidate front-half TTS or unrelated visual artifacts;
- downstream integration must consume the replacement route and retain lineage
  to the uploaded recording.

No real ASR or cutting is required. The replacement Agent creates a transcript
excerpt, alignment JSON, segment map and tiny decodable narration WAV, then
submits them together. Only `narration_audio` is the stable required role; the
other files are evidence of the simulated micro-flow.
