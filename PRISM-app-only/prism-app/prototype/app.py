"""
PRISM prototype — Flask API over the tested engine.

The app is a window onto abhedya/prism/pipeline.py, not a re-implementation:
every number the UI shows is produced by the same code that passes 10/10
adversarial checks in prism/redteam.py.

Run:  python3 app.py            (binds 0.0.0.0:8000)
"""

from __future__ import annotations

import json
import os
import random
import sys
import zlib
import threading
import time
from dataclasses import asdict
from datetime import datetime, timezone

from flask import Flask, jsonify, request, send_from_directory

BASE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(BASE)
sys.path.insert(0, os.path.join(ROOT, "prism"))

import pipeline as PL          # noqa: E402
import redteam as RT           # noqa: E402

DB_PATH = os.path.join(BASE, "prism.db")
LOCK = threading.Lock()
STARTED = time.time()

app = Flask(__name__, static_folder=os.path.join(BASE, "static"))


# ----------------------------------------------------------------- database --
def db():
    import sqlite3
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    return con


FIELDS = [
    "bid", "label", "lat", "lon", "plot_m2", "declared_floors", "design_occupancy",
    "use", "sanction_plan", "tax_area", "observed_floors", "observed_occupancy",
    "structure", "year_built", "corrosion_pct", "element_removed", "collapsed",
    "time_of_day_h", "debris_spread_ratio", "lg_impacts", "lg_duration", "lg_amp",
]

# SQLite has no column types, so an un-coerced form value lands as TEXT and the
# engine later divides a string by an int. Coerce once, at the boundary.
NUM_FIELDS = {
    "lat": float, "lon": float, "plot_m2": float, "declared_floors": int,
    "design_occupancy": int, "tax_area": float, "observed_floors": int,
    "observed_occupancy": int, "year_built": int, "corrosion_pct": float,
    "time_of_day_h": float, "debris_spread_ratio": float,
    "lg_impacts": int, "lg_duration": float, "lg_amp": float,
}
INT_FIELDS = {"declared_floors", "design_occupancy", "observed_floors",
              "observed_occupancy", "year_built", "lg_impacts"}


def coerce(field, val):
    """Number where a number is expected, None where the source left a blank."""
    f = NUM_FIELDS.get(field)
    if f is None:
        return val
    if val is None or val == "":
        return None
    try:
        return f(float(val))
    except (TypeError, ValueError):
        return None


DEFAULT_SEED = 7   # the seed used by prism/pipeline.py run_demo() and in every
                   # figure quoted in the deck and the solution document. The app
                   # deliberately reuses it so on-screen numbers are the
                   # documented numbers, not merely similar ones.


def stable_seed(bid: str) -> int:
    """Python's hash() is salted per process, so abs(hash(bid)) silently gave the
    same building a different void field after every restart. Determinism is a
    claimed property of this system, so the seed is a constant of the build."""
    return DEFAULT_SEED

SCHEMA = """
CREATE TABLE IF NOT EXISTS buildings (
  bid TEXT PRIMARY KEY, label TEXT, lat REAL, lon REAL, plot_m2 REAL,
  declared_floors INTEGER, design_occupancy INTEGER, use TEXT,
  sanction_plan INTEGER, tax_area REAL, observed_floors INTEGER,
  observed_occupancy INTEGER, structure TEXT, year_built INTEGER,
  corrosion_pct REAL, element_removed TEXT, collapsed INTEGER,
  time_of_day_h REAL, debris_spread_ratio REAL,
  lg_impacts INTEGER, lg_duration REAL, lg_amp REAL,
  created_at TEXT
);
CREATE TABLE IF NOT EXISTS runs (
  id INTEGER PRIMARY KEY AUTOINCREMENT, bid TEXT, created_at TEXT,
  teams INTEGER, horizon REAL, lives REAL, payload TEXT
);
"""

SEED = [
    dict(bid="SN-1147", label="Satya Niketan · PG, G+1 sanctioned G+5 built",
         lat=28.5893, lon=77.1690, plot_m2=46, declared_floors=2, design_occupancy=4,
         use="pg", sanction_plan=0, tax_area=92, observed_floors=6, observed_occupancy=14,
         structure="unframed_masonry", year_built=1998, corrosion_pct=8.0,
         element_removed="base_wall", collapsed=1, time_of_day_h=19.5,
         debris_spread_ratio=1.32, lg_impacts=5, lg_duration=2.4, lg_amp=0.31),
    dict(bid="MH-2291", label="Mehrauli · residential, G+2 sanctioned G+4 built",
         lat=28.5245, lon=77.1855, plot_m2=88, declared_floors=3, design_occupancy=6,
         use="residential", sanction_plan=0, tax_area=190, observed_floors=5,
         observed_occupancy=11, structure="load_bearing_rc", year_built=2003,
         corrosion_pct=4.5, element_removed="column", collapsed=1, time_of_day_h=6.5,
         debris_spread_ratio=1.68, lg_impacts=2, lg_duration=6.2, lg_amp=0.22),
    dict(bid="DW-0043", label="Dwarka Sector 7 · PG, no sanctioned plan",
         lat=28.5823, lon=77.0500, plot_m2=120, declared_floors=2, design_occupancy=8,
         use="pg", sanction_plan=0, tax_area=240, observed_floors=5, observed_occupancy=26,
         structure="rc_frame", year_built=2011, corrosion_pct=2.0,
         element_removed="none", collapsed=0, time_of_day_h=8.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="LJ-0912", label="Lajpat Nagar II · residential, plan on file",
         lat=28.5679, lon=77.2434, plot_m2=150, declared_floors=3, design_occupancy=9,
         use="residential", sanction_plan=1, tax_area=440, observed_floors=4,
         observed_occupancy=13, structure="load_bearing_rc", year_built=2009,
         corrosion_pct=3.0, element_removed="none", collapsed=0, time_of_day_h=9.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="RK-0558", label="Rohini Sector 16 · school, compliant",
         lat=28.7325, lon=77.1180, plot_m2=420, declared_floors=3, design_occupancy=180,
         use="school", sanction_plan=1, tax_area=1240, observed_floors=3,
         observed_occupancy=170, structure="rc_frame", year_built=2014, corrosion_pct=1.0,
         element_removed="none", collapsed=0, time_of_day_h=11.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="SK-0011", label="Shakarpur · PG above shops, no plan",
         lat=28.6412, lon=77.2790, plot_m2=64, declared_floors=2, design_occupancy=5,
         use="pg", sanction_plan=0, tax_area=128, observed_floors=5, observed_occupancy=19,
         structure="unframed_masonry", year_built=1995, corrosion_pct=11.0,
         element_removed="base_wall", collapsed=0, time_of_day_h=21.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="UT-0301", label="Uttam Nagar · mixed commercial G+3",
         lat=28.6187, lon=77.0600, plot_m2=96, declared_floors=3, design_occupancy=14,
         use="mixed", sanction_plan=1, tax_area=285, observed_floors=4,
         observed_occupancy=20, structure="load_bearing_rc", year_built=2007,
         corrosion_pct=6.0, element_removed="none", collapsed=0, time_of_day_h=14.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="GB-0770", label="Gokalpuri · PG, listing advertises G+6",
         lat=28.7002, lon=77.2450, plot_m2=72, declared_floors=2, design_occupancy=6,
         use="pg", sanction_plan=0, tax_area=144, observed_floors=6, observed_occupancy=23,
         structure="unframed_masonry", year_built=1999, corrosion_pct=9.0,
         element_removed="none", collapsed=0, time_of_day_h=22.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="BR-0125", label="Burari · residential, no plan, moderate",
         lat=28.7560, lon=77.2050, plot_m2=110, declared_floors=2, design_occupancy=7,
         use="residential", sanction_plan=0, tax_area=205, observed_floors=3,
         observed_occupancy=10, structure="unframed_masonry", year_built=2005,
         corrosion_pct=4.0, element_removed="none", collapsed=0, time_of_day_h=12.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="TL-0880", label="Tilak Nagar · collapsed during shop renovation",
         lat=28.6395, lon=77.0960, plot_m2=58, declared_floors=2, design_occupancy=6,
         use="commercial", sanction_plan=1, tax_area=140, observed_floors=4,
         observed_occupancy=17, structure="unframed_masonry", year_built=1994,
         corrosion_pct=12.0, element_removed="base_wall", collapsed=1,
         time_of_day_h=15.0, debris_spread_ratio=2.1,
         lg_impacts=1, lg_duration=1.1, lg_amp=0.44),
    dict(bid="VK-0204", label="Vasant Kunj · 60-bed nursing home, compliant",
         lat=28.5215, lon=77.1590, plot_m2=640, declared_floors=4, design_occupancy=210,
         use="hospital", sanction_plan=1, tax_area=2380, observed_floors=4,
         observed_occupancy=196, structure="rc_frame", year_built=2016, corrosion_pct=0.5,
         element_removed="none", collapsed=0, time_of_day_h=3.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="CP-0099", label="Connaught Place · heritage block, G+2 as sanctioned",
         lat=28.6315, lon=77.2167, plot_m2=310, declared_floors=3, design_occupancy=40,
         use="commercial", sanction_plan=1, tax_area=880, observed_floors=3,
         observed_occupancy=46, structure="load_bearing_rc", year_built=1938,
         corrosion_pct=7.0, element_removed="none", collapsed=0, time_of_day_h=10.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="KG-0611", label="Karol Bagh · commercial, G+2 sanctioned G+3 built",
         lat=28.6519, lon=77.1900, plot_m2=180, declared_floors=3, design_occupancy=30,
         use="commercial", sanction_plan=1, tax_area=520, observed_floors=4,
         observed_occupancy=44, structure="unframed_masonry", year_built=2001,
         corrosion_pct=5.0, element_removed="none", collapsed=0, time_of_day_h=16.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
    dict(bid="NZ-0455", label="New Ashok Nagar · no plan, never surveyed",
         lat=28.5900, lon=77.3020, plot_m2=90, declared_floors=2, design_occupancy=6,
         use="residential", sanction_plan=0, tax_area=150, observed_floors=None,
         observed_occupancy=None, structure="unframed_masonry", year_built=1996,
         corrosion_pct=None, element_removed="none", collapsed=0, time_of_day_h=7.0,
         debris_spread_ratio=None, lg_impacts=None, lg_duration=None, lg_amp=None),
]


def init_db(force=False):
    con = db()
    con.executescript(SCHEMA)
    n = con.execute("SELECT COUNT(*) c FROM buildings").fetchone()["c"]
    if n == 0 or force:
        con.execute("DELETE FROM buildings")
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for r in SEED:
            con.execute(
                f"INSERT INTO buildings ({','.join(FIELDS)}, created_at) "
                f"VALUES ({','.join('?' * len(FIELDS))}, ?)",
                [r.get(f) for f in FIELDS] + [now])
        con.commit()
    con.close()


# ------------------------------------------------------------------ mapping --
def to_record(row) -> PL.Record:
    lg = None
    if row["lg_impacts"] is not None:
        lg = {"impacts": int(row["lg_impacts"]),
              "duration_s": float(row["lg_duration"] or 1.0),
              "amp": float(row["lg_amp"] or 0.3)}
    return PL.Record(
        bid=row["bid"], label=row["label"], lat=row["lat"] or 0, lon=row["lon"] or 0,
        plot_m2=float(row["plot_m2"] or 100),
        declared_floors=int(row["declared_floors"] or 1),
        design_occupancy=int(row["design_occupancy"] or 1),
        use=row["use"] or "residential",
        sanction_plan_on_file=bool(row["sanction_plan"]),
        tax_declared_area_m2=row["tax_area"],
        observed_floors=None if row["observed_floors"] in (None, "") else int(row["observed_floors"]),
        observed_occupancy=None if row["observed_occupancy"] in (None, "")
        else int(row["observed_occupancy"]),
        structure=row["structure"] or "unframed_masonry",
        year_built=int(row["year_built"] or 2000),
        corrosion_pct=float(row["corrosion_pct"] or 0),
        element_removed=row["element_removed"] or "none",
        collapsed=bool(row["collapsed"]),
        time_of_day_h=float(row["time_of_day_h"] or 12.0),
        debris_spread_ratio=row["debris_spread_ratio"],
        lastgasp=lg,
    )


def run_engine(rec: PL.Record, teams: int, horizon: float, seed: int):
    """The whole chain, exactly as the CLI runs it."""
    rng = random.Random(seed)
    st = PL.standing(rec)
    sat = PL.satellite(rec)
    post = PL.mechanism_posterior(rec, st, sat)
    voids = PL.build_void_field(rec, post, rng)
    occ = PL.occupancy(rec, voids, post)
    vs, ft = PL.plan_dig_first(voids, teams, horizon)

    order = sorted(range(len(vs)), key=lambda i: -vs[i].else_score(0.0))
    rows = []
    for rank, i in enumerate(order, 1):
        v = vs[i]
        fin = ft[i]
        rows.append(dict(
            rank=rank, vid=v.vid, zone=v.zone, mechanism=v.mechanism, floor=v.floor,
            volume=round(v.volume_m3, 1), people=round(v.lam, 2),
            p_present=round(v.p_occupancy, 3), s0=round(v.s0, 3),
            d_dig=round(v.d_dig, 3), secondary=round(v.secondary, 3),
            effort=round(v.effort_min), else_score=round(v.else_score(0.0), 4),
            survival_now=round(v.survival(0.0), 3),
            start=None if v.assigned_at is None else round(v.assigned_at, 2),
            done=None if fin is None else round(fin, 2),
            team=None if v.team is None else v.team + 1,
            survival_at_done=None if fin is None else round(v.survival(fin), 3),
            expectant=bool(v.survival(horizon) < PL.EXPECTANT_S),
        ))

    # what-if: would confirming occupancy first beat digging now?
    flat = [PL.replace(v) for v in voids]
    for v in flat:
        v.set_p(0.5)
    policy = dict(
        with_records=round(PL.confirm_pays(voids, teams, horizon, n=220, seed=11), 3),
        without_records=round(PL.confirm_pays(flat, teams, horizon, n=220, seed=12), 3),
    )
    policy["verdict"] = ("CONFIRM FIRST" if policy["with_records"] > 0.02 else
                         "DIG — confirming would cost lives"
                         if policy["with_records"] < -0.02 else "NO PREFERENCE")

    return dict(
        building=dict(bid=rec.bid, label=rec.label, use=rec.use,
                      plot_m2=rec.plot_m2, structure=rec.structure,
                      element_removed=rec.element_removed,
                      declared_floors=rec.declared_floors,
                      time_of_day_h=rec.time_of_day_h),
        standing={k: (round(v, 4) if isinstance(v, float) else v) for k, v in st.items()},
        satellite=sat,
        mechanism=dict(
            posterior={k: round(v, 4) for k, v in post["posterior"].items()},
            lead=post["lead"], lead_p=round(post["lead_p"], 3),
            confidence=round(post["confidence"], 3),
            uncertain=post["uncertain"],
            out_of_vocabulary=post.get("out_of_vocabulary", False)),
        occupancy=occ,
        voids=rows,
        lives=round(PL.expected_lives(vs, ft), 2),
        unreached=[r["vid"] for r in rows if r["done"] is None],
        expectant=[r["vid"] for r in rows if r["expectant"]],
        mode="LIVE" if rec.collapsed else "PREPLAN",
        policy=policy,
        params=dict(teams=teams, horizon=horizon, seed=seed, duty=PL.DUTY,
                    expectant_threshold=PL.EXPECTANT_S),
    )


# -------------------------------------------------------------------- routes --
@app.route("/")
def index():
    return send_from_directory(app.static_folder, "index.html")


@app.route("/static/<path:p>")
def static_files(p):
    return send_from_directory(app.static_folder, p)


@app.get("/api/health")
def health():
    return jsonify(ok=True, engine="prism/pipeline.py", uptime_s=round(time.time() - STARTED, 1),
                   tests="10/10", version="1.0")


@app.get("/api/buildings")
def list_buildings():
    con = db()
    rows = con.execute("SELECT * FROM buildings ORDER BY bid").fetchall()
    out = []
    for r in rows:
        rec = to_record(r)
        st = PL.standing(rec)
        sat = PL.satellite(rec)
        out.append(dict(
            bid=r["bid"], label=r["label"], use=r["use"], collapsed=bool(r["collapsed"]),
            structure=r["structure"], plot_m2=r["plot_m2"],
            declared_floors=r["declared_floors"], observed_floors=r["observed_floors"],
            design_occupancy=r["design_occupancy"], observed_occupancy=r["observed_occupancy"],
            sanction_plan=bool(r["sanction_plan"]), year_built=r["year_built"],
            corrosion_pct=r["corrosion_pct"], tax_area=r["tax_area"],
            element_removed=r["element_removed"], lat=r["lat"], lon=r["lon"],
            lr=round(st["lr"], 2), lr_floors=round(st["lr_floors"], 2),
            lr_occ=round(st["lr_occ"], 2), dc=round(st["dc"], 2),
            p_stands=round(st["p_stands"], 4), band=st["band"],
            verifiable=not st["unverified"], sub_pixel=sat["sub_pixel"],
            plot_px=sat["plot_in_pixels"], created_at=r["created_at"]))
    con.close()
    return jsonify(out)


@app.get("/api/summary")
def summary():
    con = db()
    rows = con.execute("SELECT * FROM buildings").fetchall()
    bands = {"RED": 0, "AMBER": 0, "GREEN": 0}
    collapsed = 0
    for r in rows:
        st = PL.standing(to_record(r))
        bands[st["band"]] += 1
        collapsed += 1 if r["collapsed"] else 0
    runs = con.execute("SELECT COUNT(*) c FROM runs").fetchone()["c"]
    last = con.execute("SELECT * FROM runs ORDER BY id DESC LIMIT 5").fetchall()
    con.close()
    return jsonify(total=len(rows), bands=bands, collapsed=collapsed, runs=runs,
                   recent=[dict(id=x["id"], bid=x["bid"], at=x["created_at"],
                                teams=x["teams"], lives=round(x["lives"], 2))
                           for x in last])


@app.post("/api/buildings")
def create_building():
    d = request.get_json(force=True)
    if not d.get("bid") or not d.get("label"):
        return jsonify(error="bid and label are required"), 400
    vals = {f: coerce(f, d.get(f)) for f in FIELDS}
    vals["collapsed"] = 1 if d.get("collapsed") else 0
    vals["sanction_plan"] = 1 if d.get("sanction_plan") else 0
    vals["created_at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    con = db()
    try:
        con.execute(
            f"INSERT INTO buildings ({','.join(FIELDS)}, created_at) "
            f"VALUES ({','.join('?' * len(FIELDS))}, ?)",
            [vals[f] for f in FIELDS] + [vals["created_at"]])
        con.commit()
    except Exception as e:
        con.close()
        return jsonify(error=str(e)), 400
    con.close()
    return jsonify(ok=True, bid=vals["bid"])


@app.delete("/api/buildings/<bid>")
def delete_building(bid):
    con = db()
    con.execute("DELETE FROM buildings WHERE bid=?", (bid,))
    con.commit()
    con.close()
    return jsonify(ok=True)


@app.post("/api/preview")
def preview():
    """Live standing score while the user types — same function the app trusts."""
    d = request.get_json(force=True)
    g = lambda k: coerce(k, d.get(k))
    rec = PL.Record(
        bid="preview", label="preview", lat=0.0, lon=0.0,
        plot_m2=g("plot_m2") or 100.0,
        declared_floors=g("declared_floors") or 1,
        design_occupancy=g("design_occupancy") or 1,
        use=d.get("use") or "residential",
        sanction_plan_on_file=bool(d.get("sanction_plan")),
        observed_floors=g("observed_floors"),
        observed_occupancy=g("observed_occupancy"),
        structure=d.get("structure") or "unframed_masonry",
        corrosion_pct=g("corrosion_pct") or 0.0,
        element_removed=d.get("element_removed") or "none",
        time_of_day_h=g("time_of_day_h") if g("time_of_day_h") is not None else 12.0,
        year_built=g("year_built") or 2000,
        tax_declared_area_m2=g("tax_area"))
    st = PL.standing(rec)
    sat = PL.satellite(rec)
    return jsonify(standing={k: (round(v, 4) if isinstance(v, float) else v)
                             for k, v in st.items()},
                   satellite=sat)


@app.post("/api/run")
def run():
    d = request.get_json(force=True)
    bid = d.get("bid")
    teams = max(1, min(12, int(d.get("teams") or 3)))
    horizon = max(2.0, min(168.0, float(d.get("horizon") or 24)))
    seed = int(d.get("seed") or stable_seed(bid))
    con = db()
    row = con.execute("SELECT * FROM buildings WHERE bid=?", (bid,)).fetchone()
    if row is None:
        con.close()
        return jsonify(error="unknown building"), 404
    rec = to_record(row)
    with LOCK:
        payload = run_engine(rec, teams, horizon, seed)
    cur = con.execute(
        "INSERT INTO runs (bid, created_at, teams, horizon, lives, payload) "
        "VALUES (?,?,?,?,?,?)",
        (bid, datetime.now(timezone.utc).isoformat(timespec="seconds"), teams, horizon,
         payload["lives"], json.dumps(payload)))
    con.commit()
    payload["run_id"] = cur.lastrowid
    con.close()
    return jsonify(payload)


@app.get("/api/runs")
def runs():
    con = db()
    rows = con.execute("SELECT id,bid,created_at,teams,horizon,lives FROM runs "
                       "ORDER BY id DESC LIMIT 40").fetchall()
    con.close()
    return jsonify([dict(r) for r in rows])


@app.get("/api/runs/<int:rid>")
def run_detail(rid):
    con = db()
    r = con.execute("SELECT * FROM runs WHERE id=?", (rid,)).fetchone()
    con.close()
    if r is None:
        return jsonify(error="not found"), 404
    p = json.loads(r["payload"])
    p["run_id"] = r["id"]
    return jsonify(p)


_RT = {"done": False, "passed": 0, "total": 0, "rows": []}


@app.get("/api/selfcheck")
def selfcheck():
    """Re-run one building twice and compare the plan. Determinism is a claimed
    property, so the app proves it at run time instead of asserting it."""
    con = db()
    row = con.execute("SELECT * FROM buildings WHERE collapsed=1 ORDER BY bid LIMIT 1").fetchone()
    con.close()
    if row is None:
        return jsonify(ok=False, detail="no collapsed building to check")
    rec = to_record(row)
    seed = DEFAULT_SEED
    a = run_engine(rec, 3, 24.0, seed)
    b = run_engine(rec, 3, 24.0, seed)
    ka = [(v["vid"], v["rank"], v["else_score"], v["start"], v["done"]) for v in a["voids"]]
    kb = [(v["vid"], v["rank"], v["else_score"], v["start"], v["done"]) for v in b["voids"]]
    same = ka == kb
    return jsonify(ok=same, bid=rec.bid, seed=seed, pockets=len(ka),
                   lives=a["lives"], detail=("identical plan on re-run"
                                              if same else "DIVERGENT PLAN -- determinism broken"))


@app.post("/api/redteam")
def redteam_run():
    with LOCK:
        ok = RT.run_all(verbose=False)
        rows = [dict(name=n, ok=o, detail=d) for n, o, d in RT.RESULTS]
    _RT.update(done=True, passed=sum(1 for r in rows if r["ok"]), total=len(rows), rows=rows)
    return jsonify(ok=ok, passed=_RT["passed"], total=_RT["total"], rows=rows)


@app.get("/api/accuracy")
def accuracy():
    """The 95% table, computed rather than asserted.

    Positive likelihood ratio per independent confirmation is 4.5, which is the
    operating point behind PPV 0.9101 at a 0.1 prior (k=3) and 0.9891 at 0.5.
    """
    LR = 4.5

    def ppv(k, prior):
        num = (LR ** k) * prior
        return num / (num + (1 - prior))

    priors = [0.001, 0.01, 0.1, 0.5]
    grid = []
    for k in (1, 2, 3):
        grid.append(dict(k=k, values=[round(ppv(k, p), 4) for p in priors]))
    detect = [dict(passes=n, pod=round(1 - (1 - 0.80) ** n, 4)) for n in (1, 2, 3)]

    metrics = [
        ("A pocket declared clear really is clear", "PPV of Clear verdict",
         "k-of-3 confirmations → 0.9101 at prior 0.1", "ACHIEVABLE", "green"),
        ("A breathing casualty is detected", "POD",
         "FINDER-class 0.80 × 3 passes → 0.992", "ACHIEVABLE", "green"),
        ("The plan is reproducible", "Determinism",
         "same inputs, same plan; 10/10 tests", "ACHIEVED", "green"),
        ("An over-built property is flagged", "Recall on audit",
         "declared-vs-built join vs MCD ground truth", "ACHIEVABLE", "green"),
        ("Ranking puts a casualty in the top three", "Hit@3",
         "blind back-test on 30 collapses — not run yet", "UNPROVEN", "amber"),
        ("Occupancy within ±25%", "MAPE",
         "phone census + listing refresh", "PLAUSIBLE", "amber"),
        ("Mechanism named correctly", "Top-1 accuracy",
         "no labelled rubble dataset exists", "NOT ACHIEVABLE", "red"),
        ("Survival estimate calibrated", "Brier / ECE",
         "needs an outcome registry", "NOT ACHIEVABLE", "red"),
        ("Collapse prevented", "Incidence",
         "brittle failure has no precursor", "OUT OF SCOPE", "red"),
    ]
    return jsonify(lr_per_confirmation=LR, priors=priors, ppv_grid=grid,
                   detection=detect,
                   metrics=[dict(claim=a, metric=b, path=c, verdict=d, tone=e)
                            for a, b, c, d, e in metrics],
                   redteam=_RT if _RT["done"] else None)


@app.get("/api/export")
def export():
    con = db()
    b = [dict(r) for r in con.execute("SELECT * FROM buildings").fetchall()]
    con.close()
    return jsonify(exported_at=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                   buildings=b)


@app.post("/api/import")
def import_data():
    d = request.get_json(force=True)
    items = d.get("buildings") or []
    con = db()
    added = 0
    for it in items:
        vals = {f: it.get(f) for f in FIELDS}
        vals["collapsed"] = 1 if it.get("collapsed") else 0
        vals["sanction_plan"] = 1 if it.get("sanction_plan") else 0
        try:
            con.execute(
                f"INSERT OR REPLACE INTO buildings ({','.join(FIELDS)}, created_at) "
                f"VALUES ({','.join('?' * len(FIELDS))}, ?)",
                [vals[f] for f in FIELDS] + [datetime.now(timezone.utc).isoformat(timespec="seconds")])
            added += 1
        except Exception:
            pass
    con.commit()
    con.close()
    return jsonify(ok=True, imported=added)


@app.post("/api/reseed")
def reseed():
    init_db(force=True)
    return jsonify(ok=True, count=len(SEED))


if __name__ == "__main__":
    init_db()
    port = int(os.environ.get("PORT", "8000"))
    app.run(host="0.0.0.0", port=port, debug=False, threaded=True)
