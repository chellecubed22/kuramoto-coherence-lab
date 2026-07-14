"""Evidence layer: MCMC diagnostics and ART truth scoring."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np


@dataclass
class MCMCDiagnostics:
    r_hat: float
    ess: float
    autocorr: float
    status: str


class EvidenceLayer:
    """Super Truth / ART layer — distinguishes TRUE_COHERENCE from substitutes."""

    THRESHOLDS = {
        "substitute": {"r_hat": 1.05, "autocorr": 50, "ess_min": 100},
        "target": {"r_hat": 1.01, "autocorr": 20, "ess_min": 400},
    }

    @staticmethod
    def evaluate_coherence(r_hat: float, ess: float, autocorr: float) -> str:
        sub = EvidenceLayer.THRESHOLDS["substitute"]
        tgt = EvidenceLayer.THRESHOLDS["target"]
        if r_hat > sub["r_hat"] or autocorr > sub["autocorr"] or ess < sub["ess_min"]:
            return "SUBSTITUTE_ACTIVE"
        if r_hat <= tgt["r_hat"] and autocorr <= tgt["autocorr"] and ess >= tgt["ess_min"]:
            return "TRUE_COHERENCE"
        return "FLIP_CANDIDATE"

    @staticmethod
    def gelman_rubin(chains: np.ndarray) -> float:
        """chains shape: (n_chains, n_samples)."""
        m, n = chains.shape
        chain_means = chains.mean(axis=1)
        chain_vars = chains.var(axis=1, ddof=1)
        W = chain_vars.mean()
        B = n * ((chain_means - chain_means.mean()) ** 2).sum() / max(m - 1, 1)
        var_hat = (n - 1) / n * W + B / n
        return float(np.sqrt(max(var_hat / max(W, 1e-12), 0.0)))

    @staticmethod
    def effective_sample_size(chain: np.ndarray, max_lag: int = 50) -> float:
        x = chain - chain.mean()
        acf = np.correlate(x, x, mode="full")
        acf = acf[len(acf) // 2:]
        acf = acf / max(acf[0], 1e-12)
        tau = 1.0 + 2.0 * np.sum(acf[1:max_lag])
        return float(len(chain) / max(tau, 1.0))

    @classmethod
    def compute_diagnostics(cls, chains: np.ndarray) -> MCMCDiagnostics:
        r_hat = cls.gelman_rubin(chains)
        ess_vals = [cls.effective_sample_size(c) for c in chains]
        ess = float(min(ess_vals))
        autocorr = float(len(chains[0]) / max(ess, 1.0))
        status = cls.evaluate_coherence(r_hat, ess, autocorr)
        return MCMCDiagnostics(r_hat=r_hat, ess=ess, autocorr=autocorr, status=status)

    @staticmethod
    def simulate_chains(n_chains: int = 4, n_samples: int = 500, seed: int = 42) -> np.ndarray:
        rng = np.random.default_rng(seed)
        chains = []
        for c in range(n_chains):
            x = rng.normal(0, 1, n_samples)
            ar = 0.55 + 0.05 * c
            for i in range(1, n_samples):
                x[i] += ar * x[i - 1] + rng.normal(0, 0.4)
            chains.append(x)
        return np.array(chains)

    @staticmethod
    def art_truth(term_freqs: list[float], coherence_factor: float = 0.95, k: float = 4.2) -> dict:
        n = len(term_freqs)
        harmonic = np.mean(
            [f * abs(math.sin(2 * math.pi * i / max(n, 1))) for i, f in enumerate(term_freqs)]
        )
        truth_resonance = float(np.mean(term_freqs) * 0.98 + harmonic * 0.02)
        total = (truth_resonance * coherence_factor) / (
            1 + math.exp(-k * (truth_resonance - 0.5))
        )
        return {
            "truth_resonance": round(truth_resonance, 4),
            "total_truth": round(float(total), 4),
            "coherence_factor": coherence_factor,
        }