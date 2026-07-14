# Allowed claims (v1.2.0)

This document is binding for how results from this suite may be described.

## Allowed (supported by the simulations)

1. **Gain map is a rescaling dial.**  
   Under κ_eff = min(κ_bare/α^β, κ_cap), matched-κ_eff α-on/off runs are equivalent. Alpha does **not** add an extra synchronization effect beyond that map.

2. **Retention vs formation.**  
   Near-sync initial conditions test **coherence retention**. Random phases test **formation**. These are different questions.

3. **Candidate computational mechanisms (hypotheses only).**  
   At **fixed κ_eff**, optional modules  
   `noise_suppression`, `freq_narrowing`, `residual_meanfield`  
   can change mean CI relative to `none`.  
   That shows a **model residual**, not nature.

4. **Failures exist.**  
   Low κ_eff + random IC produces genuine non-sync (archived in `raw_sweeps/`).

## Not allowed (not supported)

| Claim | Why forbidden |
|-------|----------------|
| Alpha-specific physical synchronization mechanism | Not isolated under gain map; candidates unvalidated |
| Lower *effective* coupling threshold from “20×” bare ratios | Confounds nominal κ_bare with κ_eff |
| Biological / medical / gap-junction / dipole proof | No external data in this package |
| Energy / free-energy / universal-theory proof | E_eff is a model index only |
| Topology-insensitive universal law | Prior claims confounded by near-sync IC + high κ_eff |

## One-sentence public summary

> This is a conditional Kuramoto simulation study of a gain-rescaling rule and optional extra model terms; it does not establish a physical alpha mechanism.
