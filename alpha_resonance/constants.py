"""Physical and integration constants for Alpha Resonance OS."""

from __future__ import annotations

# Fine-structure constant (phenomenological scaler)
ALPHA: float = 1.0 / 137.035999084

# Integration defaults (match prior simulation suite)
DT: float = 0.01
TOTAL_TIME: float = 6.0
N_STEPS: int = int(TOTAL_TIME / DT)

# CMT defaults
KAPPA_CAP: float = 0.95
KAPPA_BARE_DEFAULT: float = 0.08
BETA_SCALING_DEFAULT: float = 1.0
NOISE_DEFAULT: float = 0.01

# Coherence thresholds
CI_TARGET: float = 0.75
CI_FRACTION_REQUIRED: float = 0.90

# Dual-path operator defaults
DUAL_PATH_GOOD = {"damping": 0.027, "feedback": 0.22, "boost": 0.56}
DUAL_PATH_HARM = {"damping": 0.011, "feedback": 0.38, "boost": 0.72}

# Scale epoch checkpoints
SCALE_EPOCHS = {
    -40.0: "pre-Big Bang vacuum",
    -35.0: "Planck / Boundary",
    -20.0: "inflation",
    -10.0: "QGP / nucleosynthesis",
    0.0: "recombination",
    4.0: "galaxy formation",
    9.0: "large-scale structure",
    10.5: "GER + governance band",
    12.0: "today",
}

# Composite blend weights
WEIGHT_ALPHA: float = 0.4
WEIGHT_MOBILE: float = 0.35
WEIGHT_EVIDENCE: float = 0.25