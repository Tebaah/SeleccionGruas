"""
Recover the exact table grid (column and row rule lines) from a page, by
parsing the vector paths that poppler emits with `pdftocairo -svg`.

Why not just use text positions: Liebherr load charts have merged header
cells (e.g. "14,7 m" spanning two data columns) and footnote sub-columns
("*"), so header x-positions do NOT line up with data x-positions. The
rule lines are the ground truth for "which cell is a value in".

Returns, in PDF points (top-left origin, y downwards):
    cols : sorted x of vertical separators
    rows : sorted y of horizontal separators
"""
from __future__ import annotations

import re
import subprocess
import tempfile
from dataclasses import dataclass

_NUM = r'[-+]?\d*\.?\d+(?:[eE][-+]?\d+)?'


@dataclass
class Seg:
    x0: float; y0: float; x1: float; y1: float


def _parse_transform(t: str | None):
    if not t:
        return (1, 0, 0, 1, 0, 0)
    m = re.search(r'matrix\(([^)]*)\)', t)
    if m:
        vals = [float(v) for v in re.split(r'[,\s]+', m.group(1).strip())]
        if len(vals) == 6:
            return tuple(vals)
    m = re.search(r'translate\(([^)]*)\)', t)
    if m:
        vals = [float(v) for v in re.split(r'[,\s]+', m.group(1).strip())]
        vals += [0, 0]
        return (1, 0, 0, 1, vals[0], vals[1])
    return (1, 0, 0, 1, 0, 0)


def _segments(svg: str) -> list[Seg]:
    """Only stroke drawings (fill="none") are rule lines; filled paths are
    cell decorations and glyphs, which would pollute the grid."""
    segs: list[Seg] = []
    for tag in re.findall(r'<path\b[^>]*?/>', svg, re.S):
        if 'fill="none"' not in tag:
            continue
        m = re.search(r'\bd="([^"]+)"', tag)
        if not m:
            continue
        d = m.group(1)
        tm = re.search(r'transform="([^"]+)"', tag)
        a, b, c, dd, e, f = _parse_transform(tm.group(1) if tm else None)
        pts = [(float(x), float(y))
               for x, y in re.findall(rf'[ML]\s*({_NUM})\s+({_NUM})', d)]
        ap = [(a * x + c * y + e, b * x + dd * y + f) for x, y in pts]
        for i in range(len(ap) - 1):
            segs.append(Seg(ap[i][0], ap[i][1], ap[i + 1][0], ap[i + 1][1]))
    return segs


def _cluster(vals: list[float], tol: float = 1.2):
    """Group near-equal coordinates; return (mean, count, span)."""
    vals = sorted(vals)
    groups: list[list[float]] = []
    for v in vals:
        if groups and v - groups[-1][-1] <= tol:
            groups[-1].append(v)
        else:
            groups.append([v])
    return groups


def grid_from_pdf(pdf_path: str, page: int, keep_frac: float = 0.45):
    """Return (cols, rows): x of vertical rules and y of horizontal rules.

    The chart draws each rule as one short stroke per cell, so a real rule is
    identified by the number of times a coordinate repeats (≈ number of
    rows/columns), not by the length of a single stroke.
    """
    with tempfile.TemporaryDirectory() as td:
        out = f"{td}/p.svg"
        subprocess.run(["pdftocairo", "-svg", "-f", str(page), "-l", str(page),
                        pdf_path, out], check=True, capture_output=True)
        svg = open(out, encoding="utf-8", errors="replace").read()
    segs = _segments(svg)

    vx: list[float] = []
    hy: list[float] = []
    for s in segs:
        if abs(s.x0 - s.x1) < 0.4 and abs(s.y1 - s.y0) > 1:
            vx.append((s.x0 + s.x1) / 2)
        elif abs(s.y0 - s.y1) < 0.4 and abs(s.x1 - s.x0) > 1:
            hy.append((s.y0 + s.y1) / 2)

    def rules(vals, tol):
        groups = _cluster(vals, tol)
        counts = [len(g) for g in groups]
        if not counts:
            return []
        top = max(counts)
        return sorted(round(sum(g) / len(g), 1)
                      for g in groups if len(g) >= keep_frac * top)

    return rules(vx, 1.2), rules(hy, 1.2)


if __name__ == "__main__":
    import sys
    c, r = grid_from_pdf(sys.argv[1], int(sys.argv[2]))
    print("cols", len(c), [round(x, 1) for x in c])
    print("rows", len(r), [round(y, 1) for y in r])
