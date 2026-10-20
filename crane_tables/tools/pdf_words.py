"""
Extract words + bounding boxes from a (vector) PDF using poppler's
`pdftotext -bbox-layout`.

Returns a list of Word(page, text, x0, y0, x1, y1) in PDF points, origin
top-left (the coordinate system pdftotext -bbox uses), y growing downwards.

This is the raw material for the coordinate-based chart parser: unlike a
markdown/text conversion, positions let us rebuild the radius/boom/angle
grid deterministically instead of guessing from whitespace.
"""
from __future__ import annotations

import subprocess
import xml.etree.ElementTree as ET
from dataclasses import dataclass

NS = "{http://www.w3.org/1999/xhtml}"


@dataclass
class Word:
    page: int
    text: str
    x0: float
    y0: float
    x1: float
    y1: float

    @property
    def cx(self) -> float:  # horizontal centre, used for column assignment
        return (self.x0 + self.x1) / 2

    @property
    def cy(self) -> float:  # vertical centre, used for row assignment
        return (self.y0 + self.y1) / 2


def extract_words(pdf_path: str,
                  pages: set[int] | None = None) -> list[Word]:
    """Extract words for the whole document; `pages` filters by 1-based
    absolute document page afterwards (so page numbers stay absolute)."""
    cmd = ["pdftotext", "-bbox-layout", pdf_path, "-"]
    xml = subprocess.run(cmd, check=True, capture_output=True).stdout.decode(
        "utf-8", "replace")

    root = ET.fromstring(xml)
    words: list[Word] = []
    for pno, page in enumerate(root.iter(f"{NS}page"), start=1):
        if pages is not None and pno not in pages:
            continue
        for w in page.iter(f"{NS}word"):
            txt = (w.text or "").strip()
            if not txt:
                continue
            words.append(Word(
                page=pno, text=txt,
                x0=float(w.get("xMin")), y0=float(w.get("yMin")),
                x1=float(w.get("xMax")), y1=float(w.get("yMax")),
            ))
    return words


def group_lines(words: list[Word], tol: float = 3.0) -> list[list[Word]]:
    """Group words of the *same page* into visual lines by vertical centre."""
    out: list[list[Word]] = []
    for w in sorted(words, key=lambda w: (w.cy, w.x0)):
        if out and abs(out[-1][0].cy - w.cy) <= tol:
            out[-1].append(w)
        else:
            out.append([w])
    for line in out:
        line.sort(key=lambda w: w.x0)
    return out


if __name__ == "__main__":
    import sys
    pages = set(int(x) for x in sys.argv[2:]) if len(sys.argv) > 2 else None
    ws = extract_words(sys.argv[1], pages)
    for ln in group_lines(ws):
        print(f"{ln[0].cy:7.2f} | " + "  ".join(f"{w.text}@{w.cx:.0f}" for w in ln))
