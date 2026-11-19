# CLAUDE.md

Acoustic drone localization research code (`droneloc`): reference subtraction, rotor voiceprint,
3D sound meter (GCC-PHAT / SRP with rigid-sphere steering), Kalman tracking, and a low-cost
Raspberry Pi Pico + 12 x INMP441 microphone array (`hardware/pico_mic_array/`).

- The user prefers replies in **Arabic** (right-to-left, commands in code blocks).
- `main` holds the latest version (3.0.0); work on a branch and merge into `main` by pull request.
- Run tests with `python -m pytest tests`. Keep the code Python 3.9 compatible and working on
  32-bit systems (the user's Raspberry Pi OS is armhf).
- The Applied Acoustics submission is closed (rejected, November 2026), so the code is no longer
  frozen for it. Still record any change that alters numerical results in the README, and keep
  unpublished patent drawings out of this public repository (they are in the owner's private Drive).
