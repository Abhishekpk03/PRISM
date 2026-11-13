# PRISM — the application

This is the **app-only** package: the working prototype and the engine it calls. Nothing else.

```
prism-app/
├── RUN_LOCALLY.md     ← start here: from this folder to a running app
├── prism/             the engine (703 lines, standard library only)
│   ├── pipeline.py
│   ├── redteam.py     10 adversarial checks, 10/10
│   └── PIPELINE.md
└── prototype/         the Flask + SQLite web app, seven sections
    ├── run.py         launcher: venv, flask, free port, opens browser
    ├── run.bat        Windows double-click
    ├── run.command    macOS double-click
    ├── app.py
    └── static/        index.html, app.js, style.css
```

## Run it

**Windows** — double-click `prototype\run.bat`
**macOS** — double-click `prototype/run.command`
**Linux / terminal**

```bash
cd prototype
python3 run.py
```

Then open **http://localhost:8000**. First run takes ~15 seconds (it builds a private `.venv` and
installs flask); every run after that is about a second. Python 3.10+ is the only prerequisite.

## Check it works

```bash
cd prism && python3 redteam.py      # expect: 10/10 adversarial checks passed
```

In the app: **Dashboard** should show 14 buildings, 7 RED, and *engine online · 10/10 tests*.
Then **Collapse ops → SN-1147 → Run pipeline** should give **3.88 expected lives** — the same figure
printed in the solution PDF.

## The seven sections

| Section | The question it answers |
|---|---|
| Dashboard | How big is my problem, and where is the worst of it? |
| Building queue | Which building collapses first, on records alone? |
| Intake | A new record just arrived — what band does it land in, live? |
| Collapse ops | This one has come down. What mechanism, how many inside? |
| Tasking | N teams, H hours. Which hole, in what order, what will I not reach? |
| Accuracy | What does "95 %" mean here — computed, not asserted? |
| Data | Where did each field come from, what has the system produced? |

## Notes

- The browser performs no arithmetic. Every figure comes from `/api/*`, which calls the same functions
  the command line and the red-team suite call.
- The 14 buildings are synthetic demo records. Nothing here is a claim about a real address.
- `prototype/prism.db` is created on first run and holds your edits. **Data → Reseed** resets it.
- Full troubleshooting for every platform is in **RUN_LOCALLY.md**.

For the full repository — solution document, problem statement, deck, research, git history — use
`PRISM-github-repo.zip` instead.
