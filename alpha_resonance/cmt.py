"""CMT layer: α-scaled Kuramoto networks and coherence metrics."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Optional

import numpy as np

from .constants import (
    ALPHA,
    CI_FRACTION_REQUIRED,
    CI_TARGET,
    DT,
    KAPPA_BARE_DEFAULT,
    KAPPA_CAP,
    N_STEPS,
    NOISE_DEFAULT,
    TOTAL_TIME,
)
from .networks import meanfield, regular_lattice, scale_free, smallworld, symmetric_modules
from .telascura import TelascuraLattice


class NetworkType(str, Enum):
    MEANFIELD = "meanfield"
    LATTICE = "lattice"
    SMALLWORLD = "smallworld"
    SCALEFREE = "scalefree"
    SYMMETRICMODULES = "symmetricmodules"


@dataclass
class SimulationResult:
    time: np.ndarray
    ci_global: np.ndarray
    ci_modules: Optional[list[np.ndarray]]
    kappa_eff: float
    effective_energy: np.ndarray
    power_efficiency: np.ndarray
    governance_score: np.ndarray
    mean_ci: float
    min_ci: float
    initial_ci: float
    final_ci: float
    pct_time_ge_target: float
    threshold_kappa_bare: Optional[float]
    success: bool
    parameters: dict


# Candidate mechanisms beyond pure gain rescaling (hypotheses only — not physics claims).
MECHANISM_NONE = "none"
MECHANISM_NOISE_SUPPRESSION = "noise_suppression"
MECHANISM_FREQ_NARROWING = "freq_narrowing"
MECHANISM_RESIDUAL_MEANFIELD = "residual_meanfield"
VALID_MECHANISMS = {
    MECHANISM_NONE,
    MECHANISM_NOISE_SUPPRESSION,
    MECHANISM_FREQ_NARROWING,
    MECHANISM_RESIDUAL_MEANFIELD,
}


class CMTSimulator:
    """
    Noisy Kuramoto network simulator.

    Base dynamics:
      dθ_i/dt = ω_i + (κ_eff/deg_i) Σ_j A_ij sin(θ_j - θ_i)
               + [optional residual mean-field] + ξ_i

    Gain map (legacy; a reparameterization, not a proven physical effect):
      α ON:  κ_eff = min(κ_bare / α^β, κ_cap)
      α OFF: κ_eff = min(κ_bare, κ_cap)
      Or set fixed_kappa_eff to hold κ_eff fixed (matched-κ_eff controls).

    Candidate mechanisms (independent of the gain map; tested with matched κ_eff):
      none                 — only κ_eff / noise / ω act
      noise_suppression    — noise_eff = noise * α  (quieter when mechanism on)
      freq_narrowing       — ω std = base_ω_std * α / α0  with α0=α (narrower spread)
      residual_meanfield   — add κ_res·R·sin(ψ-θ_i) with κ_res = residual_strength

    init_mode:
      near_sync — phases ~ N(0, 0.15)  [retention]
      random    — uniform [0, 2π)      [formation]
    """

    def __init__(
        self,
        network_type: NetworkType = NetworkType.MEANFIELD,
        n_nodes: int = 100,
        seed: int = 17,
        alpha_on: bool = True,
        kappa_bare: float = KAPPA_BARE_DEFAULT,
        kappa_cap: float = KAPPA_CAP,
        beta_scaling: float = 1.0,
        blend_a: float = 0.0,
        blend_b: float = 1.0,
        noise: float = NOISE_DEFAULT,
        dt: float = DT,
        total_time: float = TOTAL_TIME,
        c_inter: float = 0.10,
        p_in: float = 0.05,
        init_mode: str = "near_sync",
        fixed_kappa_eff: Optional[float] = None,
        mechanism: str = MECHANISM_NONE,
        residual_strength: float = 0.20,
        base_omega_std: float = 0.02,
    ):
        self.network_type = network_type
        self.n_nodes = n_nodes
        self.seed = seed
        self.alpha_on = alpha_on
        self.kappa_bare = kappa_bare
        self.kappa_cap = kappa_cap
        self.beta_scaling = beta_scaling
        self.blend_a = blend_a
        self.blend_b = blend_b
        self.noise = noise
        self.dt = dt
        self.total_time = total_time
        self.c_inter = c_inter
        self.p_in = p_in
        if init_mode not in ("near_sync", "random"):
            raise ValueError(f"init_mode must be 'near_sync' or 'random', got {init_mode!r}")
        self.init_mode = init_mode
        self.fixed_kappa_eff = fixed_kappa_eff
        if mechanism not in VALID_MECHANISMS:
            raise ValueError(f"mechanism must be one of {sorted(VALID_MECHANISMS)}, got {mechanism!r}")
        self.mechanism = mechanism
        self.residual_strength = float(residual_strength)
        self.base_omega_std = float(base_omega_std)
        self.rng = np.random.default_rng(seed)
        self.modules: Optional[list[list[int]]] = None
        self.adjacency = self._build_adjacency()
        self.lattice = TelascuraLattice(self.adjacency)

    def _build_adjacency(self) -> np.ndarray:
        if self.network_type == NetworkType.MEANFIELD:
            return meanfield(self.n_nodes)
        if self.network_type == NetworkType.LATTICE:
            return regular_lattice(self.n_nodes)
        if self.network_type == NetworkType.SMALLWORLD:
            return smallworld(self.n_nodes, seed=self.seed)
        if self.network_type == NetworkType.SCALEFREE:
            return scale_free(self.n_nodes, seed=self.seed)
        if self.network_type == NetworkType.SYMMETRICMODULES:
            a, mods = symmetric_modules(
                n_modules=4,
                nodes_per_module=25,
                p_in=self.p_in,
                c_inter=self.c_inter,
                seed=self.seed,
            )
            self.n_nodes = a.shape[0]
            self.modules = mods
            return a
        raise ValueError(f"Unknown network type: {self.network_type}")

    def kappa_effective(self) -> float:
        if self.fixed_kappa_eff is not None:
            return min(float(self.fixed_kappa_eff), self.kappa_cap)
        if not self.alpha_on:
            return min(self.kappa_bare, self.kappa_cap)
        if self.blend_a > 0 or self.blend_b != 1.0:
            denom = self.blend_a + self.blend_b * ALPHA
            raw = self.kappa_bare / max(denom, 1e-12)
        else:
            raw = self.kappa_bare / (ALPHA ** self.beta_scaling)
        return min(raw, self.kappa_cap)

    def noise_effective(self) -> float:
        """Noise intensity after optional mechanism (not part of gain map)."""
        if self.mechanism == MECHANISM_NOISE_SUPPRESSION:
            # Hypothesis: α suppresses phase noise (σ → σ·α). Computational only.
            return self.noise * ALPHA
        return self.noise

    def omega_std_effective(self) -> float:
        """Natural-frequency dispersion after optional mechanism."""
        if self.mechanism == MECHANISM_FREQ_NARROWING:
            # Hypothesis: α narrows frequency spread (σ_ω → σ_ω·α / α_ref, α_ref=α → σ_ω·1
            # when written as base*α; use base_omega_std * α / 0.01 scale so effect is visible:
            # σ_ω = base * α / ALPHA  would be identity. Use σ_ω = base * α / 0.05.
            return self.base_omega_std * (ALPHA / 0.05)
        return self.base_omega_std

    def residual_kappa(self) -> float:
        """Extra global mean-field drive (independent of network κ_eff gain map)."""
        if self.mechanism == MECHANISM_RESIDUAL_MEANFIELD:
            return self.residual_strength
        return 0.0

    def kappa_bare_for_target_eff(self, target_kappa_eff: float) -> float:
        """
        Invert the gain map so that kappa_effective() == min(target, kappa_cap)
        (ignoring floating-point and cap edge cases).

        α off: κ_bare = target
        α on (β form): κ_bare = target * α^β
        α on (blend):  κ_bare = target * (a + b·α)
        """
        target = min(float(target_kappa_eff), self.kappa_cap)
        if not self.alpha_on:
            return target
        if self.blend_a > 0 or self.blend_b != 1.0:
            denom = self.blend_a + self.blend_b * ALPHA
            return target * max(denom, 1e-12)
        return target * (ALPHA ** self.beta_scaling)

    @staticmethod
    def coherence_index(theta: np.ndarray) -> float:
        z = np.mean(np.exp(1j * theta))
        return float(np.abs(z))

    def module_ci(self, theta: np.ndarray) -> list[float]:
        if not self.modules:
            return []
        return [self.coherence_index(theta[m]) for m in self.modules]

    def _initial_theta(self, n: int) -> np.ndarray:
        if self.init_mode == "random":
            return self.rng.uniform(0.0, 2.0 * np.pi, n)
        # Legacy near-synchronized ensemble (tests retention, not formation)
        return self.rng.normal(0, 0.15, n) % (2 * np.pi)

    def run(self) -> SimulationResult:
        n = self.n_nodes
        steps = int(self.total_time / self.dt)
        kappa_eff = self.kappa_effective()
        noise_eff = self.noise_effective()
        omega_std = self.omega_std_effective()
        kappa_res = self.residual_kappa()
        degrees = np.maximum(self.adjacency.sum(axis=1), 1.0)

        theta = self._initial_theta(n)
        omega = self.rng.normal(0, omega_std, n)

        times = np.linspace(0, self.total_time, steps + 1)
        ci_global = np.zeros(steps + 1)
        ci_modules_ts: list[list[float]] = []
        e_eff = np.zeros(steps + 1)
        power_eff = np.zeros(steps + 1)
        gov = np.zeros(steps + 1)

        ci_global[0] = self.coherence_index(theta)
        if self.modules:
            ci_modules_ts.append(self.module_ci(theta))
        e_eff[0] = self.lattice.model_energy(kappa_eff)
        power_eff[0] = ci_global[0] ** 2
        gov[0] = 0.0

        sqrt_dt_noise = np.sqrt(2 * noise_eff * self.dt)

        for step in range(1, steps + 1):
            coupling = np.zeros(n)
            for i in range(n):
                neighbors = np.where(self.adjacency[i] > 0)[0]
                if len(neighbors) == 0:
                    continue
                weights = self.adjacency[i, neighbors]
                coupling[i] = np.sum(weights * np.sin(theta[neighbors] - theta[i])) / degrees[i]

            # Optional residual global mean-field (Kuramoto order-parameter drive)
            residual = 0.0
            if kappa_res > 0.0:
                z = np.mean(np.exp(1j * theta))
                r = float(np.abs(z))
                psi = float(np.angle(z))
                residual = kappa_res * r * np.sin(psi - theta)

            dtheta = omega + kappa_eff * coupling + residual + self.rng.normal(0, sqrt_dt_noise, n)
            theta = (theta + dtheta * self.dt) % (2 * np.pi)

            ci_global[step] = self.coherence_index(theta)
            if self.modules:
                ci_modules_ts.append(self.module_ci(theta))
            e_eff[step] = self.lattice.model_energy(kappa_eff)
            power_eff[step] = ci_global[step] ** 2
            gov[step] = gov[step - 1] + self.dt * ci_global[step] * 0.001

        pct = 100.0 * np.sum(ci_global >= CI_TARGET) / len(ci_global)
        success = bool(pct >= CI_FRACTION_REQUIRED * 100 and float(np.mean(ci_global)) >= CI_TARGET)
        mod_arrays = None
        if ci_modules_ts:
            mod_arrays = [
                np.array([ci_modules_ts[t][m] for t in range(len(ci_modules_ts))])
                for m in range(len(self.modules))
            ]

        return SimulationResult(
            time=times,
            ci_global=ci_global,
            ci_modules=mod_arrays,
            kappa_eff=kappa_eff,
            effective_energy=e_eff,
            power_efficiency=power_eff,
            governance_score=gov,
            mean_ci=float(np.mean(ci_global)),
            min_ci=float(np.min(ci_global)),
            initial_ci=float(ci_global[0]),
            final_ci=float(ci_global[-1]),
            pct_time_ge_target=float(pct),
            threshold_kappa_bare=None,
            success=success,
            parameters={
                "network": self.network_type.value,
                "alpha_on": self.alpha_on,
                "kappa_bare": self.kappa_bare,
                "kappa_cap": self.kappa_cap,
                "beta_scaling": self.beta_scaling,
                "noise": self.noise,
                "noise_eff": noise_eff,
                "omega_std": omega_std,
                "mechanism": self.mechanism,
                "residual_strength": kappa_res,
                "fixed_kappa_eff": self.fixed_kappa_eff,
                "seed": self.seed,
                "dt": self.dt,
                "total_time": self.total_time,
                "c_inter": self.c_inter,
                "p_in": self.p_in,
                "init_mode": self.init_mode,
            },
        )

    @staticmethod
    def default_kappa_grid(alpha_on: bool, init_mode: str = "near_sync") -> np.ndarray:
        """Search grids tuned for α on/off and initial-condition regime."""
        if init_mode == "random":
            # Formation from disorder needs a wider / higher search range.
            if alpha_on:
                return np.unique(
                    np.concatenate(
                        [
                            np.linspace(0.001, 0.020, 12),
                            np.linspace(0.020, 0.080, 10),
                        ]
                    )
                )
            return np.unique(
                np.concatenate(
                    [
                        np.linspace(0.05, 1.0, 12),
                        np.linspace(1.0, 12.0, 12),
                    ]
                )
            )
        if alpha_on:
            return np.linspace(0.005, 0.020, 16)
        return np.linspace(0.10, 8.0, 25)

    def find_threshold_kappa(
        self,
        kappa_grid: Optional[np.ndarray] = None,
        criterion_pct: float = CI_FRACTION_REQUIRED * 100,
    ) -> Optional[float]:
        """Minimum κ_bare for pct_time_ge_target >= criterion_pct and mean CI >= target."""
        original_kb = self.kappa_bare
        if kappa_grid is None:
            kappa_grid = self.default_kappa_grid(self.alpha_on, self.init_mode)
        for kb in kappa_grid:
            self.kappa_bare = float(kb)
            # Reset RNG so each κ probe is comparable for this seed
            self.rng = np.random.default_rng(self.seed)
            res = self.run()
            if res.pct_time_ge_target >= criterion_pct and res.mean_ci >= CI_TARGET:
                self.kappa_bare = original_kb
                self.rng = np.random.default_rng(self.seed)
                return float(kb)
        self.kappa_bare = original_kb
        self.rng = np.random.default_rng(self.seed)
        return None

    def to_csv_rows(self, result: SimulationResult) -> list[dict]:
        rows = []
        for i, t in enumerate(result.time):
            row = {
                "time": t,
                "CI": result.ci_global[i],
                "Effective_Energy": result.effective_energy[i],
                "Power_Efficiency": result.power_efficiency[i],
                "Governance_Score": result.governance_score[i],
                "kappa_eff": result.kappa_eff,
            }
            rows.append(row)
        return rows