# Data and licences

**Nothing in this project needs third-party recordings.** The default pipeline, the live
mode, the tests and the test sounds (`experiments/make_test_sounds.py`) use only

1. the synthetic rotor models in `droneloc/catalog.py` / `droneloc/synth.py` (written for this
   project, MIT like the rest of the code), and
2. recordings you make yourself with the array (yours to use as you wish).

The datasets below are **optional**. They are listed for comparison with the literature and are
never downloaded unless you ask: `python -m droneloc download <key> --accept-license` prints the
licence and refuses without the flag. `python -m droneloc libraries` shows the same summary.

| key | licence (checked 2026-11-19) | commercial / patent / product work |
|---|---|---|
| `svanstrom` | CC0 1.0 (public domain dedication); citation requested | allowed |
| `esc50` | CC BY-NC 3.0 (ESC-10 subset: CC BY 3.0) | **no** (ESC-10 subset only, with attribution) |
| `droneaudio` | Academic research and educational use licence: non-commercial academic use only; military, defence, intelligence and **security** uses prohibited; commercial use needs written permission | **no** |
| `dregon`, `spcup2019`, `salford_dronenoise` | not verified | read the terms on the dataset page first |

Notes

- The `parrot_bebop2` and `parrot_mambo` profiles store only physical numbers (rotor count,
  blade-passing frequency, level) measured from public recordings; no audio from any dataset is
  included in this repository, its releases or its figures' data files.
- For work that may lead to a product or a patent, use the synthetic models, your own
  recordings and, if needed, `svanstrom` (CC0). Keep `droneaudio` and `esc50` out of it.
- Optional experiments that read a dataset (`exp_voiceprint.run_real`, `fig06_real_spectra` in
  `experiments/make_figures.py`) skip themselves when it is not present.
- This table summarises the licence texts; it is not legal advice. Licences can change: the
  dataset's own page is authoritative.
