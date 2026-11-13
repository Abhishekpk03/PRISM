# Running PRISM on your own machine

You downloaded `PRISM-github-repo.zip`. This page takes you from the zip to the running app with the
fewest possible steps, then tells you what to do when something goes wrong.

**Total time: about 60 seconds.** The only prerequisite is Python 3.10 or newer.

---

## Step 0 — Check you have Python

Open a terminal (Windows: **Start → "cmd"**; macOS: **Terminal**; Linux: **Ctrl+Alt+T**) and run:

```bash
python3 --version        # macOS / Linux
py --version             # Windows
```

You want **3.10 or higher**. If it says 3.9, or "command not found":

| Platform | What to do |
|---|---|
| Windows | Install from https://python.org/downloads and **tick "Add python.exe to PATH"** on the first screen. This checkbox is the single most common cause of a broken setup. |
| macOS | `brew install python` — or the installer at https://python.org/downloads |
| Linux | `sudo apt install python3 python3-venv` (Debian/Ubuntu) |

Nothing else is needed. **You do not need git.** You do not need to install flask yourself.

---

## Step 1 — Unzip

Extract `PRISM-github-repo.zip`. You get:

```
abhedya/
├── RUN_LOCALLY.md      ← this file
├── README.md
├── prism/              the engine
└── prototype/          the web app
    ├── run.py          ← the launcher you are about to use
    ├── run.bat         ← Windows: double-click this instead
    ├── run.command     ← macOS: double-click this instead
    └── app.py
```

**Unzip properly — do not just preview inside the zip viewer.** On Windows, right-click → *Extract
All*. On macOS, double-click the zip. The app needs to write a database file next to itself, which it
cannot do inside a compressed archive.

---

## Step 2 — Start it

### The easy way

| Your system | Do this |
|---|---|
| **Windows** | Open the `abhedya\prototype` folder and **double-click `run.bat`** |
| **macOS** | Open the `abhedya/prototype` folder and **double-click `run.command`**¹ |
| **Linux / any terminal** | The commands below |

```bash
cd abhedya/prototype
python3 run.py
```

¹ If macOS refuses with *"cannot be opened because it is from an unidentified developer"*, right-click
the file → **Open** → **Open** again. Or just use the terminal commands.

### What you will see

```
First run: creating an isolated environment in .venv ...
Installing flask into .venv (about 10 seconds, one time only) ...
Re-launching inside .venv ...
Python  3.13.18
Flask   3.1.3
Engine  .../abhedya/prism/pipeline.py

Starting PRISM on http://localhost:8000   (Ctrl+C to stop)
```

Your browser opens by itself. If it does not, open **http://localhost:8000** manually.

The first run takes ~15 seconds because it builds a private Python environment in `prototype/.venv`.
**Every run after that starts in about a second.** If port 8000 is already taken by something else,
the launcher picks the next free one and tells you which.

---

## Step 3 — Confirm it is real

Click **Dashboard** in the left sidebar. You should see **14 buildings**, **7 RED**, and *engine online
· 10/10 tests* in the bottom-left corner.

Then: **Collapse ops → pick "SN-1147 — Satya Niketan" → Run pipeline → 3.88 expected lives.**

That number is the point. It matches the figure in the solution PDF exactly, because the app is pinned
to the same seed the document used. If you see 3.88, the engine, the database and the UI are all
healthy.

---

## Thorough check (optional, 20 seconds)

Confirm the engine independently of the web app:

```bash
cd abhedya/prism
python3 redteam.py
```

Expected: `PRISM RED TEAM -- 10/10 adversarial checks passed`. This needs no dependencies at all.

---

## Stopping it

Press **Ctrl+C** in the terminal window. On Windows, closing the window also stops it.

---

## Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `python3: command not found` | Python not installed, or not on PATH | Install from python.org; on Windows tick "Add python.exe to PATH" |
| `python` opens the Microsoft Store | Windows' stub for a missing install | Install real Python from python.org, or use `py run.py` |
| `Could not install flask` | No internet on first run | Connect once and rerun. Behind a proxy: `set HTTPS_PROXY=http://user:pass@host:port` (Windows) or `export HTTPS_PROXY=...` (macOS/Linux) |
| `error: externally-managed-environment` | A bare `pip install` on Debian/Ubuntu 12+ | You should not see this — `run.py` installs into `.venv`, never system Python. If you see it, you ran `pip` directly: use `python3 run.py` instead |
| `Address already in use` | Another server on port 8000 | The launcher now moves to 8001 automatically. To force one: `python3 run.py --port 9000` |
| Browser shows *"This site can't be reached"* | Wrong port, or the server did not start | Read the terminal. The real port is printed on the `Starting PRISM on ...` line |
| Page loads but is blank/unstyled | You opened `index.html` from the file system | Open `http://localhost:8000`, not the file. The app needs the server |
| `Permission denied` on `run.sh`/`run.command` | Files lost their execute bit (common after unzip on Windows) | `chmod +x run.sh run.command`, or just run `python3 run.py` |
| Antivirus quarantines `.venv` | Some corporate AV flags new venvs | Add the folder to your AV exclusions, or use the system Python route below |
| Windows Defender "Windows protected your PC" on the zip | Mark-of-the-web on downloads | *More info → Run anyway* |
| Nothing happens on double-click | `.bat`/`.command` association broken | Use the terminal commands — they always work |

### The manual route, if the launcher cannot work in your environment

Five lines, no magic:

```bash
cd abhedya/prototype
python3 -m venv .venv
source .venv/bin/activate        # Windows: .venv\Scripts\activate
pip install flask
python app.py
```

Then open http://localhost:8000.

---

## What the app writes to your disk

| File | What it is | Safe to delete? |
|---|---|---|
| `prototype/prism.db` | Your buildings and every run you have made | Yes — it is recreated and reseeded on next start. Use **Data → Reseed demo data** to reset without deleting. |
| `prototype/.venv/` | A private Python environment with flask | Yes — rebuilt on next run (costs ~15 s) |

Nothing else is written, nothing is sent anywhere, and the app makes no outbound network calls.
It runs entirely on your machine.

---

## Common questions

**Do I need to install a database?**
No. SQLite ships inside Python; `prism.db` is a single file created on first run.

**Can I open it from my phone on the same Wi-Fi?**
Yes — the server binds `0.0.0.0`. Find your computer's local IP (`ipconfig` / `ifconfig`) and open
`http://<that-ip>:8000` on the phone.

**Can I add my own buildings?**
Yes. **Intake** in the sidebar, or paste a JSON array in **Data → Import**. The band updates live as
you type, using the same function the engine uses.

**Can I run this on a server for the judges?**
Yes, but replace the Flask development server with a real one:
`pip install waitress && waitress-serve --port 8000 app:app` (Windows/Linux) or use gunicorn on macOS.
The development server is not built for concurrency.

**Does it need internet?**
Only for the one-time flask install. After that, fully offline.
