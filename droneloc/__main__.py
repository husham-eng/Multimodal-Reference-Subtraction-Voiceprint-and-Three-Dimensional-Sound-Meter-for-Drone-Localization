"""Command line: python -m droneloc {libraries,download,run,evaluate-array,dregon,coherence,sphere-geometry}."""
import argparse

from .catalog import DATASETS, DRONE_PROFILES, describe


def main() -> None:
    ap = argparse.ArgumentParser(prog="droneloc", description=__doc__)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("libraries", help="list drone sound libraries (synthetic profiles and datasets)")
    d = sub.add_parser("download", help="download a public dataset into ./data")
    d.add_argument("dataset", choices=[k for k, v in DATASETS.items() if v.auto_download])
    r = sub.add_parser("run", help="train all stages and run the simulated homing mission")
    r.add_argument("--drone", default="hexa_swap", choices=list(DRONE_PROFILES))
    r.add_argument("--dataset", default=None, choices=list(DATASETS),
                   help="use recordings of the drone from this dataset instead of the synthetic model")
    r.add_argument("--duration", type=float, default=40.0)
    r.add_argument("--seed", type=int, default=0)
    r.add_argument("--out", default="outputs")
    r.add_argument("--n-voiceprint", type=int, default=120, help="training segments per class")
    r.add_argument("--n-neural", type=int, default=1200, help="simulated frames for the neural localizer")
    r.add_argument("--array-radius", type=float, default=0.08, help="sphere radius [m] (0.08 = 160 mm sensor)")
    r.add_argument("--no-plots", action="store_true")
    e = sub.add_parser("evaluate-array", help="evaluate direction finding on a real multichannel recording")
    e.add_argument("--wav", required=True)
    e.add_argument("--geometry", required=True, help="CSV x,y,z per array microphone [m]")
    e.add_argument("--truth", required=True, help="CSV t_start,t_end,azimuth_deg,elevation_deg")
    e.add_argument("--refs", default=None, help="reference channel indices, e.g. 6,7")
    e.add_argument("--cal", default=None, help="target-free segment t0,t1 [s] for the reference canceller")
    e.add_argument("--band", default=None, help="lo,hi [Hz] for a beacon or broadband source")
    e.add_argument("--bpf", default=None, help="lo,hi [Hz] blade-passing-frequency search range (harmonic comb)")
    e.add_argument("--steering", default="free", choices=["free", "sphere"])
    e.add_argument("--noise", default=None, help="target-free WAV for noise cross-spectra subtraction")
    e.add_argument("--out", default="array_eval.csv")
    c = sub.add_parser("coherence", help="best possible ego-noise cancellation from reference mics (real recording)")
    c.add_argument("--wav", required=True)
    c.add_argument("--array", default="0,1,2,3,4,5", help="array channel indices")
    c.add_argument("--refs", required=True, help="reference channel indices, e.g. 6,7,8,9")
    c.add_argument("--band", default="3000,6000")
    dr = sub.add_parser("dregon", help="evaluate the direction estimator on unzipped DREGON recordings")
    dr.add_argument("--data", required=True, help="folder with the DREGON .wav and .mat files")
    dr.add_argument("--out", default="outputs/dregon")
    dr.add_argument("--segment", type=float, default=0.5, help="segment length [s]")
    dr.add_argument("--band", default=None, help="lo,hi [Hz]; default by source type in the file name")
    dr.add_argument("--units", default="auto", choices=["auto", "deg", "rad"], help="angle units in source_position")
    dr.add_argument("--noise", default=None,
                    help="noise-only in-flight WAV (no source); adds a run with noise cross-spectra subtraction")
    g = sub.add_parser("sphere-geometry", help="write the geometry CSV of the 160 mm octahedral sensor")
    g.add_argument("path", nargs="?", default="sphere160.csv")
    a = ap.parse_args()
    if a.cmd == "libraries":
        print(describe())
    elif a.cmd == "evaluate-array":
        from pathlib import Path
        from .real_array import evaluate
        pair = lambda v: tuple(float(x) for x in v.split(",")) if v else None  # noqa: E731
        evaluate(Path(a.wav), Path(a.geometry), Path(a.truth),
                 [int(i) for i in a.refs.split(",")] if a.refs else None, pair(a.cal), pair(a.band), pair(a.bpf),
                 a.steering, out_csv=Path(a.out), noise_wav=Path(a.noise) if a.noise else None)
    elif a.cmd == "coherence":
        from pathlib import Path
        from .real_array import multiple_coherence
        ints = lambda v: [int(i) for i in v.split(",")]  # noqa: E731
        multiple_coherence(Path(a.wav), ints(a.array), ints(a.refs), tuple(float(x) for x in a.band.split(",")))
    elif a.cmd == "dregon":
        from pathlib import Path
        from .dregon import run as run_dregon
        run_dregon(Path(a.data), Path(a.out), a.segment,
                   tuple(float(x) for x in a.band.split(",")) if a.band else None, a.units,
                   Path(a.noise) if a.noise else None)
    elif a.cmd == "sphere-geometry":
        from pathlib import Path
        from .real_array import write_sphere_geometry
        write_sphere_geometry(Path(a.path)); print(f"written {a.path}")
    elif a.cmd == "download":
        from .datasets import download
        download(a.dataset)
    else:
        from .pipeline import run
        run(a.drone, a.dataset, a.duration, a.seed, a.out, a.n_voiceprint, a.n_neural, not a.no_plots,
            a.array_radius)


if __name__ == "__main__":
    main()
