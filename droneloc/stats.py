"""Small statistics helpers used by the revision experiments."""
from __future__ import annotations

import numpy as np


def wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    """Wilson score 95% interval for a binomial proportion k/n."""
    if n == 0:
        return (float("nan"), float("nan"))
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * np.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def bootstrap_ci(x, stat=np.median, n_boot: int = 2000, seed: int = 0) -> tuple[float, float, float]:
    """(statistic, low, high) with a percentile bootstrap 95% interval."""
    x = np.asarray(x, float)
    x = x[np.isfinite(x)]
    if x.size == 0:
        return (float("nan"),) * 3
    rng = np.random.default_rng(seed)
    boots = np.array([stat(rng.choice(x, x.size)) for _ in range(n_boot)])
    return float(stat(x)), float(np.percentile(boots, 2.5)), float(np.percentile(boots, 97.5))


def fmt_ci(t: tuple[float, float, float], digits: int = 1, unit: str = "") -> str:
    v, lo, hi = t
    return f"{v:.{digits}f}{unit} [{lo:.{digits}f}, {hi:.{digits}f}]"
