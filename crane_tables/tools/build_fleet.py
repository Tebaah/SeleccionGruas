"""
Build one shared database for a whole fleet.

    python3 -m tools.build_fleet db/fleet.db

The manifest lists one entry per crane: pdf path, model, max capacity and an
optional page->jib override (only needed when the page tag does not carry the
jib length, as with the LTM 1300's TK/TNZK pages).
"""
from __future__ import annotations

import os
import sys

from .build_db import build

HERE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

FLEET = [
    dict(pdf=os.path.join(HERE, "..", "LTM-1300-6.3.pdf"),
         model="LTM 1300-6.3", max_capacity_t=300.0, page_jib=None),
    dict(pdf=os.path.join(HERE, "..", "LTM-1450-8.1.pdf"),
         model="LTM 1450-8.1", max_capacity_t=450.0, page_jib={}),
]


def main(db_path: str):
    if os.path.exists(db_path):
        os.remove(db_path)
    total = 0
    for entry in FLEET:
        if not os.path.exists(entry["pdf"]):
            print(f"  ! missing {entry['pdf']}")
            continue
        probs = build(entry["pdf"], db_path, model=entry["model"],
                      max_capacity_t=entry["max_capacity_t"],
                      page_jib=entry["page_jib"])
        total += len(probs)
    print(f"fleet built -> {db_path}  ({len(FLEET)} cranes, "
          f"{total} cells flagged for review)")


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "db/fleet.db")
