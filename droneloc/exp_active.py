"""Active mode (beacon homing) experiments (M2, M3, M7).

One listening window of 0.2 s at 48 kHz is synthesised at the six-microphone
sphere carried by the supply drone:

* beacon: linear chirp 3-6 kHz, 50 ms, repeated; source level ``beacon_spl``
  at 1 m, spherical spreading and ISO 9613-1 atmospheric absorption;
* the target drone's own rotor noise from the same direction;
* the listener's four rotors (near field, below the mast) with either full
  RPM ("running") or a braked spin-down ("silent"); rotor noise amplitude
  scales with (omega/omega0)^2.5;
* self-motion wind, sensor noise, rigid-sphere scattering and cardioid
  capsules, 0.5 dB sensitivity mismatch;
* four reference microphones, one 5 cm below each rotor.

Processing chains: band-energy detector (original) or matched filter;
ego-noise suppression by known-RPM harmonic notching or by a multichannel
Wiener reference canceller; direction by six-pair intensity, opposite-pair
GCC-PHAT, their fixed (0.4/0.6) or inverse-variance fusion, SRP-PHAT with
free-field or rigid-sphere steering, and intensity-gated SRP.
"""
from __future__ import annotations

import dataclasses
import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .catalog import DRONE_PROFILES
from .dsp import SPEED_OF_SOUND, angle_between_deg, db_to_pa, fibonacci_sphere, istft, stft
from .localization import GccPhat, PhaseSRP
from .reference_subtraction import ReferenceCanceller
from .simulation import octahedral_array
from .sphere import rigid_sphere_response
from .stats import bootstrap_ci, wilson
from .synth import synthesize_drone, wind_noise

FS = 48000
BAND = (3000.0, 6000.0)
G0 = 9.81


def iso9613_alpha(f, T_c: float = 20.0, rh: float = 50.0, pa: float = 101.325) -> np.ndarray:
    """Atmospheric absorption coefficient [dB/m], ISO 9613-1."""
    f = np.asarray(f, float)
    T, T0, T01, pr = T_c + 273.15, 293.15, 273.16, 101.325
    C = -6.8346 * (T01 / T) ** 1.261 + 4.6151
    h = rh * 10 ** C * (pr / pa)
    frO = (pa / pr) * (24 + 4.04e4 * h * (0.02 + h) / (0.391 + h))
    frN = (pa / pr) * (T / T0) ** -0.5 * (9 + 280 * h * np.exp(-4.170 * ((T / T0) ** (-1 / 3) - 1)))
    return 8.686 * f ** 2 * (1.84e-11 * (pr / pa) * (T / T0) ** 0.5 + (T / T0) ** -2.5 * (
        0.01275 * np.exp(-2239.1 / T) / (frO + f ** 2 / frO) + 0.1068 * np.exp(-3352.0 / T) / (frN + f ** 2 / frN)))


@dataclass
class ActiveConfig:
    beacon_spl: float = 100.0          # dB SPL at 1 m (design value of the acoustic beacon)
    chirp_s: float = 0.05
    window_s: float = 0.2
    target: str = "dji_phantom4"       # the monitoring drone (its own rotor noise is included)
    listener_level: float = 84.0       # supply drone, dB SPL at 1 m with all rotors running
    listener_rpm: float = 4500.0
    listener_blades: int = 2
    rotor_xy: float = 0.23             # rotor positions (+-x, +-y) relative to the sphere [m]
    rotor_z: float = -0.30             # sphere on a 0.30 m mast above the rotor plane
    ego_gain_db: float = 0.0           # sweep parameter: ego-noise level relative to nominal
    brake_time: float = 0.08           # time for active braking to stop a rotor [s]
    listen_delay: float = 0.10         # listening starts this long after the brake command [s]
    alpha: float = 1.0                 # capsule directivity (1 cardioid, 0 omni)
    scattering: bool = True
    gain_err_db: float = 0.5
    sensor_db: float = 20.0
    ambient_wind_ms: float = 3.0
    rotor_subsources: int = 6          # broadband rotor noise radiated by independent points on the disc
    rotor_ring_m: float = 0.15         # radius of those points (~0.8 x blade tip radius)


class Listener:
    """Fixed geometry, responses and templates for one configuration."""

    def __init__(self, cfg: ActiveConfig, seed: int = 0):
        self.cfg = cfg
        self.arr = octahedral_array(0.08, center=(0, 0, 0))
        self.normals = self.arr.positions / 0.08
        self.n = int(cfg.window_s * FS)
        self.freqs = np.fft.rfftfreq(self.n, 1 / FS)
        self.cos_grid = np.linspace(-1, 1, 721)
        self.table = rigid_sphere_response(self.freqs, 0.08, self.cos_grid) if cfg.scattering else None
        self.alpha_db = iso9613_alpha(self.freqs)
        self.gains = 10 ** (np.random.default_rng(seed).normal(0, cfg.gain_err_db, 6) / 20)
        r = cfg.rotor_xy
        self.rotors = np.array([[r, r, cfg.rotor_z], [-r, r, cfg.rotor_z], [-r, -r, cfg.rotor_z], [r, -r, cfg.rotor_z]])
        self.refs = self.rotors + np.array([0, 0, -0.05])
        nc = int(cfg.chirp_s * FS)
        t = np.arange(nc) / FS
        k = (BAND[1] - BAND[0]) / cfg.chirp_s
        self.chirp = np.sin(2 * np.pi * (BAND[0] * t + 0.5 * k * t ** 2)) * np.hanning(nc) ** 0.25
        base = DRONE_PROFILES["hexa_swap"]
        # rotor RPM is set per window (and reported as ESC telemetry), so no internal jitter
        self.rotor_profile = dataclasses.replace(base, key="listener_rotor", n_rotors=1, hover_rpm=cfg.listener_rpm,
                                                 n_blades=cfg.listener_blades, rpm_jitter=0.0,
                                                 level_1m_db=cfg.listener_level - 10 * np.log10(4))
        self.rotor_offset = float(self.rotor_profile.timbre().rotor_offsets[0])
        self.gcc = GccPhat(self.arr, FS, n_fft=1024, hop=256, interp=16)
        self.srp_free = PhaseSRP(self.gcc, "free", n_dirs=3000, min_elevation_deg=-90, fmin=BAND[0], fmax=BAND[1])
        self.srp_sph = PhaseSRP(self.gcc, "sphere", n_dirs=3000, min_elevation_deg=-90, fmin=BAND[0], fmax=BAND[1])
        self.p_ref_1m = None

    # ---------------------------------------------------------------- synthesis
    def _response(self, u: np.ndarray, dist: float, absorb: bool) -> np.ndarray:
        """(6, F) transfer from a source in unit direction u at distance dist."""
        cos = self.normals @ u
        if self.table is not None:
            x = (cos + 1) / 2 * 720
            i0 = np.minimum(np.floor(x).astype(int), 719)
            w = (x - i0)[:, None]
            H = self.table[i0] * (1 - w) + self.table[i0 + 1] * w
        else:
            H = np.exp(2j * np.pi * self.freqs[None, :] * (self.arr.positions @ u)[:, None] / SPEED_OF_SOUND)
        g = (1 - self.cfg.alpha) + self.cfg.alpha * (1 + cos) / 2
        H = H * (g * self.gains)[:, None] / max(dist, 0.05)
        if absorb:
            H = H * 10 ** (-self.alpha_db * dist / 20)[None, :]
        return H

    def _to_mics(self, sig: np.ndarray, u, dist, absorb=True) -> np.ndarray:
        return np.fft.irfft(np.fft.rfft(sig)[None, :] * self._response(u, dist, absorb), self.n, axis=1)

    def beacon(self, rng) -> np.ndarray:
        reps = int(np.ceil(self.n / self.chirp.size)) + 1
        x = np.tile(self.chirp, reps)
        s = rng.integers(0, self.chirp.size)
        x = x[s:s + self.n]
        return x / np.sqrt(np.mean(x ** 2)) * db_to_pa(self.cfg.beacon_spl)

    def rotor_signals(self, mode: str, rng) -> tuple[list[np.ndarray], np.ndarray]:
        """Signals of the four rotors and their RPM in this window (ESC telemetry)."""
        cfg = self.cfg
        t = np.arange(self.n) / FS
        out, rpms = [], []
        for _ in range(4):
            delta = rng.normal(0, 0.03)                 # rotor-to-rotor thrust differences
            rpms.append(cfg.listener_rpm * (1 + self.rotor_offset) * (1 + delta))
            if mode == "running":
                thr = np.full(self.n, 1 + delta)
            else:
                thr = (1 + delta) * np.clip(1 - (t + cfg.listen_delay) / cfg.brake_time, 0, 1)
            if not np.any(thr > 0):
                out.append(np.zeros(self.n)); continue
            s = synthesize_drone(self.rotor_profile, cfg.window_s, FS, rng, np.maximum(thr, 1e-3))
            out.append(s * (thr / (1 + delta)) ** 2.5 * 10 ** (cfg.ego_gain_db / 20))
        return out, np.array(rpms)

    def _rotor_parts(self, s: np.ndarray, rng) -> list[tuple[np.ndarray, np.ndarray]]:
        """Split one rotor's sound into a tonal part at the hub and independent
        broadband parts on a ring (distributed, partly incoherent source)."""
        K = self.cfg.rotor_subsources
        if K <= 1:
            return [(s, np.zeros(3))]
        S = np.fft.rfft(s)
        f_shaft = self.cfg.listener_rpm / 60
        tonal_mask = (np.abs(self.freqs / f_shaft - np.round(self.freqs / f_shaft)) * f_shaft) < 6.0
        tonal = np.fft.irfft(S * tonal_mask, self.n)
        broad_psd = np.abs(S * ~tonal_mask) ** 2
        parts = [(tonal, np.zeros(3))]
        for k in range(K):
            ph = np.exp(2j * np.pi * rng.random(S.size))
            b = np.fft.irfft(np.sqrt(broad_psd / K) * ph, self.n)
            a = 2 * np.pi * k / K
            parts.append((b, self.cfg.rotor_ring_m * np.array([np.cos(a), np.sin(a), 0.0])))
        return parts

    def render(self, u_target, dist, mode, speed, rng, beacon_on=True):
        """Return mics (6,n), refs (4,n), rotor RPMs (4,) and per-component signals."""
        mics = np.zeros((6, self.n))
        comp = {}
        if beacon_on:
            comp["beacon"] = self._to_mics(self.beacon(rng), u_target, dist)
            mics += comp["beacon"]
        tgt = synthesize_drone(DRONE_PROFILES[self.cfg.target], self.cfg.window_s, FS, rng)
        mics += self._to_mics(tgt, u_target, dist)
        rot, comp["rpm"] = self.rotor_signals(mode, rng)
        refs = np.zeros((4, self.n))
        for i, s in enumerate(rot):
            if not np.any(s):
                continue
            for part, off in self._rotor_parts(s, rng):
                v = self.rotors[i] + off
                mics += self._to_mics(part, v / np.linalg.norm(v), np.linalg.norm(v), absorb=False)
                for k in range(4):
                    dk = max(np.linalg.norm(self.refs[k] - v), 0.03)
                    sh = int(round(dk / SPEED_OF_SOUND * FS))
                    refs[k] += np.roll(part, sh) / dk
        v_air = max(speed, self.cfg.ambient_wind_ms)
        wind_db = 40 + 40 * np.log10(v_air / 3.0)
        for m in range(6):
            mics[m] += wind_noise(self.n, FS, rng, wind_db) + db_to_pa(self.cfg.sensor_db) * rng.standard_normal(self.n)
        for k in range(4):
            refs[k] += db_to_pa(self.cfg.sensor_db) * rng.standard_normal(self.n)
        return mics, refs, comp

    # ---------------------------------------------------------------- processing
    def band_energy(self, x: np.ndarray, lo, hi) -> np.ndarray:
        X = np.fft.rfft(x, axis=-1)
        m = (self.freqs >= lo) & (self.freqs <= hi)
        return np.sum(np.abs(X[..., m]) ** 2, axis=-1)

    def energy_detect(self, mics) -> tuple[bool, float]:
        s = np.sum(self.band_energy(mics, *BAND)) / (BAND[1] - BAND[0])
        n = np.sum(self.band_energy(mics, 7000, 10000)) / 3000
        snr = 10 * np.log10(s / max(n, 1e-30))
        return snr > 6.0, snr

    def mf_stat(self, mics) -> float:
        """Matched-filter statistic: peak/median of the channel-summed MF envelope."""
        reps = int(np.ceil(self.n / self.chirp.size))
        tpl = np.tile(self.chirp, reps)[: self.n]
        T = np.conj(np.fft.rfft(tpl))
        X = np.fft.rfft(mics, axis=1)
        y = np.fft.irfft(X * T[None, :], self.n, axis=1)
        env = np.sum(y[:, : self.chirp.size] ** 2, axis=0)
        return float(env.max() / (np.median(env) + 1e-30))

    def notch(self, mics, rpms) -> np.ndarray:
        """Remove the listener's own rotor harmonics using the per-rotor RPM from ESC telemetry.

        All rotor components (blade-passing, shaft and motor-whine harmonics) lie
        at multiples of the shaft rate, so every multiple is notched (+-1 bin,
        5 Hz resolution) on a full-window FFT."""
        X = np.fft.rfft(mics, axis=1)
        mask = np.ones(self.freqs.size)
        for r in np.atleast_1d(rpms):
            f_shaft = r / 60
            k = np.arange(1, int(self.freqs[-1] / f_shaft) + 1)
            idx = np.searchsorted(self.freqs, k * f_shaft)
            for d in (-1, 0, 1):
                mask[np.clip(idx + d, 0, mask.size - 1)] = 0.0
        return np.fft.irfft(X * mask[None, :], self.n, axis=1)

    def intensity(self, mics) -> np.ndarray:
        E = self.band_energy(mics, *BAND)
        v = np.array([E[0] - E[1], E[2] - E[3], E[4] - E[5]])
        return v / (np.linalg.norm(v) + 1e-30)

    def top3(self, mics) -> np.ndarray:
        E = self.band_energy(mics, *BAND)
        k = np.argsort(E)[-3:]
        v = (E[k, None] * self.normals[k]).sum(0)
        return v / np.linalg.norm(v)

    def gcc_pairs(self, mics) -> np.ndarray:
        """Opposite-pair GCC-PHAT with the free-field formula s = -c dtau / (2r) (original Eq. 5)."""
        X = np.fft.rfft(mics, axis=1)
        m = (self.freqs >= BAND[0]) & (self.freqs <= BAND[1])
        s = np.zeros(3)
        N = self.n * 16
        lag = int(np.ceil(0.2 / SPEED_OF_SOUND * FS * 16)) + 4
        for ax, (i, j) in enumerate([(0, 1), (2, 3), (4, 5)]):
            G = X[i] * np.conj(X[j]); G = np.where(m, G / (np.abs(G) + 1e-30), 0)
            cc = np.fft.irfft(G, N)
            w = np.concatenate([cc[-lag:], cc[: lag + 1]])
            tau = (np.argmax(w) - lag) / (FS * 16)
            s[ax] = -SPEED_OF_SOUND * tau / (2 * 0.08)
        return s / (np.linalg.norm(s) + 1e-30)

    def srp(self, mics, model="sphere", prior=None, prior_deg=40.0) -> np.ndarray:
        G = self.gcc.cross_spectra(mics, None, band=BAND)
        srp = self.srp_sph if model == "sphere" else self.srp_free
        return srp.locate(G, prior=prior, prior_deg=prior_deg)[0]

    def calibrate_range(self, rng) -> None:
        """Total in-band beacon energy at 1 m, measured as with the real sensor (several directions)."""
        P = []
        for u in fibonacci_sphere(12):
            P.append(np.sum(self.band_energy(self._to_mics(self.beacon(rng), u, 1.0, absorb=False), *BAND)))
        self.p_ref_1m = float(np.mean(P))

    def range_est(self, mics, absorb_corr: bool = True) -> float:
        P = np.sum(self.band_energy(mics, *BAND))
        d = float(np.sqrt(self.p_ref_1m / max(P, 1e-30)))
        if absorb_corr:   # solve P = P1 / d^2 * 10^(-a d / 10) with the band-average absorption
            a = float(np.mean(iso9613_alpha(np.linspace(*BAND, 16))))
            for _ in range(20):
                d = float(np.sqrt(self.p_ref_1m / max(P, 1e-30) * 10 ** (-a * d / 10)))
        return d


def fuse(u_i, u_t, w_i=0.4, w_t=0.6):
    v = w_i * u_i + w_t * u_t
    return v / (np.linalg.norm(v) + 1e-30)


def random_dir(rng, el_lo=-40, el_hi=40):
    az = rng.uniform(-np.pi, np.pi); el = np.radians(rng.uniform(el_lo, el_hi))
    return np.array([np.cos(el) * np.cos(az), np.cos(el) * np.sin(az), np.sin(el)])


# ============================================================================ window-level study
ESTIMATORS = ["intensity", "top3", "gcc_pairs", "fixed_fusion", "ivw_fusion", "srp_free", "srp_sphere", "srp_sphere_gated"]


def process(L: Listener, mics, refs, chain: str, canc=None, rpm=None):
    if chain == "notch":
        mics = L.notch(mics, rpm)
    elif chain == "ref":
        mics = canc.transform(mics, refs)
    return mics


def estimate_all(L: Listener, mics, sig_tab=None) -> dict:
    ui, ut = L.intensity(mics), L.gcc_pairs(mics)
    est = {"intensity": ui, "top3": L.top3(mics), "gcc_pairs": ut, "fixed_fusion": fuse(ui, ut),
           "srp_free": L.srp(mics, "free"), "srp_sphere": L.srp(mics, "sphere"),
           "srp_sphere_gated": L.srp(mics, "sphere", prior=ui, prior_deg=40.0)}
    if sig_tab is not None:  # inverse-variance fusion with error models calibrated offline
        snr = 10 * np.log10(max(L.mf_stat(mics), 1e-12))
        si, st = sig_tab(snr)
        est["ivw_fusion"] = fuse(ui, ut, 1 / si ** 2, 1 / st ** 2)
    return est


def calibrate_sigmas(L: Listener, rng, n: int = 160):
    """Fit per-method angular error vs matched-filter SNR (for inverse-variance fusion)."""
    rows = []
    for _ in range(n):
        u = random_dir(rng); d = 10 ** rng.uniform(np.log10(10), np.log10(150))
        mics, _, _ = L.render(u, d, "silent", 0.5, rng)
        snr = 10 * np.log10(L.mf_stat(mics))
        rows.append((snr, angle_between_deg(L.intensity(mics), u), angle_between_deg(L.gcc_pairs(mics), u)))
    rows = np.array(rows)
    edges = np.percentile(rows[:, 0], np.linspace(0, 100, 7))
    centres, si, st = [], [], []
    for a, b in zip(edges[:-1], edges[1:]):
        sel = (rows[:, 0] >= a) & (rows[:, 0] <= b)
        centres.append((a + b) / 2)
        si.append(max(np.sqrt(np.mean(rows[sel, 1] ** 2)), 0.05)); st.append(max(np.sqrt(np.mean(rows[sel, 2] ** 2)), 0.05))
    centres = np.array(centres)
    return lambda s: (float(np.interp(s, centres, si)), float(np.interp(s, centres, st)))


def window_study(n_win: int = 40, seed: int = 0, egos=(-30, -20, -10, 0, 10), save: Path | None = None) -> dict:
    """Detection (Pfa = 1%) and direction error vs ego-noise level, distance and processing chain."""
    res = {}
    L0 = Listener(ActiveConfig(), seed)
    rng = np.random.default_rng(seed)
    L0.calibrate_range(rng)
    sig_tab = calibrate_sigmas(L0, rng)
    conds = [("silent", "none"), ("running", "none"), ("running", "notch"), ("running", "ref")]
    for ego in egos:
        cfg = ActiveConfig(ego_gain_db=ego)
        L = Listener(cfg, seed); L.p_ref_1m = L0.p_ref_1m
        # reference canceller trained in flight on a beacon-free window (rotors running)
        m0, r0, _ = L.render(random_dir(rng), 300.0, "running", 8.0, rng, beacon_on=False)
        m1, r1, _ = L.render(random_dir(rng), 300.0, "running", 8.0, rng, beacon_on=False)
        canc = ReferenceCanceller(1024, 256).fit(np.hstack([m0, m1]), np.hstack([r0, r1]))
        for mode, chain in conds:
            speed = 8.0 if mode == "running" else 0.5
            # matched-filter threshold for Pfa = 1% from beacon-free windows
            null = []
            for _ in range(100):
                mics, refs, c = L.render(random_dir(rng), 1e4, mode, speed, rng, beacon_on=False)
                null.append(L.mf_stat(process(L, mics, refs, chain, canc, c["rpm"])))
            thr = float(np.percentile(null, 99))
            for d in (20, 40, 80, 120):
                det_mf = det_en = 0
                errs = {k: [] for k in ESTIMATORS}
                rerr = []
                for _ in range(n_win):
                    u = random_dir(rng)
                    mics, refs, c = L.render(u, d, mode, speed, rng)
                    x = process(L, mics, refs, chain, canc, c["rpm"])
                    det_mf += L.mf_stat(x) > thr
                    det_en += L.energy_detect(mics)[0]
                    for k, v in estimate_all(L, x, sig_tab).items():
                        errs[k].append(float(angle_between_deg(v, u)))
                    rerr.append(abs(L.range_est(x) / d - 1))
                key = f"ego{ego:+d}/{mode}/{chain}/d{d}"
                res[key] = {"pd_mf": [int(det_mf), n_win], "pd_energy": [int(det_en), n_win], "mf_threshold": thr,
                            "angle_median": {k: float(np.median(v)) for k, v in errs.items()},
                            "outlier_10deg": {k: float(np.mean(np.array(v) > 10)) for k, v in errs.items()},
                            "range_err_median": float(np.median(rerr))}
                r = res[key]
                print(f"  M2 {key:32s} Pd(MF) {det_mf:2d}/{n_win} Pd(energy) {det_en:2d}/{n_win} | "
                      f"gcc {r['angle_median']['gcc_pairs']:6.2f} fixed {r['angle_median']['fixed_fusion']:6.2f} "
                      f"ivw {r['angle_median']['ivw_fusion']:6.2f} int {r['angle_median']['intensity']:6.2f} "
                      f"top3 {r['angle_median']['top3']:6.2f} srpF {r['angle_median']['srp_free']:6.2f} "
                      f"srpS {r['angle_median']['srp_sphere']:6.2f} gated {r['angle_median']['srp_sphere_gated']:6.2f} "
                      f"(out>10: srpS {100*r['outlier_10deg']['srp_sphere']:3.0f}% gated {100*r['outlier_10deg']['srp_sphere_gated']:3.0f}%) "
                      f"range {100*r['range_err_median']:4.1f}%", flush=True)
                if save:
                    save.write_text(json.dumps(res, indent=1, default=float))
    return res


# ============================================================================ closed loop
@dataclass
class Policy:
    name: str
    mode: str            # "silent" (silence windows every 2 s) or "running" (listen every 0.5 s, motors on)
    detector: str        # "energy" or "mf"
    chain: str           # "none", "notch", "ref"
    doa: str             # "fixed_fusion", "srp_sphere_gated", ...


POLICIES = [
    Policy("silence windows, energy detector, fixed fusion (original)", "silent", "energy", "none", "fixed_fusion"),
    Policy("motors running, energy detector, fixed fusion (original baseline)", "running", "energy", "none", "fixed_fusion"),
    Policy("motors running, matched filter, SRP-sphere", "running", "mf", "none", "srp_sphere"),
    Policy("motors running, matched filter + RPM notch, SRP-sphere", "running", "mf", "notch", "srp_sphere"),
    Policy("motors running, matched filter + reference canceller, SRP-sphere", "running", "mf", "ref", "srp_sphere"),
    Policy("silence windows, matched filter, SRP-sphere (revised)", "silent", "mf", "none", "srp_sphere"),
]


def closed_loop(policy: Policy, trial: int, L: Listener, thr: float, canc, sig_tab, max_t=60.0) -> dict:
    from .tracking import Kalman3D
    rng = np.random.default_rng(10_000 + trial)
    az = rng.uniform(-np.pi, np.pi)
    target0 = np.array([80 * np.cos(az), 80 * np.sin(az), rng.uniform(-10, 10)])
    drift = rng.normal(0, 0.2, 3); drift[2] = 0
    p = np.zeros(3); v = np.zeros(3)
    period = 2.0 if policy.mode == "silent" else 0.5
    kf = Kalman3D(period, accel_std=0.5, sigma_angle_deg=6.0, sigma_log_range=0.13, gate=16.27)
    misses = 0; t = 0.0; terminal_t = 0.0; dt = 0.05
    def target(t):
        return target0 + drift * t + 4 * np.array([np.cos(0.2 * t), np.sin(0.2 * t), 0])
    errs = []
    while t < max_t:
        # ---- listen
        tg = target(t); rel = tg - p; d = np.linalg.norm(rel); u = rel / d
        speed = np.linalg.norm(v) if policy.mode == "running" else 0.5
        mics, refs, c = L.render(u, d, policy.mode, speed, rng)
        x = process(L, mics, refs, policy.chain, canc, c["rpm"])
        det = L.energy_detect(mics)[0] if policy.detector == "energy" else (L.mf_stat(x) > thr)
        kf.predict()
        if det:
            est = estimate_all(L, x, sig_tab)[policy.doa]
            errs.append(float(angle_between_deg(est, u)))
            z = p + est * L.range_est(x)
            if not kf.update(z, p):
                misses += 1
                if misses >= 3:
                    kf.x = None; kf.update(z, p); misses = 0
            else:
                misses = 0
        # ---- guide for one period
        for _ in range(int(round(period / dt))):
            if kf.position is not None:
                rel_e = kf.position - p; d_e = np.linalg.norm(rel_e)
                vt = kf.x[3:].copy(); vt = vt / max(1, np.linalg.norm(vt) / 3.0)
                cmd = np.clip(0.8 * (d_e - 2.0), 0, 8.0) * rel_e / max(d_e, 1e-6) + vt
                terminal = d_e < 2.5
            else:
                cmd = np.array([0, 0, 0.5]); terminal = False   # search: hover and climb slowly
            dv = cmd - v
            v = v + dv * min(1.0, 4.0 * dt / max(np.linalg.norm(dv), 1e-9))
            p = p + v * dt; t += dt
            terminal_t = terminal_t + dt if terminal else 0.0
            if terminal_t >= 3.0:
                true_d = np.linalg.norm(target(t) - p)
                return {"success": bool(1 <= true_d <= 4), "false_arrival": bool(not 1 <= true_d <= 4), "time": t,
                        "final_dist": float(true_d), "median_err": float(np.median(errs)) if errs else float("nan")}
    return {"success": False, "false_arrival": False, "time": max_t, "final_dist": float(np.linalg.norm(target(t) - p)),
            "median_err": float(np.median(errs)) if errs else float("nan")}


def loop_study(n_trials: int = 30, seed: int = 0, rotor_subsources: int = 6, policies=None) -> dict:
    cfg = ActiveConfig(rotor_subsources=rotor_subsources)
    L = Listener(cfg, seed)
    rng = np.random.default_rng(seed + 1)
    L.calibrate_range(rng)
    sig_tab = calibrate_sigmas(L, rng)
    m0, r0, _ = L.render(random_dir(rng), 300.0, "running", 8.0, rng, beacon_on=False)
    m1, r1, _ = L.render(random_dir(rng), 300.0, "running", 8.0, rng, beacon_on=False)
    canc = ReferenceCanceller(1024, 256).fit(np.hstack([m0, m1]), np.hstack([r0, r1]))
    res = {}
    for pol in (policies or POLICIES):
        null = []
        for _ in range(100):
            mics, refs, c = L.render(random_dir(rng), 1e4, pol.mode, 8.0 if pol.mode == "running" else 0.5, rng, beacon_on=False)
            null.append(L.mf_stat(process(L, mics, refs, pol.chain, canc, c["rpm"])))
        thr = float(np.percentile(null, 99))
        trials = [closed_loop(pol, k, L, thr, canc, sig_tab) for k in range(n_trials)]
        ns = sum(t["success"] for t in trials); nf = sum(t["false_arrival"] for t in trials)
        times = [t["time"] for t in trials if t["success"]]
        res[pol.name] = {"success": [ns, n_trials], "success_ci": wilson(ns, n_trials), "false_arrivals": nf,
                         "mean_time": float(np.mean(times)) if times else float("nan"),
                         "median_dir_err": float(np.nanmedian([t["median_err"] for t in trials])), "trials": trials}
        print(f"  M2-loop {pol.name:70s} success {ns:2d}/{n_trials} CI [{res[pol.name]['success_ci'][0]:.2f}, "
              f"{res[pol.name]['success_ci'][1]:.2f}] false {nf:2d} time {res[pol.name]['mean_time']:5.1f} s "
              f"dir err {res[pol.name]['median_dir_err']:6.2f}", flush=True)
    return res


# ============================================================================ silence-window cost (M7)
def silence_window_budget(mass=3.0, n_rot=4, prop_d_in=15.0, rpm=4500.0, rotor_inertia=1.5e-4,
                          brake_torque=0.9, fm=0.6, eta_motor=0.8, pre_climb=1.5, cycle=2.0,
                          listen=0.2, brake=0.1) -> dict:
    """First-order energy and timing model of one brake / listen / recover cycle.

    rotor_inertia [kg m^2] (propeller + motor bell) and brake_torque [N m]
    are the quantities to be measured on the bench (see the hardware guide)."""
    rho, g = 1.225, G0
    A = n_rot * np.pi * (prop_d_in * 0.0254 / 2) ** 2
    P_hover = (mass * g) ** 1.5 / np.sqrt(2 * rho * A) / fm
    w0 = rpm * 2 * np.pi / 60
    t_stop = rotor_inertia * w0 / brake_torque
    t_unpowered = brake + listen                        # thrust absent during braking and listening
    v_end = pre_climb - g * t_unpowered                 # vertical speed when thrust returns
    z_peak = pre_climb ** 2 / (2 * g)
    z_end = pre_climb * t_unpowered - 0.5 * g * t_unpowered ** 2
    E_spin = n_rot * 0.5 * rotor_inertia * w0 ** 2 / eta_motor
    E_arrest = 0.5 * mass * v_end ** 2 / fm
    E_preclimb = mass * g * (pre_climb * 0.3) / fm   # extra lift work during the 0.3 s pre-climb
    E_cycle = E_spin + E_arrest + E_preclimb - P_hover * t_unpowered  # rotors off: hover power saved
    return {"hover_power_W": P_hover, "t_stop_s": t_stop, "t_unpowered_s": t_unpowered,
            "vertical_speed_at_recovery_ms": v_end, "net_height_change_m": z_end, "peak_rise_m": z_peak,
            "E_spinup_J": E_spin, "E_arrest_J": E_arrest, "E_preclimb_J": E_preclimb,
            "E_net_per_cycle_J": E_cycle, "E_hover_per_cycle_J": P_hover * cycle,
            "overhead_pct": 100 * E_cycle / (P_hover * cycle)}


def run_m2(out: Path = Path("outputs/results")) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    res = {"budget": silence_window_budget()}
    b = res["budget"]
    print(f"  M7 budget: hover {b['hover_power_W']:.0f} W, rotor stop {1e3*b['t_stop_s']:.0f} ms, recovery speed "
          f"{b['vertical_speed_at_recovery_ms']:.2f} m/s, net height {b['net_height_change_m']:+.2f} m, "
          f"overhead {b['overhead_pct']:.1f}% of hover energy per 2 s cycle", flush=True)
    a = iso9613_alpha(np.array([3000, 4500, 6000]))
    res["absorption_db_per_m"] = a.tolist()
    print(f"  absorption at 3/4.5/6 kHz: {a.round(4)} dB/m", flush=True)
    res["window"] = window_study(egos=(-10, 0, 10), seed=1, save=out / "m2_window_part2.json")
    part1 = out / "m2_window_part1.json"          # ego -30 and -20 dB, recovered from the first run's log
    if part1.exists():
        res["window"] = {**json.loads(part1.read_text()), **res["window"]}
    print("  -- closed loop, distributed (partly incoherent) rotor noise", flush=True)
    res["loop"] = loop_study(rotor_subsources=6)
    print("  -- closed loop, coherent point-source rotor noise (optimistic for reference cancellation)", flush=True)
    res["loop_coherent"] = loop_study(rotor_subsources=1, policies=[p for p in POLICIES if p.mode == "running"])
    (out / "m2.json").write_text(json.dumps(res, indent=1, default=float))
    return res
