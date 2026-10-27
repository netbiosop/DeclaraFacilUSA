"""Llenado de los PDF oficiales del IRS / Filling the official IRS PDFs (pypdf).

Los PDF del IRS son formularios XFA + AcroForm. Se elimina la parte XFA (si no, Adobe Reader mostraría la versión XFA
vacía), se escriben los valores en los campos AcroForm y, por defecto, se "aplanan": el texto queda impreso en la
página y se quitan los campos, para que se vea e imprima igual en cualquier visor.
"""
from __future__ import annotations

import io
from typing import Dict, Iterable, List, Optional

try:  # pypdf es necesario solo para generar los formularios
    import pypdf
    from pypdf.generic import (ArrayObject, BooleanObject, DecodedStreamObject, DictionaryObject, FloatObject,
                               NameObject)
except ImportError:  # pragma: no cover - se informa en la interfaz
    pypdf = None


class MissingDependency(RuntimeError):
    pass


def require():
    if pypdf is None:
        raise MissingDependency("pypdf")


def _fmt_ssn(value: str, maxlen: Optional[int]) -> str:
    digits = "".join(ch for ch in value if ch.isdigit())
    if maxlen == 11 and len(digits) == 9:
        return f"{digits[:3]}-{digits[3:5]}-{digits[5:]}"
    return value


def _prepare(value, spec):
    """Convierte el valor del constructor en lo que espera el campo. spec: ruta | [ruta, estado] | [ruta, None, maxlen]."""
    if isinstance(spec, str):
        return spec, None, str(value)
    path, state = spec[0], spec[1]
    if state:  # casilla
        return path, state, None
    maxlen = spec[2] if len(spec) > 2 else None
    text = str(value)
    if maxlen:
        text = _fmt_ssn(text, maxlen) if maxlen in (9, 11) else text
        if maxlen == 9 or maxlen == 17:  # SSN / número de ruta / cuenta en casillas: solo dígitos
            text = "".join(ch for ch in text if ch.isalnum())
        text = text[:maxlen]
    return path, None, text


def fill(pdf_path, fields: Dict[str, object], values: Dict[str, object], *, flatten: bool = True,
         pages: Optional[Iterable[int]] = None) -> bytes:
    """Llena un PDF. fields: mapa clave -> campo (de data/formularios/<año>.json); values: clave -> texto | True.
    pages: índices (0..) de páginas a conservar (p. ej. solo la página 2 para un estudiante adicional del 8863)."""
    require()
    reader = pypdf.PdfReader(str(pdf_path))
    writer = pypdf.PdfWriter(clone_from=reader)
    acro = writer._root_object.get("/AcroForm")
    if acro is not None:
        acro = acro.get_object()
        if "/XFA" in acro:
            del acro[NameObject("/XFA")]
        acro[NameObject("/NeedAppearances")] = BooleanObject(True)
    texts: Dict[str, str] = {}
    checks: Dict[str, str] = {}
    for key, val in values.items():
        if key not in fields or val in (None, "", False):
            continue
        path, state, text = _prepare(val, fields[key])
        if state:
            checks[path] = state
        else:
            texts[path] = text
    # Cada valor se aplica en la página donde está el campo. En modo aplanado las casillas se marcan con una "X"
    # dibujada (la apariencia del IRS usa la fuente ZapfDingbats sin incrustar y algunos visores no la muestran).
    marks: Dict[int, List[list]] = {}
    for pi, page in enumerate(writer.pages):
        sel = {}
        for a in page.get("/Annots") or []:
            a = a.get_object()
            parts, node = [], a
            while node is not None:
                if "/T" in node:
                    parts.append(str(node["/T"]))
                node = node.get("/Parent")
                node = node.get_object() if node is not None else None
            name = ".".join(reversed(parts))
            if name in texts:
                sel[name] = _fit(texts[name], a)
            elif name in checks:
                if flatten:
                    marks.setdefault(pi, []).append([float(x) for x in a["/Rect"]])
                else:
                    sel[name] = checks[name]
        if sel:
            writer.update_page_form_field_values(writer.pages[pi], sel, auto_regenerate=False, flatten=flatten)
    for pi, rects in marks.items():
        box = writer.pages[pi].mediabox
        writer.pages[pi].merge_page(_marks_page(float(box.width), float(box.height), rects))
    if flatten:
        for page in writer.pages:
            if "/Annots" in page:
                keep = ArrayObject([a for a in page["/Annots"] if a.get_object().get("/Subtype") != "/Widget"])
                if keep:
                    page[NameObject("/Annots")] = keep
                else:
                    del page[NameObject("/Annots")]
        if "/AcroForm" in writer._root_object:
            del writer._root_object[NameObject("/AcroForm")]
    if pages is not None:
        keep = set(pages)
        for i in range(len(writer.pages) - 1, -1, -1):
            if i not in keep:
                writer.remove_page(i)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def _fit(text: str, widget):
    """Reduce el tamaño de letra si el texto no cabe en el campo (nombres y direcciones largos)."""
    try:
        x1, _y1, x2, _y2 = (float(v) for v in widget["/Rect"])
        da = str(widget.get("/DA") or (widget.get("/Parent").get_object().get("/DA") if widget.get("/Parent") else "") or "")
        ff = int(widget.get("/Ff") or (widget.get("/Parent").get_object().get("/Ff", 0) if widget.get("/Parent") else 0))
    except (KeyError, TypeError, ValueError):
        return text
    if ff & (1 << 24):  # campo "comb" (una letra por casilla)
        return text
    parts = da.split()
    size = 9.0
    if "Tf" in parts:
        try:
            size = float(parts[parts.index("Tf") - 1]) or 9.0
        except ValueError:
            pass
    avail = abs(x2 - x1) - 4
    need = sum(0.72 if ch.isupper() or ch.isdigit() else 0.56 for ch in text) * size
    if need <= avail or avail <= 0:
        return text
    return (text, "", max(5.0, round(size * avail / need, 1)))


def _marks_page(width, height, rects):
    page = pypdf.PageObject.create_blank_page(width=width, height=height)
    ops = ["q 0 0 0 RG 0.9 w 1 J"]
    for x1, y1, x2, y2 in rects:
        x1, x2 = sorted((x1, x2))
        y1, y2 = sorted((y1, y2))
        side = min(x2 - x1, y2 - y1)
        cx, cy = (x1 + x2) / 2, (y1 + y2) / 2
        h = side * 0.32
        ops.append(f"{cx - h:.2f} {cy - h:.2f} m {cx + h:.2f} {cy + h:.2f} l S "
                   f"{cx - h:.2f} {cy + h:.2f} m {cx + h:.2f} {cy - h:.2f} l S")
    ops.append("Q")
    content = DecodedStreamObject()
    content.set_data(" ".join(ops).encode("ascii"))
    page[NameObject("/Contents")] = content
    return page


# ---------------------------------------------------------------------------------------------------- borrador
def _pdf_str(s: str) -> str:
    return s.replace("\\", "\\\\").replace("(", "\\(").replace(")", "\\)")


def _watermark_page(width: float, height: float, big: str, small: str):
    """Página transparente con la marca de agua 'BORRADOR' en diagonal (Helvetica estándar, sin dependencias)."""
    page = pypdf.PageObject.create_blank_page(width=width, height=height)
    font = DictionaryObject({NameObject("/Type"): NameObject("/Font"), NameObject("/Subtype"): NameObject("/Type1"),
                             NameObject("/BaseFont"): NameObject("/Helvetica-Bold"),
                             NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    gs = DictionaryObject({NameObject("/Type"): NameObject("/ExtGState"), NameObject("/ca"): FloatObject(0.30),
                           NameObject("/CA"): FloatObject(0.30)})
    gs2 = DictionaryObject({NameObject("/Type"): NameObject("/ExtGState"), NameObject("/ca"): FloatObject(0.85),
                            NameObject("/CA"): FloatObject(0.85)})
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/WmF"): font}),
        NameObject("/ExtGState"): DictionaryObject({NameObject("/WmG"): gs, NameObject("/WmH"): gs2}),
    })
    size = 58 if len(big) <= 12 else max(30, int(58 * 12 / len(big)))
    # ancho aproximado de Helvetica-Bold: 0.6 em por carácter
    tw = 0.62 * size * len(big)
    c, s = 0.8192, 0.5736  # cos/sin de 35°
    cx, cy = width / 2, height / 2
    x = cx - c * tw / 2
    y = cy - s * tw / 2
    stream = (f"q /WmG gs 0.85 0.1 0.1 rg BT /WmF {size} Tf {c} {s} {-s} {c} {x:.1f} {y:.1f} Tm "
              f"({_pdf_str(big)}) Tj ET Q "
              f"q /WmH gs 0.75 0.05 0.05 rg BT /WmF 9 Tf 1 0 0 1 36 {height - 14:.1f} Tm ({_pdf_str(small)}) Tj ET Q")
    content = DecodedStreamObject()
    content.set_data(stream.encode("cp1252", "replace"))
    page[NameObject("/Contents")] = content
    return page


def watermark(pdf_bytes: bytes, big: str, small: str) -> bytes:
    require()
    reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
    writer = pypdf.PdfWriter(clone_from=reader)
    for page in writer.pages:
        box = page.mediabox
        page.merge_page(_watermark_page(float(box.width), float(box.height), big, small))
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def merge(parts: List[bytes]) -> bytes:
    require()
    writer = pypdf.PdfWriter()
    for data in parts:
        writer.append(pypdf.PdfReader(io.BytesIO(data)))
    if "/AcroForm" in writer._root_object:
        del writer._root_object[NameObject("/AcroForm")]
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()


def page_count(pdf_bytes: bytes) -> int:
    require()
    return len(pypdf.PdfReader(io.BytesIO(pdf_bytes)).pages)


# ---------------------------------------------------------------------------------------------------- hojas de texto
def _wrap(text: str, width: int) -> List[str]:
    out = []
    for para in str(text).split("\n"):
        line = ""
        for word in para.split(" "):
            if len(line) + len(word) + (1 if line else 0) > width:
                if line:
                    out.append(line)
                while len(word) > width:
                    out.append(word[:width])
                    word = word[width:]
                line = word
            else:
                line = f"{line} {word}" if line else word
        out.append(line)
    return out


def text_document(blocks: List[tuple], footer: str = "") -> bytes:
    """PDF tamaño carta con texto simple (Helvetica). blocks: lista de (estilo, texto); estilos: 'h1', 'h2', 'p',
    'mono', 'box' (recuadro destacado), 'sp' (espacio). Sin dependencias externas."""
    require()
    W, H, M = 612, 792, 54
    writer = pypdf.PdfWriter()
    fonts = DictionaryObject()
    for key, base in (("/F1", "/Helvetica"), ("/F2", "/Helvetica-Bold"), ("/F3", "/Courier")):
        fonts[NameObject(key)] = DictionaryObject({NameObject("/Type"): NameObject("/Font"),
                                                   NameObject("/Subtype"): NameObject("/Type1"),
                                                   NameObject("/BaseFont"): NameObject(base),
                                                   NameObject("/Encoding"): NameObject("/WinAnsiEncoding")})
    styles = {"h1": ("/F2", 16, 20, 62), "h2": ("/F2", 11.5, 15, 86), "p": ("/F1", 10, 13.5, 100),
              "mono": ("/F3", 9, 11.5, 92), "box": ("/F2", 11, 14.5, 80)}
    pages, ops, y = [], [], H - M

    def flush():
        nonlocal ops, y
        if footer:
            ops.append(f"BT /F1 8 Tf 0.4 0.4 0.4 rg {M} 30 Td ({_pdf_str(footer)}) Tj ET")
        pages.append(ops)
        ops, y = [], H - M

    for style, text in blocks:
        if style == "sp":
            y -= float(text or 8)
            continue
        font, size, lead, width = styles[style]
        lines = _wrap(text, width)
        need = lead * len(lines) + (10 if style == "box" else 4)
        if y - need < M:
            flush()
        if style == "box":
            y -= 8
            top = y
            ops.append(f"q 0.93 0.95 0.99 rg 0.75 0.8 0.9 RG {M - 6} {top - need - 2:.1f} {W - 2 * M + 12} {need + 4:.1f} "
                       f"re B Q")
            y -= 6
        color = "0.1 0.2 0.45 rg" if style in ("h1", "h2") else "0 0 0 rg"
        for ln in lines:
            y -= lead
            ops.append(f"BT {font} {size} Tf {color} {M} {y:.1f} Td ({_pdf_str(ln)}) Tj ET")
        y -= 4 if style != "box" else 12
    if ops or not pages:
        flush()
    for content_ops in pages:
        page = pypdf.PageObject.create_blank_page(width=W, height=H)
        page[NameObject("/Resources")] = DictionaryObject({NameObject("/Font"): fonts})
        content = DecodedStreamObject()
        content.set_data("\n".join(content_ops).encode("cp1252", "replace"))
        page[NameObject("/Contents")] = writer._add_object(content)
        writer.add_page(page)
    buf = io.BytesIO()
    writer.write(buf)
    return buf.getvalue()
