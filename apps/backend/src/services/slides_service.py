"""PPTX metin çıkarımı + isteğe bağlı LibreOffice render (Yetenek 01).

LibreOffice yoksa render kopyası üretilmez; pop-up metin alıntısı fallback'i kullanılır.
"""

from __future__ import annotations

import shutil
import subprocess  # nosec B404 — LibreOffice headless dönüşümü (argv listesi, shell yok)
from contextlib import suppress
from pathlib import Path

from pptx import Presentation
from pptx.enum.shapes import MSO_SHAPE_TYPE

WINDOWS_SOFFICE_PATHS = (
    r"C:\Program Files\LibreOffice\program\soffice.exe",
    r"C:\Program Files (x86)\LibreOffice\program\soffice.exe",
)


class SlidesError(Exception):
    """Kullanıcıya gösterilecek Türkçe hata mesajı taşır."""


def _collect_shape_lines(shape, lines: list[str]) -> None:
    """Bir şeklin metin çerçevesi/tablosu/grup içindeki tüm metinlerini toplar."""
    if shape.has_text_frame:
        for para in shape.text_frame.paragraphs:
            line = "".join(run.text for run in para.runs).strip()
            if line:
                lines.append(line)
    if getattr(shape, "has_table", False):
        for row in shape.table.rows:
            cells = [cell.text.strip() for cell in row.cells]
            line = " | ".join(c for c in cells if c)
            if line:
                lines.append(line)
    if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
        for child in shape.shapes:
            _collect_shape_lines(child, lines)


def extract_pptx_slides(path: str) -> list[dict]:
    """Slide bazlı metin çıkarır: [{"slide": 1, "text": "..."}, ...].

    Başlık + gövde + tablolar + gruplar + konuşmacı notları toplanır.
    """
    try:
        prs = Presentation(path)
    except Exception as exc:
        raise SlidesError("Sunum okunamadı, dosya bozuk olabilir.") from exc

    slides: list[dict] = []
    for i, slide in enumerate(prs.slides, start=1):
        lines: list[str] = []
        for shape in slide.shapes:
            _collect_shape_lines(shape, lines)
        with suppress(Exception):
            if slide.has_notes_slide:
                notes_frame = slide.notes_slide.notes_text_frame
                if notes_frame is not None:
                    notes = notes_frame.text.strip()
                    if notes:
                        lines.append(f"[Not] {notes}")
        slides.append({"slide": i, "text": "\n".join(lines)})
    return slides


def find_soffice() -> str | None:
    """LibreOffice ikilisi arar; yoksa None (metin alıntısı fallback'i kullanılır)."""
    for name in ("soffice", "libreoffice"):
        found = shutil.which(name)
        if found:
            return found
    for path in WINDOWS_SOFFICE_PATHS:
        if Path(path).exists():
            return path
    return None


def render_pptx_to_pdf(pptx_path: str, out_dir: str) -> str | None:
    """LibreOffice headless ile PPTX→PDF kopyası üretir; yoksa None döner."""
    soffice = find_soffice()
    if soffice is None:
        return None
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    try:
        subprocess.run(  # nosec B603 — shell yok; argümanlar sabit + kullanıcının kendi dosyası
            [
                soffice,
                "--headless",
                "--convert-to",
                "pdf",
                "--outdir",
                str(out),
                pptx_path,
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            timeout=120,
            check=True,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    pdf = out / f"{Path(pptx_path).stem}.pdf"
    return str(pdf) if pdf.exists() else None
