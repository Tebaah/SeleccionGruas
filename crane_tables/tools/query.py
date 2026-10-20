"""
Crane configuration selector.

Given a required load, a working radius and (optionally) a boom length or a
lift height, return every tabulated configuration that can make the lift, with
the margin, so the operator picks the cheapest adequate setup.

Capacity lookup follows the usual reading of a load chart:
  * capacity is interpolated linearly between the two tabulated radii that
    bracket the requested radius;
  * below the smallest tabulated radius the smallest-radius value is used
    (capacity near the machine is capped by structural limits);
  * beyond the largest tabulated radius for a boom, that column cannot reach.

Usage:
    python3 -m tools.query db/cranes.db --load 25 --radius 30
    python3 -m tools.query db/cranes.db --load 25 --radius 30 --system T --cw 88
"""
from __future__ import annotations

import argparse
import math
import sqlite3
from dataclasses import dataclass


@dataclass
class Config:
    crane: str
    page: int
    system: str
    counterweight_t: float | None
    jib_m: float | None
    boom_m: float
    angle_deg: float | None
    footnote: str
    capacity_t: float      # governing (interpolated) capacity at the radius
    hook_height_m: float | None = None


def _load(path):
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    return con


def _interp(points: list[tuple[float, float]], radius: float) -> float | None:
    """points sorted by radius -> interpolated capacity, or None if out of range."""
    if not points:
        return None
    if radius > points[-1][0]:
        return None
    if radius <= points[0][0]:
        return points[0][1]
    for (r0, v0), (r1, v1) in zip(points, points[1:]):
        if r0 <= radius <= r1:
            if r1 == r0:
                return v0
            t = (radius - r0) / (r1 - r0)
            return v0 + t * (v1 - v0)
    return None


def hook_height(boom_m: float, radius_m: float, heel_h: float = 3.0,
                heel_off: float = 1.5, head_len: float = 2.3) -> float | None:
    """Hook height reached by a main boom at a given working radius.

    boom tip height = heel_h + sqrt(L^2 - x^2),  x = horizontal heel->load;
    hook height = tip - head_len (boom head + hook block, vertically).
    Defaults are calibrated against the LTM 1300 Hubhöhen diagram (p.15):
    the 90 m boom tops out at ~90 m hook height => heel_h-head_len ~ 0.7 m.
    Returns None when the boom is too short to reach the radius.
    """
    x = abs(radius_m - heel_off)
    if x >= boom_m:
        return None
    return heel_h + math.sqrt(boom_m * boom_m - x * x) - head_len


def select(db_path: str, load_t: float, radius_m: float,
           system: str | None = None, cw: float | None = None,
           boom_m: float | None = None, crane: str | None = None,
           include_footnote: bool = True, height_m: float | None = None,
           heel_h: float = 3.0, heel_off: float = 1.5,
           head_len: float = 2.3) -> list[Config]:
    con = _load(db_path)
    q = ("SELECT cr.model AS crane, ch.page, ch.system, ch.counterweight_t, "
         "ch.jib_m, c.boom_m, c.angle_deg, c.footnote, c.radius_m, c.capacity_t "
         "FROM capacity c JOIN chart ch ON ch.id=c.chart_id "
         "JOIN crane cr ON cr.id=ch.crane_id")
    cols: dict[tuple, list[tuple[float, float]]] = {}
    meta: dict[tuple, sqlite3.Row] = {}
    for row in con.execute(q):
        if system and row["system"] != system:
            continue
        if crane and row["crane"] != crane:
            continue
        if cw is not None and row["counterweight_t"] != cw:
            continue
        if boom_m is not None and row["boom_m"] != boom_m:
            continue
        if not include_footnote and row["footnote"] == "*":
            continue
        key = (row["crane"], row["page"], row["system"], row["counterweight_t"],
               row["jib_m"], row["boom_m"], row["angle_deg"], row["footnote"])
        cols.setdefault(key, []).append((row["radius_m"], row["capacity_t"]))
        meta[key] = row
    con.close()

    out: list[Config] = []
    for key, pts in cols.items():
        pts.sort()
        cap = _interp(pts, radius_m)
        if cap is None or cap < load_t:
            continue
        r = meta[key]
        hh = None
        if height_m is not None:
            # height check only meaningful for a plain main-boom column
            if r["angle_deg"] is None:
                hh = hook_height(r["boom_m"], radius_m, heel_h, heel_off, head_len)
                if hh is None or hh < height_m:
                    continue
        out.append(Config(crane=r["crane"], page=r["page"], system=r["system"],
                          counterweight_t=r["counterweight_t"], jib_m=r["jib_m"],
                          boom_m=r["boom_m"], angle_deg=r["angle_deg"],
                          footnote=r["footnote"], capacity_t=cap,
                          hook_height_m=hh))
    out.sort(key=lambda c: (-c.capacity_t, c.counterweight_t or 0, c.boom_m))
    return out


def best(db_path: str, load_t: float, radius_m: float, **kw) -> Config | None:
    res = select(db_path, load_t, radius_m, **kw)
    return res[0] if res else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("db")
    ap.add_argument("--load", type=float, required=True, help="required load, t")
    ap.add_argument("--radius", type=float, required=True, help="working radius, m")
    ap.add_argument("--height", type=float, help="hook height required, m")
    ap.add_argument("--system", help="T, TK/TNZK, TVK/TVNZK, TS, TNZF, TK 21, TF 14 ...")
    ap.add_argument("--crane", help="limit to one crane model")
    ap.add_argument("--cw", type=float, help="counterweight, t")
    ap.add_argument("--boom", type=float, help="fixed boom length, m")
    ap.add_argument("--top", type=int, default=25)
    a = ap.parse_args()
    res = select(a.db, a.load, a.radius, a.system, a.cw, a.boom, a.crane,
                 height_m=a.height)
    print(f"load {a.load} t @ radius {a.radius} m"
          f"{f' @ height {a.height} m' if a.height else ''} -> {len(res)} feasible")
    print(f"{'crane':16} {'system':11} {'p':>3} {'cw':>4} {'jib':>5} {'boom':>6} "
          f"{'ang':>5} {'fn':>2} {'h_gancho':>8} {'cap t':>7} {'util%':>6}")
    for c in res[:a.top]:
        util = 100 * a.load / c.capacity_t
        hh = f"{c.hook_height_m:8.2f}" if c.hook_height_m is not None else "       -"
        print(f"{c.crane:16} {c.system:11} {c.page:>3} {c.counterweight_t or 0:>4g} "
              f"{c.jib_m if c.jib_m is not None else '-':>5} {c.boom_m:>6g} "
              f"{c.angle_deg if c.angle_deg is not None else '-':>5} "
              f"{c.footnote:>2} {hh} "
              f"{c.capacity_t:>7.2f} {util:>6.1f}")


if __name__ == "__main__":
    main()
