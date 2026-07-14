# Kuramoto Coherence Lab

**A conditional simulation study — computational only**

Small Python lab for **noisy Kuramoto networks**: coherence index (CI), a 1/α-style **gain rescaling** map, matched-κ_eff controls, and optional residual model terms.

> This does **not** prove a physical alpha force, biological/medical effect, energy device, or Theory of Everything.  
> See [CLAIMS.md](CLAIMS.md).

Based on work by Michelle D. Williams (simulation suite v1.2 lineage). Public product name is intentionally plain so strangers know what they are installing.

---

## What you can do with it

| Command | Purpose |
|---------|---------|
| `python run_framework.py --quick` | ~1 minute demo: matched gain map + candidate mechanisms |
| `python run_framework.py --suite --output ./output` | Full sweep package (slower) |

---

## Quick start (Windows PowerShell)

```powershell
git clone https://github.com/Chellecubed22/kuramoto-coherence-lab.git
cd kuramoto-coherence-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_framework.py --quick
```

> If the GitHub username differs, replace `Chellecubed22` with yours after the first push.

### Mac / Linux

```bash
git clone https://github.com/Chellecubed22/kuramoto-coherence-lab.git
cd kuramoto-coherence-lab
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python run_framework.py --quick
```

**Requirements:** Python 3.10+, see `requirements.txt` (`numpy`, `matplotlib`).

---

## What the quick demo shows

1. **Gain map is a dial** — at the **same** effective coupling κ_eff, α-on and α-off should match (reparameterization, not a free magic effect).  
2. **Optional mechanisms** at fixed κ_eff — computational hypotheses only (`noise_suppression`, `freq_narrowing`, `residual_meanfield`).  
3. **No external bio/physics validation** in this package.

Retention (near-sync start) and formation (random phases) are different questions — see CLAIMS.md.

---

## Project layout

```
run_framework.py          # entry point
requirements.txt
CLAIMS.md                 # what you may / may not claim
EMPIRICAL_VALIDATION.md   # boundary notes (if present)
config/                   # parameters / networks
alpha_resonance/          # source
examples/                 # sample figures / summaries from prior runs
START_HERE.md             # full ship-from-scratch guide for the author
```

---

## Honest one-sentence summary

This is a **conditional Kuramoto simulation study** of a gain-rescaling rule and optional extra model terms; it does **not** establish a physical alpha mechanism.

---

## License

MIT — see [LICENSE](LICENSE).

---

## Contact

Michelle D. Williams — `chellecubed22@outlook.com`
