import numpy as np
import pytest

from droneloc.catalog import DRONE_PROFILES, describe
from droneloc.dsp import angle_between_deg, istft, snr_db, spl_db, stft, welch_psd
from droneloc.localization import SoundMeter3D, harmonic_level_db
from droneloc.reference_subtraction import ReferenceCanceller
from droneloc.simulation import Scene, render, static
from droneloc.synth import synthesize_drone
from droneloc.voiceprint import N_FFT, estimate_bpf

FS = 16000


def test_catalog_lists_profiles_and_datasets():
    text = describe()
    assert "hexa_swap" in text and "DroneAudioDataset" in text


def test_stft_roundtrip():
    x = np.random.default_rng(0).standard_normal((2, 5000))
    y = istft(stft(x, 512, 128), 512, 128, 5000)
    assert np.allclose(x, y, atol=1e-8)


@pytest.mark.parametrize("key", list(DRONE_PROFILES))
def test_synth_level_and_bpf(key):
    p = DRONE_PROFILES[key]
    x = synthesize_drone(p, 2.0, FS, np.random.default_rng(1))
    assert abs(spl_db(x) - p.level_1m_db) < 0.1
    f0, _ = estimate_bpf(welch_psd(x, N_FFT, N_FFT // 4), FS, 0.7 * p.bpf_hz, 1.35 * p.bpf_hz)
    assert abs(f0 / p.bpf_hz - 1) < 0.05


@pytest.fixture(scope="module")
def trained():
    rng = np.random.default_rng(2)
    scene = Scene()
    cal = render(scene, 4.0, drone_on=False, rng=rng)
    return scene, ReferenceCanceller().fit(cal.mics, cal.refs), rng


def test_reference_subtraction_reduces_interference(trained):
    scene, canc, rng = trained
    val = render(scene, 2.0, drone_on=False, rng=rng)
    assert canc.reduction_db(val.mics, val.refs) > 15


def test_sound_meter_localizes_after_subtraction(trained):
    scene, canc, rng = trained
    p = DRONE_PROFILES[scene.drone]
    l1 = harmonic_level_db(synthesize_drone(p, 3.0, FS, rng)[None], FS, p.bpf_hz)[0]
    meter = SoundMeter3D(scene.array, FS, l1)
    pos = np.array([8.0, -6.0, 7.0])
    scene.trajectory = static(pos)
    rec = render(scene, 0.5, rng=rng)
    clean = canc.transform(rec.mics, rec.refs)
    assert snr_db(rec.target, clean - rec.target) > snr_db(rec.target, rec.mics - rec.target) + 10
    m = meter.measure(clean, p.bpf_hz)
    v = pos - scene.array.center
    assert angle_between_deg(m["direction"], v) < 5
    assert abs(m["range"] / np.linalg.norm(v) - 1) < 0.35


def test_evaluate_array_end_to_end(tmp_path):
    """The real-recording tool, exercised on a simulated sphere recording with known truth."""
    import soundfile as sf
    from droneloc.real_array import evaluate, write_sphere_geometry
    rng = np.random.default_rng(3)
    scene = Scene(scattering=True, machinery_level_db=-100, wind_level_db=30, bird_level_db=-100)
    truth = []
    chunks = []
    for k, (az, el) in enumerate([(30, 20), (-120, 35), (160, 10)]):
        a, e = np.radians(az), np.radians(el)
        scene.trajectory = static(scene.array.center + 15 * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)]))
        chunks.append(render(scene, 1.0, rng=rng).mics)
        truth.append(f"{k:.1f},{k + 1:.1f},{az},{el}")
    x = np.hstack(chunks)
    sf.write(tmp_path / "rec.wav", (x / np.abs(x).max() * 0.9).T, FS, subtype="FLOAT")
    write_sphere_geometry(tmp_path / "geo.csv")
    (tmp_path / "truth.csv").write_text("t_start,t_end,azimuth_deg,elevation_deg\n" + "\n".join(truth) + "\n")
    s = evaluate(tmp_path / "rec.wav", tmp_path / "geo.csv", tmp_path / "truth.csv", bpf=(105, 200), steering="sphere")
    assert s["median_error"][0] < 3


def test_dregon_batch(tmp_path):
    """The DREGON command on a synthetic recording in the DREGON file layout (plane wave, moving source)."""
    import soundfile as sf
    from scipy.io import savemat
    from droneloc.dregon import DREGON_MICS, run as run_dregon
    fs, dur, c = 44100, 4.0, 343.0
    rng = np.random.default_rng(5)
    n = int(fs * dur)
    t = np.arange(n) / fs
    az = np.linspace(20, 80, n)          # source sweeps in azimuth (degrees, as in DREGON)
    el = np.full(n, -30.0)
    s = rng.standard_normal(n)
    S = np.fft.rfft(s)
    f = np.fft.rfftfreq(n, 1 / fs)
    x = np.zeros((8, n))
    for k in range(4):                   # four 1 s blocks, each a plane wave from its centre direction
        sl = slice(k * fs, (k + 1) * fs)
        a, e = np.radians(az[sl].mean()), np.radians(el[sl].mean())
        u = np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])
        for m in range(8):
            x[m, sl] = np.fft.irfft(S * np.exp(2j * np.pi * f * (DREGON_MICS[m] @ u) / c), n)[sl]
    x += 0.05 * rng.standard_normal(x.shape)
    rec = tmp_path / "data" / "DREGON_free-flight_whitenoise_room1"
    rec.mkdir(parents=True)
    sf.write(rec / "DREGON_free-flight_whitenoise_room1.wav", (x / np.abs(x).max() * 0.9).T, fs)
    t0 = 1.5e9
    savemat(rec / "DREGON_free-flight_whitenoise_room1_audiots.mat", {"audio_timestamps": t0 + t})
    ts = t0 + np.arange(0, dur, 0.01)
    savemat(rec / "DREGON_free-flight_whitenoise_room1_sourcepos.mat", {"source_position": {
        "timestamps": ts, "azimuth": np.interp(ts - t0, t, az), "elevation": np.full(ts.size, -30.0),
        "distance": np.full(ts.size, 2.0)}})
    motors = tmp_path / "data" / "DREGON_free-flight_nosource_room1"
    motors.mkdir()
    sf.write(motors / "DREGON_free-flight_nosource_room1.wav", 0.01 * rng.standard_normal((fs, 8)), fs)
    out = run_dregon(tmp_path / "data", tmp_path / "out", segment=0.5,
                     noise=motors / "DREGON_free-flight_nosource_room1.wav")
    assert out["skipped"] == []  # the noise recording is not evaluated as a target recording
    for v in ("plain", "noise_sub", "noise_adapt"):
        assert out["all"][v]["segments"] >= 6
        assert out["all"][v]["median_error"][0] < 8
    out = run_dregon(tmp_path / "data", tmp_path / "out2", segment=0.5)
    assert out["skipped"] == ["DREGON_free-flight_nosource_room1"]
    assert (tmp_path / "out" / "dregon_summary.json").exists()


def test_offline_chain_without_network():
    """Training and the passive run-time chain complete with every network connection blocked."""
    import urllib.request
    import pytest
    from droneloc.offline import NetworkUsed, blocked_network
    from droneloc.reference_subtraction import ReferenceCanceller
    from droneloc.localization import SoundMeter3D
    from droneloc.voiceprint import VoiceprintModel
    with blocked_network():
        with pytest.raises(NetworkUsed):  # the guard really blocks
            urllib.request.urlopen("http://example.com", timeout=2)
        rng = np.random.default_rng(0)
        vp = VoiceprintModel.train("hexa_swap", n_per_class=12, fs=FS, seed=0)
        scene = Scene(machinery_level_db=75, wind_level_db=35)
        cal = render(scene, 4.0, drone_on=False, rng=rng)
        canc = ReferenceCanceller().fit(cal.mics, cal.refs)
        scene.trajectory = static(scene.array.center + np.array([10.0, 5.0, 4.0]))
        rec = render(scene, 1.0, rng=rng)
        clean = canc.transform(rec.mics, rec.refs)
        ana = vp.analyse(clean[0])
        m = SoundMeter3D(scene.array, FS, vp.level_1m_db).measure(clean[:, -FS // 2:], ana["bpf_hz"])
    assert np.isfinite(m["position"]).all()
