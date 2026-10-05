"""Run the experiments reported in the manuscript.

    python experiments/run_experiments.py m1 m4 m6      # passive mode
    python experiments/run_experiments.py m5            # voiceprint
    python experiments/run_experiments.py m2            # active mode
Results are written to outputs/results/*.json.
"""
import sys
import time

sys.path.insert(0, ".")

parts = sys.argv[1:] or ["m1", "m4", "m5", "m6", "m2"]
for p in parts:
    t0 = time.time()
    print(f"=== {p} ===", flush=True)
    if p == "m1":
        from droneloc.exp_passive import run_m1; run_m1()
    elif p == "m4":
        from droneloc.exp_passive import run_m4; run_m4()
    elif p == "m6":
        from droneloc.exp_passive import run_m6; run_m6()
    elif p == "m5":
        from droneloc.exp_voiceprint import run_m5; run_m5()
    elif p == "m2":
        from droneloc.exp_active import run_m2; run_m2()
    print(f"=== {p} done in {time.time() - t0:.0f} s ===", flush=True)
