# PRISM — a collapse-decision system that refuses to guess

**Which hole do I dig first — and what exactly do I not know?**

INNOVEX 2026 · Season 02 · NSS IT Wing · Problem Statement 5 *"Project Abhedya"* · Focus Area 03, Search & Rescue

```
engine            703 lines of Python · standard library only · no dependencies
red team          10 / 10 adversarial checks passing
prototype         7 sections · Flask + SQLite · verified headlessly, 0 console errors
provenance        every number on screen traced to a tested function; seed pinned to 7
```

![Dashboard](docs/screenshots/01-dashboard.png)

---

## The premise

PRISM is a decision system for the first hours after a structural collapse. It answers one question
for a rescue commander: *given a stack of property records and no sensors on the ground yet, which
hole do I dig first, and what exactly do I not know?*

It starts from an uncomfortable premise. The sensor story that wins hackathons — drones, thermal,
ground-penetrating radar, "AI finds survivors" — is not what is missing in the field. What is missing
is that **a building's own records already contain much of the answer**, and nobody joins them to the
collapse. Declared floors against built floors. Design occupancy against actual. A two-storey
sanction and a six-storey building.

PRISM joins them, carries each record's bias into the estimate rather than discarding it, and ranks
survivable voids by **expected lives per team-hour** — so the plan is executable rather than
aspirational.

And where the records cannot answer, it says so. That refusal is the invention, not a shortcoming.

---

## Quickstart

```bash
git clone https://github.com/<you>/<repo>.git && cd <repo>

python3 prism/redteam.py        # 10/10, no dependencies
cd prototype && ./run.sh        # installs flask if missing, serves 0.0.0.0:8000
```

Open `http://localhost:8000`. The database is created and seeded with 14 building records on first
run; it persists across restarts. Two minutes of clicking: **Dashboard → Building queue → Collapse
ops → pick a collapsed building → Run pipeline → Tasking.**

---

## The application

Not a one-page demo. Seven sections, each answering a different question a commander actually asks.

| Section | The question it answers |
|---|---|
| **Dashboard** | How big is my problem, and where is the worst of it? |
| **Building queue** | Which of these 14 buildings collapses first, on records alone? |
| **Intake** | I just got a new record — what band does it land in, live? |
| **Collapse ops** | This one has come down. What mechanism, and how many people are inside? |
| **Tasking** | I have N teams and H hours. Which hole, in what order, and what will I not reach? |
| **Accuracy** | What does "95 %" mean here, computed rather than asserted? |
| **Data** | Where did every field come from, and what has the system produced? |

![Collapse ops](docs/screenshots/02-collapse-ops.png)

The browser performs no arithmetic. Every figure arrives from `/api/*`, which calls the same functions
the command-line demo and the red-team suite call. The app is pinned to `DEFAULT_SEED = 7` — the seed
used in the documents — so on-screen numbers are the *documented* numbers, not merely similar ones.
Satya Niketan at 3 teams over 24 h gives **3.88 expected lives** and a top-five dig list at ELSE
**0.499 / 0.274 / 0.226 / 0.210 / 0.201**, exactly as printed in the solution PDF.

![Tasking](docs/screenshots/03-tasking.png)

The tasking view is where the honesty is most visible. One team on a 12-hour horizon does not
silently drop the rest of the list — it states **"Not reached within 12 h: V01, V06, V02, V04, V03,
V08 — re-triage when a team frees up."**

---

## The pipeline

```
                    ┌──────────────┐   ┌──────────────┐   ┌───────────────────┐
 records ─────────▶ │ ① standing   │──▶│ ② satellite  │──▶│ ③ mechanism       │
 declared vs built  │    band      │   │   auditor    │   │   posterior       │
                    └──────────────┘   └──────────────┘   └─────────┬─────────┘
                                                                    │ gate 0.60
                    ┌──────────────┐   ┌──────────────┐   ┌─────────▼─────────┐
 clearance ◀────────│ ⑥ tasking    │◀──│ ⑤ survival   │◀──│ ④ void field      │
 k-of-n PPV         │  lives /     │   │   clock      │   │   where the air   │
                    │  team-hour   │   │              │   │   pockets are     │
                    └──────────────┘   └──────────────┘   └───────────────────┘
```

| # | Stage | What it does | The honest part |
|---|---|---|---|
| 1 | **Standing band** | Load ratio from declared-vs-built floors × design-vs-actual occupancy; gravity and seismic fragility | Reported as probability *conditional on a design-basis event*, not an annual rate, and labelled as such |
| 2 | **Satellite auditor** | Sentinel-2 roof geometry against the sanctioned footprint | 10 m per pixel. A 46 m² plot is 0.46 px. The output is often *"imagery cannot see this building"* |
| 3 | **Mechanism posterior** | Six collapse classes, Bayes mixture | Below the 0.60 gate: `UNCERTAIN`, not a best guess |
| 4 | **Void field** | Where a person could still be alive, dig effort per pocket | Geometry follows the lead mechanism, not a uniform grid |
| 5 | **Survival clock** | Time of day, heads known, lognormal survival per pocket | Calibration is against literature, not a registry — stated, not hidden |
| 6 | **Tasking** | `ELSE` = lives per team-hour, scheduled across teams with a duty cycle | Unreached pockets are named |
| 7 | **Sensing** | Phone census, last-gasp sensor hits | Each carries its own bias; silence is not absence |
| 8 | **Evidence ledger** | Every claim, its source, and its confidence | Declared vs observed is never blurred |
| 9 | **Clearance algebra** | k-of-n confirmations before a pocket is called clear | False-positive rate stated, not assumed away |

---

## The 95 % claim, stated honestly

Nine metrics sit behind the phrase. **Four are reached.** The rest are named.

| Claim | Metric | Path | Verdict |
|---|---|---|---|
| A pocket declared clear really is clear | PPV | k-of-3 → **0.9101** at prior 0.1; **0.9891** at 0.5 | Achievable |
| A breathing casualty is detected | POD | 0.80 sensor × 3 passes → **0.992** | Achievable |
| The plan is reproducible | Determinism | same inputs, same plan — checked live in the app | **Achieved** |
| An over-built property is flagged | Recall on audit | declared-vs-built join against municipal ground truth | Achievable |
| Ranking puts a casualty in the top three | Hit@3 | blind back-test on 30 collapses | Unproven |
| Occupancy within ±25 % | MAPE | phone census + listing refresh | Plausible |
| Mechanism named correctly | Top-1 accuracy | no labelled rubble dataset exists | Not achievable |
| Survival estimate calibrated | Brier / ECE | needs an outcome registry | Not achievable |
| Collapse prevented | Incidence | brittle failure has no precursor | Out of scope |

Only three things move a number toward 95 %: **redundancy** (buy independent confirmations), **better
prior data** (records before sensors), and **refusal** (say `UNCERTAIN` instead of estimating). The
third is the invention. *PRISM is designed so that its failures are legible.*

![Accuracy](docs/screenshots/04-accuracy.png)

---

## Honesty rules the code enforces

- **No verdict of "no survivors."** A cleared pocket is a statement about a search area, never about a
  person. Expectant is a resource judgment, not a death certificate — a red-team test forbids the word
  in the output.
- **Sensor silence is not proof of absence.** After an all-negative phone census the belief floor is
  0.03, not zero.
- **Unverifiable is not compliant.** A building with no sanction plan and no independent observation
  gets its band floored at AMBER rather than a GREEN built from missing evidence.
- **A pre-plan is not a dispatch.** The app labels runs against uncollapsed buildings `PRE-PLAN` and
  calls the figure "lives at risk, modelled" — never "lives saved".
- **Capacity shortfall is stated.** Pockets the horizon cannot cover are listed by name, not dropped.

---

## What is verified, and how

```bash
python3 prism/redteam.py          # 10/10
cd prototype && python3 verify_ui.py   # drives all 7 sections, fails on any console error
```

The ten adversarial checks cover: unit consistency, scheduler safety, posterior normalisation,
survival monotonicity, unknown structures, stale records, sensor silence, forbidden output, capacity
shortfall, and the value-of-information regime.

`verify_ui.py` drives the running app in a headless browser and fails loudly on any console error. **It
found eight real defects**, including an accuracy page that fetched nothing, string values reaching
the engine from the intake form, and a per-process `hash()` that silently changed the dig plan between
server restarts — which would have made the "same inputs, same plan" claim false in the product while
true in the report. All eight are fixed; the screenshots in this README come from that harness.

---

## Repository map

| Path | What it is |
|---|---|
| `prism/pipeline.py` | The engine — nine stages, `math` and `random` only |
| `prism/redteam.py` | Ten adversarial checks, 10/10 |
| `prism/PIPELINE.md` | Stage-by-stage specification and the failure mode of each stage |
| `prototype/` | Flask + SQLite app, seven sections, with its own README |
| `PROBLEM_STATEMENT.md` / `.pdf` | 7-page gap analysis: exact failure points, with sources |
| `SOLUTION_DESCRIPTION.md` / `.pdf` | 10-page solution document, 95 % treated as maths, kill criteria |
| `PRISM_pipeline.pptx` | 16-slide deck · `PIPELINE_SPEAKER_SCRIPT.md` |
| `research/` | Analysis and figure-generation scripts behind the documents |
| `docs/screenshots/` | The running application |

The documents are **generated** by `build_problem_pdf.py`, `build_solution_pdf.py` and
`build_pipeline_deck.py`. Corrections flow from code to document, never the other way.

---

## Known limits

- The 14 building records are **synthetic**, shaped field-for-field like the open-data sources the
  pipeline expects (OSM/Overpass, Google Open Buildings 2.5D, Sentinel-2, municipal tax records, NDMA
  SACHET, IMD) so a live adapter can replace them without touching the engine. Nothing here is a claim
  about a real Delhi address.
- The satellite stage audits *whether imagery can answer the question*. It does not claim satellite
  detects rebar corrosion, storey legality, or a collapse in real time.
- No outcome registry exists, so survival estimates are calibrated against literature rather than
  recovered casualties. Listed as not achievable rather than hidden.
- `prototype/` runs on the Flask development server. Concurrency is not the subject of this build.

---

## Requirements

Python 3.10+ for the engine (no third-party packages). The prototype needs `flask` and installs it on
first run. Regenerating the PDFs and deck needs `reportlab`, `pymupdf` and `python-pptx`; the built
artefacts are committed so you do not need them to read or run anything.

---

<sub>Built for INNOVEX 2026. No licence specified — add one before reuse.</sub>
