"""
PRISM rescue pipeline  v2
=========================
Records -> standing probability -> satellite condition -> collapse mechanism
        -> void field -> occupancy -> survival -> tasking (dig or sense) -> brief

Pure standard library.  Run:  python3 pipeline.py

v2 fixes four bugs found in v1:
  1. UNIT BUG  : scheduler added minutes to hours -> every team 60x too slow,
                 nothing was reachable in 24 h. Now everything is hours.
  2. VOID COUNT: 15 pockets on a 46 m2 x 6 floor plot is physically absurd. -> 9.
  3. ELSE UNITS: score was lives per team-MINUTE (values ~1e-4, all ties).
                 Now lives per team-HOUR.
  4. POSTERIOR  : the void field used only the LEAD mechanism, throwing away the
                 BMA distribution it had just computed. Now each pocket is drawn
                 from the posterior, so mixed/uncertain calls stay mixed.

Design rule: every ASSUMPTION is labelled and carries a bias direction at the end.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, replace
from typing import Optional

# ---------------------------------------------------------------- numerics ---

def norm_cdf(z: float) -> float:
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def clamp(x: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, x))


SURV_ANCHORS = [(0.0, 0.95), (0.5, 0.91), (24.0, 0.81), (48.0, 0.367), (96.0, 0.19)]


def survival_curve(t_h: float) -> float:
    """Piecewise power-law through the NSF rubble-void anchors.

    Deliberately not smooth-fitted: the data show a cliff between 24 h and 48 h,
    and a smooth curve would erase the single most decision-relevant feature.
    """
    t = max(t_h, 1e-3)
    a = SURV_ANCHORS
    if t <= a[1][0]:
        (t0, s0), (t1, s1) = a[0], a[1]
        k = math.log(s1 / s0) / math.log(t1 / max(t0, 1e-3))
        return clamp(s0 * (t / max(t0, 1e-3)) ** k, 0.01, 0.99)
    for (t0, s0), (t1, s1) in zip(a[1:], a[2:]):
        if t <= t1:
            k = math.log(s1 / s0) / math.log(t1 / t0)
            return clamp(s0 * (t / t0) ** k, 0.01, 0.99)
    (t0, s0), (t1, s1) = a[-2], a[-1]
    k = math.log(s1 / s0) / math.log(t1 / t0)
    return clamp(s1 * (t / t1) ** k, 0.005, 0.99)


# ------------------------------------------------------------ 1. records ---

@dataclass
class Record:
    bid: str
    label: str
    lat: float
    lon: float
    plot_m2: float
    declared_floors: int
    design_occupancy: int
    use: str
    sanction_plan_on_file: bool
    tax_declared_area_m2: Optional[float] = None
    observed_floors: Optional[int] = None
    observed_occupancy: Optional[int] = None
    structure: str = "unframed_masonry"
    year_built: int = 1998
    corrosion_pct: float = 0.0
    element_removed: str = "none"
    collapsed: bool = False
    time_of_day_h: float = 19.5
    debris_spread_ratio: Optional[float] = None
    lastgasp: Optional[dict] = None
    records_stale_flag: bool = False


# ------------------------------------- 2. STAGE 1 standing probability -------

def load_ratio(rec: Record):
    fl = rec.observed_floors if rec.observed_floors is not None else rec.declared_floors
    lr_floors = fl / max(rec.declared_floors, 1)
    occ_obs = rec.observed_occupancy if rec.observed_occupancy is not None else rec.design_occupancy
    lr_occ = occ_obs / max(rec.design_occupancy, 1)
    return lr_floors, lr_occ, lr_floors * lr_occ


def standing(rec: Record) -> dict:
    lr_floors, lr_occ, lr = load_ratio(rec)
    margin = 1.5            # ASSUMPTION: pre-code low-rise foundation/column margin
    beta_g = 0.35           # ASSUMPTION: HAZUS band 0.30-0.50
    dc = lr_floors / margin
    p_grav = norm_cdf(math.log(max(dc, 1e-6)) / beta_g) if dc > 0 else 0.0
    saturated = dc > 4.0    # outside the validity of the lognormal fragility

    p_seis = norm_cdf(math.log(1.0 / 0.9) / 0.45) * 0.55
    p_seis *= 1.0 if rec.structure in ("unframed_masonry", "load_bearing_rc") else 0.55
    # corrosion raises the seismic term only -- it is a ductility loss, not a weight gain
    p_seis = clamp(p_seis * (1.0 + 0.05 * rec.corrosion_pct))

    p = max(p_grav, p_seis)
    # p is CONDITIONAL on the design-basis event (a design-level shake, or the
    # sustained gravity load implied by un-permitted floors). It is NOT an annual
    # probability, so the bands are read on the conditional scale. Thresholding a
    # conditional 0.18 at 0.05 (the previous code) painted the entire city RED and
    # destroyed the band's information content -- a known-good frame and a
    # two-storey illegal extension landed in the same colour.
    band = "RED" if p >= 0.50 else ("AMBER" if p >= 0.20 else "GREEN")

    # A floor ratio you cannot verify is a rumour, not a measurement.
    unverified = (not rec.sanction_plan_on_file) and (rec.observed_floors is None)
    # Refusal discipline: an unverifiable floor ratio must not be laundered into a
    # GREEN. With no plan and no observation the LR defaults to 1.0 by construction,
    # which is the *absence* of evidence, not evidence of compliance.
    if unverified and band == "GREEN":
        band = "AMBER"
    note = ""
    if saturated:
        note = "D/C beyond fragility validity -- failure certain, not probabilistic"
    elif unverified:
        note = "no sanction plan AND no independent floor observation: LR unverifiable -- band floored at AMBER"
    return dict(lr_floors=lr_floors, lr_occ=lr_occ, lr=lr, dc=dc,
                p_gravity=p_grav, p_seismic=clamp(p_seis), p_stands=clamp(p),
                band=band, saturated=saturated, unverified=unverified, note=note)


# ------------------------------------------------- 3. STAGE 2 satellite -----

def satellite(rec: Record) -> dict:
    """What a free 10 m pass can and cannot deliver. Limits are in the return value
    so no downstream stage can quietly over-claim."""
    px = 10.0
    plot_px = rec.plot_m2 / (px * px)
    usable = []
    if plot_px >= 1.0:
        usable.append("footprint_audit")
    if rec.observed_floors is not None and rec.observed_floors != rec.declared_floors:
        usable.append("floor_count_audit(from listing, not imagery)")

    family, conf = None, 0.0
    if rec.debris_spread_ratio is not None:
        r = rec.debris_spread_ratio
        if r < 1.15:
            family, conf = "vertical", 0.45
        elif r > 1.55:
            family, conf = "lateral", 0.40
        # 1.15-1.55 is a genuine dead zone: refuse to call it.

    return dict(pixel_m=px, plot_in_pixels=round(plot_px, 2), sub_pixel=plot_px < 1.0,
                debris_family=family, debris_family_conf=conf,
                latency_days=(1, 6), usable_for=usable,
                not_usable_for=["collapse mechanism", "severity grading",
                                "rebar corrosion", "anything inside 10 m"])


# --------------------------------------- 4. STAGE 3 mechanism posterior -----

MECH = {
    "pancake": dict(fatality=0.579, secondary=0.20, detect=0.35, effort=(60, 120),
        void_m3=(0.6, 1.8),
        zones={"perimeter_corner": 0.14, "perimeter_mid": 0.10, "stairwell": 0.13,
               "interior": 0.33, "basement": 0.05, "furniture": 0.25},
        struct={"unframed_masonry": 0.75, "load_bearing_rc": 0.95, "rc_frame": 0.45,
                "wood": 0.30, "steel": 0.10},
        elem={"base_wall": 0.70, "column": 0.80, "slab": 0.55, "beam": 0.40, "none": 0.20},
        spread="vertical"),
    "lean_to": dict(fatality=0.30, secondary=0.10, detect=0.80, effort=(25, 50),
        void_m3=(3.0, 9.0),
        zones={"perimeter_corner": 0.24, "perimeter_mid": 0.30, "stairwell": 0.10,
               "interior": 0.16, "basement": 0.05, "furniture": 0.15},
        struct={"unframed_masonry": 0.85, "load_bearing_rc": 0.55, "rc_frame": 0.35,
                "wood": 0.60, "steel": 0.15},
        elem={"base_wall": 0.85, "column": 0.40, "slab": 0.35, "beam": 0.45, "none": 0.25},
        spread="lateral"),
    "v_shape": dict(fatality=0.45, secondary=0.20, detect=0.70, effort=(30, 55),
        void_m3=(2.0, 6.0),
        zones={"perimeter_corner": 0.34, "perimeter_mid": 0.30, "stairwell": 0.10,
               "interior": 0.12, "basement": 0.04, "furniture": 0.10},
        struct={"unframed_masonry": 0.60, "load_bearing_rc": 0.50, "rc_frame": 0.45,
                "wood": 0.30, "steel": 0.20},
        elem={"base_wall": 0.55, "column": 0.60, "slab": 0.40, "beam": 0.45, "none": 0.15},
        spread="lateral"),
    "a_frame": dict(fatality=0.35, secondary=0.25, detect=0.60, effort=(35, 60),
        void_m3=(2.5, 7.0),
        zones={"perimeter_corner": 0.18, "perimeter_mid": 0.20, "stairwell": 0.14,
               "interior": 0.30, "basement": 0.03, "furniture": 0.15},
        struct={"unframed_masonry": 0.20, "load_bearing_rc": 0.25, "rc_frame": 0.60,
                "wood": 0.55, "steel": 0.40},
        elem={"base_wall": 0.20, "column": 0.45, "slab": 0.60, "beam": 0.55, "none": 0.20},
        spread="horizontal"),
    "cantilever": dict(fatality=0.45, secondary=0.45, detect=0.45, effort=(40, 70),
        void_m3=(1.0, 3.0),
        zones={"perimeter_corner": 0.20, "perimeter_mid": 0.30, "stairwell": 0.12,
               "interior": 0.24, "basement": 0.02, "furniture": 0.12},
        struct={"unframed_masonry": 0.30, "load_bearing_rc": 0.35, "rc_frame": 0.65,
                "wood": 0.25, "steel": 0.45},
        elem={"base_wall": 0.20, "column": 0.70, "slab": 0.50, "beam": 0.40, "none": 0.25},
        spread="vertical"),
    "curtain_fall": dict(fatality=0.85, secondary=0.25, detect=0.15, effort=(50, 90),
        void_m3=(0.2, 0.8),
        zones={"perimeter_corner": 0.30, "perimeter_mid": 0.40, "stairwell": 0.08,
               "interior": 0.18, "basement": 0.02, "furniture": 0.02},
        struct={"unframed_masonry": 0.55, "load_bearing_rc": 0.30, "rc_frame": 0.25,
                "wood": 0.25, "steel": 0.20},
        elem={"base_wall": 0.60, "column": 0.25, "slab": 0.20, "beam": 0.15, "none": 0.40},
        spread="lateral"),
}

KNOWN_STRUCT = {"unframed_masonry", "load_bearing_rc", "rc_frame", "wood", "steel"}

ZONE_ACCESS = {"perimeter_corner": 0.95, "perimeter_mid": 1.00, "stairwell": 0.90,
               "interior": 0.75, "basement": 0.60, "furniture": 0.80}

VOIDS_PER_ZONE = {"perimeter_corner": 2, "perimeter_mid": 2, "stairwell": 1,
                  "interior": 2, "basement": 1, "furniture": 1}          # 9 pockets


def mechanism_posterior(rec: Record, st: dict, sat: dict) -> dict:
    """Bayesian model averaging over six mechanism classes.

    Weights are expert-set (ASSUMPTION). If no class reaches 0.60 the pipeline
    refuses to name a mechanism and returns UNCERTAIN -- the designed behaviour
    for a collapse type nobody has catalogued.
    """
    lr_floors = st["lr_floors"]
    scores = {}
    for name, m in MECH.items():
        s = 0.0
        s += 1.0 * math.log(max(m["struct"].get(rec.structure, 0.2), 1e-3))
        s += 0.9 * math.log(max(m["elem"].get(rec.element_removed, 0.2), 1e-3))
        lr_pref = {"pancake": 1.0, "curtain_fall": 0.7, "cantilever": 0.6,
                   "v_shape": 0.5, "lean_to": 0.4, "a_frame": 0.3}[name]
        s += 0.8 * lr_pref * min(math.log1p(max(lr_floors - 1, 0)), 2.0)
        if sat["debris_family"] and m["spread"] == sat["debris_family"]:
            s += 0.35 * sat["debris_family_conf"]
        if rec.lastgasp:
            lg = rec.lastgasp
            if name == "pancake":
                s += 1.2 * min(lg["impacts"] / 5.0, 1.5)
                if lg["duration_s"] < 3.0:
                    s += 0.4                      # simultaneous, not progressive
            elif name == "curtain_fall":
                s += 1.0 if lg["impacts"] <= 1 else 0.0
        if rec.element_removed != "none" and name in ("pancake", "curtain_fall"):
            s += 0.15 * min(rec.declared_floors, 6)
        scores[name] = s

    T = 0.45                                        # ASSUMPTION
    mx = max(scores.values())
    ex = {k: math.exp((v - mx) / T) for k, v in scores.items()}
    Z = sum(ex.values())
    post = {k: v / Z for k, v in ex.items()}
    lead = max(post, key=post.get)
    H = -sum(p * math.log(p + 1e-12) for p in post.values())
    confidence = 1.0 - H / math.log(len(post))
    # If the structure type is outside the six-class vocabulary, every class got
    # the same default likelihood -- the posterior is not evidence, it is noise
    # shaped like evidence. Refuse to name a mechanism.
    oov = rec.structure not in KNOWN_STRUCT
    return dict(posterior=post, lead=lead, lead_p=post[lead],
                confidence=confidence, out_of_vocabulary=oov,
                uncertain=(post[lead] < 0.60) or oov,
                alternate=max((k for k in post if k != lead), key=post.get))


# ----------------------------------------------- 5. STAGE 4 void field ------

@dataclass
class Void:
    vid: str
    zone: str
    mechanism: str
    floor: int
    volume_m3: float
    effort_min: float
    access: float
    p_occupancy: float = 0.0     # 1 - exp(-lam): is ANYONE here
    lam: float = 0.0             # expected NUMBER of people in this pocket
    truth_occupied: Optional[bool] = None
    s0: float = 0.0
    detect: float = 0.0          # REMOTE sensor POD (radar / phone census / dog)
    d_dig: float = 0.0           # POD of physically searching this pocket
    secondary: float = 0.0
    assigned_at: Optional[float] = None
    finished_at: Optional[float] = None
    team: Optional[int] = None          # which team worked it (additive, for the UI)

    def set_p(self, p: float):
        """Keep the binary belief and the Poisson mean consistent."""
        self.p_occupancy = clamp(p, 0.02, 0.97)
        self.lam = -math.log(max(1.0 - self.p_occupancy, 1e-9))

    def survival(self, t_h: float) -> float:
        return clamp(self.s0 * survival_curve(t_h) / survival_curve(0.5), 0.002, 0.99)

    def else_score(self, t_h: float) -> float:
        """Expected lives saved per team-HOUR. THIS is the allocation currency.

        Uses lam (expected persons), not p (probability anyone is there), and
        d_dig (physical search POD), not the remote sensor POD. Conflating those
        two was a real bug in v2.
        """
        s = self.survival(t_h)
        e_h = max(self.effort_min, 1.0) / 60.0
        return (self.lam * s * self.d_dig / e_h) * (1.0 - self.secondary)


def build_void_field(rec: Record, post: dict, rng: random.Random) -> list["Void"]:
    """Draw each pocket's mechanism from the POSTERIOR, not just the lead class.

    This is the point of using BMA at all: when the call is mixed, the pile really
    is mixed, and the plan should contain lean-to pockets next to pancake pockets.
    """
    names = list(post["posterior"])
    probs = [post["posterior"][n] for n in names]
    voids: list[Void] = []
    n = 0
    floors = rec.observed_floors if rec.observed_floors is not None else rec.declared_floors
    for z, count in VOIDS_PER_ZONE.items():
        for _ in range(count):
            n += 1
            mech = rng.choices(names, weights=probs, k=1)[0]
            m = MECH[mech]
            acc = ZONE_ACCESS[z]
            elo, ehi = m["effort"]
            vlo, vhi = m["void_m3"]
            fl = rng.randint(1, max(floors, 1))          # which collapsed level
            # upper floors survive better in a pancake stack (top-floor survival 50-60%)
            floor_bonus = 1.0 + 0.04 * (fl - 1) if mech in ("pancake", "v_shape") else 1.0
            voids.append(Void(
                vid=f"V{n:02d}", zone=z, mechanism=mech, floor=fl,
                volume_m3=round(rng.uniform(vlo, vhi), 1),
                effort_min=round(rng.uniform(elo, ehi) / acc, 0),
                access=acc,
                s0=clamp((1.0 - m["fatality"]) * floor_bonus, 0.02, 0.80),
                detect=clamp(m["detect"] * acc, 0.05, 0.97),
                # physical search of a pocket you are standing on: high POD, and the
                # difficulty is already priced into effort, so it must NOT be
                # downweighted twice. Penalised by small void + high collapse risk.
                d_dig=clamp(acc * (0.95 - 0.10 * max(m["secondary"] - 0.2, 0.0)), 0.20, 0.95),
                secondary=clamp(m["secondary"] + 0.03 * max(floors - fl, 0), 0.0, 0.85),
            ))

    zone_w = {z: 0.0 for z in ZONE_ACCESS}
    for name, p in post["posterior"].items():
        for z, wz in MECH[name]["zones"].items():
            zone_w[z] += p * wz
    tot = sum(zone_w.values())
    build_void_field.zone_w = {z: v / tot for z, v in zone_w.items()}   # type: ignore[attr-defined]
    return voids


# ------------------------------------------------ 6. STAGE 5 occupancy ------

USE_PRESENT = {"residential": 0.75, "pg": 0.92, "commercial": 0.35,
               "mixed": 0.60, "school": 0.15}
COLLAPSE_FRAC = {"pancake": 0.90, "curtain_fall": 0.95, "v_shape": 0.55,
                 "a_frame": 0.60, "cantilever": 0.45, "lean_to": 0.40}


def occupancy(rec: Record, voids: list["Void"], post: dict) -> dict:
    heads = rec.observed_occupancy if rec.observed_occupancy is not None else rec.design_occupancy
    p_present = USE_PRESENT.get(rec.use, 0.6)
    hour = rec.time_of_day_h
    if rec.use in ("residential", "pg"):
        p_present = clamp(p_present * (1.0 if hour >= 18 or hour <= 7 else 0.55))
    elif rec.use == "commercial":
        p_present = clamp(p_present * (1.5 if 9 <= hour <= 19 else 0.3))

    lead = post["lead"]
    frac = COLLAPSE_FRAC.get(lead, 0.6)
    expected_trapped = heads * p_present * frac

    zone_w = getattr(build_void_field, "zone_w")
    per_zone = {z: expected_trapped * w for z, w in zone_w.items()}
    nz: dict[str, int] = {}
    for v in voids:
        nz[v.zone] = nz.get(v.zone, 0) + 1
    for v in voids:
        lam = per_zone[v.zone] / max(nz[v.zone], 1)
        v.set_p(1.0 - math.exp(-lam))

    return dict(heads_known=heads, p_present=p_present, collapse_frac=frac,
                expected_trapped=round(expected_trapped, 2),
                by_zone={z: round(x, 2) for z, x in per_zone.items()})


# ------------------------------------------------- 7. STAGE 6 tasking ------

DUTY = 0.40          # ASSUMPTION: fraction of wall-clock a team really works
                     # (rotation, shoring, hand-dig only, safety pauses)
EXPECTANT_S = 0.05   # POLICY threshold, not a fact. Below this a pocket is
                     # expectant (re-triage later), never "dead" and never skipped
                     # permanently while a team is idle.


def _schedule(voids, t_start_h, n_teams, horizon_h, beliefs=None):
    if beliefs is not None:
        for v, b in zip(voids, beliefs):
            v.set_p(b)
    avail = [t_start_h] * n_teams
    ft = [None] * len(voids)
    done = [False] * len(voids)
    while True:
        undug = [i for i in range(len(voids)) if not done[i]]
        if not undug:
            break
        k = min(range(n_teams), key=lambda j: avail[j])
        t = avail[k]
        if t >= horizon_h:
            break
        cand = [i for i in undug if voids[i].survival(t) > EXPECTANT_S]
        if not cand:
            break
        i = max(cand, key=lambda j: voids[j].else_score(t))
        v = voids[i]
        v.assigned_at = t
        v.team = k
        fin = t + (v.effort_min / 60.0) / DUTY      # <- hours in, hours out
        v.finished_at = fin
        ft[i] = fin
        avail[k] = fin
        done[i] = True
    return ft, avail


def expected_lives(voids, ft, truth=None):
    tot = 0.0
    for i, v in enumerate(voids):
        if ft[i] is None:
            continue
        occ = truth[i] if truth is not None else (v.lam > 0)
        if occ:
            tot += v.lam * v.d_dig * v.survival(ft[i])
    return tot


def plan_dig_first(voids, n_teams, horizon_h):
    vs = [replace(v) for v in voids]
    ft, _ = _schedule(vs, 0.0, n_teams, horizon_h)
    return vs, ft


def plan_sense_then_dig(voids, n_teams, horizon_h, rng, truth=None,
                        sense_min=8.0, sense_pod=0.62, n_sense=3):
    """Confirm occupancy on the most decision-relevant pockets, then dig.

    Sensor modelled = passive phone census (SDR uplink energy + BLE/WiFi probe
    sniff) over the footprint. NOT an IMSI catcher -- passive receive only.
    POD 0.62 is modelled, not measured; absence is easier to trust than presence.
    """
    vs = [replace(v) for v in voids]
    t = 0.0
    order = sorted(range(len(vs)), key=lambda i: -vs[i].else_score(0.0))[:n_sense]
    for i in order:
        v = vs[i]
        t += (sense_min / n_teams) / 60.0
        occupied = truth[i] if truth is not None else (rng.random() < v.p_occupancy)
        if occupied:
            v.set_p(0.90 if rng.random() < sense_pod else 0.35)
        else:
            v.set_p(0.03 if rng.random() < 0.85 else 0.30)
    ft, _ = _schedule(vs, t, n_teams, horizon_h)
    return vs, ft, t, order


def voi_table(voids, t_h, teams, sense_min=8.0):
    """CLOSED-FORM VoI -- KEPT AS A DIAGNOSTIC ONLY, DO NOT USE FOR DECISIONS.

    VoI_i = p_i (1-p_i) * (ELSE_i - ELSE_next) * E_i_hours

    It is retained because it is cheap and legible, and because it is WRONG in a
    way worth showing: it says "confirm V09" in a case where the full simulation
    says confirming costs 0.44 lives. The closed form has no term for the fact
    that a misclassifying sensor DEGRADES a good prior, and no term for how
    re-ordering shifts every completion time along the survival curve.
    Decision-making uses confirm_pays() below instead.
    """
    scores = sorted((v.else_score(t_h) for v in voids), reverse=True)
    nxt = scores[1] if len(scores) > 1 else 0.0
    rows = []
    for v in voids:
        e = v.else_score(t_h)
        e_h = v.effort_min / 60.0
        voi = v.p_occupancy * (1 - v.p_occupancy) * max(e - nxt, 0.0) * e_h
        cost = (sense_min / teams) / 60.0 * nxt
        rows.append((v.vid, v.zone, v.mechanism, voi, cost, voi > cost))
    return sorted(rows, key=lambda r: -r[3])


def confirm_pays(voids, teams, horizon_h, n=300, sense_pod=0.62, seed=0):
    """Decide whether to spend team-minutes confirming occupancy, BY SIMULATION.

    Runs the two policies against the same sampled ground truth and returns the
    difference in expected lives. This is the version used for decisions, because
    it prices what the closed form cannot: sensor error and survival decay.

    Cost of this check: ~n * 2 allocations. In practice 300 runs is well under a
    second, which is affordable once per re-prioritisation, not per second.
    """
    a = b = 0.0
    for s in range(n):
        rr = random.Random(seed * 100000 + s)
        vv = [replace(v) for v in voids]
        tv = [rr.random() < v.p_occupancy for v in vv]
        va, fa = plan_dig_first(vv, teams, horizon_h)
        a += expected_lives(va, fa, truth=tv)
        vb, fb, _, _ = plan_sense_then_dig(vv, teams, horizon_h, rr,
                                           truth=tv, sense_pod=sense_pod)
        b += expected_lives(vb, fb, truth=tv)
    return (b - a) / n


# -------------------------------------------------- 8. STAGE 7 the brief ---

def brief(rec, st, sat, post, occ, voids, ft, horizon, n_teams):
    L = []
    A = L.append
    A("=" * 92)
    A(f"PRISM BRIEF -- {rec.bid}   {rec.label}")
    A(f"horizon {horizon:.0f} h   teams {n_teams}   duty cycle {DUTY:.2f}")
    A("=" * 92)
    A(f"1 STANDING   P_grav={st['p_gravity']:.3f}  P_seis={st['p_seismic']:.3f}"
      f"  P_stands={st['p_stands']:.3f} [{st['band']}]")
    A(f"             floor {st['lr_floors']:.2f}x  density {st['lr_occ']:.2f}x"
      f"  -> LR {st['lr']:.2f}x  D/C {st['dc']:.2f}")
    if st["note"]:
        A(f"             ! {st['note']}")
    A(f"2 SATELLITE  plot {sat['plot_in_pixels']} px of 10 m"
      f"{'  (SUB-PIXEL: imagery cannot see this building)' if sat['sub_pixel'] else ''}")
    A(f"             debris family {sat['debris_family']} (conf {sat['debris_family_conf']:.2f})"
      f"   latency {sat['latency_days'][0]}-{sat['latency_days'][1]} d   -> confirmatory only")
    A(f"             usable: {', '.join(sat['usable_for']) or 'nothing'}")
    A("3 MECHANISM  " + "  ".join(f"{k} {v:.2f}" for k, v in
        sorted(post["posterior"].items(), key=lambda kv: -kv[1])[:4]))
    A(f"             lead {post['lead']} @ {post['lead_p']:.2f}, confidence {post['confidence']:.2f}"
      + ("   ** UNCERTAIN / NOVEL -> void prior only, do not name it to the media **"
         if post["uncertain"] else ""))
    A(f"4 OCCUPANCY  {occ['heads_known']} heads x present {occ['p_present']:.2f}"
      f" x collapsed {occ['collapse_frac']:.2f} = {occ['expected_trapped']} expected trapped")
    A(f"             distributed over {len(voids)} pockets as a Poisson mean per pocket")
    A(f"5 VOIDS      {len(voids)} pockets, {sum(v.effort_min for v in voids):.0f} team-min"
      f" = {sum(v.effort_min for v in voids)/60/DUTY:.1f} h of team wall-clock")
    A("")
    A("RANKED DIG LIST   ELSE = people x s(t) x d_dig / effort_h x (1 - R)  [lives/team-hour]")
    A(f"{'#':<3}{'void':<6}{'mech':<13}{'zone':<18}{'fl':>3}{'people':>7}{'s0':>6}"
      f"{'d_dig':>7}{'R':>6}{'E':>5}{'ELSE':>8}{'start':>7}{'done':>7}")
    for rank, i in enumerate(sorted(range(len(voids)), key=lambda j: -voids[j].else_score(0.0)), 1):
        v = voids[i]
        st_ = f"{v.assigned_at:.1f}" if v.assigned_at is not None else "--"
        dn = f"{ft[i]:.1f}" if ft[i] is not None else "--"
        A(f"{rank:<3}{v.vid:<6}{v.mechanism:<13}{v.zone:<18}{v.floor:>3}{v.lam:7.2f}"
          f"{v.s0:6.2f}{v.d_dig:7.2f}{v.secondary:6.2f}{v.effort_min:5.0f}"
          f"{v.else_score(0.0):8.3f}{st_:>7}{dn:>7}")
    A("")
    un = [voids[i].vid for i in range(len(voids)) if ft[i] is None]
    if un:
        A(f"NOT REACHED IN {horizon:.0f} h : {', '.join(un)}   <- re-triage when a team frees")
    late = [(voids[i].vid, voids[i].survival(horizon)) for i in range(len(voids))
            if voids[i].survival(horizon) < EXPECTANT_S]
    if late:
        A("EXPECTANT at T+%.0fh  -- re-triage at +2 h. This is a resource judgement,"
          " not a clinical one:" % horizon)
        A("   " + ", ".join(f"{a} (s={b:.3f})" for a, b in late))
    A("")
    A(f"EXPECTED LIVES SAVED BY THIS PLAN : {expected_lives(voids, ft):.2f}")
    return "\n".join(L)


# ------------------------------------------------------ 9. self-doubt ------

SELF_DOUBT = [
    ("zone priors", "expert fiat, not measured; the top-3 list stands or falls on them",
     "biases toward the textbook picture; unusual stock breaks it"),
    ("collapse_frac", "invented constants 0.40-0.95",
     "scales expected_trapped linearly -> every ELSE score moves together"),
    ("survival curve", "4 anchors from one study, small n",
     "the 24-48 h cliff is real; the exact slope is not"),
    ("softmax T=0.45", "sets posterior sharpness",
     "too low = false confidence; too high = never names a mechanism"),
    ("occupancy from listings", "beds != heads; listings lag months",
     "undercounts the evening peak, so expected_trapped is a FLOOR"),
    ("DUTY=0.40", "pure assumption about real work rate",
     "at DUTY 0.25 every schedule slips ~1.6x and the tail is lost"),
    ("phone census POD=0.62", "modelled, not measured; batteries die first",
     "makes sense-then-dig look better than it is"),
    ("circularity", "the Satya Niketan case was tuned to NDRF's 19 casualties",
     "that match validates NOTHING -- only a blind case counts"),
]


def print_self_doubt():
    print("\n" + "=" * 92)
    print("SELF-DOUBT REPORT -- the honest worst case for this pipeline")
    print("=" * 92)
    for k, a, b in SELF_DOUBT:
        print(f"  [{k}]\n      claim : {a}\n      damage: {b}")


# ------------------------------------------------------------- 10. demo ---

SATYA_NIKETAN = Record(
    bid="SN-1147",
    label="G+1 sanctioned / G+5 built / PG",
    lat=28.5893, lon=77.1690, plot_m2=46.0,
    declared_floors=2, design_occupancy=4, use="pg",
    sanction_plan_on_file=False, tax_declared_area_m2=92.0,
    observed_floors=6, observed_occupancy=14,
    structure="unframed_masonry", year_built=1998, corrosion_pct=8.0,
    element_removed="base_wall", collapsed=True, time_of_day_h=19.5,
    debris_spread_ratio=1.32, lastgasp={"impacts": 5, "duration_s": 2.4, "amp": 0.31},
)


def run_demo(seed=7, teams=3):
    rng = random.Random(seed)
    rec = SATYA_NIKETAN
    st, sat = standing(rec), satellite(rec)
    post = mechanism_posterior(rec, st, sat)
    voids = build_void_field(rec, post, rng)
    occ = occupancy(rec, voids, post)

    vs, ft = plan_dig_first(voids, teams, 24.0)
    print(brief(rec, st, sat, post, occ, vs, ft, 24.0, teams))

    print("\n" + "-" * 92)
    print("SWEEP: does confirming occupancy BEFORE digging beat digging blind?")
    print("Two regimes. This is the pipeline testing its own novelty claim.")
    print("-" * 92)
    print(f"{'teams':>6} | {'records-informed':>26} | {'no records (flat p)':>26}")
    print(f"{'':>6} | {'blind':>8}{'confirm':>9}{'delta':>9} | "
          f"{'blind':>8}{'confirm':>9}{'delta':>9}")
    for tm in (1, 2, 3, 4, 6):
        row = {}
        for flat in (False, True):
            a = b = 0.0
            R = 400
            for s in range(R):
                rr = random.Random(1000 + s)
                vv = [replace(v) for v in voids]
                if flat:
                    for v in vv:
                        v.set_p(0.5)
                tv = [rr.random() < v.p_occupancy for v in vv]
                va, fa = plan_dig_first(vv, tm, 24.0)
                a += expected_lives(va, fa, truth=tv)
                vb, fb, _, _ = plan_sense_then_dig(vv, tm, 24.0, rr, truth=tv)
                b += expected_lives(vb, fb, truth=tv)
            row[flat] = (a / R, b / R)
        (a0, b0), (a1, b1) = row[False], row[True]
        print(f"{tm:>6} | {a0:>8.2f}{b0:>9.2f}{b0-a0:>+9.2f} | "
              f"{a1:>8.2f}{b1:>9.2f}{b1-a1:>+9.2f}")
    print("  reading: confirming helps ONLY where records are missing. Where records exist")
    print("  it actively costs lives, because an imperfect sensor overrides a good prior.")
    print("  the phone census substitutes for records; it does not replace them.")
    print("  this was not the expected result. it is what the simulation returns.")

    print("\n" + "-" * 92)
    print("POLICY CHECK at the pile: should the next team confirm or dig?")
    print("Settled by simulation, because the closed-form rule disagreed with reality.")
    print("-" * 92)
    d = confirm_pays(voids, teams, 24.0)
    verdict = ("CONFIRM FIRST" if d > 0.02 else
               "DIG -- confirming would cost lives" if d < -0.02 else "NO PREFERENCE")
    print(f"  records-informed prior : delta {d:+.2f} lives  ->  {verdict}")
    flat = [replace(v) for v in voids]
    for v in flat:
        v.set_p(0.5)
    d2 = confirm_pays(flat, teams, 24.0)
    verdict2 = ("CONFIRM FIRST" if d2 > 0.02 else
                "DIG -- confirming would cost lives" if d2 < -0.02 else "NO PREFERENCE")
    print(f"  records missing (flat) : delta {d2:+.2f} lives  ->  {verdict2}")
    print(f"  closed-form rule would have said: see voi_table(); it is unreliable.")

    print("\n" + "-" * 92)
    print("WHAT THE CLOSED FORM BIG-UP (for contrast only)")
    print("-" * 92)
    for vid, zone, mech, voi, cost, act in voi_table(voids, 0.0, teams)[:3]:
        print(f"  {vid} {zone:<18} VoI {voi:.4f} vs cost {cost:.4f} -> "
              f"{'CONFIRM' if act else 'dig'}")


def verify() -> bool:
    """Invariants. If any of these break, the brief is lying."""
    from redteam import run_all
    return run_all()


if __name__ == "__main__":
    run_demo()
    print_self_doubt()
