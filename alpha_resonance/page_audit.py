"""Page-curve inspired stability audit on phase entropy."""

from __future__ import annotations

import numpy as np


def phase_entropy(theta: np.ndarray, n_bins: int = 36) -> float:
    """
    S = -Σ p_k log p_k  (histogram of phases mod 2π).
    """
    hist, _ = np.histogram(theta % (2 * np.pi), bins=n_bins, range=(0, 2 * np.pi), density=True)
    hist = hist + 1e-12
    hist = hist / hist.sum()
    return float(-np.sum(hist * np.log(hist)))


def entropy_recovery_fraction(
    entropy_trace: np.ndarray,
    perturb_index: int,
) -> float:
    """
    (S(T) - S(t_p)) / (S_max - S(t_p)) — lower is better recovery.
    """
    s_p = entropy_trace[perturb_index]
    s_final = entropy_trace[-1]
    s_max = float(np.max(entropy_trace))
    denom = s_max - s_p
    if abs(denom) < 1e-12:
        return 0.0
    return float((s_final - s_p) / denom)


def audit_stabilization(
    entropy_trace: np.ndarray,
    perturb_index: int,
    epsilon_s: float = 0.15,
) -> dict:
    """Returns pass/fail for Page-curve style recovery."""
    frac = entropy_recovery_fraction(entropy_trace, perturb_index)
    passed = frac <= epsilon_s
    return {
        "entropy_recovery_fraction": frac,
        "epsilon_s": epsilon_s,
        "stabilized": passed,
        "verdict": "STABLE" if passed else "UNSTABLE_OR_SLOW_RECOVERY",
    }