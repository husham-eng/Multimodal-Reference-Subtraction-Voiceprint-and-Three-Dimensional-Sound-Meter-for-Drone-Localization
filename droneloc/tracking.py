"""Constant-velocity Kalman filter that fuses (direction, range) measurements."""
from __future__ import annotations

import numpy as np


class Kalman3D:
    def __init__(self, dt: float, accel_std: float = 1.5, sigma_angle_deg: float = 3.0,
                 sigma_log_range: float = 0.12, gate: float = 16.0):
        self.dt = dt
        self.F = np.eye(6)
        self.F[:3, 3:] = dt * np.eye(3)
        g = np.vstack([0.5 * dt ** 2 * np.eye(3), dt * np.eye(3)])
        self.Q = accel_std ** 2 * g @ g.T
        self.Hm = np.hstack([np.eye(3), np.zeros((3, 3))])
        self.sig_a = np.radians(sigma_angle_deg)
        self.sig_r = sigma_log_range * np.log(10)  # relative range std
        self.gate = gate
        self.x: np.ndarray | None = None
        self.P = np.eye(6)

    def _meas_cov(self, origin, z):
        v = z - origin
        r = np.linalg.norm(v)
        u = v / r
        e1 = np.cross(u, [0, 0, 1.0])
        if np.linalg.norm(e1) < 1e-6:
            e1 = np.cross(u, [1.0, 0, 0])
        e1 /= np.linalg.norm(e1)
        e2 = np.cross(u, e1)
        return ((self.sig_r * r) ** 2 * np.outer(u, u)
                + (self.sig_a * r) ** 2 * (np.outer(e1, e1) + np.outer(e2, e2)) + 1e-4 * np.eye(3))

    def predict(self) -> None:
        if self.x is not None:
            self.x = self.F @ self.x
            self.P = self.F @ self.P @ self.F.T + self.Q

    def update(self, z: np.ndarray, origin: np.ndarray) -> bool:
        R = self._meas_cov(origin, z)
        if self.x is None:
            self.x = np.concatenate([z, np.zeros(3)])
            self.P = np.diag(np.concatenate([np.diag(R), [9.0] * 3]))
            return True
        y = z - self.Hm @ self.x
        S = self.Hm @ self.P @ self.Hm.T + R
        if y @ np.linalg.solve(S, y) > self.gate:  # outlier (e.g. bird, reflection)
            return False
        K = self.P @ self.Hm.T @ np.linalg.inv(S)
        self.x = self.x + K @ y
        self.P = (np.eye(6) - K @ self.Hm) @ self.P
        return True

    @property
    def position(self) -> np.ndarray | None:
        return None if self.x is None else self.x[:3].copy()
