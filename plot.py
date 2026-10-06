"""Parsed LLX dicts -> golden HTML (absolute layout, one <style> block, no style="")."""
import html
import re

_COLOR = re.compile(r"^#[0-9A-Fa-f]{6}$")


def px(pt):
    s = f"{round(float(pt) * 96 / 72, 2):.2f}".rstrip("0").rstrip(".")
    return ("0" if s in ("", "-0") else s) + "px"


def _color(c, default="#000000"):
    return (c if c and _COLOR.match(c) else default).lower()


def _fallback(family):
    f = family.lower()
    if "mono" in f or "courier" in f:
        return "monospace"
    if "sans" not in f and any(k in f for k in ("times", "georgia", "garamond", "serif")):
        return "serif"
    return "sans-serif"


def font_family(family):
    name = re.sub(r"[^\w .\-]", "", family).strip() or "Arial"
    parts = [f"'{name}'"]
    if name.lower() == "helvetica":
        parts.append("Arial")
    parts.append(_fallback(name))
    return ",".join(parts)


def _rule(cls, decls):
    return f".{cls} {{ " + "; ".join(decls) + " }"


def build_html(elements):
    page = next((e for e in elements if e["type"] == "page"), None)
    if page is None:
        raise ValueError("LLX has no \\page line")
    rules, body = [], []
    n = 0
    for e in elements:
        t = e["type"]
        if t == "page":
            continue
        n += 1
        cls = f"e{n}"
        box = [f"left:{px(e['x'])}", f"top:{px(e['y'])}",
               f"width:{px(e['w'])}", f"height:{px(e['h'])}"]
        z = f"z-index:{int(e['z'])}"
        if t == "text":
            d = box + [
                f"line-height:{px(e['h'])}", "white-space:pre",
                f"font-family:{font_family(e['font'])}",
                f"font-weight:{int(e['weight'])}",
            ]
            if e.get("italic"):
                d.append("font-style:italic")
            d += [f"font-size:{px(e['size'])}", f"color:{_color(e['color'])}", z]
            rules.append(_rule(cls, d))
            body.append(f'<div class="{cls}">{html.escape(e["text"])}</div>')
        elif t == "image":
            rules.append(_rule(cls, box + [z]))
            ident = html.escape(str(e["id"]))
            body.append(f'<div class="img-placeholder {cls}" data-id="{ident}"></div>')
        elif t == "shape":
            sw = e.get("sw") or 0
            if e["kind"] == "line":
                col = _color(e["stroke"] or e["fill"])
                thick = sw if sw > 0 else 0.75
                if e["w"] >= e["h"]:
                    d = [f"left:{px(e['x'])}", f"top:{px(e['y'] + e['h'] / 2 - thick / 2)}",
                         f"width:{px(e['w'])}", f"height:{px(thick)}"]
                else:
                    d = [f"left:{px(e['x'] + e['w'] / 2 - thick / 2)}", f"top:{px(e['y'])}",
                         f"width:{px(thick)}", f"height:{px(e['h'])}"]
                d.append(f"background:{col}")
            else:
                d = list(box)
                if e.get("fill"):
                    d.append(f"background:{_color(e['fill'])}")
                if e.get("stroke") and sw > 0:
                    d.append(f"border:{px(sw)} solid {_color(e['stroke'])}")
                if e["kind"] == "rrect":
                    d.append(f"border-radius:{px(e.get('r', 0))}")
            if e.get("opacity", 1) != 1:
                d.append(f"opacity:{round(e['opacity'], 3):g}")
            d.append(z)
            rules.append(_rule(cls, d))
            body.append(f'<div class="{cls}"></div>')

    base = [
        "body { margin:0 }",
        ".page { " + "; ".join([
            "position:relative", f"width:{px(page['w'])}", f"height:{px(page['h'])}",
            "margin:0 auto", f"background:{_color(page.get('bg'), '#ffffff')}",
            "overflow:hidden"]) + " }",
        ".page div { position:absolute; box-sizing:border-box; margin:0 }",
        ".img-placeholder { background:#eeeeee; border:1px dashed #aaaaaa }",
    ]
    css = "\n".join(base + rules)
    return (
        '<!DOCTYPE html>\n<html lang="en">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        f"<title>pdf2html</title>\n<style>\n{css}\n</style>\n</head>\n<body>\n"
        '<div class="page">\n' + "\n".join(body) + "\n</div>\n</body>\n</html>\n"
    )
