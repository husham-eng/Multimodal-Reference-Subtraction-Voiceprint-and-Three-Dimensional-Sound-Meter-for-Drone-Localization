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
