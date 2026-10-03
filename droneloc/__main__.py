"""Command line: python -m droneloc {libraries,download,run}."""
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
    a = ap.parse_args()
    if a.cmd == "libraries":
        print(describe())
    elif a.cmd == "download":
        from .datasets import download
        download(a.dataset)
    else:
        from .pipeline import run
        run(a.drone, a.dataset, a.duration, a.seed, a.out, a.n_voiceprint, a.n_neural, not a.no_plots,
            a.array_radius)


if __name__ == "__main__":
    main()
