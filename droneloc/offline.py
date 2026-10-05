"""Offline operation: run the passive chain with all network access blocked and time it.

Training data are prepared once beforehand (synthetic models, or recordings copied to
./data); after that, training and every run-time step use only local files and the CPU.
`blocked_network()` makes any socket connection raise, so a run that completes inside it
has provably not used the internet.
"""
from __future__ import annotations

import contextlib
import io
import pickle
import platform
import socket
import time

import numpy as np


class NetworkUsed(RuntimeError):
    pass


@contextlib.contextmanager
def blocked_network():
    """Every attempt to open a network connection raises NetworkUsed."""
    def deny(*a, **k):
        raise NetworkUsed("network access attempted")
    saved = socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    socket.getaddrinfo = deny
    try:
        yield
    finally:
        socket.socket.connect, socket.socket.connect_ex, socket.create_connection, socket.getaddrinfo = saved


def benchmark(n_voiceprint: int = 120, seconds: float = 20.0, seed: int = 0) -> dict:
    """Train and run the realistic passive chain offline; per-hop processing time on this CPU."""
    from .exp_passive import calibrate_level
    from .localization import SoundMeter3D
    from .reference_subtraction import ReferenceCanceller
    from .simulation import Scene, homing_trajectory, octahedral_array, render
    from .tracking import Kalman3D
    from .voiceprint import VoiceprintModel

    fs, rng = 16000, np.random.default_rng(seed)
    with blocked_network():
        t0 = time.perf_counter()
        vp = VoiceprintModel.train("hexa_swap", n_per_class=n_voiceprint, fs=fs, seed=seed, rpm_range=0.30, sensor_aug=True)
        t_vp = time.perf_counter() - t0
        scene = Scene(array=octahedral_array(0.08), fs=fs, drone="hexa_swap", scattering=True, pos_err_mm=1.0,
                      gain_err_db=0.5, delay_err_us=5.0)
        cal = render(scene, 8.0, drone_on=False, rng=rng)
        t0 = time.perf_counter()
        canc = ReferenceCanceller().fit(cal.mics, cal.refs)
        t_canc = time.perf_counter() - t0
        meter = SoundMeter3D(scene.array, fs, calibrate_level(scene, rng), steering="sphere")
        scene.trajectory = homing_trajectory(seconds)
        rec = render(scene, seconds, rng=rng)
        frame, hop = int(0.5 * fs), int(0.25 * fs)
        kf = Kalman3D(hop / fs)
        steps = {"reference subtraction": [], "voiceprint": [], "sphere SRP + range": [], "Kalman": []}
        for end in range(fs, rec.mics.shape[1] + 1, hop):
            t1 = time.perf_counter()
            clean = canc.transform(rec.mics[:, end - fs:end], rec.refs[:, end - fs:end])
            t2 = time.perf_counter()
            ana = vp.analyse(clean[0])
            t3 = time.perf_counter()
            m = meter.measure(clean[:, -frame:], ana["bpf_hz"]) if ana["is_target"] else None
            t4 = time.perf_counter()
            kf.predict()
            if m is not None:
                kf.update(m["position"], scene.array.center)
            t5 = time.perf_counter()
            for k, a, b in zip(steps, (t1, t2, t3, t4), (t2, t3, t4, t5)):
                steps[k].append(b - a)
    per = {k: 1000 * float(np.median(v)) for k, v in steps.items()}
    total = np.array([sum(x) for x in zip(*steps.values())])
    buf = io.BytesIO(); pickle.dump(vp, buf)
    return {
        "cpu": platform.processor() or platform.machine(), "python": platform.python_version(),
        "hops": len(total), "hop_ms": 1000 * hop / fs, "frame_ms": 1000 * frame / fs,
        "median_step_ms": per, "median_total_ms": 1000 * float(np.median(total)),
        "p95_total_ms": 1000 * float(np.percentile(total, 95)),
        "real_time_factor": float(np.median(total) / (hop / fs)),
        "train_voiceprint_s": t_vp, "train_canceller_s": t_canc,
        "voiceprint_model_mb": buf.tell() / 1e6, "network": "blocked (no connection attempted)",
    }
