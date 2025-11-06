#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import sys
import datetime as dt
from pathlib import Path
from typing import Iterable, Optional

MD_DIRNAME = "md"  # Zielordnername

def log(msg: str) -> None:
    print(msg, flush=True)

def to_markdown_pymupdf4llm(pdf_path: Path) -> str:
    import pymupdf4llm  # type: ignore
    return pymupdf4llm.to_markdown(str(pdf_path))

def to_markdown_fallback(pdf_path: Path) -> str:
    try:
        from pdfminer.high_level import extract_text  # type: ignore
        text = extract_text(str(pdf_path)) or ""
    except Exception:
        text = ""
    if not text.strip():
        return (f"_Hinweis_: Konnte aus '{pdf_path.name}' keinen Text extrahieren. "
                "Ist es ggf. gescannt (ohne OCR)?")
    # sehr einfache Absatzheuristik
    lines = [ln.rstrip() for ln in text.splitlines()]
    paras, buf = [], []
    for ln in lines:
        if ln.strip():
            buf.append(ln)
        else:
            if buf:
                paras.append(" ".join(buf))
                buf = []
    if buf:
        paras.append(" ".join(buf))
    return "\n\n".join(paras)

def write_markdown(md_text: str, pdf_path: Path, base_root: Path, md_root: Path) -> Path:
    """
    Schreibt Markdown in den md_root-Spiegelpfad relativ zu base_root.
    Beispiel: pdf=/a/b/c/foo.pdf, base_root=/a/b  ->  md_root/c/foo.md
    """
    rel = pdf_path.resolve().relative_to(base_root.resolve())
    out_path = (md_root / rel).with_suffix(".md")
    out_path.parent.mkdir(parents=True, exist_ok=True)

    header = (
        "---\n"
        f"title: {pdf_path.stem}\n"
        f"source_pdf: {rel.as_posix()}\n"
        f"converted_utc: {dt.datetime.utcnow().isoformat()}Z\n"
        "---\n\n"
    )
    out_path.write_text(header + md_text, encoding="utf-8")
    return out_path

def convert_one(pdf_path: Path, base_root: Path, md_root: Path) -> Optional[Path]:
    try:
        try:
            md = to_markdown_pymupdf4llm(pdf_path)
        except ImportError:
            log("pymupdf4llm nicht gefunden – Fallback (pdfminer.six) wird versucht.")
            md = to_markdown_fallback(pdf_path)
        outp = write_markdown(md, pdf_path, base_root, md_root)
        log(f"OK: {pdf_path}  →  {outp}")
        return outp
    except Exception as e:
        log(f"FEHLER bei {pdf_path}: {e}")
        return None

def find_pdfs(root: Path) -> Iterable[Path]:
    for dirpath, dirnames, filenames in os.walk(root, followlinks=False):
        dirnames[:] = [d for d in dirnames if not Path(dirpath, d).is_symlink()]
        for fn in filenames:
            if fn.lower().endswith(".pdf"):
                yield Path(dirpath) / fn

def main() -> int:
    args = sys.argv[1:]
    if len(args) == 0:
        # Modus A: alle PDFs unterhalb CWD, Ausgaben nach ./md
        base_root = Path.cwd().resolve()
        md_root = (base_root / MD_DIRNAME).resolve()
        log(f"[Batch] Suche PDFs unter: {base_root}")
        pdfs = list(find_pdfs(base_root))
        if not pdfs:
            log("Keine PDF-Dateien gefunden.")
            return 0
        ok = 0
        for pdf in pdfs:
            if convert_one(pdf, base_root, md_root):
                ok += 1
        log(f"Fertig. Konvertiert: {ok} von {len(pdfs)} PDFs. Ziel: {md_root}")
        return 0

    if len(args) == 1:
        # Modus B: exakt eine Datei
        pdf = Path(args[0]).expanduser().resolve()
        if not pdf.is_file() or pdf.suffix.lower() != ".pdf":
            log(f"Pfad ist keine PDF-Datei: {pdf}")
            return 2
        base_root = pdf.parent.resolve()
        md_root = (base_root / MD_DIRNAME).resolve()
        log(f"[Single] Verarbeite: {pdf}")
        convert_one(pdf, base_root, md_root)
        log(f"Ziel: {md_root}")
        return 0

    log("Benutzung:\n  pdf2md              # alle PDFs unter CWD → ./md\n  pdf2md <file.pdf>   # nur diese Datei → ./md neben der Datei")
    return 2

if __name__ == "__main__":
    try:
        sys.exit(main())
    except KeyboardInterrupt:
        log("Abgebrochen.")
        sys.exit(1)
