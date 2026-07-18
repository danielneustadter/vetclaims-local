"""Fill official VA form templates (AcroForm layer under XFA — the XFA is
dropped so the plain AcroForm is authoritative, the approach proven in
e2096-platform). Signature fields are never touched: the veteran signs after
review."""

from __future__ import annotations

import io
from pathlib import Path

import pypdfium2 as pdfium
from pypdf import PdfReader, PdfWriter
from pypdf.generic import NameObject, BooleanObject

FORMS_DIR = Path(__file__).parent / "forms"

TEMPLATES = {
    "21-526EZ": FORMS_DIR / "vba-21-526ez.pdf",
    "21-4138": FORMS_DIR / "vba-21-4138.pdf",
    "21-0966": FORMS_DIR / "vba-21-0966.pdf",
}


def fill_form(form: str, text_fields: dict[str, str],
              checkbox_fields: dict[str, str] | None = None) -> bytes:
    """Fill a template and return PDF bytes. Checkbox values are appearance
    state names without the leading slash (e.g. "1")."""
    reader = PdfReader(str(TEMPLATES[form]))
    writer = PdfWriter()
    writer.append(reader)

    acro = writer._root_object.get("/AcroForm")
    if acro is not None:
        acro = acro.get_object()
        if "/XFA" in acro:
            del acro["/XFA"]
        acro[NameObject("/NeedAppearances")] = BooleanObject(True)

    values: dict[str, str] = {k: v for k, v in text_fields.items() if v}
    for name, state in (checkbox_fields or {}).items():
        values[name] = f"/{state.lstrip('/')}"

    remaining = dict(values)
    for page in writer.pages:
        if not remaining:
            break
        page_fields = {}
        annots = page.get("/Annots") or []
        names_on_page = set()
        for a in annots:
            obj = a.get_object()
            names_on_page.add(_fq_name(obj))
        for name in list(remaining):
            if name in names_on_page:
                page_fields[name] = remaining.pop(name)
        if page_fields:
            writer.update_page_form_field_values(page, page_fields,
                                                 auto_regenerate=True)
    if remaining:
        raise KeyError(f"fields not found in {form}: {sorted(remaining)[:8]}"
                       f"{' …' if len(remaining) > 8 else ''}")
    out = io.BytesIO()
    writer.write(out)
    return out.getvalue()


def _fq_name(obj) -> str:
    parts = []
    while obj is not None:
        t = obj.get("/T")
        if t:
            parts.append(str(t))
        parent = obj.get("/Parent")
        obj = parent.get_object() if parent is not None else None
    return ".".join(reversed(parts))


def render_page_png(pdf_bytes: bytes, page_no: int, scale: float = 2.0) -> bytes:
    """Rasterize one page (1-based) to PNG — used for previews and the
    field-verification pass. pdfium's form init renders field values."""
    doc = pdfium.PdfDocument(pdf_bytes)
    try:
        doc.init_forms()
        page = doc[page_no - 1]
        bitmap = page.render(scale=scale, may_draw_forms=True)
        img = bitmap.to_pil()
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        return buf.getvalue()
    finally:
        doc.close()


def list_fields(form: str) -> dict:
    reader = PdfReader(str(TEMPLATES[form]))
    return {k: str(v.get("/FT")) for k, v in (reader.get_fields() or {}).items()}
