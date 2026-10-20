"""
Export the capacity database to CSV/JSON, and re-import an edited CSV.

This is the bridge for the "semi-manual" route: dump a spreadsheet-friendly
file, review/correct it by hand, load it back. The CSV is the single editable
source of truth for a human, so anything the parser is unsure about can be
fixed without touching code.

    python3 -m tools.export db/cranes.db out/ltm1300.csv
    python3 -m tools.import_csv db/cranes.db out/ltm1300.csv
"""
from __future__ import annotations

import csv
import json
import os
import sqlite3
import sys

FIELDS = ["model", "page", "system", "counterweight_t", "boom_min", "boom_max",
          "jib_m", "ballast_options", "boom_m", "angle_deg", "footnote",
          "radius_m", "capacity_t"]


def export_csv(db: str, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    rows = con.execute("""
        SELECT cr.model, ch.page, ch.system, ch.counterweight_t, ch.boom_min,
               ch.boom_max, ch.jib_m, ch.ballast_options,
               c.boom_m, c.angle_deg, c.footnote, c.radius_m, c.capacity_t
        FROM capacity c
        JOIN chart ch ON ch.id=c.chart_id
        JOIN crane cr ON cr.id=ch.crane_id
        ORDER BY ch.page, c.boom_m, c.angle_deg, c.radius_m
    """).fetchall()
    with open(path, "w", newline="") as fh:
        w = csv.writer(fh)
        w.writerow(FIELDS)
        for r in rows:
            w.writerow([r[k] if r[k] is not None else "" for k in FIELDS])
    con.close()
    print(f"wrote {len(rows)} rows -> {path}")


def export_json(db: str, path: str):
    os.makedirs(os.path.dirname(path) or ".", exist_ok=True)
    con = sqlite3.connect(db)
    con.row_factory = sqlite3.Row
    data = [dict(r) for r in con.execute("SELECT * FROM capacity LIMIT 0")]
    charts = [dict(r) for r in con.execute("SELECT * FROM chart")]
    cranes = [dict(r) for r in con.execute("SELECT * FROM crane")]
    caps = [dict(r) for r in con.execute("SELECT * FROM capacity")]
    con.close()
    with open(path, "w") as fh:
        json.dump({"cranes": cranes, "charts": charts, "capacity": caps}, fh,
                  indent=1)
    print(f"wrote {len(caps)} capacity rows -> {path}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print(__doc__)
        sys.exit(1)
    if sys.argv[2].endswith(".json"):
        export_json(sys.argv[1], sys.argv[2])
    else:
        export_csv(sys.argv[1], sys.argv[2])
