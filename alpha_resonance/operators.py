"""Ten-operator cosmogenic recurrence and dual-path wiggle tracker."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .constants import DUAL_PATH_GOOD, DUAL_PATH_HARM, SCALE_EPOCHS


@dataclass
class ScaleSnapshot:
    scale: float
    label: str
    good_amplitude: float
    harm_amplitude: float
    coherence: float
    stability_good: float
    stability_harm: float
    ger_active: bool
    spark_active: bool


class DualPathEngine:
    """
    Δ_i = T + B + R + S + P + C + E + M + G + J

    Implements good vs harm dual-path propagation across s ∈ [s_min, s_max].
    """

    def __init__(
        self,
        delta0: float = 1e-8,
        n_scales: int = 600,
        s_min: float = -40.0,
        s_max: float = 12.0,
    ):
        self.delta0 = delta0
        self.n_scales = n_scales
        self.s_min = s_min
        self.s_max = s_max

    @staticmethod
    def transfer_step(delta_prev: float, ds: float, mode: str, i: int) -> float:
        params = DUAL_PATH_GOOD if mode == "good" else DUAL_PATH_HARM
        damping = params["damping"]
        feedback = params["feedback"]
        boost = params["boost"]

        wave_mod = 1.0 + boost * math.sin(2 * math.pi * i / 8)
        fb_term = feedback * delta_prev if i > 1 else 0.0

        boundary = -0.02 * delta_prev if i < 30 else 0.0

        ger = 0.0
        if i > 520:
            ger = 0.03 * math.exp(-0.5 * max(0, i - 520) ** 2 / 40 ** 2)

        spark = 0.0
        if i > 540:
            spark = 0.06 * math.exp(-0.9 * max(0, i - 540) ** 2 / 35 ** 2)

        coherence_pull = -0.015 * delta_prev if mode == "good" and delta_prev > 1e-6 else 0.0

        delta = (
            delta_prev * math.exp(-damping * ds) * wave_mod
            + fb_term
            + boundary
            + coherence_pull
            + ger
            + spark
        )
        return max(delta, 0.0)

    def run(self) -> dict:
        scales = np.linspace(self.s_min, self.s_max, self.n_scales)
        good = np.zeros(self.n_scales)
        harm = np.zeros(self.n_scales)
        good[0] = harm[0] = self.delta0

        for i in range(1, self.n_scales):
            ds = scales[i] - scales[i - 1]
            good[i] = self.transfer_step(good[i - 1], ds, "good", i)
            harm[i] = self.transfer_step(harm[i - 1], ds, "harm", i)

        stab_good = -np.cumsum(good) / np.arange(1, self.n_scales + 1)
        stab_harm = -np.cumsum(harm) / np.arange(1, self.n_scales + 1)

        snapshots = []
        for s, label in SCALE_EPOCHS.items():
            idx = int(np.argmin(np.abs(scales - s)))
            g, h = good[idx], harm[idx]
            coh = min(g, h) / max(g, h) if max(g, h) > 0 else 0.0
            snapshots.append(
                ScaleSnapshot(
                    scale=s,
                    label=label,
                    good_amplitude=float(g),
                    harm_amplitude=float(h),
                    coherence=float(coh),
                    stability_good=float(stab_good[idx]),
                    stability_harm=float(stab_harm[idx]),
                    ger_active=idx > 520,
                    spark_active=idx > 540,
                )
            )

        # Good path remains restorative (positive, finite) even when harm dominates at s=12
        verdict = (
            "RESTORATIVE PATH VIABLE"
            if good[-1] > 0 and np.isfinite(good[-1])
            else "HARM PATH DOMINANT"
        )

        return {
            "scales": scales,
            "good": good,
            "harm": harm,
            "stability_good": stab_good,
            "stability_harm": stab_harm,
            "snapshots": snapshots,
            "final_good": float(good[-1]),
            "final_harm": float(harm[-1]),
            "dual_path_verdict": verdict,
        }

    @staticmethod
    def propulsion_proxy(grad_k_mean: float, kappa_eff: float) -> float:
        """Minimal thrust proxy ∝ |∇K| * κ_eff (Document 18)."""
        return abs(grad_k_mean) * kappa_eff