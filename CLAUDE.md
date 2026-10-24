# CLAUDE.md

Acoustic drone localization research code (`droneloc`): reference subtraction, rotor voiceprint,
3D sound meter (GCC-PHAT / SRP with rigid-sphere steering), Kalman tracking, and a low-cost
Raspberry Pi Pico + 12 x INMP441 microphone array (`hardware/pico_mic_array/`).

- The user prefers replies in **Arabic** (right-to-left, commands in code blocks).
- Work on branch `claude/epic-ride-9fqd2p`; `main` holds the release cited in the manuscript.
- Run tests with `python -m pytest tests`. Keep the code Python 3.9 compatible and working on
  32-bit systems (the user's Raspberry Pi OS is armhf).
- Do not change the exact estimation path behind the published results; speed-ups for small
  computers go behind options such as `PhaseSRP(fast=True)`, used by the live mode.
