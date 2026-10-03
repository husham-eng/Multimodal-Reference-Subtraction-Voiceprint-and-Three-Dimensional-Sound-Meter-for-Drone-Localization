"""Figures and audio for a mission run."""
from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402

from .dsp import angle_between_deg, stft  # noqa: E402


def save_all(out: Path, rec, clean, rows, center, fs, profile) -> None:
    _trajectory(out / "trajectory_3d.png", rec, rows, center)
    _errors(out / "errors.png", rows, center)
    _spectrograms(out / "spectrograms.png", rec, clean, fs, profile)
    _audio(out, rec, clean, fs)


def _arr(rows, key):
    sel = [r for r in rows if key in r]
    return np.array([r["t"] for r in sel]), np.array([r[key] for r in sel]).reshape(-1, 3)


def _trajectory(path, rec, rows, center):
    fig = plt.figure(figsize=(8, 7))
    ax = fig.add_subplot(projection="3d")
    p = rec.positions[:: rec.fs // 20]
    ax.plot(*p.T, "k-", lw=2, label="true path")
    for key, style, lab in [("raw", "x", "no subtraction"), ("meter", ".", "3D sound meter"),
                            ("neural", "+", "neural localizer")]:
        _, e = _arr(rows, key)
        if len(e):
            ax.plot(*e.T, style, ms=4, alpha=0.6, label=lab)
    _, tr = _arr(rows, "track")
    ax.plot(*tr.T, "r-", lw=1.5, label="Kalman track")
    ax.scatter(*center, c="g", s=80, marker="^", label="station array")
    lim = np.abs(p).max() * 1.1
    ax.set(xlim=(-lim, lim), ylim=(-lim, lim), zlim=(0, p[:, 2].max() * 1.3), xlabel="x [m]", ylabel="y [m]",
           zlabel="z [m]", title="Drone homing: true vs. estimated 3D position")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _errors(path, rows, center):
    fig, axs = plt.subplots(3, 1, figsize=(9, 8), sharex=True)
    for key, lab in [("raw", "no subtraction"), ("meter", "3D sound meter"), ("neural", "neural"),
                     ("track", "Kalman track")]:
        t, e = _arr(rows, key)
        if not len(t):
            continue
        tru = np.array([r["truth"] for r in rows if key in r]) - center
        e = e - center
        axs[0].plot(t, angle_between_deg(e, tru), label=lab)
        axs[1].plot(t, np.linalg.norm(e, axis=1), label=lab)
        axs[2].plot(t, np.linalg.norm(e - tru, axis=1), label=lab)
    t = np.array([r["t"] for r in rows])
    axs[1].plot(t, np.linalg.norm(np.array([r["truth"] for r in rows]) - center, axis=1), "k--", label="true")
    axs[0].set(ylabel="direction error [deg]", yscale="log")
    axs[1].set(ylabel="range [m]")
    axs[2].set(ylabel="position error [m]", yscale="log", xlabel="time [s]")
    for a in axs:
        a.grid(alpha=0.3)
    axs[0].legend(fontsize=8, ncol=4)
    fig.tight_layout()
    fig.savefig(path, dpi=120)
    plt.close(fig)


def _spectrograms(path, rec, clean, fs, profile):
    seg = slice(0, min(rec.mics.shape[1], 12 * fs))
    fig, axs = plt.subplots(3, 1, figsize=(9, 9), sharex=True)
    for ax, x, title in [(axs[0], rec.mics[0, seg], "microphone 1: raw"),
                         (axs[1], clean[0, seg], "after multimodal reference subtraction"),
                         (axs[2], rec.target[0, seg], "drone only (ground truth)")]:
        S = 20 * np.log10(np.abs(stft(x, 2048, 512)) + 1e-9)
        ext = [0, x.size / fs, 0, fs / 2]
        ax.imshow(S, origin="lower", aspect="auto", extent=ext, vmin=S.max() - 70, vmax=S.max(), cmap="magma")
        ax.set(ylim=(0, 3000), ylabel="Hz", title=title)
    for k in range(1, 6):
        axs[2].axhline(k * profile.bpf_hz, color="c", lw=0.5, ls="--")
    axs[2].set_xlabel("time [s]")
    fig.tight_layout()
    fig.savefig(path, dpi=110)
    plt.close(fig)


def _audio(out, rec, clean, fs):
    import soundfile as sf

    for name, x in [("mic1_raw", rec.mics[0]), ("mic1_clean", clean[0]), ("drone_truth", rec.target[0])]:
        sf.write(out / f"{name}.wav", 0.9 * x / np.abs(x).max(), fs)
