#!/usr/bin/env python3
"""
Alpha Resonance OS — main entry point.

Run: python run_framework.py
     python run_framework.py --quick
     python run_framework.py --output C:\\path\\to\\output
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from alpha_resonance import AlphaResonanceOS, CMTSimulator, DualPathEngine, NetworkType
from alpha_resonance.constants import ALPHA, KAPPA_CAP
from alpha_resonance.full_deliverables import run_exact_deliverables


def print_banner() -> None:
    print("=" * 72)
    print("  KURAMOTO COHERENCE LAB  (suite lineage v1.2.0)")
    print("  Gain rescaling + candidate mechanisms (computational only)")
    print("  Not a physical / biological mechanism claim")
    print("=" * 72)


def run_quick_demo() -> None:
    """MRE: matched gain-map control + candidate mechanisms at fixed κ_eff."""
    import numpy as np

    print("\n[1] Gain map is NOT special — matched κ_eff=0.1 (same seed)")
    for alpha_on in (True, False):
        sim = CMTSimulator(
            network_type=NetworkType.MEANFIELD,
            alpha_on=alpha_on,
            seed=17,
            noise=0.01,
            kappa_cap=KAPPA_CAP,
            init_mode="random",
        )
        sim.kappa_bare = sim.kappa_bare_for_target_eff(0.1)
        sim.rng = np.random.default_rng(17)
        res = sim.run()
        tag = "α ON " if alpha_on else "α OFF"
        print(
            f"  {tag}: κ_eff={res.kappa_eff:.4f}  mean_CI={res.mean_ci:.4f}  "
            f"(expect match)"
        )

    print("\n[2–3] Mechanisms BEYOND gain map — fixed κ_eff=0.1")
    for mech in (
        "none",
        "noise_suppression",
        "freq_narrowing",
        "residual_meanfield",
    ):
        sim = CMTSimulator(
            network_type=NetworkType.MEANFIELD,
            alpha_on=False,
            fixed_kappa_eff=0.1,
            kappa_bare=0.1,
            seed=17,
            init_mode="random",
            noise=0.01,
            mechanism=mech,
        )
        sim.rng = np.random.default_rng(17)
        res = sim.run()
        print(
            f"  {mech:22s}  mean_CI={res.mean_ci:.4f}  final={res.final_ci:.4f}  "
            f"noise_eff={res.parameters['noise_eff']:.5f}"
        )

    print("\n[4] Bio/physics: closed without external data (see CLAIMS.md)")
    print(f"  α = {ALPHA:.8f}  (constant used only as a number in formulas)")
    print("  Full suite: python run_framework.py --suite --output ./output")


def run_full(output_dir: Path, seed: int) -> None:
    print("\nRunning full framework suite...")
    os_engine = AlphaResonanceOS(output_dir=output_dir, seed=seed)
    report = os_engine.run_full()

    print("\n--- COMPOSITE SCORES ---")
    for k, v in report.composite_scores.items():
        if k != "falsification_flags":
            print(f"  {k}: {v}")

    print("\n--- OMEGA SEAL (Doc 26) ---")
    for k, v in report.omega_seal.items():
        print(f"  {k}: {v}")

    if report.falsification_flags:
        print("\n--- FALSIFICATION FLAGS ---")
        for f in report.falsification_flags:
            print(f"  ! {f}")

    print(f"\nArtifacts written to: {output_dir.resolve()}")
    print("  - FRAMEWORK_EQUATIONS.md (parent dir)")
    print("  - run_manifest_final.json")
    print("  - FRAMEWORK_REPORT.json")
    print("  - methods.txt")
    print("  - simulation_*.csv")


def main() -> None:
    parser = argparse.ArgumentParser(description="Alpha Resonance OS")
    parser.add_argument("--quick", action="store_true", help="Fast demo only")
    parser.add_argument(
        "--suite",
        action="store_true",
        help="Generate exact simulation-suite deliverables (CSVs, PNGs, manifest)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "output",
        help="Output directory for artifacts",
    )
    parser.add_argument("--seed", type=int, default=17)
    args = parser.parse_args()

    print_banner()

    if args.suite:
        print("\nGenerating exact simulation-suite deliverables...")
        result = run_exact_deliverables(args.output)
        print(f"\nDone: {result['files_produced']} files → {result['output_dir']}")
    elif args.quick:
        run_quick_demo()
    else:
        run_full(args.output, args.seed)


if __name__ == "__main__":
    main()