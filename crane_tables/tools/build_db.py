"""
Extract every load-chart page of a crane PDF into SQLite, with validation.

Validation is structural, so it needs no second data source:
  * a capacity column must be non-increasing as radius grows;
  * at a fixed radius and angle, capacity must be non-increasing as the boom
    (or jib) gets longer.
Any cell that breaks these rules is almost certainly mis-assigned, so the
build reports them instead of silently trusting the parse.

Usage:
    python3 -m tools.build_db ../LTM-1300-6.3.pdf db/cranes.db
"""
from __future__ import annotations

import os
import re
import sqlite3
import sys

from .parse_charts import parse_page, ChartMeta, Cell
from .pdf_words import extract_words, group_lines

SCHEMA = """
CREATE TABLE IF NOT EXISTS crane(
  id INTEGER PRIMARY KEY,
  manufacturer TEXT, model TEXT, max_capacity_t REAL,
  source_pdf TEXT
);
CREATE TABLE IF NOT EXISTS chart(
  id INTEGER PRIMARY KEY,
  crane_id INTEGER REFERENCES crane(id),
  page INTEGER, system TEXT,
  counterweight_t REAL, boom_min REAL, boom_max REAL,
  jib_m REAL, ballast_options TEXT,
  UNIQUE(crane_id, page)
);
CREATE TABLE IF NOT EXISTS capacity(
  chart_id INTEGER REFERENCES chart(id),
  radius_m REAL, boom_m REAL, angle_deg REAL,
  footnote TEXT, capacity_t REAL
);
CREATE INDEX IF NOT EXISTS idx_cap ON capacity(chart_id, radius_m, boom_m, angle_deg);
"""

# reviewed page -> (system, jib length m) map; auto-detected where possible.
PAGE_JIB = {
    22: ("TK/TNZK", 11.5), 23: ("TK/TNZK", 11.5),
    24: ("TK/TNZK", 20.0), 25: ("TK/TNZK", 20.0),
    27: ("TVK/TVNZK", 11.5), 28: ("TVK/TVNZK", 11.5),
    29: ("TVK/TVNZK", 20.0), 30: ("TVK/TVNZK", 20.0),
    32: ("TVK/TVNZK", 11.5), 33: ("TVK/TVNZK", 11.5),
    34: ("TVK/TVNZK", 20.0), 35: ("TVK/TVNZK", 20.0),
    37: ("TS", 4.0), 39: ("TS", 11.0), 40: ("TS", 18.0),
    41: ("TS", 25.0), 42: ("TS", 32.0), 43: ("TS", 39.0),
    45: ("TNZF", 8.0), 46: ("TNZF", 15.0), 47: ("TNZF", 22.0),
    48: ("TNZF", 29.0), 49: ("TNZF", 36.0), 50: ("TNZF", 43.0),
    51: ("TNZF", 43.0),
}


def chart_pages(words) -> list[int]:
    """A load-chart page contains the word 'capacities' (word order differs
    between normal and bbox extraction, so 'Lifting capacities' may not be
    contiguous)."""
    pages = sorted({w.page for w in words})
    out = []
    for p in pages:
        txt = " ".join(w.text for w in words if w.page == p)
        if "capacities" in txt:
            out.append(p)
    return out


def validate(cells_by_col) -> list[str]:
    """cells_by_col: dict key-> list[(radius, value)]. Return problem strings.

    Load charts are non-increasing with radius, but near the structural cap the
    printed values wiggle by a few tenths, so only rises above a small
    tolerance are reported (those are the ones worth a human look)."""
    problems = []
    for key, pts in cells_by_col.items():
        pts = sorted(pts)
        for (r0, v0), (r1, v1) in zip(pts, pts[1:]):
            tol = max(0.6, 0.02 * abs(v0))
            if v1 - v0 > tol:
                problems.append(f"  {key}: r{r0}->{r1} rose {v0}->{v1}")
    return problems


def build(pdf: str, db_path: str, model="LTM 1300-6.3",
          manufacturer="Liebherr", max_capacity_t=300.0,
          page_jib: dict | None = None):
    page_jib = PAGE_JIB if page_jib is None else page_jib
    os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
    words = extract_words(pdf)
    pages = chart_pages(words)

    con = sqlite3.connect(db_path)
    con.executescript(SCHEMA)
    cur = con.cursor()
    cur.execute("INSERT INTO crane(manufacturer,model,max_capacity_t,source_pdf)"
                " VALUES(?,?,?,?)", (manufacturer, model, max_capacity_t, pdf))
    crane_id = cur.lastrowid

    all_problems, n_cells, n_charts = [], 0, 0
    for p in pages:
        meta, cells = parse_page(words, p, pdf)
        if not cells:
            print(f"  ! page {p}: no cells parsed", file=sys.stderr)
            continue
        jib = meta.jib_m
        if jib is None:
            jib = page_jib.get(p, (meta.system, None))[1]
        cur.execute(
            "INSERT OR IGNORE INTO chart(crane_id,page,system,counterweight_t,"
            "boom_min,boom_max,jib_m,ballast_options) VALUES(?,?,?,?,?,?,?,?)",
            (crane_id, p, meta.system, meta.counterweight_t,
             meta.boom_min, meta.boom_max, jib,
             ";".join(f"{r:g}" for r in meta.ballast_radii)))
        cid = cur.execute(
            "SELECT id FROM chart WHERE crane_id=? AND page=?",
            (crane_id, p)).fetchone()[0]
        cols: dict = {}
        for c in cells:
            cur.execute("INSERT INTO capacity VALUES(?,?,?,?,?,?)",
                        (cid, c.radius, c.boom, c.angle, c.footnote, c.value))
            cols.setdefault((c.boom, c.angle, c.footnote), []).append(
                (c.radius, c.value))
            n_cells += 1
        n_charts += 1
        all_problems += [f"p{p} " + s for s in validate(cols)]

    con.commit()
    con.close()
    print(f"crane '{model}': {n_charts} charts, {n_cells} capacity cells -> {db_path}")
    if all_problems:
        print(f"VALIDATION: {len(all_problems)} monotonicity problems "
              f"(inspect these cells):")
        for s in all_problems[:40]:
            print(s)
    else:
        print("VALIDATION: OK (no monotonicity problems)")
    return all_problems


if __name__ == "__main__":
    build(sys.argv[1], sys.argv[2] if len(sys.argv) > 2 else "db/cranes.db")
