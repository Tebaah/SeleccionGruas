"""
Turn a Liebherr load-chart page into structured records.

Why this shape (see README):
  * column bands come from the table's own rule lines, not from text x-positions
    -- merged header cells ("14,7 m" spanning two data columns) and footnote
    sub-columns ("*") make text positions unreliable;
  * radius labels in the left/right margins give the row bands;
  * a page may hold ONE or TWO vertically stacked sub-tables, so we segment the
    page on every boom-length header line.

Output per page: ChartMeta + list[Cell].
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass, field

from .pdf_words import extract_words, group_lines
from .svg_grid import grid_from_pdf

NUM = re.compile(r"^\d+(?:[.,]\d+)?$")
NUMM = re.compile(r"^(\d+(?:[.,]\d+)?)\s*m$")     # "90m" / "90 m" glued
ANGLE = re.compile(r"^(\d+(?:[.,]\d+)?)°$")


def f(t: str) -> float:
    return float(t.replace(",", "."))


@dataclass
class Cell:
    radius: float
    value: float
    boom: float | None
    angle: float | None
    footnote: str


@dataclass
class ChartMeta:
    page: int
    system: str
    counterweight_t: float | None = None
    boom_min: float | None = None
    boom_max: float | None = None
    jib_m: float | None = None
    ballast_radii: list[float] = field(default_factory=list)
    jibs: list[str] = field(default_factory=list)


def page_words(words, page):
    return [w for w in words if w.page == page]


def _system(pagew) -> str:
    """Read the model-family tag printed at the top-right of the page
    (e.g. 'T', 'TS', 'TNZF', 'TK 7', 'TF 17,5', 'TN 14 - 21').

    The tag is the right-most cluster of words in the page header."""
    top = [w for w in pagew if w.cy < 62]
    if not top:
        return "T"
    xmax = max(w.x1 for w in top)
    # window on the word CENTRE, not its left edge: family tags such as
    # "TVK/TVNZK" are wide and would fall out of a left-edge window.
    tag_words = [w for w in top if w.cx > xmax - 150]
    # group into visual lines, keep the lowest line (the tag row)
    lines = group_lines(tag_words, tol=6)
    if not lines:
        return "T"
    text = " ".join(w.text for w in lines[0])
    text = " ".join(text.split())
    # drop a leading 'Traglasten'/'Hubhöhen' if the row got merged
    for junk in ("Traglasten", "Hubhöhen"):
        text = text.replace(junk, "").strip()
    return text or "T"


def _jib_from_tag(tag: str) -> float | None:
    m = re.search(r"(\d+[.,]?\d*)\s*m?\b", tag.replace("–", "-"))
    if not m:
        return None
    try:
        return f(m.group(1))
    except ValueError:
        return None


def _meta(pagew) -> ChartMeta:
    m = ChartMeta(page=0, system="")
    for ln in group_lines([w for w in pagew if w.cy < 175]):
        for i in range(len(ln) - 1):
            if NUM.match(ln[i].text) and ln[i + 1].text == "t":
                m.counterweight_t = f(ln[i].text)
        txt = " ".join(w.text for w in ln)
        mm = re.search(r"(\d+[.,]?\d*)\s*[–\-]\s*(\d+[.,]?\d*)\s*m\b", txt)
        if mm and m.boom_min is None:
            m.boom_min, m.boom_max = f(mm.group(1)), f(mm.group(2))
    for ln in group_lines([w for w in pagew if 120 < w.cy < 172]):
        for i in range(len(ln) - 1):
            if NUM.match(ln[i].text) and ln[i + 1].text == "m" \
                    and 150 < ln[i].cx and f(ln[i].text) < 12:
                m.ballast_radii.append(f(ln[i].text))
    m.ballast_radii = sorted(set(m.ballast_radii))
    for ln in group_lines(pagew):
        txt = " ".join(w.text for w in ln)
        for jm in re.finditer(r"((?:K/NZK|NZK|NZF|S|V|K)\s?\d+[.,]?\d*\s?m)", txt):
            s = " ".join(jm.group(1).split())
            if s not in m.jibs:
                m.jibs.append(s)
    return m


def _radius_rows(pagew, cols):
    left = [w for w in pagew if w.cx < cols[0] - 1 and NUM.match(w.text)]
    right = [w for w in pagew if w.cx > cols[-1] + 1 and NUM.match(w.text)]
    rows = []
    for lw in sorted(left, key=lambda w: w.cy):
        for rw in right:
            if abs(rw.cy - lw.cy) < 3.5 and abs(f(rw.text) - f(lw.text)) < 1e-6:
                rows.append((f(lw.text), lw.cy))
                break
    return rows


def _header_lines(pagew, data_top):
    """All boom-length header lines and angle header lines above `data_top`."""
    booms, angles = [], []
    for ln in group_lines([w for w in pagew if w.cy < data_top]):
        n_m = 0
        for i, w in enumerate(ln):
            mm = NUMM.match(w.text)
            if mm:
                booms.append((f(mm.group(1)), w.cx, w.cy))
                n_m += 1
            elif NUM.match(w.text) and i + 1 < len(ln) and ln[i + 1].text == "m":
                booms.append((f(w.text), w.cx, w.cy))
                n_m += 1
            am = ANGLE.match(w.text)
            if am:
                angles.append((f(am.group(1)), w.cx, w.cy))
        if n_m < 3:
            # not a boom header line -> drop the 1-2 stray tokens (ballast/range)
            del booms[len(booms) - n_m:]
    return booms, angles


def _nearest(items, cx):
    """items: (value, x, [y]); return the item whose x is closest to cx."""
    best, bd = None, 1e9
    for it in items:
        d = abs(it[1] - cx)
        if d < bd:
            best, bd = it, d
    return best


def _angle_groups(aline):
    """Split the angle header row into per-column groups. Each boom repeats a
    fixed angle set: 0/20/40, 0/10/20/40, or *boom* angles 83/75/67. A new
    group starts when the sequence reverses direction."""
    groups: list[list[tuple[float, float, float]]] = []
    direction = 0
    for a in sorted(aline, key=lambda t: t[1]):
        if not groups:
            groups.append([a])
            continue
        d = a[0] - groups[-1][-1][0]
        if d == 0 or (direction and d * direction < 0):
            groups.append([a])
            direction = 0          # unknown again: don't split the next token
        else:
            groups[-1].append(a)
            direction = d
    return groups


def _col_labels(bands, bline, aline):
    """(boom, angle) for each column band."""
    if not bline:
        return [(None, None)] * len(bands)
    if not aline:
        out = []
        for (_, _, cx) in bands:
            b = _nearest(bline, cx)
            out.append((b[0] if b else None, None))
        return out
    groups = _angle_groups(aline)
    # label each group by the longest boom token inside its x-span
    leaf: list[tuple[float, float | None]] = []   # (cx, (boom, angle))
    for g in groups:
        xs = [a[1] for a in g]
        x0, x1 = min(xs) - 11, max(xs) + 11
        cand = [b for b in bline if x0 <= b[1] <= x1]
        label = max(cand, key=lambda b: b[0])[0] if cand else \
            (_nearest(bline, sum(xs) / len(xs)) or (None,))[0]
        for a in g:
            leaf.append((a[1], (label, a[0])))
    out = []
    for (_, _, cx) in bands:
        best = min(leaf, key=lambda t: abs(t[0] - cx)) if leaf else None
        out.append(best[1] if best and abs(best[0] - cx) < 13 else
                   ((_nearest(bline, cx) or (None,))[0], None))
    return out


def parse_page(words, page, pdf_path) -> tuple[ChartMeta, list[Cell]]:
    pagew = page_words(words, page)
    cols, _ = grid_from_pdf(pdf_path, page)
    meta = _meta(pagew)
    tag = _system(pagew)
    meta.page, meta.system = page, tag
    meta.jib_m = _jib_from_tag(tag)
    if len(cols) < 3:
        return meta, []

    rows = _radius_rows(pagew, cols)
    if not rows:
        return meta, []
    data_top = rows[0][1]
    boom_tokens, angle_tokens = _header_lines(pagew, data_top + 400)

    # ---- segment the page into stacked sub-tables on boom-header lines -----
    boom_ys = sorted({round(b[2], 1) for b in boom_tokens})
    # merge header tokens that are within 2pt (same visual line)
    groups: list[list[float]] = []
    for y in boom_ys:
        if groups and y - groups[-1][-1] <= 2:
            groups[-1].append(y)
        else:
            groups.append([y])
    header_ys = [sum(g) / len(g) for g in groups if
                 len([b for b in boom_tokens if sum(g) / len(g) - 1 <= b[2] <= sum(g) / len(g) + 1]) >= 3]
    if not header_ys:
        return meta, []

    angle_ys = sorted({round(a[2], 1) for a in angle_tokens})
    bands = [(cols[i], cols[i + 1], (cols[i] + cols[i + 1]) / 2)
             for i in range(len(cols) - 1)]

    cells: list[Cell] = []
    for hi, hy in enumerate(header_ys):
        y_end = header_ys[hi + 1] if hi + 1 < len(header_ys) else 1e9
        bline = sorted([b for b in boom_tokens if abs(b[2] - hy) <= 1.2],
                       key=lambda b: b[1])
        aline_y = min([y for y in angle_ys if hy < y < y_end], default=None)
        aline = []
        if aline_y is not None:
            aline = sorted([p for p in angle_tokens if abs(p[2] - aline_y) <= 1.2],
                           key=lambda p: p[1])
        col_labels = _col_labels(bands, bline, aline)

        # footnote star(s) between this header and its first data row
        sub_rows = [r for r in rows if hy < r[1] < y_end]
        if not sub_rows:
            continue
        foot_x = [w.cx for w in pagew if w.text == "*"
                  and hy < w.cy < sub_rows[0][1]]
        rc = [r[1] for r in sub_rows]
        bounds = [rc[0] - (rc[1] - rc[0]) / 2 if len(rc) > 1 else rc[0] - 5]
        for i in range(len(rc) - 1):
            bounds.append((rc[i] + rc[i + 1]) / 2)
        bounds.append(rc[-1] + (rc[-1] - rc[-2]) / 2 if len(rc) > 1 else rc[-1] + 5)

        for w in pagew:
            if not NUM.match(w.text):
                continue
            if not (cols[0] - 0.5 < w.cx < cols[-1] + 0.5):
                continue
            if not (bounds[0] <= w.cy <= bounds[-1]):
                continue
            bi = next((i for i, (x0, x1, _) in enumerate(bands)
                       if x0 - 0.5 <= w.cx < x1 + 0.5), None)
            ri = next((i for i in range(len(bounds) - 1)
                       if bounds[i] <= w.cy < bounds[i + 1]), None)
            if bi is None or ri is None:
                continue
            boom, ang = col_labels[bi]
            foot = "*" if any(bands[bi][0] - 1 <= fx < bands[bi][1] + 1
                              for fx in foot_x) else ""
            cells.append(Cell(radius=sub_rows[ri][0], value=f(w.text),
                              boom=boom, angle=ang, footnote=foot))
    return meta, cells
