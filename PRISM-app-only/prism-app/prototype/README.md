# PRISM — collapse decision system, working prototype

A Flask + SQLite application over the tested engine in `../prism/pipeline.py`. The browser never
does the maths: every number on screen arrives from a `/api/*` call that calls the same functions
the command-line demo and the red-team suite call.

## Run

```bash
cd abhedya/prototype
python3 run.py           # creates .venv, installs flask, opens the browser
```

Windows: double-click `run.bat`. macOS: double-click `run.command`. The launcher finds a free port
automatically, so a busy 8000 is not a problem.

Full instructions, including troubleshooting for every platform, are in
[`../RUN_LOCALLY.md`](../RUN_LOCALLY.md).

If you already have flask installed, `python3 app.py` runs the server directly on port 8000.

Open `http://<host>:8000`. The database `prism.db` is created on first run and seeded with 14 Delhi
building records; it persists across restarts. Delete it to start clean.

## The seven sections

| Section | What it does | Where the numbers come from |
|---|---|---|
| **Dashboard** | queue size, band split, highest standing risk, engine status, run history | `/api/summary`, `/api/buildings` |
| **Building queue** | every property ranked by load ratio; filter by band or collapsed; drawer with the record | `standing()`, `satellite()` |
| **Intake** | add a building; the band recomputes on every keystroke (debounced 180 ms) | `POST /api/preview` → `standing()` |
| **Collapse ops** | nine-stage chain: posterior, occupancy, policy check, top of the dig list | `POST /api/run` → the whole chain |
| **Tasking** | per-team gantt coloured by survival at entry, full ranked list, unreached and expectant panels | `plan_dig_first()`, `expected_lives()` |
| **Accuracy** | the nine metrics behind "95 %", the PPV grid, live determinism check, red-team runner | `/api/accuracy`, `/api/selfcheck`, `redteam.run_all()` |
| **Data** | export / import / reseed, open-data provenance, run history, raw records | `prism.db` |

## Traceability rules the app obeys

1. **No arithmetic in JavaScript.** The UI formats and sorts; it never scores. If a figure is on
   screen, a tested Python function produced it.
2. **The seed is a constant of the build (`DEFAULT_SEED = 7`).** The app reproduces the documented
   run exactly: Satya Niketan, 3 teams, 24 h → 3.88 expected lives, 9 pockets, top five pockets
   at ELSE 0.499 / 0.274 / 0.226 / 0.210 / 0.201. The Accuracy page proves determinism live by
   running the same record twice and comparing the plans.
3. **Refusal survives the UI.** A novel or ambiguous structure shows `UNCERTAIN · NOVEL` and falls
   back to the survivable-void prior; pockets nobody will reach in time are listed under
   *Stated, not hidden*; expectant is never rendered as dead.
4. **A pre-plan is not a dispatch.** Running a building that has not collapsed labels the whole page
   `PRE-PLAN` and relabels the life figure "lives at risk, modelled".

## API

| Method | Path | Purpose |
|---|---|---|
| GET | `/api/health` | engine liveness, red-team score |
| GET/POST/DELETE | `/api/buildings[/<bid>]` | the record store |
| GET | `/api/summary` | counts, bands, recent runs |
| POST | `/api/preview` | live standing score for the intake form |
| POST | `/api/run` | full chain; persists the run and returns the plan |
| GET | `/api/runs`, `/api/runs/<id>` | run history, reload a saved plan |
| GET | `/api/accuracy` | the nine metrics and the PPV grid |
| GET | `/api/selfcheck` | determinism check, run twice, compared |
| POST | `/api/redteam` | the ten adversarial checks |
| GET | `/api/export`, POST `/api/import`, POST `/api/reseed` | data movement |

## Files

```
app.py              Flask app: SQLite store, coercion at the boundary, run_engine()
static/index.html   shell: sidebar, topbar, drawer, toast
static/style.css    self-contained design system (no CDN, no external fonts)
static/app.js       hash router and the seven view renderers
requirements.txt    flask>=3.0
run.py              cross-platform launcher: venv, flask, free port, opens browser
run.bat             Windows double-click launcher
run.command         macOS double-click launcher
run.sh              bash launcher
verify_ui.py        headless check of all seven sections
```

## Known limits, stated rather than hidden

- The 14 building records are **synthetic**, shaped field-for-field like the open-data sources listed
  on the Data page. No live adapter is wired, so nothing here is a claim about a real Delhi address.
- Single-process Flask development server. Concurrency is not the subject of this prototype.
- No authentication: this is a contest demo, not a deployed system.
