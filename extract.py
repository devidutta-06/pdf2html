"""PDF (1 page, real text) -> list of element dicts: shape, image, text.

Images: only the bbox is read. No pixels are extracted, decoded or encoded.
"""
import re

import fitz  

# order matters: longer / more specific names first
_WEIGHTS = [
    ("extrabold", 800), ("ultrabold", 800), ("semibold", 600), ("demibold", 600),
    ("demi", 600), ("extralight", 200), ("ultralight", 200), ("hairline", 100),
    ("thin", 100), ("black", 900), ("heavy", 900), ("bold", 700),
    ("medium", 500), ("light", 300), ("regular", 400), ("book", 400),
]


def parse_font(pdf_name, flags):
    """'ABCDEF+Montserrat-BoldItalic' -> ('Montserrat', 700, True)."""
    name = re.sub(r"^[^+]*\+", "", pdf_name or "")
    name = name.replace(",", "-")
    base, _, style = name.partition("-")
    base = re.sub(r"(PSMT|MT|PS)$", "", base) or base
    family = re.sub(r"(?<=[a-z])(?=[A-Z])|(?<=[A-Z])(?=[A-Z][a-z])", " ", base).strip()
    style_l = re.sub(r"[^a-z]", "", style.lower())
    weight = None
    for key, val in _WEIGHTS:
        if key in style_l:
            weight = val
            break
    if weight is None:
        weight = 700 if flags & 16 else 400
    italic = ("italic" in style_l) or ("oblique" in style_l) or bool(flags & 2)
    return family or "Arial", weight, italic


def _hex_int(c):
    return f"#{int(c):06X}"


def _rgb(t):
    if t is None:
        return None
    if len(t) == 1:
        t = (t[0],) * 3
    if len(t) != 3:
        return None
    return "#" + "".join(f"{round(max(0.0, min(1.0, v)) * 255):02X}" for v in t)


def _near(a, b, tol=0.5):
    return abs(a - b) <= tol


def _is_axis_rect(items, rect):
    """Closed path made only of straight segments that follow the bbox edges."""
    if not (3 <= len(items) <= 5):
        return False
    xs, ys = (rect.x0, rect.x1), (rect.y0, rect.y1)
    for it in items:
        for p in (it[1], it[2]):
            if not (any(_near(p.x, x) for x in xs) and any(_near(p.y, y) for y in ys)):
                return False
    return True


def _extract_text(page):
    out = []
    for block in page.get_text("dict")["blocks"]:
        if block.get("type") != 0:
            continue
        for line in block["lines"]:
            runs = []
            for s in line["spans"]:
                txt = re.sub(r"[\x00-\x08\x0b-\x1f]", "", s["text"])
                if not txt:
                    continue
                style = (s["font"], round(s["size"], 2), s["color"], s["flags"])
                bb = fitz.Rect(s["bbox"])
                if runs and runs[-1]["style"] == style:
                    runs[-1]["text"] += txt
                    runs[-1]["bbox"] |= bb
                else:
                    runs.append({"style": style, "text": txt, "bbox": bb})
            for r in runs:
                if not r["text"].strip():
                    continue
                font, size, color, flags = r["style"]
                family, weight, italic = parse_font(font, flags)
                bb = r["bbox"]
                out.append({
                    "type": "text", "x": bb.x0, "y": bb.y0, "w": bb.width, "h": bb.height,
                    "font": family, "weight": weight, "italic": int(italic),
                    "size": size, "color": _hex_int(color), "text": r["text"],
                })
    return out


def _extract_shapes(page):
    out, skipped = [], 0
    for d in page.get_drawings():
        kind_t = d.get("type", "")
        fill = _rgb(d.get("fill")) if "f" in kind_t else None
        stroke = _rgb(d.get("color")) if "s" in kind_t else None
        if fill is None and stroke is None:
            continue
        sw = float(d.get("width") or 0) if stroke else 0.0
        if fill is not None:
            op = d.get("fill_opacity")
        else:
            op = d.get("stroke_opacity")
        op = 1.0 if op is None else float(op)
        items = d["items"]
        ops = [i[0] for i in items]
        rect = fitz.Rect(d["rect"])
        base = {"type": "shape", "fill": fill, "stroke": stroke, "sw": sw, "opacity": op}

        def box(kind, rect, **extra):
            e = dict(base, kind=kind, x=rect.x0, y=rect.y0, w=rect.width, h=rect.height)
            e.update(extra)
            return e

        if ops in (["re"], ["qu"]) or (set(ops) == {"l"} and _is_axis_rect(items, rect)):
            if (rect.width < 0.01 or rect.height < 0.01):
                if stroke is not None:
                    out.append(box("line", rect, fill=None))
                else:
                    skipped += 1
            else:
                out.append(box("rect", rect))
        elif ops == ["l"]:
            if stroke is None:
                skipped += 1
                continue
            p1, p2 = items[0][1], items[0][2]
            r = fitz.Rect(min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y))
            out.append(box("line", r, fill=None))
        elif set(ops) <= {"l", "c"} and ops.count("c") == 4 and rect.width > 0 and rect.height > 0:
            c = next(i for i in items if i[0] == "c")
            dx, dy = abs(c[4].x - c[1].x), abs(c[4].y - c[1].y)
            rad = min(dx, dy) or max(dx, dy)
            rad = min(rad, rect.width / 2, rect.height / 2)
            out.append(box("rrect", rect, r=rad))
        elif set(ops) == {"l"} and fill is None and stroke is not None:
            for it in items:  # open polyline -> one line per segment
                p1, p2 = it[1], it[2]
                r = fitz.Rect(min(p1.x, p2.x), min(p1.y, p2.y), max(p1.x, p2.x), max(p1.y, p2.y))
                out.append(box("line", r, fill=None))
        else:
            skipped += 1  # polygons, free curves: ignored
    return out, skipped


def _extract_images(page):
    out = []
    page_area = page.rect.get_area()
    for info in page.get_image_info():  # bbox only, no pixel access
        bb = fitz.Rect(info["bbox"])
        if bb.width <= 0 or bb.height <= 0:
            continue
        if (bb & page.rect).get_area() / page_area >= 0.9:
            continue  # background image, page stays white
        out.append({"type": "image", "x": bb.x0, "y": bb.y0, "w": bb.width, "h": bb.height})
    return out


def extract(pdf_path):
    """Return (elements, page_w, page_h, info). Elements carry id and z."""
    doc = fitz.open(pdf_path)
    if not doc.is_pdf:
        raise ValueError("Input must be a PDF.")
    if doc.page_count < 1:
        raise ValueError("PDF has no pages.")
    page = doc[0]
    shapes, skipped = _extract_shapes(page)
    images = _extract_images(page)
    texts = _extract_text(page)

    for i, e in enumerate(shapes, 1):
        e["id"], e["z"] = f"s{i}", i
    for i, e in enumerate(images, 1):
        e["id"], e["z"] = f"img{i}", len(shapes) + i
    for i, e in enumerate(texts, 1):
        e["id"], e["z"] = f"t{i}", len(shapes) + len(images) + i

    flow = sorted(images + texts, key=lambda e: (round(e["y"]), e["x"]))
    elements = shapes + flow
    info = {
        "pages": doc.page_count, "shapes": len(shapes), "images": len(images),
        "texts": len(texts), "skipped_paths": skipped,
    }
    return elements, page.rect.width, page.rect.height, info
