"""Document parsing (Markdown/TXT/HTML/PDF via PyMuPDF + Tesseract OCR fallback) and text cleaning."""

from __future__ import annotations

import re
import shutil
import subprocess
from pathlib import Path


def clean_text(raw: str) -> str:
    """Normalize whitespace, strip control characters, and tidy bullet formatting."""
    text = raw.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", " ", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def extract_text_from_file(file_path: Path) -> str:
    """Extract text from .md, .txt, .html, or .pdf (with OCR fallback for scanned PDFs)."""
    suffix = file_path.suffix.lower()
    if suffix in (".md", ".txt", ".csv"):
        return clean_text(file_path.read_text(encoding="utf-8", errors="ignore"))

    if suffix in (".html", ".htm"):
        raw = file_path.read_text(encoding="utf-8", errors="ignore")
        stripped = re.sub(r"<script.*?</script>|<style.*?</style>", " ", raw, flags=re.DOTALL | re.IGNORECASE)
        stripped = re.sub(r"<[^>]+>", " ", stripped)
        return clean_text(stripped)

    if suffix == ".pdf":
        import fitz  # PyMuPDF

        doc = fitz.open(str(file_path))
        pages_text: list[str] = []
        for page in doc:
            txt = page.get_text("text").strip()
            if len(txt) < 30 and shutil.which("tesseract"):
                # OCR fallback for scanned page
                pix = page.get_pixmap(dpi=200)
                img_bytes = pix.tobytes("png")
                proc = subprocess.run(
                    ["tesseract", "stdin", "stdout", "-l", "eng+hin+mar"],
                    input=img_bytes,
                    capture_output=True,
                    timeout=30,
                )
                if proc.returncode == 0:
                    txt = proc.stdout.decode("utf-8", errors="ignore")
            pages_text.append(txt)
        doc.close()
        return clean_text("\n\n".join(pages_text))

    raise ValueError(f"Unsupported document format: {suffix}")
