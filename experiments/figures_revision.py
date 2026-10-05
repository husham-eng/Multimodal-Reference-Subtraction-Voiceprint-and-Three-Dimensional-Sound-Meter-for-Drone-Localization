"""Figures of the revised manuscript (600 dpi PNG + vector PDF).

    python experiments/figures_revision.py static     # model / diagram figures
    python experiments/figures_revision.py results    # figures from outputs/revision/*.json
"""
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
import numpy as np  # noqa: E402
from matplotlib.patches import FancyBboxPatch  # noqa: E402

sys.path.insert(0, ".")
OUT = Path("outputs/revision/figs")
OUT.mkdir(parents=True, exist_ok=True)
plt.rcParams.update({"font.size": 9, "axes.titlesize": 9, "axes.labelsize": 9, "legend.fontsize": 8, "font.family": "DejaVu Sans"})


def save(fig, name):
    fig.savefig(OUT / f"{name}.png", dpi=600, bbox_inches="tight")
    fig.savefig(OUT / f"{name}.pdf", bbox_inches="tight")
    plt.close(fig)
    print("saved", name)


# ----------------------------------------------------------------------------- static figures
def fig_geometry():
    fig = plt.figure(figsize=(7.0, 3.0))
    ax = fig.add_subplot(1, 2, 1, projection="3d")
    u, v = np.mgrid[0:2 * np.pi:40j, 0:np.pi:20j]
    ax.plot_wireframe(np.cos(u) * np.sin(v), np.sin(u) * np.sin(v), np.cos(v), color="0.8", lw=0.4)
    P = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]])
    names = ["+x", "−x", "+y", "−y", "+z", "−z"]
    cols = ["#c0504d", "#c0504d", "#4f81bd", "#4f81bd", "#9bbb59", "#9bbb59"]
    for p, n, c in zip(P, names, cols):
        ax.scatter(*p, s=40, color=c, depthshade=False)
        ax.text(*(1.25 * p), n, ha="center", va="center")
    s = np.array([0.55, 0.45, 0.70]); s = s / np.linalg.norm(s)
    ax.quiver(0, 0, 0, *(1.6 * s), color="k", lw=1.2, arrow_length_ratio=0.12)
    ax.text(*(1.75 * s), "u (source)", fontsize=8)
    ax.set_box_aspect((1, 1, 1)); ax.set_axis_off()
    ax.set_title("(a) sensor geometry (r = 80 mm)", y=0.98)
    ax2 = fig.add_subplot(1, 2, 2)
    th = np.linspace(0, 2 * np.pi, 361)
    from droneloc.sphere import rigid_sphere_response
    for f, ls in [(500, ":"), (2000, "--"), (5000, "-")]:
        H = rigid_sphere_response(np.array([float(f)]), 0.08, np.cos(th))[:, 0]
        ax2.plot(np.degrees(th), 20 * np.log10(np.abs(H)), ls, color="k", label=f"{f/1000:g} kHz")
    ax2.set(xlabel="angle between microphone axis and source (deg)", ylabel="pressure re free field (dB)",
            xlim=(0, 360), title="(b) rigid-sphere gain of one omni microphone")
    ax2.grid(alpha=0.3); ax2.legend(loc="lower center")
    fig.subplots_adjust(wspace=0.35)
    save(fig, "fig01_geometry_directivity")


def fig_sphere_delay():
    from droneloc.sphere import group_delay, rigid_sphere_response
    f = np.linspace(50, 8000, 800)
    H = rigid_sphere_response(f, 0.08, np.array([1.0, -1.0]))
    gd = group_delay(f, H) * 1e3
    fig, ax = plt.subplots(1, 2, figsize=(6.6, 2.5))
    ax[0].plot(f / 1e3, 20 * np.log10(np.abs(H[0])), "k-", label="facing the source")
    ax[0].plot(f / 1e3, 20 * np.log10(np.abs(H[1])), "k--", label="opposite side")
    ax[0].set(xlabel="frequency (kHz)", ylabel="level re free field (dB)", title="(a) magnitude"); ax[0].grid(alpha=0.3); ax[0].legend()
    ax[1].plot(f / 1e3, gd[1] - gd[0], "k-", label="rigid sphere")
    ax[1].axhline(2 * 0.08 / 343 * 1e3, color="k", ls=":", label="free field 2r/c")
    ax[1].axhline(0.08 / 343 * (np.pi / 2 + 1) * 1e3, color="0.5", ls="--", label="Woodworth (r/c)(π/2+1)")
    ax[1].set(xlabel="frequency (kHz)", ylabel="opposite-pair delay (ms)", title="(b) maximum TDOA", ylim=(0.4, 0.75))
    ax[1].grid(alpha=0.3); ax[1].legend()
    fig.tight_layout(); save(fig, "fig03_sphere_delay")


def _boxes(ax, boxes, y=1.0, w=1.55, h=1.2, gap=0.25, x0=0.1):
    xs = []
    for i, (t, c) in enumerate(boxes):
        x = x0 + i * (w + gap)
        ax.add_patch(FancyBboxPatch((x, y), w, h, boxstyle="round,pad=0.02", fc=c, ec="0.3"))
        ax.text(x + w / 2, y + h / 2, t, ha="center", va="center", fontsize=7.5)
        if i:
            ax.annotate("", xy=(x, y + h / 2), xytext=(x - gap, y + h / 2), arrowprops=dict(arrowstyle="->", color="0.2"))
        xs.append(x)
    return xs


def fig_architectures():
    fig, axs = plt.subplots(2, 1, figsize=(7.0, 3.6))
    for ax in axs:
        ax.axis("off"); ax.set_xlim(0, 12.6); ax.set_ylim(0, 2.6)
    _boxes(axs[0], [("6-ch sphere\n48 kHz", "#e8f0fb"), ("rotor silence\nwindow 0.2 s\n(or ego-noise\ncancellation)", "#fbeedd"),
                    ("matched-filter\ndetection\n(chirp 3–6 kHz)", "#efeafb"), ("direction:\nintensity-gated\nSRP (sphere)", "#e3f4ec"),
                    ("range: level\n+ ISO 9613-1\nabsorption", "#e3f4ec"), ("Kalman\ntracker", "#f1efe9"), ("guidance\n(MAVLink)", "#f1efe9")])
    axs[0].set_title("(a) active mode: beacon homing of a supply drone", fontsize=9, loc="left")
    _boxes(axs[1], [("6-ch sphere\n16 kHz", "#e8f0fb"), ("reference\nsubtraction\n(fixed / gated\nadaptive)", "#fbeedd"),
                    ("drone-type\nsignature\n(BPF, harmonics)", "#efeafb"), ("SRP-PHAT with\nharmonic comb,\nsphere steering", "#e3f4ec"),
                    ("range from\ncalibrated\nharmonic level", "#e3f4ec"), ("Kalman\ntracker", "#f1efe9"), ("station\nguidance", "#f1efe9")])
    axs[1].set_title("(b) passive mode: station listening to the arriving drone", fontsize=9, loc="left")
    fig.tight_layout(); save(fig, "fig04_architectures")


def fig_timing():
    from droneloc.exp_active import silence_window_budget
    b = silence_window_budget()
    t = np.linspace(0, 2.0, 2001)
    rpm = np.ones_like(t)
    tb, tl = 1.40 + 0.3, 1.40 + 0.3 + 0.1
    stop = np.clip(1 - (t - tb) / b["t_stop_s"], 0, 1)
    rpm = np.where(t < tb, 1.0, np.where(t < tl + 0.2, stop, np.clip((t - tl - 0.2) / b["t_stop_s"], 0, 1)))
    fig, ax = plt.subplots(2, 1, figsize=(6.6, 2.8), sharex=True, gridspec_kw={"height_ratios": [1, 1.4]})
    for (a, w, c, lab) in [(0, 1.4, "#cfe8d5", "normal flight"), (1.4, 0.3, "#f8d9a8", "pre-climb 0.3 s"),
                           (1.7, 0.1, "#f2b8b5", "braking 0.1 s"), (1.8, 0.2, "#c9c3ee", "listening 0.2 s")]:
        ax[0].axvspan(a, a + w, color=c, label=lab)
    ax[0].set_yticks([]); ax[0].legend(ncol=4, loc="upper center", bbox_to_anchor=(0.5, 1.45), frameon=False)
    ax[1].plot(t, rpm, "k-", label=f"rotor speed (active braking, stop in {1e3*b['t_stop_s']:.0f} ms)")
    ax[1].plot(t, np.clip(rpm, 0, 1) ** 2.5, "k--", label="rotor noise amplitude ∝ ω$^{2.5}$")
    ax[1].set(xlabel="time within the 2 s cycle (s)", ylabel="relative", xlim=(1.2, 2.0)); ax[1].legend(loc="lower left"); ax[1].grid(alpha=0.3)
    fig.tight_layout(); save(fig, "fig05_listening_cycle")


def fig_lobes():
    fig = plt.figure(figsize=(3.4, 3.4))
    ax = fig.add_subplot(projection="3d")
    th, ph = np.mgrid[0:np.pi:50j, 0:2 * np.pi:50j]
    dirs = np.stack([np.sin(th) * np.cos(ph), np.sin(th) * np.sin(ph), np.cos(th)], -1)
    P = np.array([[1, 0, 0], [-1, 0, 0], [0, 1, 0], [0, -1, 0], [0, 0, 1], [0, 0, -1]])
    cols = ["#c0504d", "#e6a19f", "#4f81bd", "#a7c0de", "#6f9a2f", "#bcd696"]
    for p, c in zip(P, cols):
        g = ((1 + dirs @ p) / 2) ** 1.5
        ctr = 0.32 * p
        xyz = ctr[None, None, :] + dirs * (0.85 * g)[..., None]
        ax.plot_surface(*xyz.transpose(2, 0, 1), color=c, alpha=0.35, linewidth=0, shade=True)
    u, v = np.mgrid[0:2 * np.pi:30j, 0:np.pi:15j]
    ax.plot_surface(0.3 * np.cos(u) * np.sin(v), 0.3 * np.sin(u) * np.sin(v), 0.3 * np.cos(v), color="0.45")
    for p, n in zip(P, ["+x", "−x", "+y", "−y", "+z", "−z"]):
        ax.text(*(1.35 * p), n, ha="center", va="center", fontsize=8)
    ax.set_box_aspect((1, 1, 1)); ax.set_axis_off(); ax.view_init(22, 35)
    save(fig, "fig02b_pickup_lobes")


def fig_real_spectra():
    from droneloc.catalog import DRONE_PROFILES
    from droneloc.datasets import find_clips, read_wav
    from droneloc.dsp import welch_psd
    from droneloc.synth import synthesize_drone
    from scipy.signal import butter, sosfiltfilt
    fig, axs = plt.subplots(1, 2, figsize=(6.8, 2.5))
    f = np.fft.rfftfreq(4096, 1 / 16000)
    for ax, (d, lab) in zip(axs, [("parrot_bebop2", "(a) Parrot Bebop"), ("parrot_mambo", "(b) Parrot Mambo")]):
        clips = find_clips("droneaudio", d)
        if not clips:
            continue
        x = np.concatenate([read_wav(p, 16000) for p in clips[:200]])
        x = sosfiltfilt(butter(4, 80 / 8000, "high", output="sos"), x)
        p = welch_psd(x, 4096); p /= p.max()
        s = synthesize_drone(DRONE_PROFILES[d], 8, 16000, np.random.default_rng(0)); ps = welch_psd(s, 4096); ps /= ps.max()
        ax.plot(f / 1e3, 10 * np.log10(p + 1e-12), "k-", lw=0.7, label="real clips (DroneAudioDataset)")
        ax.plot(f / 1e3, 10 * np.log10(ps + 1e-12) - 25, color="0.55", lw=0.7, label="tuned model (−25 dB offset)")
        for k in range(1, 8):
            ax.axvline(k * DRONE_PROFILES[d].bpf_hz / 1e3, color="0.3", lw=0.4, ls=":")
        ax.set(xlim=(0, 4), ylim=(-95, 25), xlabel="frequency (kHz)", ylabel="relative PSD (dB)",
               title=f"{lab}, BPF {DRONE_PROFILES[d].bpf_hz:.0f} Hz"); ax.legend(loc="upper right", ncol=1, fontsize=6.5, framealpha=0.95)
    fig.tight_layout(); save(fig, "fig06_real_spectra")


# ----------------------------------------------------------------------------- result figures
def load(n):
    p = Path("outputs/revision") / f"{n}.json"
    return json.loads(p.read_text()) if p.exists() else None


def fig_active_window():
    m2 = load("m2")
    if not m2:
        return
    W = m2["window"]
    fig, axs = plt.subplots(1, 2, figsize=(6.8, 2.6))
    for (mode, chain, ls, lab) in [("silent", "none", "-", "silence window"), ("running", "none", "--", "motors running"),
                                   ("running", "notch", ":", "running + RPM notch"), ("running", "ref", "-.", "running + reference canceller")]:
        egos = [-30, -20, -10, 0, 10]
        e80 = [W[f"ego{e:+d}/{mode}/{chain}/d80"]["angle_median"]["srp_sphere_gated"] for e in egos]
        pd = [W[f"ego{e:+d}/{mode}/{chain}/d80"]["pd_mf"][0] / W[f"ego{e:+d}/{mode}/{chain}/d80"]["pd_mf"][1] for e in egos]
        axs[0].semilogy(egos, e80, "k" + ls, marker="o", ms=3, label=lab)
        axs[1].plot(egos, pd, "k" + ls, marker="o", ms=3, label=lab)
    axs[0].set(xlabel="ego-noise level re nominal (dB)", ylabel="median direction error (deg)", title="(a) 80 m, intensity-gated SRP")
    axs[1].set(xlabel="ego-noise level re nominal (dB)", ylabel="P$_D$ at P$_{FA}$ = 1 %", title="(b) matched-filter detection, 80 m", ylim=(-0.03, 1.03))
    for a in axs:
        a.grid(alpha=0.3)
    axs[1].legend(loc="lower left")
    fig.tight_layout(); save(fig, "fig08_active_window")


def fig_loop():
    m2 = load("m2")
    if not m2:
        return
    fig, ax = plt.subplots(figsize=(6.8, 2.8))
    labels, vals, lo, hi, cols = [], [], [], [], []
    short = {"silence windows, energy detector, fixed fusion (original)": "silence, energy, fixed fusion (orig.)",
             "motors running, energy detector, fixed fusion (original baseline)": "running, energy, fixed fusion (orig.)",
             "motors running, matched filter, SRP-sphere": "running, MF, SRP",
             "motors running, matched filter + RPM notch, SRP-sphere": "running, MF + notch, SRP",
             "motors running, matched filter + reference canceller, SRP-sphere": "running, MF + ref. canceller, SRP",
             "silence windows, matched filter, SRP-sphere (revised)": "silence, MF, SRP (revised)"}
    for key, col in (("loop", "0.25"), ("loop_coherent", "0.7")):
        for name, r in m2.get(key, {}).items():
            k, n = r["success"]
            labels.append(short.get(name, name) + (" *" if key == "loop_coherent" else ""))
            vals.append(k / n); lo.append(k / n - r["success_ci"][0]); hi.append(r["success_ci"][1] - k / n); cols.append(col)
    y = np.arange(len(labels))
    ax.barh(y, vals, xerr=[lo, hi], color=cols, capsize=2)
    ax.set_yticks(y); ax.set_yticklabels(labels, fontsize=7); ax.invert_yaxis()
    ax.set(xlabel="successful arrivals (fraction of 30 trials, 95% Wilson CI)", xlim=(0, 1.02))
    ax.grid(alpha=0.3, axis="x")
    ax.text(1.0, len(labels) - 0.3, "* coherent point-source rotor model", ha="right", fontsize=7)
    fig.tight_layout(); save(fig, "fig09_closed_loop")


def fig_m4():
    m4 = load("m4")
    if not m4:
        return
    scen = ["baseline", "ref_wind", "moving", "drift"]
    meth = ["fixed/acoustic", "fixed/vibration", "fixed/both", "adaptive/both", "recalibrated/both"]
    fig, ax = plt.subplots(figsize=(6.8, 2.5))
    w = 0.16
    shades = ["0.1", "0.35", "0.55", "0.75", "0.9"]
    for i, m in enumerate(meth):
        vals = [m4[s][m]["success_5deg"][0] / m4[s][m]["success_5deg"][1] for s in scen]
        ax.bar(np.arange(4) + (i - 2) * w, vals, w, color=shades[i], edgecolor="k", lw=0.4, label=m)
    ax.set_xticks(range(4)); ax.set_xticklabels(["stationary", "+20 dB wind on ref. mic", "moving machinery", "3 dB ref. gain drift"])
    ax.set(ylabel="fraction of positions\nwith error < 5°", ylim=(0, 1.05)); ax.grid(alpha=0.3, axis="y")
    ax.legend(ncol=5, fontsize=6.5, loc="upper center", bbox_to_anchor=(0.5, 1.22), frameon=False)
    fig.tight_layout(); save(fig, "fig10_reference_ablation")


if __name__ == "__main__":
    what = sys.argv[1:] or ["static", "results"]
    if "static" in what:
        fig_geometry(); fig_sphere_delay(); fig_architectures(); fig_timing(); fig_lobes(); fig_real_spectra()
    if "results" in what:
        fig_active_window(); fig_loop(); fig_m4()
