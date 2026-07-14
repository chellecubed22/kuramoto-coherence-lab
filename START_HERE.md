# START HERE — From scratch to “one other person can use this”

This folder is a **clean ship kit** built from your existing simulation suite.
Follow the steps in order. Do not skip ahead to GitHub until Step 4 works on your PC.

**Product name (honest):** Kuramoto Coherence Lab  
**What it is:** A small Python package that simulates noisy Kuramoto networks and tests a gain-rescaling rule.  
**What it is not:** A Theory of Everything, medical tool, energy device, or planetary system.

---

## Big picture (5 stages)

| Stage | Goal | Done when |
|-------|------|-----------|
| 1 | Run it on *your* computer | `python run_framework.py --quick` prints numbers |
| 2 | Make it stranger-proof | README is clear; claims are bounded |
| 3 | User test with one human | Someone else runs it once successfully |
| 4 | Put it on the internet | Public GitHub repo exists |
| 5 | (Optional) Citeable snapshot | Zenodo/OSF DOI |

---

## Stage 0 — What you need installed

1. **Python 3.10+** (you already have Python on this machine).
2. **Git** (you already have Git).
3. A free **GitHub** account: https://github.com/signup  
4. A terminal: PowerShell is fine.

Check:

```powershell
python --version
git --version
```

---

## Stage 1 — Run the lab on your machine (30 minutes)

### 1.1 Open the project folder

```powershell
cd $env:USERPROFILE\Documents\Projects\Kuramoto_Coherence_Lab
```

### 1.2 Create a virtual environment (keeps packages clean)

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

If PowerShell blocks activation:

```powershell
Set-ExecutionPolicy -Scope CurrentUser RemoteSigned
.\.venv\Scripts\Activate.ps1
```

### 1.3 Install dependencies

```powershell
python -m pip install --upgrade pip
pip install -r requirements.txt
```

### 1.4 Run the 60-second demo

```powershell
python run_framework.py --quick
```

**Success looks like:**

- Banner about gain rescaling / computational only  
- Section `[1]` matched κ_eff α-on / α-off with similar mean CI  
- Section `[2–3]` mechanism names with mean CI numbers  
- No red traceback  

### 1.5 (Optional) Longer suite

```powershell
python run_framework.py --suite --output .\output
```

This can take much longer. For shipping, **`--quick` is enough**.

**Checkpoint:** If Stage 1 fails, fix that before anything else. Nobody else can use what you cannot run.

---

## Stage 2 — Make it stranger-proof (1–2 hours)

A stranger only needs three things:

1. **README.md** — what it is, how to run, what not to claim  
2. **CLAIMS.md** — hard boundaries  
3. **requirements.txt** — dependencies  

You already have these in this folder. Read them once and edit only:

- Your preferred display name in README  
- Contact email (optional)  
- GitHub username placeholders  

**Rules for the public surface:**

- Use the lab name, not “planetary OS”  
- Keep the one-sentence summary from CLAIMS.md  
- Do not add glyphs, balloons, HSRT merge language to the README  

**Checkpoint:** Hand the README to yourself tomorrow morning. If you can follow it cold, a stranger might too.

---

## Stage 3 — One other person (the real “use” test)

Pick **one** person:

- A patient friend with a laptop, **or**  
- Henric (ask for a **reproduction check**, not co-authorship), **or**  
- A Discord/Reddit tech helper who likes “try this zip”

### Message you can copy/paste

```text
Could you help me with a 10-minute test?

1. Install Python 3.10+ if needed
2. Download/clone this project
3. In the folder, run:

   python -m venv .venv
   .venv\Scripts\activate          (Windows)
   # or: source .venv/bin/activate (Mac/Linux)
   pip install -r requirements.txt
   python run_framework.py --quick

4. Reply with: did it work? paste the last ~20 lines of output.
   (No need to understand the theory.)
```

**Success:** they get numbers without you screen-sharing for an hour.  
**Failure:** fix README/install steps from their confusion, then try again.

Do **not** call it a world-changing framework when you ask. Call it a small simulation lab.

---

## Stage 4 — Put it on GitHub (so the internet can use it)

### 4.1 Create an empty repo on GitHub

1. Log into GitHub  
2. **New repository**  
3. Name: `kuramoto-coherence-lab`  
4. Public  
5. **Do not** add README/license on GitHub if this folder already has them (avoids merge mess)  
6. Create  

### 4.2 Initialize git in this folder and push

```powershell
cd $env:USERPROFILE\Documents\Projects\Kuramoto_Coherence_Lab

# ignore junk
@"
.venv/
__pycache__/
*.pyc
output/
.DS_Store
"@ | Set-Content .gitignore

git init
git add .
git status
git commit -m "Initial public release: Kuramoto Coherence Lab (conditional simulation study)"

# Replace YOURUSER with your GitHub username
git branch -M main
git remote add origin https://github.com/YOURUSER/kuramoto-coherence-lab.git
git push -u origin main
```

If GitHub asks you to log in, use a **Personal Access Token** or GitHub CLI (`gh auth login`).

### 4.3 Add a short About blurb on GitHub

```text
Conditional Kuramoto network lab: gain rescaling + controls. Computational only — not physics/medical claims.
```

**Checkpoint:** Open the repo in a private browser window. Clone it to a **second folder** and run Stage 1 again as if you were a stranger:

```powershell
cd $env:USERPROFILE\Downloads
git clone https://github.com/YOURUSER/kuramoto-coherence-lab.git
cd kuramoto-coherence-lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_framework.py --quick
```

If that works, you have shipped something **one other person can use**.

---

## Stage 5 — Optional upgrades (only after Stage 4)

| Upgrade | Why | When |
|---------|-----|------|
| MIT or Apache-2.0 `LICENSE` file | Clear reuse rights | With first public push |
| Zenodo “DOI” from GitHub | Citable snapshot | After README is stable |
| Google Colab notebook | No local install | If friends hate terminals |
| 2–4 page PDF methods note | Academia-shaped | After one external re-run |

Colab sketch (later): upload the repo or open from GitHub → one cell `!pip install -r requirements.txt` → one cell `!python run_framework.py --quick`.

---

## What not to build in this first ship

- Planetary dashboards, glyphs, StratoGlyph, ritual engines  
- “Alpha Resonance OS” branding as the product name  
- HSRT co-authorship claims  
- TOE / CMB / medical language  

Those block users. Ship the lab first.

---

## Troubleshooting

| Problem | Fix |
|---------|-----|
| `python` not found | Use full path or `py -3` on Windows |
| `pip` fails on matplotlib | `pip install numpy matplotlib` |
| Activation script disabled | `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` |
| Long suite too slow | Only ship `--quick` as the user path |
| Friend on Mac | Same steps; use `source .venv/bin/activate` |

---

## Definition of done

You are done with “something one person can use” when:

1. [ ] You run `--quick` successfully  
2. [ ] README + CLAIMS are honest  
3. [ ] One other human runs `--quick` (or you clone fresh and simulate stranger)  
4. [ ] Public GitHub link works without your personal `Documents` path  

Everything else is optional.

---

## Your next 60 minutes (do only this)

```powershell
cd $env:USERPROFILE\Documents\Projects\Kuramoto_Coherence_Lab
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
python run_framework.py --quick
```

If that prints results, open `README.md`, put your GitHub username in the clone URL, then do Stage 4.
