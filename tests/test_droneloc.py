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


def test_pico_packet_reader():
    from droneloc.pico import PacketReader, make_packet
    rng = np.random.default_rng(0)
    d = [rng.integers(-32768, 32767, (64, 12)).astype(np.int16) for _ in range(4)]
    raw = b"junk" + make_packet(0, d[0]) + make_packet(1, d[1])
    bad = bytearray(make_packet(2, d[2])); bad[30] ^= 1          # corrupt packet 2
    raw += bytes(bad) + make_packet(3, d[3])
    rd = PacketReader()
    out = []
    for i in range(0, len(raw), 100):                              # arbitrary chunking
        out += rd.feed(raw[i:i + 100])
    assert [o[0] for o in out] == [0, 1, None, 3]
    assert np.array_equal(out[0][3], d[0]) and np.array_equal(out[3][3], d[3])
    assert not out[2][3].any() and out[2][3].shape == (64, 12)    # gap filled with zeros
    assert rd.bad >= 1 and rd.lost == 1 and out[0][2] == 15625


def _live_recording(tmp_path, az, el, machinery_db, cal_s=0.0, on_s=3.0):
    """Simulated sphere + reference channels as an int16 WAV: cal_s s drone absent, then on_s s drone on."""
    import soundfile as sf
    rng = np.random.default_rng(5)
    scene = Scene(scattering=True, machinery_level_db=machinery_db, wind_level_db=30, bird_level_db=-100)
    a, e = np.radians(az), np.radians(el)
    scene.trajectory = static(scene.array.center + 15 * np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)]))
    parts = [render(scene, cal_s, drone_on=False, rng=rng)] if cal_s else []
    parts.append(render(scene, on_s, rng=rng))
    x = np.hstack([np.vstack([p.mics, p.refs]) for p in parts])
    sf.write(tmp_path / "live.wav", (x / np.abs(x).max() * 0.9).T, FS, subtype="PCM_16")
    return tmp_path / "live.wav", parts[0].refs.shape[0]


def test_live_wav_replay(tmp_path):
    from droneloc import live
    wav, _ = _live_recording(tmp_path, 40, 25, machinery_db=-100)
    rows = live.run(live.wav_bytes(wav), live.SPHERE_DIRS * 0.08, quiet=True, log=tmp_path / "log.csv",
                    bpf=(105, 200), steering="sphere")
    assert len(rows) >= 9 and (tmp_path / "log.csv").exists()
    err = [angle_between_deg(live_unit(r), live_unit({"azimuth_deg": 40, "elevation_deg": 25})) for r in rows]
    assert np.median(err) < 5


def test_live_reference_calibration(tmp_path):
    from droneloc import live
    wav, R = _live_recording(tmp_path, -110, 30, machinery_db=80, cal_s=3.0)
    kw = dict(bpf=(105, 200), steering="sphere", quiet=True)
    refs = list(range(6, 6 + R))
    with_ref = live.run(live.wav_bytes(wav), live.SPHERE_DIRS * 0.08, refs=refs, cal_seconds=3.0, **kw)
    assert with_ref[0]["t"] >= 3.0                                  # estimates start after calibration
    truth = live_unit({"azimuth_deg": -110, "elevation_deg": 30})
    err = np.median([angle_between_deg(live_unit(r), truth) for r in with_ref])
    without = live.run(live.wav_bytes(wav), live.SPHERE_DIRS * 0.08, **kw)
    err0 = np.median([angle_between_deg(live_unit(r), truth) for r in without if r["t"] > 3.0])
    assert err < 3 and err0 > 30                                  # machinery dominates without references


def live_unit(r):
    a, e = np.radians(r["azimuth_deg"]), np.radians(r["elevation_deg"])
    return np.array([np.cos(e) * np.cos(a), np.cos(e) * np.sin(a), np.sin(e)])


def test_frames_match_sliding_window():
    from numpy.lib.stride_tricks import sliding_window_view
    from droneloc.dsp import frames
    x = np.random.default_rng(0).standard_normal((3, 5000))
    for n_fft, hop in [(1024, 256), (2048, 512), (4096, 1024), (64, 7)]:
        assert np.array_equal(frames(x, n_fft, hop), sliding_window_view(x, n_fft, axis=-1)[..., ::hop, :])
    assert np.array_equal(frames(x[1:, ::2], 128, 32), sliding_window_view(x[1:, ::2], 128, axis=-1)[..., ::32, :])


@pytest.mark.parametrize("model", ["free", "sphere"])
def test_fast_srp_matches_exact(tmp_path, model):
    import soundfile as sf
    from droneloc.localization import GccPhat, PhaseSRP
    from droneloc.simulation import MicArray
    from droneloc import live
    wav, _ = _live_recording(tmp_path, 75, 15, machinery_db=-100, on_s=2.0)
    x = sf.read(str(wav))[0].T[:6]
    gcc = GccPhat(MicArray(live.SPHERE_DIRS * 0.08, np.zeros(3)), FS)
    exact, fast = (PhaseSRP(gcc, model, n_dirs=2000, min_elevation_deg=-90, fast=f) for f in (False, True))
    for a in range(0, len(x[0]) - 8000, 8000):
        G = gcc.cross_spectra(x[:, a:a + 8000], 150.0)
        assert angle_between_deg(exact.locate(G)[0], fast.locate(G)[0]) < 0.5


def test_live_skips_late_windows():
    """A slow computer that receives 2 s at once computes only the newest window."""
    from droneloc import live
    x = (np.random.default_rng(1).standard_normal((3 * FS, 6)) * 3000).astype(np.int16)
    L = live.LiveLocator(live.SPHERE_DIRS * 0.08, FS, band=(300, 4000), skip_late=True)
    assert [r["t"] for r in L.push(x[:FS])] == [1.0]                # windows ending at 0.5 and 0.75 s skipped
    r = L.push(x[FS:3 * FS])
    assert [q["t"] for q in r] == [3.0] and L.skipped == 2 + 7
