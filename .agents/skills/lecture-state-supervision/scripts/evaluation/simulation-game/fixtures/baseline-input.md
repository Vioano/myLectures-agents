# Accelerated simulation input

The original production plan assumes all narration uses IndexTTS. S01-S02 are
the front half and S03-S05 are the back half. Audio and visual work may proceed
independently; only the integration candidate depends on both.

The sample narration contains two pronunciation cases:

- S01-S02: `\pi` and `theta` appear in a short explanation.
- S03-S05: a Fourier decomposition is described with `omega` and `phi`.

This is a process simulation. Produce tiny, explicitly labelled placeholders.
Do not synthesize speech or implement/render a real animation.

For a visual task, create:

1. one Python file containing only a comment or assignment that says which
   Manim scene was simulated;
2. one small JSON timeline with a positive duration and one beat.

For a narration task, create a short TTS text and a decodable tiny WAV whose
contents are explicitly marked as a placeholder.
