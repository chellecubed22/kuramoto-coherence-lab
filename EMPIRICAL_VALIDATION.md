# Empirical validation boundary (Task 4)

Simulations alone **cannot** promote any candidate mechanism to biology or physics.

## What would be required (external)

| Domain | Minimum independent evidence |
|--------|------------------------------|
| **Physics** | Measured coupling / noise / frequency statistics that match a *specific* mechanism formula; blinded comparison vs null models; published methods |
| **Biology** | Pre-registered experiment; controls; effect size; replication; ethics approval where applicable |
| **Engineering** | Hardware or field data with error bars; failure modes; independent replication |

## Mapping candidates → measurable targets (if ever tested)

| Mechanism (sim only) | Would need to measure |
|----------------------|------------------------|
| `noise_suppression` | Phase noise vs a control that holds coupling fixed |
| `freq_narrowing` | Natural-frequency dispersion under the claimed condition |
| `residual_meanfield` | Extra global drive **not** explained by pairwise κ_eff |

## Process

1. Keep κ_eff matched in any model–data comparison.  
2. Pre-specify the mechanism equation **before** looking at data.  
3. Report failures and null results.  
4. Do **not** retrofit “alpha” language onto unrelated success.

## Status in v1.2

- **Gain map:** falsified as an *independent* sync mechanism (matched-κ_eff Δ ≈ 0).  
- **Candidate extras:** computational only; **no** empirical validation included.  
- **Bio/physics claims:** **closed** until external evidence exists.
