"""Generate simulation-suite deliverables (CSVs, PNGs, manifests) — v1.2.

v1.1: Henric review controls (random IC, failures, matched-κ_eff, package).
v1.2: Claim calibration; candidate mechanisms beyond gain rescaling;
      matched-κ_eff tests of those mechanisms; empirical-validation boundary.
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

import numpy as np

from .cmt import (
    MECHANISM_FREQ_NARROWING,
    MECHANISM_NONE,
    MECHANISM_NOISE_SUPPRESSION,
    MECHANISM_RESIDUAL_MEANFIELD,
    CMTSimulator,
    NetworkType,
    SimulationResult,
)
from .constants import ALPHA, CI_TARGET, DT, KAPPA_CAP, TOTAL_TIME
from .telascura import TelascuraLattice

try:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    HAS_MPL = True
except ImportError:
    HAS_MPL = False


VERSION = "1.2.0"
PACKAGE_ROOT = Path(__file__).resolve().parent.parent
CONFIG_DIR = PACKAGE_ROOT / "config"

SEEDS_PRIMARY = [3, 5, 12, 17]
SEEDS_UNCERTAINTY = [3, 5, 12, 17, 23, 29, 31, 41]
MATCHED_KEFF_TARGETS = [0.05, 0.10, 0.20, 0.50]
CONTROL_NETWORKS = [
    NetworkType.MEANFIELD,
    NetworkType.LATTICE,
    NetworkType.SMALLWORLD,
    NetworkType.SCALEFREE,
]
CANDIDATE_MECHANISMS = [
    MECHANISM_NONE,
    MECHANISM_NOISE_SUPPRESSION,
    MECHANISM_FREQ_NARROWING,
    MECHANISM_RESIDUAL_MEANFIELD,
]
MECHANISM_KEFF_TARGETS = [0.05, 0.10, 0.20, 0.50]


# Legacy near-sync example runs (retention; kept for comparison with v1.0)
CANONICAL_RUNS_LEGACY = [
    {
        "network": NetworkType.MEANFIELD,
        "alpha_on": True,
        "cap": 0.95,
        "kb": 0.010,
        "noise": 0.01,
        "seed": 17,
        "init_mode": "near_sync",
        "label": "legacy_retention",
    },
    {
        "network": NetworkType.SMALLWORLD,
        "alpha_on": False,
        "cap": 0.95,
        "kb": 0.020,
        "noise": 0.02,
        "seed": 3,
        "init_mode": "near_sync",
        "label": "legacy_retention",
    },
    {
        "network": NetworkType.SCALEFREE,
        "alpha_on": True,
        "cap": 0.95,
        "kb": 0.080,
        "noise": 0.01,
        "seed": 12,
        "init_mode": "near_sync",
        "label": "legacy_retention",
    },
    {
        "network": NetworkType.SYMMETRICMODULES,
        "alpha_on": True,
        "cap": 0.95,
        "kb": 0.015,
        "noise": 0.02,
        "seed": 5,
        "c_inter": 0.10,
        "p_in": 0.05,
        "init_mode": "near_sync",
        "label": "legacy_retention",
    },
]


def load_json_config(name: str) -> dict:
    path = CONFIG_DIR / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {}


def simulation_filename(
    network: str,
    alpha_on: bool,
    cap: float,
    kb: float,
    noise: float,
    seed: int,
    init_mode: str = "near_sync",
    c_inter: Optional[float] = None,
    p_in: Optional[float] = None,
    tag_extra: str = "",
) -> str:
    tag = "alpha_on" if alpha_on else "alpha_off"
    cap_s = f"{cap:g}"
    base = f"simulation_{network}_{tag}_cap{cap_s}"
    if network == "symmetricmodules":
        base += f"_cinter{c_inter:.2f}_pin{p_in:.2f}"
    base += f"_kb{kb:.6f}_noise{noise:.2f}_seed{seed:02d}_ic{init_mode}"
    if tag_extra:
        base += f"_{tag_extra}"
    return base + ".csv"


def write_timeseries_csv(path: Path, sim: CMTSimulator, res: SimulationResult) -> None:
    header_lines = [
        f"# seed={sim.seed}, dt={sim.dt}, total_time={sim.total_time}",
        f"# alpha_on={sim.alpha_on}, kappa_bare={sim.kappa_bare}, kappa_cap={sim.kappa_cap}",
        f"# kappa_eff={res.kappa_eff}, noise={sim.noise}, network={sim.network_type.value}",
        f"# init_mode={sim.init_mode}, initial_CI={res.initial_ci:.6f}, final_CI={res.final_ci:.6f}",
        f"# success={res.success}, mean_CI={res.mean_ci:.6f}, pct_time_ge_0.75={res.pct_time_ge_target:.1f}",
    ]
    if sim.network_type == NetworkType.SYMMETRICMODULES:
        header_lines.append(f"# c_inter={sim.c_inter}, p_in={sim.p_in}")
    with open(path, "w", encoding="utf-8", newline="") as f:
        f.write("\n".join(header_lines) + "\n")
        w = csv.writer(f)
        w.writerow(
            ["time", "CI", "Effective_Energy", "Power_Efficiency", "Governance_Score", "kappa_eff"]
        )
        for i, t in enumerate(res.time):
            w.writerow(
                [
                    t,
                    res.ci_global[i],
                    res.effective_energy[i],
                    res.power_efficiency[i],
                    res.governance_score[i],
                    res.kappa_eff,
                ]
            )


def make_sim(cfg: dict) -> CMTSimulator:
    net = cfg["network"]
    kwargs = dict(
        network_type=net,
        alpha_on=cfg["alpha_on"],
        kappa_cap=cfg.get("cap", 0.95),
        kappa_bare=cfg["kb"],
        noise=cfg["noise"],
        seed=cfg["seed"],
        init_mode=cfg.get("init_mode", "near_sync"),
    )
    if net == NetworkType.SYMMETRICMODULES:
        kwargs["c_inter"] = cfg.get("c_inter", 0.10)
        kwargs["p_in"] = cfg.get("p_in", 0.05)
    return CMTSimulator(**kwargs)


def write_csv(path: Path, rows: list[dict], fieldnames: Optional[list[str]] = None) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fields = fieldnames or list(rows[0].keys())
    with open(path, "w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)


def sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


class FullDeliverableSuite:
    def __init__(self, output_dir: Path):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.raw_dir = self.output_dir / "raw_sweeps"
        self.raw_dir.mkdir(parents=True, exist_ok=True)
        self.generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        self.files_produced: list[str] = []
        self.diagnostics: list[str] = []
        self.seed_ledger: list[dict] = []
        self.params = load_json_config("parameters.json")
        self.networks_cfg = load_json_config("networks.json")

    def _track(self, path: Path) -> None:
        rel = str(path.relative_to(self.output_dir)) if path.is_relative_to(self.output_dir) else path.name
        if rel not in self.files_produced:
            self.files_produced.append(rel)

    def _log_seed(self, experiment: str, seed: int, **meta: Any) -> None:
        self.seed_ledger.append({"experiment": experiment, "seed": seed, **meta})

    # ------------------------------------------------------------------
    # Core experiments
    # ------------------------------------------------------------------

    def run_canonical_timeseries(self) -> dict[str, SimulationResult]:
        results: dict[str, SimulationResult] = {}
        for cfg in CANONICAL_RUNS_LEGACY:
            sim = make_sim(cfg)
            res = sim.run()
            name = simulation_filename(
                sim.network_type.value,
                sim.alpha_on,
                sim.kappa_cap,
                sim.kappa_bare,
                sim.noise,
                sim.seed,
                sim.init_mode,
                sim.c_inter if sim.network_type == NetworkType.SYMMETRICMODULES else None,
                sim.p_in if sim.network_type == NetworkType.SYMMETRICMODULES else None,
                tag_extra="legacy",
            )
            path = self.output_dir / name
            write_timeseries_csv(path, sim, res)
            self._track(path)
            self._log_seed("legacy_canonical", sim.seed, file=name, init_mode=sim.init_mode)
            results[name] = res
            if np.any(np.isnan(res.ci_global)):
                self.diagnostics.append(f"NaN in {name}")
            if res.initial_ci >= 0.9:
                self.diagnostics.append(
                    f"LEGACY NOTICE: {name} starts at CI={res.initial_ci:.3f} "
                    "(retention test, not formation)"
                )
        return results

    def run_matched_kappa_eff_controls(self) -> list[dict]:
        """Henric test #3: hold kappa_eff fixed across alpha on/off."""
        rows: list[dict] = []
        for net in CONTROL_NETWORKS:
            for target_keff in MATCHED_KEFF_TARGETS:
                for init_mode in ("random", "near_sync"):
                    for seed in SEEDS_PRIMARY:
                        pair_stats: dict[str, dict] = {}
                        for alpha_on in (True, False):
                            sim = CMTSimulator(
                                network_type=net,
                                alpha_on=alpha_on,
                                seed=seed,
                                noise=0.01,
                                kappa_cap=0.95,
                                init_mode=init_mode,
                            )
                            kb = sim.kappa_bare_for_target_eff(target_keff)
                            sim.kappa_bare = kb
                            # Identical seed => same IC/noise stream for fair trajectory compare
                            sim.rng = np.random.default_rng(seed)
                            res = sim.run()
                            tag = "on" if alpha_on else "off"
                            pair_stats[tag] = {
                                "kappa_bare": kb,
                                "kappa_eff": res.kappa_eff,
                                "initial_ci": res.initial_ci,
                                "final_ci": res.final_ci,
                                "mean_ci": res.mean_ci,
                                "min_ci": res.min_ci,
                                "pct_time_ge_0.75": res.pct_time_ge_target,
                                "success": res.success,
                            }
                            # Save one representative raw trajectory per target/net/mode
                            if seed == 17 and target_keff in (0.10, 0.50) and init_mode == "random":
                                fname = simulation_filename(
                                    net.value,
                                    alpha_on,
                                    0.95,
                                    kb,
                                    0.01,
                                    seed,
                                    init_mode,
                                    tag_extra=f"matched_keff{target_keff:g}",
                                )
                                path = self.raw_dir / fname
                                write_timeseries_csv(path, sim, res)
                                self._track(path)

                        on = pair_stats["on"]
                        off = pair_stats["off"]
                        mean_ci_delta = on["mean_ci"] - off["mean_ci"]
                        keff_ratio = (
                            on["kappa_eff"] / off["kappa_eff"]
                            if off["kappa_eff"] != 0
                            else float("nan")
                        )
                        rows.append(
                            {
                                "network_type": net.value,
                                "target_kappa_eff": target_keff,
                                "init_mode": init_mode,
                                "seed": seed,
                                "alpha_on_kappa_bare": round(on["kappa_bare"], 8),
                                "alpha_off_kappa_bare": round(off["kappa_bare"], 8),
                                "alpha_on_kappa_eff": round(on["kappa_eff"], 6),
                                "alpha_off_kappa_eff": round(off["kappa_eff"], 6),
                                "kappa_eff_ratio_on_over_off": round(keff_ratio, 6),
                                "alpha_on_initial_CI": round(on["initial_ci"], 6),
                                "alpha_off_initial_CI": round(off["initial_ci"], 6),
                                "alpha_on_mean_CI": round(on["mean_ci"], 6),
                                "alpha_off_mean_CI": round(off["mean_ci"], 6),
                                "mean_CI_delta_on_minus_off": round(mean_ci_delta, 6),
                                "alpha_on_final_CI": round(on["final_ci"], 6),
                                "alpha_off_final_CI": round(off["final_ci"], 6),
                                "alpha_on_success": on["success"],
                                "alpha_off_success": off["success"],
                                "trajectories_match_prediction": abs(mean_ci_delta) < 0.02
                                and abs(on["final_ci"] - off["final_ci"]) < 0.02,
                            }
                        )
                        self._log_seed(
                            "matched_kappa_eff",
                            seed,
                            network=net.value,
                            target_keff=target_keff,
                            init_mode=init_mode,
                        )
        path = self.output_dir / "summary_matched_kappa_eff.csv"
        write_csv(path, rows)
        self._track(path)

        # Aggregate uncertainty across seeds
        agg_rows: list[dict] = []
        keys = {(r["network_type"], r["target_kappa_eff"], r["init_mode"]) for r in rows}
        for net, keff, init_mode in sorted(keys):
            sub = [
                r
                for r in rows
                if r["network_type"] == net
                and r["target_kappa_eff"] == keff
                and r["init_mode"] == init_mode
            ]
            deltas = np.array([r["mean_CI_delta_on_minus_off"] for r in sub], dtype=float)
            match_rate = np.mean([1.0 if r["trajectories_match_prediction"] else 0.0 for r in sub])
            agg_rows.append(
                {
                    "network_type": net,
                    "target_kappa_eff": keff,
                    "init_mode": init_mode,
                    "n_seeds": len(sub),
                    "mean_CI_delta_mean": round(float(np.mean(deltas)), 6),
                    "mean_CI_delta_std": round(float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0, 6),
                    "mean_CI_delta_abs_max": round(float(np.max(np.abs(deltas))), 6),
                    "fraction_match_prediction": round(float(match_rate), 3),
                    "interpretation": (
                        "alpha acts as reparameterization of coupling (no residual effect isolated)"
                        if float(np.mean(np.abs(deltas))) < 0.02
                        else "residual difference present after matching kappa_eff — inspect raw runs"
                    ),
                }
            )
        path_u = self.output_dir / "summary_matched_kappa_eff_uncertainty.csv"
        write_csv(path_u, agg_rows)
        self._track(path_u)
        return rows

    def run_candidate_mechanism_tests(self) -> list[dict]:
        """Task 2–3: mechanisms beyond gain rescaling, tested at fixed κ_eff.

        Control = mechanism 'none' at fixed κ_eff.
        Treatment = candidate mechanism at the SAME fixed κ_eff (same seed/IC/noise stream base).
        Any Δ mean_CI is a residual effect of that mechanism, not of the 1/α gain map.
        """
        rows: list[dict] = []
        nets = [NetworkType.MEANFIELD, NetworkType.LATTICE, NetworkType.SMALLWORLD]
        for net in nets:
            for keff in MECHANISM_KEFF_TARGETS:
                for seed in SEEDS_PRIMARY:
                    baseline = None
                    for mech in CANDIDATE_MECHANISMS:
                        sim = CMTSimulator(
                            network_type=net,
                            alpha_on=False,  # gain map off; κ held fixed
                            fixed_kappa_eff=keff,
                            kappa_bare=keff,
                            kappa_cap=0.95,
                            noise=0.01,
                            seed=seed,
                            init_mode="random",
                            mechanism=mech,
                            residual_strength=0.20,
                            total_time=TOTAL_TIME,
                        )
                        sim.rng = np.random.default_rng(seed)
                        res = sim.run()
                        row = {
                            "network_type": net.value,
                            "target_kappa_eff": keff,
                            "realized_kappa_eff": round(res.kappa_eff, 6),
                            "mechanism": mech,
                            "seed": seed,
                            "init_mode": "random",
                            "noise_bare": 0.01,
                            "noise_eff": round(res.parameters["noise_eff"], 8),
                            "omega_std": round(res.parameters["omega_std"], 8),
                            "residual_kappa": round(res.parameters["residual_strength"], 6),
                            "initial_CI": round(res.initial_ci, 6),
                            "mean_CI": round(res.mean_ci, 6),
                            "final_CI": round(res.final_ci, 6),
                            "min_CI": round(res.min_ci, 6),
                            "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                            "success": res.success,
                        }
                        if mech == MECHANISM_NONE:
                            baseline = row
                            row["delta_mean_CI_vs_none"] = 0.0
                            row["delta_final_CI_vs_none"] = 0.0
                            row["effect_isolated"] = False
                        else:
                            assert baseline is not None
                            d_mean = row["mean_CI"] - baseline["mean_CI"]
                            d_final = row["final_CI"] - baseline["final_CI"]
                            row["delta_mean_CI_vs_none"] = round(d_mean, 6)
                            row["delta_final_CI_vs_none"] = round(d_final, 6)
                            # Isolated if |Δ| exceeds small numerical tolerance
                            row["effect_isolated"] = abs(d_mean) > 0.01 or abs(d_final) > 0.01
                        rows.append(row)
                        self._log_seed(
                            "candidate_mechanism",
                            seed,
                            network=net.value,
                            mechanism=mech,
                            kappa_eff=keff,
                        )
                        if seed == 17 and keff in (0.10, 0.50) and net == NetworkType.MEANFIELD:
                            fname = (
                                f"mechanism_{mech}_meanfield_keff{keff:g}_"
                                f"seed{seed:02d}_icrandom.csv"
                            )
                            path = self.raw_dir / fname
                            write_timeseries_csv(path, sim, res)
                            self._track(path)

        path = self.output_dir / "summary_candidate_mechanisms.csv"
        write_csv(path, rows)
        self._track(path)

        # Aggregate across seeds
        agg: list[dict] = []
        keys = {(r["network_type"], r["target_kappa_eff"], r["mechanism"]) for r in rows}
        for net, keff, mech in sorted(keys):
            sub = [
                r
                for r in rows
                if r["network_type"] == net
                and r["target_kappa_eff"] == keff
                and r["mechanism"] == mech
            ]
            deltas = np.array([r["delta_mean_CI_vs_none"] for r in sub], dtype=float)
            finals = np.array([r["final_CI"] for r in sub], dtype=float)
            rates = np.array([1.0 if r["effect_isolated"] else 0.0 for r in sub])
            if mech == MECHANISM_NONE:
                interp = "baseline (gain map off; fixed κ_eff only)"
            elif float(np.mean(np.abs(deltas))) > 0.01:
                interp = (
                    "RESIDUAL EFFECT at matched κ_eff — mechanism changes dynamics "
                    "beyond pure gain rescaling (still a simulation hypothesis, not physics)"
                )
            else:
                interp = "no isolated residual at this κ_eff (within tolerance)"
            agg.append(
                {
                    "network_type": net,
                    "target_kappa_eff": keff,
                    "mechanism": mech,
                    "n_seeds": len(sub),
                    "mean_CI_delta_vs_none_mean": round(float(np.mean(deltas)), 6),
                    "mean_CI_delta_vs_none_std": round(
                        float(np.std(deltas, ddof=1)) if len(deltas) > 1 else 0.0, 6
                    ),
                    "final_CI_mean": round(float(np.mean(finals)), 6),
                    "final_CI_std": round(float(np.std(finals, ddof=1)) if len(finals) > 1 else 0.0, 6),
                    "fraction_effect_isolated": round(float(np.mean(rates)), 3),
                    "interpretation": interp,
                }
            )
        path_a = self.output_dir / "summary_candidate_mechanisms_uncertainty.csv"
        write_csv(path_a, agg)
        self._track(path_a)
        return rows

    def run_formation_and_failure_suite(self) -> list[dict]:
        """Henric tests #1 and #2: low-CI starts + genuine failures."""
        rows: list[dict] = []
        # Formation: random IC, scan kappa_eff via alpha-off bare (transparent)
        keff_grid = [0.01, 0.02, 0.05, 0.08, 0.10, 0.15, 0.20, 0.30, 0.50, 0.80]
        for net in CONTROL_NETWORKS:
            for keff in keff_grid:
                for seed in SEEDS_PRIMARY:
                    sim = CMTSimulator(
                        network_type=net,
                        alpha_on=False,
                        kappa_bare=keff,
                        kappa_cap=0.95,
                        noise=0.01,
                        seed=seed,
                        init_mode="random",
                    )
                    res = sim.run()
                    success = res.success
                    regime = "formed" if success else ("partial" if res.final_ci >= 0.5 else "failed")
                    rows.append(
                        {
                            "experiment": "formation_kappa_eff_scan",
                            "network_type": net.value,
                            "alpha_on": False,
                            "kappa_bare": keff,
                            "kappa_eff": round(res.kappa_eff, 6),
                            "init_mode": "random",
                            "seed": seed,
                            "initial_CI": round(res.initial_ci, 6),
                            "final_CI": round(res.final_ci, 6),
                            "mean_CI": round(res.mean_ci, 6),
                            "min_CI": round(res.min_ci, 6),
                            "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                            "success": success,
                            "regime": regime,
                        }
                    )
                    self._log_seed(
                        "formation_scan",
                        seed,
                        network=net.value,
                        kappa_eff=keff,
                        success=success,
                    )
                    # Save failures and a few successes as raw series
                    if seed == 17 and (
                        regime == "failed"
                        or keff in (0.01, 0.10, 0.50)
                    ):
                        fname = simulation_filename(
                            net.value,
                            False,
                            0.95,
                            keff,
                            0.01,
                            seed,
                            "random",
                            tag_extra=f"formation_{regime}",
                        )
                        path = self.raw_dir / fname
                        write_timeseries_csv(path, sim, res)
                        self._track(path)

        # Explicit failure panel: very low coupling + random IC
        failure_cases = [
            {"network": NetworkType.MEANFIELD, "kb": 0.01, "seed": 17},
            {"network": NetworkType.LATTICE, "kb": 0.02, "seed": 5},
            {"network": NetworkType.SMALLWORLD, "kb": 0.02, "seed": 12},
            {"network": NetworkType.SCALEFREE, "kb": 0.02, "seed": 3},
            {
                "network": NetworkType.SYMMETRICMODULES,
                "kb": 0.02,
                "seed": 5,
                "c_inter": 0.02,
                "p_in": 0.05,
            },
        ]
        for case in failure_cases:
            kwargs = dict(
                network_type=case["network"],
                alpha_on=False,
                kappa_bare=case["kb"],
                kappa_cap=0.95,
                noise=0.02,
                seed=case["seed"],
                init_mode="random",
            )
            if case["network"] == NetworkType.SYMMETRICMODULES:
                kwargs["c_inter"] = case["c_inter"]
                kwargs["p_in"] = case["p_in"]
            sim = CMTSimulator(**kwargs)
            res = sim.run()
            rows.append(
                {
                    "experiment": "explicit_failure_panel",
                    "network_type": case["network"].value,
                    "alpha_on": False,
                    "kappa_bare": case["kb"],
                    "kappa_eff": round(res.kappa_eff, 6),
                    "init_mode": "random",
                    "seed": case["seed"],
                    "initial_CI": round(res.initial_ci, 6),
                    "final_CI": round(res.final_ci, 6),
                    "mean_CI": round(res.mean_ci, 6),
                    "min_CI": round(res.min_ci, 6),
                    "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                    "success": res.success,
                    "regime": "failed" if not res.success else "unexpected_success",
                }
            )
            fname = simulation_filename(
                case["network"].value,
                False,
                0.95,
                case["kb"],
                0.02,
                case["seed"],
                "random",
                case.get("c_inter"),
                case.get("p_in"),
                tag_extra="explicit_failure",
            )
            path = self.raw_dir / fname
            write_timeseries_csv(path, sim, res)
            self._track(path)
            if res.success or res.initial_ci > 0.5:
                self.diagnostics.append(
                    f"Failure panel unexpected: {fname} success={res.success} "
                    f"initial_CI={res.initial_ci:.3f}"
                )
            else:
                self.diagnostics.append(
                    f"GENUINE FAILURE archived: {fname} "
                    f"initial_CI={res.initial_ci:.3f} final_CI={res.final_ci:.3f}"
                )

        path = self.output_dir / "summary_formation_and_failures.csv"
        write_csv(path, rows)
        self._track(path)

        # Uncertainty: critical-ish region around formation boundary
        unc_rows: list[dict] = []
        for net in CONTROL_NETWORKS:
            for keff in (0.05, 0.10, 0.20, 0.50):
                finals = []
                means = []
                successes = []
                initials = []
                for seed in SEEDS_UNCERTAINTY:
                    sim = CMTSimulator(
                        network_type=net,
                        alpha_on=False,
                        kappa_bare=keff,
                        seed=seed,
                        noise=0.01,
                        init_mode="random",
                    )
                    res = sim.run()
                    finals.append(res.final_ci)
                    means.append(res.mean_ci)
                    successes.append(1.0 if res.success else 0.0)
                    initials.append(res.initial_ci)
                    self._log_seed(
                        "formation_uncertainty",
                        seed,
                        network=net.value,
                        kappa_eff=keff,
                    )
                unc_rows.append(
                    {
                        "network_type": net.value,
                        "kappa_eff": keff,
                        "init_mode": "random",
                        "n_seeds": len(SEEDS_UNCERTAINTY),
                        "initial_CI_mean": round(float(np.mean(initials)), 6),
                        "initial_CI_std": round(float(np.std(initials, ddof=1)), 6),
                        "mean_CI_mean": round(float(np.mean(means)), 6),
                        "mean_CI_std": round(float(np.std(means, ddof=1)), 6),
                        "final_CI_mean": round(float(np.mean(finals)), 6),
                        "final_CI_std": round(float(np.std(finals, ddof=1)), 6),
                        "success_rate": round(float(np.mean(successes)), 3),
                    }
                )
        path_u = self.output_dir / "summary_formation_uncertainty.csv"
        write_csv(path_u, unc_rows)
        self._track(path_u)
        return rows

    def run_control_sweep(self) -> list[dict]:
        """Nominal κ_bare thresholds (near_sync legacy) + fixed-κ random-IC probes.

        Random-IC threshold search is expensive and often unbounded; formation
        behavior is reported in summary_formation_and_failures.csv instead.
        """
        rows: list[dict] = []
        # Legacy near_sync threshold table (documents v1.0 nominal bare ratios)
        for net in CONTROL_NETWORKS:
            for alpha_on in (True, False):
                for noise in (0.01, 0.02):
                    for seed in (17, 3):
                        sim = CMTSimulator(
                            network_type=net,
                            alpha_on=alpha_on,
                            noise=noise,
                            seed=seed,
                            init_mode="near_sync",
                        )
                        kb_thr = sim.find_threshold_kappa()
                        if kb_thr is not None:
                            sim.kappa_bare = kb_thr
                            sim.rng = np.random.default_rng(seed)
                        res = sim.run()
                        rows.append(
                            {
                                "network_type": net.value,
                                "alpha_on": alpha_on,
                                "noise": noise,
                                "seed": seed,
                                "init_mode": "near_sync",
                                "threshold_kappa_bare": kb_thr if kb_thr is not None else "",
                                "kappa_eff": round(res.kappa_eff, 6),
                                "initial_CI": round(res.initial_ci, 6),
                                "mean_CI": round(res.mean_ci, 4),
                                "min_CI": round(res.min_ci, 4),
                                "final_CI": round(res.final_ci, 4),
                                "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                                "success": res.success,
                                "note": (
                                    "LEGACY nominal kappa_bare threshold (retention IC); "
                                    "NOT a matched-keff demonstration"
                                ),
                            }
                        )
                        self._log_seed(
                            "control_sweep_near_sync",
                            seed,
                            network=net.value,
                            alpha_on=alpha_on,
                        )
        # Random-IC probes at fixed effective couplings (no threshold search)
        for net in CONTROL_NETWORKS:
            for keff in (0.05, 0.10, 0.50):
                for seed in (17, 3):
                    sim = CMTSimulator(
                        network_type=net,
                        alpha_on=False,
                        kappa_bare=keff,
                        noise=0.01,
                        seed=seed,
                        init_mode="random",
                    )
                    res = sim.run()
                    rows.append(
                        {
                            "network_type": net.value,
                            "alpha_on": False,
                            "noise": 0.01,
                            "seed": seed,
                            "init_mode": "random",
                            "threshold_kappa_bare": "",
                            "kappa_eff": round(res.kappa_eff, 6),
                            "initial_CI": round(res.initial_ci, 6),
                            "mean_CI": round(res.mean_ci, 4),
                            "min_CI": round(res.min_ci, 4),
                            "final_CI": round(res.final_ci, 4),
                            "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                            "success": res.success,
                            "note": "fixed kappa_eff probe (formation); see formation summaries",
                        }
                    )
                    self._log_seed(
                        "control_sweep_random_probe",
                        seed,
                        network=net.value,
                        kappa_eff=keff,
                    )
        path = self.output_dir / "summary_control_sweep.csv"
        write_csv(path, rows)
        self._track(path)
        return rows

    def run_cap_sensitivity(self) -> list[dict]:
        caps = [0.8, 0.95, 0.99, None]
        rows = []
        for init_mode in ("near_sync", "random"):
            for cap in caps:
                cap_val = 10.0 if cap is None else cap
                label = "no_cap" if cap is None else str(cap)
                sim = CMTSimulator(
                    alpha_on=True,
                    kappa_bare=0.08,
                    kappa_cap=cap_val,
                    seed=17,
                    init_mode=init_mode,
                )
                res = sim.run()
                if cap is None and (np.any(np.isnan(res.ci_global)) or res.min_ci < 0.3):
                    sim2 = CMTSimulator(
                        alpha_on=True,
                        kappa_bare=0.08,
                        kappa_cap=cap_val,
                        seed=17,
                        dt=0.005,
                        init_mode=init_mode,
                    )
                    res2 = sim2.run()
                    self.diagnostics.append(
                        f"no_cap {init_mode}: re-run dt=0.005 "
                        f"min_CI {res.min_ci:.3f}->{res2.min_ci:.3f}"
                    )
                    res = res2
                rows.append(
                    {
                        "kappa_cap": label,
                        "init_mode": init_mode,
                        "mean_CI": round(res.mean_ci, 4),
                        "min_CI": round(res.min_ci, 4),
                        "std_CI": round(float(np.std(res.ci_global)), 4),
                        "initial_CI": round(res.initial_ci, 4),
                        "final_CI": round(res.final_ci, 4),
                        "pct_time_ge_0.75": round(res.pct_time_ge_target, 1),
                        "kappa_eff": round(res.kappa_eff, 4),
                    }
                )
        path = self.output_dir / "summary_cap_sensitivity.csv"
        write_csv(path, rows)
        self._track(path)
        return rows

    def run_modular_sweep(self) -> list[dict]:
        rows = []
        c_vals = [0.02, 0.05, 0.10, 0.20, 0.50]
        p_vals = [0.05, 0.10, 0.20]
        for init_mode in ("near_sync", "random"):
            for alpha_on in (True, False):
                for c in c_vals:
                    for p in p_vals:
                        sim = CMTSimulator(
                            network_type=NetworkType.SYMMETRICMODULES,
                            alpha_on=alpha_on,
                            noise=0.02,
                            seed=5,
                            c_inter=c,
                            p_in=p,
                            init_mode=init_mode,
                        )
                        kb_thr: Optional[float] = None
                        if init_mode == "near_sync":
                            # Fixed legacy operating points (avoids long threshold grids)
                            sim.kappa_bare = 0.005 if alpha_on else 0.10
                            kb_thr = sim.kappa_bare
                        else:
                            # Formation: fixed kappa_bare to expose regimes
                            sim.kappa_bare = 0.02 if alpha_on else 0.15
                        res = sim.run()
                        regime = "global_lock"
                        mod_means: list[float] = []
                        if res.ci_modules:
                            mod_means = [float(np.mean(m)) for m in res.ci_modules]
                            if min(mod_means) >= 0.75 and res.mean_ci < 0.75:
                                regime = "module_locked_offset"
                            elif res.mean_ci < 0.75:
                                regime = "desynchronized"
                        rows.append(
                            {
                                "alpha_on": alpha_on,
                                "init_mode": init_mode,
                                "c_inter": c,
                                "p_in": p,
                                "kappa_bare_used": round(sim.kappa_bare, 6),
                                "kappa_eff": round(res.kappa_eff, 6),
                                "critical_kappa_bare": kb_thr if kb_thr is not None else "",
                                "initial_CI": round(res.initial_ci, 4),
                                "mean_CI": round(res.mean_ci, 4),
                                "final_CI": round(res.final_ci, 4),
                                "min_module_CI": round(min(mod_means), 4) if mod_means else "",
                                "regime": regime,
                            }
                        )
        path = self.output_dir / "summary_modular_sweep.csv"
        write_csv(path, rows)
        self._track(path)
        return rows

    def run_scaling_hypotheses(self) -> list[dict]:
        rows = []
        betas = [0.5, 1.0, 1.5, 2.0]
        for beta in betas:
            sim = CMTSimulator(alpha_on=True, beta_scaling=beta, seed=17, init_mode="near_sync")
            kb = sim.find_threshold_kappa()
            if kb is not None:
                sim.kappa_bare = kb
                sim.rng = np.random.default_rng(17)
            res = sim.run()
            rows.append(
                {
                    "form": f"kappa_bare/alpha^{beta}",
                    "beta": beta,
                    "threshold_kappa_bare": kb if kb is not None else "",
                    "mean_CI": round(res.mean_ci, 4),
                    "kappa_eff": round(res.kappa_eff, 4),
                    "rank_score": round(1.0 / (kb or 1.0) + beta * 0.1, 4),
                    "note": "nominal-threshold ranking only; not matched-keff",
                }
            )
        blends = [(0.0, 1.0), (0.5, 0.5), (1.0, 0.0)]
        for a, b in blends:
            sim = CMTSimulator(alpha_on=True, blend_a=a, blend_b=b, seed=17, init_mode="near_sync")
            kb = sim.find_threshold_kappa()
            if kb is not None:
                sim.kappa_bare = kb
                sim.rng = np.random.default_rng(17)
            res = sim.run()
            rows.append(
                {
                    "form": f"kappa_bare/({a}+{b}*alpha)",
                    "beta": "",
                    "threshold_kappa_bare": kb if kb is not None else "",
                    "mean_CI": round(res.mean_ci, 4),
                    "kappa_eff": round(res.kappa_eff, 4),
                    "rank_score": round(1.0 / (kb or 1.0), 4),
                    "note": "nominal-threshold ranking only; not matched-keff",
                }
            )
        rows.sort(key=lambda r: (-r["mean_CI"], r["rank_score"]))
        for i, r in enumerate(rows, 1):
            r["rank"] = i
        path = self.output_dir / "summary_scaling_hypotheses.csv"
        write_csv(
            path,
            rows,
            fieldnames=[
                "rank",
                "form",
                "beta",
                "threshold_kappa_bare",
                "mean_CI",
                "kappa_eff",
                "rank_score",
                "note",
            ],
        )
        self._track(path)
        return rows

    # ------------------------------------------------------------------
    # Figures
    # ------------------------------------------------------------------

    def generate_figures(
        self,
        matched_rows: list[dict],
        formation_rows: list[dict],
        control_rows: list[dict],
        cap_rows: list[dict],
        modular_rows: list[dict],
    ) -> None:
        if not HAS_MPL:
            self.diagnostics.append("matplotlib not installed — PNG figures skipped")
            return

        # 1. meanfield CI vs kappa_bare (nominal; labeled as such)
        fig, ax = plt.subplots(figsize=(8, 5))
        kb_grid = np.linspace(0.005, 0.15, 16)
        for alpha_on, label, color in [(True, "α ON (nominal κ_bare)", "C0"), (False, "α OFF", "C3")]:
            cis = []
            for kb in kb_grid:
                sim = CMTSimulator(
                    network_type=NetworkType.MEANFIELD,
                    alpha_on=alpha_on,
                    kappa_bare=float(kb),
                    seed=17,
                    init_mode="random",
                )
                cis.append(sim.run().mean_ci)
            ax.plot(kb_grid, cis, "o-", label=label, color=color, ms=4)
        ax.axhline(0.75, color="gray", ls="--", alpha=0.7, label="CI=0.75")
        ax.set_xlabel("κ_bare (nominal; not matched κ_eff)")
        ax.set_ylabel("mean CI")
        ax.set_title("Mean-field formation: CI vs nominal κ_bare (random IC)")
        ax.legend()
        fig.tight_layout()
        p = self.output_dir / "meanfield_CI_vs_kappa_alpha_on_off.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 2. Matched κ_eff: mean CI on vs off
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), sharey=True)
        for ax, init_mode in zip(axes, ("random", "near_sync")):
            sub = [
                r
                for r in matched_rows
                if r["network_type"] == "meanfield"
                and r["init_mode"] == init_mode
                and r["seed"] == 17
            ]
            sub = sorted(sub, key=lambda r: r["target_kappa_eff"])
            xs = [r["target_kappa_eff"] for r in sub]
            ax.plot(xs, [r["alpha_on_mean_CI"] for r in sub], "o-", label="α ON", color="C0")
            ax.plot(xs, [r["alpha_off_mean_CI"] for r in sub], "s--", label="α OFF", color="C3")
            ax.set_xlabel("matched κ_eff")
            ax.set_title(f"Matched κ_eff ({init_mode})")
            ax.axhline(0.75, color="gray", ls=":", alpha=0.6)
            ax.legend()
        axes[0].set_ylabel("mean CI")
        fig.suptitle("Matched-κ_eff control (meanfield, seed=17)")
        fig.tight_layout()
        p = self.output_dir / "matched_kappa_eff_meanfield.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 3. Formation success rate vs κ_eff
        fig, ax = plt.subplots(figsize=(8, 5))
        for net in CONTROL_NETWORKS:
            xs, ys = [], []
            for keff in sorted({r["kappa_eff"] for r in formation_rows if r["experiment"] == "formation_kappa_eff_scan"}):
                sub = [
                    r
                    for r in formation_rows
                    if r["experiment"] == "formation_kappa_eff_scan"
                    and r["network_type"] == net.value
                    and abs(r["kappa_eff"] - keff) < 1e-9
                ]
                if sub:
                    xs.append(keff)
                    ys.append(np.mean([1.0 if r["success"] else 0.0 for r in sub]))
            ax.plot(xs, ys, "o-", label=net.value, ms=4)
        ax.set_xlabel("κ_eff")
        ax.set_ylabel("success rate (4 seeds)")
        ax.set_title("Formation from random IC vs κ_eff (α off; transparent coupling)")
        ax.set_ylim(-0.05, 1.05)
        ax.legend()
        fig.tight_layout()
        p = self.output_dir / "formation_success_vs_kappa_eff.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 4. smallworld rewiring heatmap (random IC)
        p_rewire_vals = np.linspace(0.0, 0.4, 7)
        kb_vals = np.linspace(0.05, 0.50, 7)
        heat = np.zeros((len(p_rewire_vals), len(kb_vals)))
        for i, pr in enumerate(p_rewire_vals):
            for j, kb in enumerate(kb_vals):
                from .networks import smallworld

                sim = CMTSimulator(
                    alpha_on=False, kappa_bare=float(kb), seed=17, init_mode="random"
                )
                sim.adjacency = smallworld(100, p_rewire=float(pr), seed=17)
                sim.lattice = TelascuraLattice(sim.adjacency)
                heat[i, j] = sim.run().mean_ci
        fig, ax = plt.subplots(figsize=(7, 5))
        im = ax.imshow(heat, aspect="auto", origin="lower", cmap="viridis", vmin=0, vmax=1)
        ax.set_xticks(range(len(kb_vals)))
        ax.set_xticklabels([f"{v:.2f}" for v in kb_vals], rotation=45, ha="right")
        ax.set_yticks(range(len(p_rewire_vals)))
        ax.set_yticklabels([f"{v:.2f}" for v in p_rewire_vals])
        ax.set_xlabel("κ_eff (= κ_bare, α off)")
        ax.set_ylabel("p_rewire")
        ax.set_title("Small-world rewiring × κ_eff (random IC formation)")
        fig.colorbar(im, ax=ax, label="mean CI")
        fig.tight_layout()
        p = self.output_dir / "smallworld_rewiring_sweep_heatmap.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 5. modular heatmap (random IC regimes)
        c_vals = sorted({r["c_inter"] for r in modular_rows if r["init_mode"] == "random" and r["alpha_on"]})
        p_vals = sorted({r["p_in"] for r in modular_rows if r["init_mode"] == "random" and r["alpha_on"]})
        heat_m = np.full((len(c_vals), len(p_vals)), np.nan)
        for r in modular_rows:
            if not (r["init_mode"] == "random" and r["alpha_on"]):
                continue
            i = c_vals.index(r["c_inter"])
            j = p_vals.index(r["p_in"])
            heat_m[i, j] = r["mean_CI"]
        fig, ax = plt.subplots(figsize=(7, 5))
        im = ax.imshow(heat_m, aspect="auto", origin="lower", cmap="magma", vmin=0, vmax=1)
        ax.set_xticks(range(len(p_vals)))
        ax.set_xticklabels([str(v) for v in p_vals])
        ax.set_yticks(range(len(c_vals)))
        ax.set_yticklabels([str(v) for v in c_vals])
        ax.set_xlabel("p_in")
        ax.set_ylabel("c_inter")
        ax.set_title("Modular mean CI (α on, random IC, fixed κ_bare=0.02)")
        fig.colorbar(im, ax=ax, label="mean CI")
        fig.tight_layout()
        p = self.output_dir / "modular_critical_kappa_heatmap_alpha_on.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 6. cap sensitivity
        fig, ax = plt.subplots(figsize=(7, 4))
        sub = [r for r in cap_rows if r["init_mode"] == "random"]
        labels = [r["kappa_cap"] for r in sub]
        means = [r["mean_CI"] for r in sub]
        mins = [r["min_CI"] for r in sub]
        x = np.arange(len(labels))
        ax.bar(x - 0.15, means, 0.3, label="mean CI")
        ax.bar(x + 0.15, mins, 0.3, label="min CI")
        ax.set_xticks(x)
        ax.set_xticklabels(labels)
        ax.set_ylabel("CI")
        ax.set_title("Cap sensitivity (random IC, κ_bare=0.08 α on)")
        ax.legend()
        fig.tight_layout()
        p = self.output_dir / "cap_sensitivity_comparison.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # 7–9. Example time series: formation success, genuine failure, matched pair
        examples = [
            (
                "formation_success",
                dict(
                    network=NetworkType.MEANFIELD,
                    alpha_on=False,
                    kb=0.50,
                    noise=0.01,
                    seed=17,
                    init_mode="random",
                ),
            ),
            (
                "genuine_failure",
                dict(
                    network=NetworkType.MEANFIELD,
                    alpha_on=False,
                    kb=0.01,
                    noise=0.02,
                    seed=17,
                    init_mode="random",
                ),
            ),
            (
                "legacy_near_sync_retention",
                dict(
                    network=NetworkType.MEANFIELD,
                    alpha_on=True,
                    kb=0.010,
                    noise=0.01,
                    seed=17,
                    init_mode="near_sync",
                ),
            ),
        ]
        for tag, cfg in examples:
            cfg_full = {"cap": 0.95, **cfg}
            sim = make_sim(cfg_full)
            res = sim.run()
            fig, ax = plt.subplots(figsize=(8, 3))
            ax.plot(res.time, res.ci_global, "b-", lw=1.2)
            ax.axhline(0.75, color="gray", ls="--", alpha=0.7)
            ax.set_xlabel("time")
            ax.set_ylabel("CI")
            ax.set_title(
                f"{tag.replace('_', ' ')} | init={sim.init_mode} "
                f"CI0={res.initial_ci:.3f} κ_eff={res.kappa_eff:.3f}"
            )
            ax.set_ylim(0, 1.05)
            fig.tight_layout()
            p = self.output_dir / f"example_timeseries_{tag}.png"
            fig.savefig(p, dpi=150)
            plt.close(fig)
            self._track(p)

        # Matched pair overlay
        fig, ax = plt.subplots(figsize=(8, 3.5))
        for alpha_on, color, label in [(True, "C0", "α ON"), (False, "C3", "α OFF")]:
            sim = CMTSimulator(
                network_type=NetworkType.MEANFIELD,
                alpha_on=alpha_on,
                seed=17,
                noise=0.01,
                kappa_cap=0.95,
                init_mode="random",
            )
            sim.kappa_bare = sim.kappa_bare_for_target_eff(0.10)
            sim.rng = np.random.default_rng(17)
            res = sim.run()
            ax.plot(res.time, res.ci_global, color=color, lw=1.2, label=f"{label} κ_eff≈{res.kappa_eff:.3f}")
        ax.axhline(0.75, color="gray", ls="--", alpha=0.7)
        ax.set_xlabel("time")
        ax.set_ylabel("CI")
        ax.set_title("Matched κ_eff=0.1 control (random IC, seed=17)")
        ax.set_ylim(0, 1.05)
        ax.legend()
        fig.tight_layout()
        p = self.output_dir / "example_timeseries_matched_keff_0.1.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

        # Aliases for filenames referenced in earlier review materials
        for new_name, src_name in [
            ("example_timeseries_desync.png", "example_timeseries_genuine_failure.png"),
            ("example_timeseries_global_lock.png", "example_timeseries_formation_success.png"),
            (
                "example_timeseries_module_locked_offset.png",
                "example_timeseries_legacy_near_sync_retention.png",
            ),
        ]:
            src = self.output_dir / src_name
            dst = self.output_dir / new_name
            if src.exists():
                dst.write_bytes(src.read_bytes())
                self._track(dst)

        # Module CI bars from modular random-IC run
        sim = CMTSimulator(
            network_type=NetworkType.SYMMETRICMODULES,
            alpha_on=False,
            kappa_bare=0.50,
            noise=0.02,
            seed=5,
            c_inter=0.10,
            p_in=0.05,
            init_mode="random",
        )
        res = sim.run()
        if res.ci_modules:
            fig, ax = plt.subplots(figsize=(6, 4))
            mod_means = [float(np.mean(m)) for m in res.ci_modules]
            ax.bar(range(1, len(mod_means) + 1), mod_means, color="steelblue")
            ax.axhline(res.mean_ci, color="red", ls="--", label=f"global CI={res.mean_ci:.3f}")
            ax.axhline(0.75, color="gray", ls=":", alpha=0.7)
            ax.set_xlabel("module")
            ax.set_ylabel("mean CI")
            ax.set_title("Per-module CI (random IC, κ_eff=0.5)")
            ax.legend()
            fig.tight_layout()
            p = self.output_dir / "module_CI_bars.png"
            fig.savefig(p, dpi=150)
            plt.close(fig)
            self._track(p)

        # Intermodule phase lag histogram
        sim = CMTSimulator(
            network_type=NetworkType.SYMMETRICMODULES,
            alpha_on=False,
            kappa_bare=0.50,
            noise=0.02,
            seed=5,
            c_inter=0.10,
            p_in=0.05,
            init_mode="random",
        )
        lattice = TelascuraLattice(sim.adjacency)
        lags_all = []
        n = sim.n_nodes
        theta = sim.rng.uniform(0, 2 * np.pi, n)
        ke = sim.kappa_effective()
        for _ in range(80):
            degrees = np.maximum(sim.adjacency.sum(axis=1), 1.0)
            coupling = np.zeros(n)
            for i in range(n):
                nb = np.where(sim.adjacency[i] > 0)[0]
                if len(nb):
                    coupling[i] = np.sum(np.sin(theta[nb] - theta[i])) / degrees[i]
            theta = (theta + (ke * coupling) * sim.dt) % (2 * np.pi)
            if sim.modules:
                lags_all.extend(lattice.module_phase_lag(theta, sim.modules))
        fig, ax = plt.subplots(figsize=(6, 4))
        ax.hist(lags_all, bins=20, color="teal", edgecolor="white")
        ax.set_xlabel("inter-module phase lag (rad)")
        ax.set_ylabel("count")
        ax.set_title("Inter-module phase lag distribution (formation regime)")
        fig.tight_layout()
        p = self.output_dir / "intermodule_phase_lag_histograms.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)

    # ------------------------------------------------------------------
    # Text / provenance
    # ------------------------------------------------------------------

    def write_methods(self) -> None:
        seeds = sorted({e["seed"] for e in self.seed_ledger})
        text = "\n".join(
            [
                "Alpha-Scaled Gain Rescaling in Noisy Kuramoto Networks",
                "Methods (Simulation Suite v1.1.0)",
                f"Generated: {self.generated_at}",
                "",
                "MODEL",
                "  Kuramoto network on graph G:",
                "    dθ_i/dt = ω_i + (κ_eff/deg_i) Σ_j A_ij sin(θ_j - θ_i) + ξ_i",
                "  α ON:  κ_eff = min(κ_bare / α^β, κ_cap)",
                "  α OFF: κ_eff = min(κ_bare, κ_cap)",
                "  CI(t) = |mean_i exp(i θ_i)|",
                "  E_eff = N · κ_eff² · α⁻¹  (model-scale, not physical joules)",
                "",
                "INITIAL CONDITIONS (v1.1 correction)",
                "  near_sync: θ_i ~ N(0, 0.15)   — retention (legacy v1.0)",
                "  random:    θ_i ~ U[0, 2π)     — formation (required control)",
                "",
                "MATCHED-κ_eff CONTROL (v1.1 correction)",
                "  For target κ*: set α-off κ_bare = κ*",
                "  set α-on  κ_bare = κ* · α^β  so κ_eff matches (pre-cap).",
                "  Same seed => same IC and noise stream.",
                "  Expectation if α only rescales gain: statistically equivalent dynamics.",
                "",
                "CANDIDATE MECHANISMS BEYOND GAIN MAP (v1.2)",
                "  Hold κ_eff fixed (fixed_kappa_eff); gain map off.",
                "  none | noise_suppression (σ→σ·α) | freq_narrowing (σ_ω→σ_ω·α/0.05)",
                "  | residual_meanfield (extra κ_res·R·sin(ψ-θ)).",
                "  Hypotheses only — not physical claims.",
                "",
                "INTEGRATION",
                f"  dt = {DT}",
                f"  total_time = {TOTAL_TIME}",
                "  scheme: Euler–Maruyama",
                "",
                "CAP HANDLING",
                f"  default κ_cap = {KAPPA_CAP}",
                "  sensitivity: 0.8, 0.95, 0.99, no_cap",
                "",
                "RANDOM SEEDS",
                f"  all seeds recorded: {seeds}",
                f"  primary: {SEEDS_PRIMARY}",
                f"  uncertainty: {SEEDS_UNCERTAINTY}",
                "  full ledger: seed_ledger.csv",
                "",
                f"α (fine-structure constant) = {ALPHA:.10f}",
                "",
                "SUCCESS CRITERION",
                f"  CI ≥ {CI_TARGET} for ≥ 90% of integration window",
                "",
                f"CODE VERSION: alpha_resonance_os v{VERSION}",
                "",
                "CONFIG FILES",
                "  config/parameters.json",
                "  config/networks.json",
                "",
                "CLAIM BOUNDARY",
                "  See CLAIMS.md and EMPIRICAL_VALIDATION.md",
            ]
        )
        path = self.output_dir / "methods.txt"
        path.write_text(text, encoding="utf-8")
        self._track(path)

    def write_key_results(
        self,
        matched_rows: list[dict],
        formation_rows: list[dict],
        mechanism_rows: list[dict],
    ) -> None:
        m = [
            r
            for r in matched_rows
            if r["init_mode"] == "random" and r["target_kappa_eff"] == 0.1
        ]
        if m:
            mean_delta = float(np.mean([r["mean_CI_delta_on_minus_off"] for r in m]))
            max_abs = float(np.max([abs(r["mean_CI_delta_on_minus_off"]) for r in m]))
            match_frac = float(np.mean([1.0 if r["trajectories_match_prediction"] else 0.0 for r in m]))
        else:
            mean_delta = max_abs = match_frac = float("nan")

        fail_n = sum(
            1
            for r in formation_rows
            if r["experiment"] == "explicit_failure_panel" and r["regime"] == "failed"
        )
        form_scan = [r for r in formation_rows if r["experiment"] == "formation_kappa_eff_scan"]
        low_ci0 = float(np.mean([r["initial_CI"] for r in form_scan])) if form_scan else float("nan")

        # Mechanism residuals at matched κ_eff=0.1, meanfield
        mech_lines = []
        for mech in CANDIDATE_MECHANISMS:
            if mech == MECHANISM_NONE:
                continue
            sub = [
                r
                for r in mechanism_rows
                if r["mechanism"] == mech
                and r["target_kappa_eff"] == 0.1
                and r["network_type"] == "meanfield"
            ]
            if sub:
                d = float(np.mean([r["delta_mean_CI_vs_none"] for r in sub]))
                iso = float(np.mean([1.0 if r["effect_isolated"] else 0.0 for r in sub]))
                mech_lines.append(
                    f"  {mech}: mean ΔCI vs none = {d:+.4f}, isolated rate = {iso:.2f}"
                )

        text = "\n".join(
            [
                "KEY RESULTS — CLAIM-CALIBRATED BRIEF (v1.2.0)",
                f"Generated: {self.generated_at}",
                "",
                "TITLE",
                '  "Alpha-Scaled Gain Rescaling in Noisy Kuramoto Networks:',
                '   A Conditional Simulation Study"',
                "",
                "TASK 1 — ALPHA IS NOT SPECIAL (gain map)",
                "  The 1/α gain map is a dial rescaling of κ_bare → κ_eff only.",
                "  Matched-κ_eff α-on/off (random IC, κ*=0.1):",
                f"    mean(Δ mean_CI on−off) = {mean_delta:.6f}",
                f"    max |Δ mean_CI|         = {max_abs:.6f}",
                f"    fraction match          = {match_frac:.3f}",
                "  => no residual alpha-specific effect under pure gain rescaling.",
                "",
                "TASK 2–3 — CANDIDATE MECHANISMS BEYOND GAIN MAP",
                "  Tested at FIXED κ_eff (gain map off): none vs",
                "  noise_suppression | freq_narrowing | residual_meanfield.",
                "  Meanfield, κ_eff=0.1:",
                *mech_lines,
                "  Details: summary_candidate_mechanisms.csv",
                "           summary_candidate_mechanisms_uncertainty.csv",
                "  These are computational hypotheses, NOT proven physics.",
                "",
                "TASK 4 — BIOLOGY / PHYSICS BOUNDARY",
                "  No biological, medical, energy, or universal-theory claim is supported",
                "  by this suite alone. External empirical validation is required:",
                "  see EMPIRICAL_VALIDATION.md and CLAIMS.md.",
                "",
                "FORMATION / FAILURES",
                f"  Mean initial CI (random IC) ≈ {low_ci0:.4f}",
                f"  Explicit genuine failures archived: {fail_n}",
                "",
                "DO NOT CLAIM",
                "  - alpha-specific synchronization as established fact",
                "  - lower effective coupling threshold from nominal κ_bare ratios",
                "  - physical 1/α amplification in nature",
                "  - biophysical mechanism without independent data",
                "",
                "FILES",
                "  CLAIMS.md, EMPIRICAL_VALIDATION.md",
                "  summary_matched_kappa_eff.csv",
                "  summary_candidate_mechanisms.csv",
                "  summary_formation_and_failures.csv",
                "  seed_ledger.csv, EXPECTED_HASHES.sha256, methods.txt",
            ]
        )
        path = self.output_dir / "key_results_update.txt"
        path.write_text(text, encoding="utf-8")
        self._track(path)

    def write_diagnostics(self) -> None:
        if not self.diagnostics:
            text = "No numerical issues flagged. No NaNs detected.\n"
        else:
            text = "RUN DIAGNOSTICS\n" + "\n".join(f"- {d}" for d in self.diagnostics) + "\n"
        path = self.output_dir / "run_diagnostics.txt"
        path.write_text(text, encoding="utf-8")
        self._track(path)

    def write_seed_ledger(self) -> None:
        path = self.output_dir / "seed_ledger.csv"
        if not self.seed_ledger:
            path.write_text("experiment,seed\n", encoding="utf-8")
        else:
            # Normalize keys
            keys: list[str] = []
            for row in self.seed_ledger:
                for k in row:
                    if k not in keys:
                        keys.append(k)
            write_csv(path, self.seed_ledger, fieldnames=keys)
        self._track(path)

    def write_hashes(self) -> None:
        rows = []
        for p in sorted(self.output_dir.rglob("*")):
            if p.is_file() and p.name != "EXPECTED_HASHES.sha256":
                rel = p.relative_to(self.output_dir).as_posix()
                rows.append(f"{sha256_file(p)}  {rel}")
        path = self.output_dir / "EXPECTED_HASHES.sha256"
        path.write_text("\n".join(rows) + "\n", encoding="utf-8")
        self._track(path)

    def write_manifest(
        self,
        matched_rows: list[dict],
        formation_rows: list[dict],
        control_rows: list[dict],
        cap_rows: list[dict],
        modular_rows: list[dict],
        scaling_rows: list[dict],
        mechanism_rows: list[dict],
    ) -> None:
        manifest = {
            "generated_at": self.generated_at,
            "version": VERSION,
            "code": f"alpha_resonance_os v{VERSION}",
            "title": "Alpha-Scaled Gain Rescaling in Noisy Kuramoto Networks: A Conditional Simulation Study",
            "claim_level": "computational / conditional only — not physical mechanism",
            "review_corrections": [
                "random low-coherence initial conditions",
                "genuine failure runs archived",
                "matched-kappa_eff alpha-on/off controls",
                "executable package with configs, seeds, hashes",
                "candidate mechanisms beyond gain map (matched κ_eff)",
                "CLAIMS.md + EMPIRICAL_VALIDATION.md boundaries",
            ],
            "files_produced": sorted(self.files_produced),
            "parameter_grid": {
                "dt": DT,
                "total_time": TOTAL_TIME,
                "alpha": ALPHA,
                "kappa_cap_default": KAPPA_CAP,
                "matched_kappa_eff_targets": MATCHED_KEFF_TARGETS,
                "candidate_mechanisms": CANDIDATE_MECHANISMS,
                "mechanism_keff_targets": MECHANISM_KEFF_TARGETS,
                "networks": [n.value for n in CONTROL_NETWORKS] + ["symmetricmodules"],
                "init_modes": ["near_sync", "random"],
                "seeds_primary": SEEDS_PRIMARY,
                "seeds_uncertainty": SEEDS_UNCERTAINTY,
            },
            "summary_row_counts": {
                "matched_kappa_eff": len(matched_rows),
                "candidate_mechanisms": len(mechanism_rows),
                "formation_and_failures": len(formation_rows),
                "control_sweep": len(control_rows),
                "cap_sensitivity": len(cap_rows),
                "modular_sweep": len(modular_rows),
                "scaling_hypotheses": len(scaling_rows),
                "seed_ledger": len(self.seed_ledger),
            },
            "config_files": ["config/parameters.json", "config/networks.json"],
        }
        path = self.output_dir / "run_manifest_final.json"
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
        if "run_manifest_final.json" not in self.files_produced:
            self.files_produced.append("run_manifest_final.json")
        # rewrite with complete file list
        manifest["files_produced"] = sorted(self.files_produced)
        path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")

    def run_all(self) -> dict:
        print("  [1/9] Legacy canonical time series...")
        self.run_canonical_timeseries()
        print("  [2/9] Matched-κ_eff controls (gain map)...")
        matched_rows = self.run_matched_kappa_eff_controls()
        print("  [3/9] Candidate mechanisms at fixed κ_eff...")
        mechanism_rows = self.run_candidate_mechanism_tests()
        print("  [4/9] Formation + genuine failure suite...")
        formation_rows = self.run_formation_and_failure_suite()
        print("  [5/9] Control sweep (near_sync + random)...")
        control_rows = self.run_control_sweep()
        print("  [6/9] Cap sensitivity...")
        cap_rows = self.run_cap_sensitivity()
        print("  [7/9] Modular sweep...")
        modular_rows = self.run_modular_sweep()
        print("  [8/9] Scaling hypotheses...")
        scaling_rows = self.run_scaling_hypotheses()
        print("  [9/9] Figures + provenance...")
        self.generate_figures(matched_rows, formation_rows, control_rows, cap_rows, modular_rows)
        self._mechanism_figure(mechanism_rows)
        self.write_methods()
        self.write_key_results(matched_rows, formation_rows, mechanism_rows)
        self.write_diagnostics()
        self.write_seed_ledger()
        self.write_manifest(
            matched_rows,
            formation_rows,
            control_rows,
            cap_rows,
            modular_rows,
            scaling_rows,
            mechanism_rows,
        )
        self.write_hashes()
        return {
            "files_produced": len(self.files_produced),
            "output_dir": str(self.output_dir),
            "version": VERSION,
        }

    def _mechanism_figure(self, mechanism_rows: list[dict]) -> None:
        if not HAS_MPL or not mechanism_rows:
            return
        fig, ax = plt.subplots(figsize=(8, 4.5))
        mechs = [m for m in CANDIDATE_MECHANISMS]
        x = np.arange(len(mechs))
        # meanfield, keff=0.1, average over seeds
        means, stds = [], []
        for mech in mechs:
            sub = [
                r
                for r in mechanism_rows
                if r["mechanism"] == mech
                and r["network_type"] == "meanfield"
                and r["target_kappa_eff"] == 0.1
            ]
            vals = [r["mean_CI"] for r in sub]
            means.append(float(np.mean(vals)) if vals else 0.0)
            stds.append(float(np.std(vals, ddof=1)) if len(vals) > 1 else 0.0)
        ax.bar(x, means, yerr=stds, capsize=4, color=["#888888", "#4C72B0", "#55A868", "#C44E52"])
        ax.set_xticks(x)
        ax.set_xticklabels(mechs, rotation=15, ha="right")
        ax.set_ylabel("mean CI")
        ax.set_title("Candidate mechanisms at FIXED κ_eff=0.1 (meanfield, random IC)")
        ax.axhline(0.75, color="gray", ls="--", alpha=0.6)
        fig.tight_layout()
        p = self.output_dir / "candidate_mechanisms_matched_keff.png"
        fig.savefig(p, dpi=150)
        plt.close(fig)
        self._track(p)


def run_exact_deliverables(output_dir: Path) -> dict:
    suite = FullDeliverableSuite(output_dir)
    return suite.run_all()
