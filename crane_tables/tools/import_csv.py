"""
Import a (reviewed) capacity CSV back into a fresh SQLite database.

Reuses the same structural validation as the PDF path, so a hand-edited file
is checked for monotonicity before it is trusted.

    python3 -m tools.import_csv db/reviewed.db out/ltm1300.csv
"""
from __future__ import annotations

import csv
import os
import sqlite3
import sys
from collections import defaultdict

from .build_db import SCHEMA, validate


def _num(s):
    return float(s) if s not in ("", None) else None


def import_csv(db: str, path: str):
    os.makedirs(os.path.dirname(db) or ".", exist_ok=True)
    if os.path.exists(db):
        os.remove(db)
    con = sqlite3.connect(db)
    con.executescript(SCHEMA)
    cur = con.cursor()
    cranes: dict[str, int] = {}
    charts: dict[tuple, int] = {}
    cols: dict = defaultdict(list)
    n = 0
    with open(path, newline="") as fh:
        for row in csv.DictReader(fh):
            model = row["model"]
            if model not in cranes:
                cur.execute("INSERT INTO crane(manufacturer,model,source_pdf)"
                            " VALUES(?,?,?)", ("Liebherr", model, path))
                cranes[model] = cur.lastrowid
            ck = (model, int(row["page"]))
            if ck not in charts:
                cur.execute(
                    "INSERT INTO chart(crane_id,page,system,counterweight_t,"
                    "boom_min,boom_max,jib_m,ballast_options)"
                    " VALUES(?,?,?,?,?,?,?,?)",
                    (cranes[model], int(row["page"]), row["system"],
                     _num(row["counterweight_t"]), _num(row["boom_min"]),
                     _num(row["boom_max"]), _num(row["jib_m"]),
                     row["ballast_options"]))
                charts[ck] = cur.lastrowid
            cur.execute("INSERT INTO capacity VALUES(?,?,?,?,?,?)",
                        (charts[ck], _num(row["radius_m"]), _num(row["boom_m"]),
                         _num(row["angle_deg"]), row["footnote"] or "",
                         _num(row["capacity_t"])))
            cols[(ck, row["boom_m"], row["angle_deg"], row["footnote"])].append(
                (_num(row["radius_m"]), _num(row["capacity_t"])))
            n += 1
    con.commit()

    probs = []
    for k, pts in cols.items():
        probs += validate({k: pts})
    con.close()
    print(f"imported {n} rows, {len(charts)} charts -> {db}")
    print(f"VALIDATION: {'OK' if not probs else str(len(probs)) + ' problems'}")
    for p in probs[:20]:
        print(p)


if __name__ == "__main__":
    import_csv(sys.argv[1], sys.argv[2])
