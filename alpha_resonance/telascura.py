"""Telascura lattice: informational field K, gradients, and LTS clock."""

from __future__ import annotations

import numpy as np

from .constants import ALPHA, DT


class TelascuraLattice:
    """
    Coherent informational network on graph G.

    Equations (see FRAMEWORK_EQUATIONS.md §I–II, §IV):
      K_i = |mean_j exp(i(θ_j - θ_i))|
      (∇K)_i = mean_j (K_j - K_i)
      c_eff = c0 * (1 + ε_K * K_global)
    """

    def __init__(self, adjacency: np.ndarray, c0: float = 1.0, epsilon_k: float = 0.05):
        self.adjacency = adjacency.astype(float)
        self.n = adjacency.shape[0]
        self.c0 = c0
        self.epsilon_k = epsilon_k
        self.degrees = np.maximum(self.adjacency.sum(axis=1), 1.0)

    def local_coherence(self, theta: np.ndarray) -> np.ndarray:
        """K_i(t) per node."""
        k = np.zeros(self.n)
        for i in range(self.n):
            neighbors = np.where(self.adjacency[i] > 0)[0]
            if len(neighbors) == 0:
                k[i] = 0.0
                continue
            diffs = theta[neighbors] - theta[i]
            k[i] = np.abs(np.mean(np.exp(1j * diffs)))
        return k

    def global_coherence(self, theta: np.ndarray) -> float:
        """K_global(t) = mean_i K_i."""
        return float(np.mean(self.local_coherence(theta)))

    def gradient_k(self, theta: np.ndarray) -> np.ndarray:
        """Discrete (∇K)_i."""
        k = self.local_coherence(theta)
        grad = np.zeros(self.n)
        for i in range(self.n):
            neighbors = np.where(self.adjacency[i] > 0)[0]
            if len(neighbors) == 0:
                grad[i] = 0.0
                continue
            grad[i] = float(np.mean(k[neighbors] - k[i]))
        return grad

    def adjusted_kappa(self, kappa_bare: float, theta: np.ndarray, eta: float = 0.5) -> np.ndarray:
        """κ_i^adj = κ_bare * exp(η * (∇K)_i)."""
        return kappa_bare * np.exp(eta * self.gradient_k(theta))

    def effective_speed(self, theta: np.ndarray) -> float:
        """c_eff = c0 * (1 + ε_K * K_global)."""
        return self.c0 * (1.0 + self.epsilon_k * self.global_coherence(theta))

    def sync_period(self, length: float, theta: np.ndarray) -> float:
        """τ_sync = L / c_eff."""
        c_eff = self.effective_speed(theta)
        return length / max(c_eff, 1e-12)

    def module_phase_lag(self, theta: np.ndarray, modules: list[list[int]]) -> list[float]:
        """|arg(z_a) - arg(z_b)| between consecutive modules."""
        z_phases = []
        for mod in modules:
            z = np.mean(np.exp(1j * theta[mod]))
            z_phases.append(np.angle(z))
        lags = []
        for a in range(len(z_phases) - 1):
            d = np.abs(z_phases[a] - z_phases[a + 1])
            lags.append(float(min(d, 2 * np.pi - d)))
        return lags

    def model_energy(self, kappa_eff: float) -> float:
        """E_eff = N * κ_eff² * α⁻¹ (model-scale)."""
        return self.n * (kappa_eff ** 2) * (1.0 / ALPHA)