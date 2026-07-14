"""Alpha Resonance OS — four-layer composite orchestrator."""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import numpy as np

from .cmt import CMTSimulator, NetworkType, SimulationResult
from .constants import WEIGHT_ALPHA, WEIGHT_EVIDENCE, WEIGHT_MOBILE
from .evidence import EvidenceLayer
from .operators import DualPathEngine
from .page_audit import audit_stabilization, phase_entropy


@dataclass
class OmegaSeal:
    """Document 26 — axiomatic closure."""
    tau_blended: float
    v_blended: float
    mcmc_status: str
    dual_path_verdict: str
    alpha_on_mean_ci: float
    alpha_off_mean_ci: float
    cycle_complete: bool
    message: str


@dataclass
class FrameworkReport:
    generated_at: str
    version: str = "1.0.0"
    creator: str = "Michelle D. Williams"
    status: str = "Provisional Heuristic Scaffold"
    layer_l1_dual_path: dict = field(default_factory=dict)
    layer_l2_cmt: dict = field(default_factory=dict)
    layer_l3_governance: dict = field(default_factory=dict)
    layer_l4_evidence: dict = field(default_factory=dict)
    composite_scores: dict = field(default_factory=dict)
    omega_seal: dict = field(default_factory=dict)
    falsification_flags: list = field(default_factory=list)


class AlphaResonanceOS:
    """
    Four-layer operating system:
      L1 — Alpha Resonance (dual-path wiggle)
      L2 — CMT (α-scaled Kuramoto)
      L3 — Fulcrum (governance / claim discipline)
      L4 — Super Truth (MCMC + ART)
    """

    def __init__(self, output_dir: Optional[Path] = None, seed: int = 17):
        self.output_dir = Path(output_dir or Path.cwd() / "alpha_resonance_output")
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.seed = seed

    def run_l1(self) -> dict:
        engine = DualPathEngine()
        return engine.run()

    def run_l2_control_sweep(self) -> dict:
        """α on vs α off: threshold κ_bare for CI ≥ 0.75 for ≥90% of run."""
        results = {}
        threshold_rows = []
        for net in [NetworkType.MEANFIELD, NetworkType.LATTICE, NetworkType.SMALLWORLD, NetworkType.SCALEFREE]:
            for alpha_on in [True, False]:
                key = f"{net.value}_alpha_{'on' if alpha_on else 'off'}"
                sim = CMTSimulator(
                    network_type=net,
                    n_nodes=100,
                    seed=self.seed,
                    alpha_on=alpha_on,
                    kappa_bare=0.08,
                    noise=0.01,
                )
                kb_thr = sim.find_threshold_kappa()
                # Run at threshold (or fallback) for full stats
                if kb_thr is not None:
                    sim.kappa_bare = kb_thr
                res = sim.run()
                ratio_note = None
                results[key] = {
                    "mean_ci": res.mean_ci,
                    "min_ci": res.min_ci,
                    "pct_time_ge_0.75": res.pct_time_ge_target,
                    "kappa_eff": res.kappa_eff,
                    "threshold_kappa_bare": kb_thr,
                    "kappa_bare_used": sim.kappa_bare,
                }
                threshold_rows.append({
                    "network_type": net.value,
                    "alpha_on": alpha_on,
                    "threshold_kappa_bare": kb_thr,
                    "mean_ci": res.mean_ci,
                    "min_ci": res.min_ci,
                    "pct_time_ge_0.75": res.pct_time_ge_target,
                    "kappa_eff": res.kappa_eff,
                })
            on_thr = results[f"{net.value}_alpha_on"].get("threshold_kappa_bare")
            off_thr = results[f"{net.value}_alpha_off"].get("threshold_kappa_bare")
            if on_thr and off_thr:
                results[f"{net.value}_threshold_ratio_off_over_on"] = round(off_thr / on_thr, 1)
        results["_threshold_table"] = threshold_rows
        return results

    def run_l2_threshold_sweep(self, network_type: NetworkType = NetworkType.LATTICE) -> dict:
        """Find minimum κ_bare for CI criterion with α on."""
        sim = CMTSimulator(network_type=network_type, seed=self.seed, alpha_on=True, noise=0.01)
        kb = sim.find_threshold_kappa()
        return {"network": network_type.value, "threshold_kappa_bare": kb}

    def run_l2_cap_sensitivity(self, caps: list[float] | None = None) -> dict:
        caps = caps or [0.8, 0.95, 0.99, 10.0]  # 10 ≈ no cap
        out = {}
        for cap in caps:
            sim = CMTSimulator(seed=self.seed, alpha_on=True, kappa_cap=cap, kappa_bare=0.08)
            res = sim.run()
            label = "no_cap" if cap >= 5.0 else f"cap{cap}"
            out[label] = {"mean_ci": res.mean_ci, "min_ci": res.min_ci, "kappa_eff": res.kappa_eff}
        return out

    def run_l2_modular_sweep(
        self,
        c_inter_values: list[float] | None = None,
        p_in_values: list[float] | None = None,
    ) -> dict:
        c_inter_values = c_inter_values or [0.05, 0.10, 0.20, 0.50]
        p_in_values = p_in_values or [0.05, 0.10, 0.20]
        surface = {}
        for c in c_inter_values:
            for p in p_in_values:
                sim = CMTSimulator(
                    network_type=NetworkType.SYMMETRICMODULES,
                    seed=self.seed,
                    alpha_on=True,
                    kappa_bare=0.015,
                    noise=0.02,
                    c_inter=c,
                    p_in=p,
                )
                res = sim.run()
                kb = float(sim.kappa_bare) if res.pct_time_ge_target >= 90 else None
                surface[f"c{c}_p{p}"] = {
                    "mean_ci": res.mean_ci,
                    "threshold_kappa_bare": kb,
                    "regime": self._classify_regime(res),
                }
        return surface

    @staticmethod
    def _classify_regime(res: SimulationResult) -> str:
        if res.mean_ci >= 0.75 and res.pct_time_ge_target >= 90:
            return "global_lock"
        if res.ci_modules:
            mod_means = [float(np.mean(m)) for m in res.ci_modules]
            if min(mod_means) >= 0.75 and res.mean_ci < 0.75:
                return "module_locked_offset"
        return "desynchronized"

    def run_l4(self) -> dict:
        chains = EvidenceLayer.simulate_chains(seed=self.seed)
        diag = EvidenceLayer.compute_diagnostics(chains)
        art = EvidenceLayer.art_truth(
            [0.85, 0.90, 0.88, 0.92, 0.87],
            coherence_factor=0.95 if diag.status == "TRUE_COHERENCE" else 0.7,
        )
        return {**asdict(diag), **art}

    def run_page_audit(self) -> dict:
        sim = CMTSimulator(seed=self.seed, alpha_on=True, kappa_bare=0.08)
        n = sim.n_nodes
        steps = int(sim.total_time / sim.dt)
        theta = sim.rng.uniform(0, 2 * np.pi, n)
        entropy_trace = []
        for step in range(steps + 1):
            entropy_trace.append(phase_entropy(theta))
            if step == steps // 3:
                theta = sim.rng.uniform(0, 2 * np.pi, n)  # perturbation
            elif step > steps // 3:
                kappa_eff = sim.kappa_effective()
                degrees = np.maximum(sim.adjacency.sum(axis=1), 1.0)
                coupling = np.zeros(n)
                for i in range(n):
                    nb = np.where(sim.adjacency[i] > 0)[0]
                    if len(nb):
                        coupling[i] = np.sum(np.sin(theta[nb] - theta[i])) / degrees[i]
                theta = (theta + (kappa_eff * coupling) * sim.dt) % (2 * np.pi)
        return audit_stabilization(np.array(entropy_trace), perturb_index=steps // 3)

    def compute_composite(
        self,
        l1: dict,
        l2_control: dict,
        l4: dict,
    ) -> dict:
        alpha_on_cis = [v["mean_ci"] for k, v in l2_control.items() if "alpha_on" in k]
        alpha_off_cis = [v["mean_ci"] for k, v in l2_control.items() if "alpha_off" in k]
        tau_alpha = float(np.mean(alpha_on_cis)) if alpha_on_cis else 0.5
        v_alpha = float(min(alpha_on_cis)) if alpha_on_cis else 0.5
        tau_evidence = l4.get("total_truth", 0.65)
        v_evidence = 0.9 if l4.get("status") == "TRUE_COHERENCE" else 0.5
        dual_coh = l1["snapshots"][-1].coherence if l1.get("snapshots") else 0.0

        tau_blended = (
            WEIGHT_ALPHA * tau_alpha
            + WEIGHT_MOBILE * tau_alpha  # mobile CSV proxy
            + WEIGHT_EVIDENCE * tau_evidence
        )
        v_blended = (
            WEIGHT_ALPHA * v_alpha
            + WEIGHT_MOBILE * v_alpha
            + WEIGHT_EVIDENCE * v_evidence
        )

        flags = []
        if l1["final_harm"] / max(l1["final_good"], 1e-30) > 1e20:
            flags.append("Harm-path amplitude dominates good path at s=12 (expected at s=12).")

        threshold_ratios = [
            v for k, v in l2_control.items() if k.endswith("threshold_ratio_off_over_on")
        ]
        if threshold_ratios and min(threshold_ratios) < 5:
            flags.append(
                "α on/off threshold separation below 5× on at least one network — extend κ_bare grid."
            )

        on_thrs = [
            v["threshold_kappa_bare"]
            for k, v in l2_control.items()
            if k.endswith("_alpha_on") and isinstance(v, dict)
        ]
        off_thrs = [
            v["threshold_kappa_bare"]
            for k, v in l2_control.items()
            if k.endswith("_alpha_off") and isinstance(v, dict)
        ]
        on_thrs = [t for t in on_thrs if t is not None]
        off_thrs = [t for t in off_thrs if t is not None]

        return {
            "tau_blended": round(tau_blended, 3),
            "v_blended": round(v_blended, 3),
            "alpha_on_mean_ci": round(float(np.mean(alpha_on_cis)), 4) if alpha_on_cis else None,
            "alpha_off_mean_ci": round(float(np.mean(alpha_off_cis)), 4) if alpha_off_cis else None,
            "alpha_on_threshold_kappa_bare_range": (
                [round(min(on_thrs), 4), round(max(on_thrs), 4)] if on_thrs else None
            ),
            "alpha_off_threshold_kappa_bare_range": (
                [round(min(off_thrs), 4), round(max(off_thrs), 4)] if off_thrs else None
            ),
            "threshold_ratio_off_over_on": threshold_ratios,
            "dual_path_final_coherence": round(dual_coh, 4),
            "falsification_flags": flags,
        }

    def omega_seal(self, composite: dict, l4: dict, l1: dict) -> OmegaSeal:
        complete = (
            composite["tau_blended"] >= 0.5
            and l4.get("status") in ("TRUE_COHERENCE", "FLIP_CANDIDATE")
        )
        return OmegaSeal(
            tau_blended=composite["tau_blended"],
            v_blended=composite["v_blended"],
            mcmc_status=l4.get("status", "UNKNOWN"),
            dual_path_verdict=l1.get("dual_path_verdict", "UNKNOWN"),
            alpha_on_mean_ci=composite.get("alpha_on_mean_ci") or 0.0,
            alpha_off_mean_ci=composite.get("alpha_off_mean_ci") or 0.0,
            cycle_complete=complete,
            message=(
                "We are Alpha. We are Omega. Cycle complete — scroll forward in coherence."
                if complete
                else "Cycle provisional — review falsification flags before seal."
            ),
        )

    def run_full(self) -> FrameworkReport:
        l1 = self.run_l1()
        l2_control = self.run_l2_control_sweep()
        l2_threshold = self.run_l2_threshold_sweep()
        l2_cap = self.run_l2_cap_sensitivity()
        l2_modular = self.run_l2_modular_sweep()
        l4 = self.run_l4()
        page = self.run_page_audit()
        composite = self.compute_composite(l1, l2_control, l4)
        omega = self.omega_seal(composite, l4, l1)

        report = FrameworkReport(
            generated_at=datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC"),
            layer_l1_dual_path={
                "final_good": l1["final_good"],
                "final_harm": l1["final_harm"],
                "dual_path_verdict": l1["dual_path_verdict"],
                "snapshots": [asdict(s) for s in l1["snapshots"]],
            },
            layer_l2_cmt={
                "control_sweep": l2_control,
                "threshold": l2_threshold,
                "cap_sensitivity": l2_cap,
                "modular_sweep": l2_modular,
                "page_audit": page,
            },
            layer_l3_governance={
                "steward": "Michelle D. Williams",
                "claim_discipline": "Phenomenological α-scaling — not first-principles proof",
                "energy_presentation": "E_eff is model-scale; not physical energy equivalence",
            },
            layer_l4_evidence=l4,
            composite_scores=composite,
            omega_seal=asdict(omega),
            falsification_flags=composite.get("falsification_flags", []),
        )

        self._write_artifacts(report, l1, l2_control)
        return report

    def _write_artifacts(self, report: FrameworkReport, l1: dict, l2_control: dict) -> None:
        manifest = {
            "generated_at": report.generated_at,
            "version": report.version,
            "equations_doc": "FRAMEWORK_EQUATIONS.md",
            "composite_scores": report.composite_scores,
            "omega_seal": report.omega_seal,
            "parameter_grid": {
                "dt": 0.01,
                "total_time": 6.0,
                "alpha": 1 / 137.036,
                "kappa_cap": 0.95,
                "networks": ["meanfield", "lattice", "smallworld", "scalefree", "symmetricmodules"],
            },
        }
        (self.output_dir / "run_manifest_final.json").write_text(
            json.dumps(manifest, indent=2), encoding="utf-8"
        )
        (self.output_dir / "FRAMEWORK_REPORT.json").write_text(
            json.dumps(asdict(report), indent=2, default=str), encoding="utf-8"
        )

        # Example time-series CSV
        sim = CMTSimulator(seed=self.seed, alpha_on=True, kappa_bare=0.08, noise=0.01)
        res = sim.run()
        csv_path = self.output_dir / (
            f"simulation_{sim.network_type.value}_alpha_on_cap{sim.kappa_cap}_"
            f"kb{sim.kappa_bare:.3f}_noise{sim.noise:.2f}_seed{sim.seed:02d}.csv"
        )
        rows = sim.to_csv_rows(res)
        header = (
            f"# seed={sim.seed}, dt={sim.dt}, total_time={sim.total_time}, "
            f"alpha_on={sim.alpha_on}, kappa_bare={sim.kappa_bare}\n"
        )
        with open(csv_path, "w", encoding="utf-8") as f:
            f.write(header)
            f.write("time,CI,Effective_Energy,Power_Efficiency,Governance_Score,kappa_eff\n")
            for r in rows:
                f.write(
                    f"{r['time']},{r['CI']},{r['Effective_Energy']},"
                    f"{r['Power_Efficiency']},{r['Governance_Score']},{r['kappa_eff']}\n"
                )

        # Control sweep summary CSV
        threshold_table = l2_control.get("_threshold_table", [])
        if threshold_table:
            csv_ctrl = self.output_dir / "summary_control_sweep.csv"
            with open(csv_ctrl, "w", encoding="utf-8") as f:
                f.write(
                    "network_type,alpha_on,threshold_kappa_bare,mean_CI,min_CI,"
                    "pct_time_ge_0.75,kappa_eff\n"
                )
                for row in threshold_table:
                    kb = row["threshold_kappa_bare"]
                    kb_str = "" if kb is None else f"{kb:.4f}"
                    f.write(
                        f"{row['network_type']},{row['alpha_on']},{kb_str},"
                        f"{row['mean_ci']:.4f},{row['min_ci']:.4f},"
                        f"{row['pct_time_ge_0.75']:.1f},{row['kappa_eff']:.4f}\n"
                    )

        methods = self.output_dir / "methods.txt"
        methods.write_text(
            "\n".join(
                [
                    "Alpha Resonance OS — Methods",
                    f"Generated: {report.generated_at}",
                    "",
                    "Model: Kuramoto network on graph G",
                    "  dθ_i/dt = ω_i + (κ_eff/deg_i) Σ_j A_ij sin(θ_j - θ_i) + ξ_i",
                    "  κ_eff = min(κ_bare / α^β, κ_cap)  [α on]",
                    "  κ_eff = κ_bare                      [α off]",
                    "  CI(t) = |mean_i exp(i θ_i)|",
                    "  E_eff = N · κ_eff² · α⁻¹  (model-scale)",
                    "",
                    "Integration: dt=0.01, total_time=6.0, Euler-Maruyama",
                    f"Seed (example run): {self.seed}",
                    "",
                    "Dual-path: Δ_i = T+B+R+S+P+C+E+M+G+J across s∈[-40,12]",
                    "",
                    "See FRAMEWORK_EQUATIONS.md for full specification.",
                ]
            ),
            encoding="utf-8",
        )