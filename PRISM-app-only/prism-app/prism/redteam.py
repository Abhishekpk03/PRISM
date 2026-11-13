"""
redteam.py -- the pipeline's own attempt to break itself.

Eight adversarial cases. A rescue plan that has not been attacked is a guess
with formatting. Every test states what SHOULD happen, then checks it.

Run:  python3 redteam.py
"""

from __future__ import annotations

import math
import random

import pipeline as P
from pipeline import (Record, SATYA_NIKETAN, build_void_field, brief,
                      expected_lives, mechanism_posterior, occupancy,
                      plan_dig_first, plan_sense_then_dig, satellite,
                      standing, survival_curve)

RESULTS: list[tuple[str, bool, str]] = []


def check(name: str, ok: bool, detail: str = ""):
    RESULTS.append((name, bool(ok), detail))
    return ok


def _run(rec, n_teams=3, horizon=24.0, seed=11):
    rng = random.Random(seed)
    st, sat = standing(rec), satellite(rec)
    post = mechanism_posterior(rec, st, sat)
    voids = build_void_field(rec, post, rng)
    occ = occupancy(rec, voids, post)
    vs, ft = plan_dig_first(voids, n_teams, horizon)
    return dict(st=st, sat=sat, post=post, voids=vs, occ=occ, ft=ft,
                txt=brief(rec, st, sat, post, occ, vs, ft, horizon, n_teams))


# ---------------------------------------------------------------- tests ---

def test_units():
    """Work consumed per team must match declared effort. v1 failed this by 60x."""
    r = _run(SATYA_NIKETAN)
    vs, ft = r["voids"], r["ft"]
    total_work_h = sum(v.effort_min for v in vs if v.finished_at) / 60.0
    total_wall_h = sum((v.finished_at - v.assigned_at) for v in vs if v.finished_at)
    ok = math.isclose(total_wall_h, total_work_h / P.DUTY, rel_tol=1e-6)
    span = max((v.finished_at for v in vs if v.finished_at), default=0)
    check("units: wall-clock = work / duty", ok,
          f"work {total_work_h:.2f}h -> wall {total_wall_h:.2f}h, span {span:.1f}h")


def test_no_double_booking():
    """Two voids must never be worked at the same time by the same team."""
    r = _run(SATYA_NIKETAN)
    iv = sorted((v.assigned_at, v.finished_at) for v in r["voids"] if v.finished_at)
    # with 3 teams we can have up to 3 concurrent; check no MORE than n overlap
    events = []
    for a, b in iv:
        events.append((a, 1))
        events.append((b, -1))
    events.sort()
    cur = peak = 0
    for _, d in events:
        cur += d
        peak = max(peak, cur)
    check("scheduler: concurrency <= teams", peak <= 3, f"peak concurrency {peak} with 3 teams")


def test_posterior_conservation():
    """Posterior must sum to 1 for any record, including absurd ones."""
    rng = random.Random(3)
    worst = 1.0
    for _ in range(300):
        rec = Record(bid="X", label="x", lat=0, lon=0, plot_m2=rng.uniform(20, 500),
                     declared_floors=rng.randint(1, 6), design_occupancy=rng.randint(1, 30),
                     use=rng.choice(["pg", "residential", "commercial", "mixed", "school"]),
                     sanction_plan_on_file=rng.random() < 0.3,
                     observed_floors=rng.choice([None, rng.randint(1, 9)]),
                     observed_occupancy=rng.choice([None, rng.randint(1, 60)]),
                     structure=rng.choice(list({"unframed_masonry", "load_bearing_rc",
                                                "rc_frame", "wood", "steel", "precast_panel"})),
                     element_removed=rng.choice(["none", "base_wall", "column", "slab", "beam"]),
                     collapsed=True,
                     debris_spread_ratio=rng.choice([None, rng.uniform(0.9, 2.5)]),
                     lastgasp=rng.choice([None, {"impacts": rng.randint(1, 8),
                                                 "duration_s": rng.uniform(0.5, 9),
                                                 "amp": 0.3}]))
        st, sat = standing(rec), satellite(rec)
        post = mechanism_posterior(rec, st, sat)
        worst = min(worst, abs(sum(post["posterior"].values()) - 1.0))
        if not (0 <= post["lead_p"] <= 1):
            check("posterior: range", False, f"lead_p out of range {post['lead_p']}")
            return
    check("posterior: sums to 1 over 300 random buildings", worst < 1e-9,
          f"max deviation {worst:.2e}")


def test_monotone_survival():
    """Survival must never increase with time."""
    prev, bad = 1.1, None
    t = 0.05
    while t <= 240:
        s = survival_curve(t)
        if s > prev + 1e-12:
            bad = t
            break
        prev = s
        t *= 1.08
    check("survival curve: monotone non-increasing", bad is None,
          f"no violation 0.05-240 h" if bad is None else f"rises at {bad:.2f}h")


def test_novel_mechanism():
    """An uncatalogued structural type must NOT get a confident mechanism label."""
    rec = Record(bid="NOV-1", label="precast panel infill, no plan",
                 lat=0, lon=0, plot_m2=180, declared_floors=4, design_occupancy=20,
                 use="residential", sanction_plan_on_file=False,
                 structure="precast_panel", element_removed="column", collapsed=True,
                 debris_spread_ratio=1.7, lastgasp={"impacts": 2, "duration_s": 6.0, "amp": 0.2})
    r = _run(rec)
    post = r["post"]
    ok = post["uncertain"] and post["out_of_vocabulary"]
    check("novel mechanism: refuses to over-commit", ok,
          f"lead={post['lead']} p={post['lead_p']:.2f} "
          f"OOV={post['out_of_vocabulary']} uncertain={post['uncertain']}")


def test_stale_records():
    """No plan and no observation -> LR must be marked unverifiable, not trusted."""
    rec = Record(bid="STALE-1", label="no plan, no listing",
                 lat=0, lon=0, plot_m2=60, declared_floors=3, design_occupancy=6,
                 use="residential", sanction_plan_on_file=False, collapsed=True)
    r = _run(rec)
    ok = r["st"]["unverified"] and ("unverifiable" in r["txt"])
    check("stale records: flags unverifiable LR", ok,
          f"unverified={r['st']['unverified']}")


def test_phone_dead_victim():
    """If the phone census hears nothing, the pipeline must NOT conclude 'empty'."""
    r = _run(SATYA_NIKETAN)
    rng = random.Random(42)
    vs, ft, t, order = plan_sense_then_dig(r["voids"], 3, 24.0, rng, truth=[False] * len(r["voids"]))
    floor_p = min(v.p_occupancy for v in vs)
    ok = floor_p >= 0.02   # absence evidence can never drive belief to zero
    check("sensor silence is not proof of absence", ok,
          f"min belief after an all-negative census = {floor_p:.2f} (floor 0.02)")


def test_expectant_never_dead():
    """At T+240h the brief must say expectant + re-triage, never 'no survivors'."""
    rec = P.replace(SATYA_NIKETAN)
    r = _run(rec, n_teams=1, horizon=240.0)
    txt = r["txt"].lower()
    ok = ("expectant" in txt) and ("no survivors" not in txt) and ("dead" not in txt)
    check("expectant != dead in the output text", ok,
          "brief uses expectant/re-triage wording")


def test_capacity_shortfall():
    """One team, 6 h: most pockets must be explicitly listed as not reached."""
    r = _run(SATYA_NIKETAN, n_teams=1, horizon=6.0)
    done = sum(1 for f in r["ft"] if f is not None)
    ok = done < len(r["voids"]) and "NOT REACHED" in r["txt"]
    check("capacity shortfall is stated, not hidden", ok,
          f"{done}/{len(r['voids'])} reached in 6 h, shortfall listed")


def test_voi_regime(n=300):
    """The core novelty claim, tested against itself.

    Claim: confirm-before-dig pays where records are MISSING and costs lives where
    records exist. If this test flips, the 'value of information' slide is false.
    """
    rng = random.Random(7)
    rec = SATYA_NIKETAN
    st, sat = standing(rec), satellite(rec)
    post = mechanism_posterior(rec, st, sat)
    base = build_void_field(rec, post, rng)
    occupancy(rec, base, post)

    d_good = P.confirm_pays(base, 3, 24.0, n=n, seed=1)
    flat = [P.replace(v) for v in base]
    for v in flat:
        v.set_p(0.5)
    d_flat = P.confirm_pays(flat, 3, 24.0, n=n, seed=2)

    ok = (d_flat > 0.05) and (d_good < -0.05)
    check("VoI: helps where records are missing, costs where they exist", ok,
          f"flat {d_flat:+.2f}, records {d_good:+.2f} lives @3 teams")


# ------------------------------------------------------------------ main --

def run_all(verbose: bool = True) -> bool:
    RESULTS.clear()
    test_units()
    test_no_double_booking()
    test_posterior_conservation()
    test_monotone_survival()
    test_novel_mechanism()
    test_stale_records()
    test_phone_dead_victim()
    test_expectant_never_dead()
    test_capacity_shortfall()
    test_voi_regime()
    passed = sum(1 for _, ok, _ in RESULTS if ok)
    if verbose:
        print("=" * 92)
        print(f"PRISM RED TEAM -- {passed}/{len(RESULTS)} adversarial checks passed")
        print("=" * 92)
        for name, ok, detail in RESULTS:
            print(f"  [{'PASS' if ok else 'FAIL'}] {name}\n         {detail}")
        if passed < len(RESULTS):
            print("\n  A FAILING TEST MEANS THE BRIEF CANNOT BE TRUSTED AS WRITTEN.")
    return passed == len(RESULTS)


if __name__ == "__main__":
    run_all()
