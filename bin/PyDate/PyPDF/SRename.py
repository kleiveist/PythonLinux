#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, sys, unicodedata
import fitz  # PyMuPDF

# Bereich in cm relativ zum UNTEREN linken Seitenrand
X_CM, Y_CM, W_CM, H_CM = 21.5, 1.1, 8.3, 1.7
CM_TO_PT = 72.0 / 2.54
INSET_PT = 0.5

STRECKE_RE   = re.compile(r"\bStrecke\s+(\d+)\b", re.IGNORECASE)
SKIP_LINE_RE = re.compile(r"^\s*(Abteilung|Zeichn\.-?Nr\.?|EMR|Anlage|Deckblatt)\b", re.IGNORECASE)
# neu: bevorzugte Kennzeilen wie SR36SK07E19FOP1, G701R404SK04E12FOP1, G809EGSK99E8FOP1, …
ID_LINE_RE   = re.compile(r"^\s*=?(?:SR\d|G\d)[A-Za-z0-9]*")

try:
    fitz.TOOLS.mupdf_display_errors(False)
    fitz.TOOLS.mupdf_display_warnings(False)
except Exception:
    pass
os.environ.setdefault("PYTHONIOENCODING", "utf-8")

def print_safe(s: str) -> None:
    try:
        sys.stdout.write(s + ("\n" if not s.endswith("\n") else ""))
    except Exception:
        sys.stdout.write(s.encode("utf-8", "replace").decode("utf-8", "replace") + "\n")

def safe_name(s: str) -> str:
    s = unicodedata.normalize("NFKC", " ".join(s.strip().split()))
    s = re.sub(r'[\\/:*?"<>|]', "", s)
    s = re.sub(r"[^A-Za-z0-9 +=]", "", s)  # nur Buchstaben/Ziffern, Leerzeichen, +, =
    return s.strip(" .")

def _shrink_rect(r: fitz.Rect, dx: float, dy: float) -> fitz.Rect:
    return fitz.Rect(r.x0 + dx, r.y0 + dy, r.x1 - dx, r.y1 - dy)

def _intersects(a: fitz.Rect, b: fitz.Rect) -> bool:
    c = a & b
    return c.width > 0 and c.height > 0

def rect_from_cm_bottom_left(page) -> fitz.Rect:
    ph = page.rect.height
    x0 = X_CM * CM_TO_PT
    x1 = (X_CM + W_CM) * CM_TO_PT
    yb = Y_CM * CM_TO_PT
    hp = H_CM * CM_TO_PT
    y0 = ph - (yb + hp)
    y1 = ph - yb
    r = fitz.Rect(x0, y0, x1, y1)
    r = _shrink_rect(r, INSET_PT, INSET_PT) & page.rect
    if r.width <= 0 or r.height <= 0:
        r = fitz.Rect(x0, y0, max(x0+1, x1), max(y0+1, y1)) & page.rect
    return r

def read_lines_in_region(pdf_path: str):
    lines = []
    try:
        doc = fitz.open(pdf_path)
    except Exception as e:
        print_safe(f"✗ Kann PDF nicht öffnen: {os.path.basename(pdf_path)} – {e}")
        return lines
    try:
        if len(doc) == 0:
            return lines
        page = doc[0]
        region = rect_from_cm_bottom_left(page)
        # nur Linke Feldhälfte (rechts stehen „Abteilung / Zeichn.-Nr.“)
        left = fitz.Rect(region.x0, region.y0, region.x0 + region.width*0.55, region.y1)

        # robust: rawdict ohne clip -> Zeilen nach BBox filtern
        try:
            rd = page.get_text("rawdict")
            bucket = []
            for b in rd.get("blocks", []):
                if b.get("type", 0) != 0:
                    continue
                for l in b.get("lines", []):
                    lbox = None; spans = []
                    for sp in l.get("spans", []):
                        x0,y0,x1,y1 = sp.get("bbox", [0,0,0,0])
                        r = fitz.Rect(x0,y0,x1,y1)
                        t = sp.get("text", "")
                        spans.append((r,t))
                        lbox = r if lbox is None else (lbox | r)
                    if not spans or lbox is None:
                        continue
                    if _intersects(lbox, left):
                        spans.sort(key=lambda t:(t[0].y0,t[0].x0))
                        text = "".join(t[1] for t in spans).strip()
                        if text:
                            bucket.append(((lbox.y0+lbox.y1)/2, spans[0][0].x0, text))
            if bucket:
                bucket.sort(key=lambda t:(t[0], t[1]))
                lines = [t[2] for t in bucket if t[2].strip()]
        except Exception:
            lines = []

        # Fallback: blocks
        if not lines:
            try:
                for x0,y0,x1,y1,txt,*_ in page.get_text("blocks"):
                    if _intersects(fitz.Rect(x0,y0,x1,y1), left):
                        for ln in txt.splitlines():
                            ln = ln.strip()
                            if ln: lines.append(ln)
            except Exception:
                pass

        # Letzter Fallback: erste paar Zeilen der Seite
        if not lines:
            try:
                whole = page.get_text("text") or ""
                for ln in whole.splitlines():
                    ln = ln.strip()
                    if ln: lines.append(ln)
                    if len(lines) >= 3: break
            except Exception:
                pass

        return lines
    finally:
        doc.close()

def choose_name_from_lines(all_lines):
    if not all_lines:
        return None
    base = [ln for ln in all_lines if not SKIP_LINE_RE.match(ln)]

    # 2. Zeile (gefiltert) = "Strecke xx"?
    if len(base) > 1:
        m = STRECKE_RE.search(base[1])
        if m: return f"Strecke {m.group(1)}"

    # bevorzugt SR… / G… Identifier
    for ln in base:
        if ID_LINE_RE.match(ln):
            return safe_name(ln)

    # sonst: Zeile mit '=' oder '+'
    for ln in base:
        if '+' in ln or '=' in ln:
            return safe_name(ln)

    # sonst: erste gefilterte Zeile
    if base:
        return safe_name(base[0])

    # absolute Notreserve: aus allen Zeilen SR/G am Anfang
    for ln in all_lines:
        if ID_LINE_RE.match(ln):
            return safe_name(ln)

    return None

def rename_pdfs_in_cwd():
    pdfs = sorted([f for f in os.listdir(".") if f.lower().endswith(".pdf")])
    if not pdfs:
        print_safe("Keine PDFs gefunden."); return
    for fn in pdfs:
        try:
            lines = read_lines_in_region(fn)
            new_core = choose_name_from_lines(lines)
        except Exception as e:
            print_safe(f"Fehler bei {fn}: {e}"); continue
        if not new_core:
            print_safe(f"Übersprungen (kein Name im Bereich): {fn}"); continue
        new_name = f"{new_core}.pdf"
        if new_name == fn:
            print_safe(f"✓ Bereits korrekt: {fn}"); continue
        base, ext = os.path.splitext(new_name)
        cand, k = new_name, 2
        while os.path.exists(cand):
            cand = f"{base} ({k}){ext}"; k += 1
        try:
            os.rename(fn, cand)
            print_safe(f"{fn}  →  {cand}")
        except Exception as e:
            print_safe(f"Konnte nicht umbenennen: {fn} → {cand}: {e}")

if __name__ == "__main__":
    rename_pdfs_in_cwd()
