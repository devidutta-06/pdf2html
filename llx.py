"""Layout-LaTeX (LLX): one command per line, units in points.

to_llx(elements, page_w, page_h) -> str
from_llx(text) -> list[dict]   (first dict is the page)
"""
import re

_FLOAT = {"x", "y", "w", "h", "size", "sw", "opacity", "r"}
_INT = {"weight", "italic", "z"}
_REQUIRED = {
    "page": ["w", "h"],
    "shape": ["id", "kind", "x", "y", "w", "h", "z"],
    "text": ["id", "x", "y", "w", "h", "font", "weight", "size", "color", "z"],
    "image": ["id", "x", "y", "w", "h", "z"],
}
_HEAD = re.compile(r"\\(page|shape|text|image)\[")
_ATTR = re.compile(r'\s*([A-Za-z_]\w*)=("(?:[^"\\]|\\.)*"|[^,\]"]*)\s*([,\]])')
_UNESC = {"\\": "\\", "{": "{", "}": "}", "n": "\n"}


def _n(v, nd=2):
    s = f"{float(v):.{nd}f}".rstrip("0").rstrip(".")
    return "0" if s in ("", "-0") else s


def _q(v, force=False):
    s = str(v)
    if force or s == "" or re.search(r'[\s,"\[\]{}\\]', s):
        return '"' + s.replace("\\", "\\\\").replace('"', '\\"') + '"'
    return s


def _esc_text(t):
    t = t.replace("\r\n", "\n").replace("\r", "\n")
    return (t.replace("\\", "\\\\").replace("{", "\\{")
             .replace("}", "\\}").replace("\n", "\\n"))


def _box(e):
    return f"x={_n(e['x'])},y={_n(e['y'])},w={_n(e['w'])},h={_n(e['h'])}"


def to_llx(elements, page_w, page_h):
    lines = [f"\\page[w={_n(page_w)},h={_n(page_h)},bg=#FFFFFF]"]
    for e in elements:
        t = e["type"]
        if t == "shape":
            extra = f",r={_n(e['r'])}" if e["kind"] == "rrect" else ""
            lines.append(
                f"\\shape[id={_q(e['id'])},kind={e['kind']},{_box(e)}{extra},"
                f"fill={e['fill'] or 'none'},stroke={e['stroke'] or 'none'},"
                f"sw={_n(e['sw'])},opacity={_n(e['opacity'], 3)},z={int(e['z'])}]")
        elif t == "text":
            lines.append(
                f"\\text[id={_q(e['id'])},{_box(e)},font={_q(e['font'], True)},"
                f"weight={int(e['weight'])},italic={int(e['italic'])},size={_n(e['size'])},"
                f"color={e['color']},z={int(e['z'])}]{{{_esc_text(e['text'])}}}")
        elif t == "image":
            lines.append(f"\\image[id={_q(e['id'])},{_box(e)},z={int(e['z'])}]")
        else:
            raise ValueError(f"unknown element type {t!r}")
    return "\n".join(lines) + "\n"


def _parse_line(line):
    m = _HEAD.match(line)
    if not m:
        raise ValueError("expected \\page, \\shape, \\text or \\image command")
    kind, pos, attrs = m.group(1), m.end(), {}
    if line[pos:pos + 1] == "]":
        pos += 1
    else:
        while True:
            am = _ATTR.match(line, pos)
            if not am:
                raise ValueError(f"bad attribute at column {pos + 1}")
            key, val = am.group(1), am.group(2)
            if val.startswith('"'):
                val = re.sub(r"\\(.)", r"\1", val[1:-1])
            attrs[key] = val
            pos = am.end()
            if am.group(3) == "]":
                break
    rest = line[pos:].strip()
    text = None
    if kind == "text":
        if not rest.startswith("{"):
            raise ValueError("\\text needs {...} content")
        buf, i = [], 1
        while True:
            if i >= len(rest):
                raise ValueError("unterminated {...} text")
            ch = rest[i]
            if ch == "\\":
                nxt = rest[i + 1:i + 2]
                if nxt not in _UNESC:
                    raise ValueError(f"bad escape \\{nxt}")
                buf.append(_UNESC[nxt])
                i += 2
            elif ch == "}":
                if i != len(rest) - 1:
                    raise ValueError("unexpected text after closing }")
                break
            elif ch == "{":
                raise ValueError("unescaped { in text")
            else:
                buf.append(ch)
                i += 1
        text = "".join(buf)
    elif rest:
        raise ValueError(f"unexpected text after ]: {rest[:20]!r}")

    for k in _REQUIRED[kind]:
        if k not in attrs:
            raise ValueError(f"missing attribute {k!r}")
    for k in list(attrs):
        try:
            if k in _FLOAT:
                attrs[k] = float(attrs[k])
            elif k in _INT:
                attrs[k] = int(float(attrs[k]))
        except ValueError:
            raise ValueError(f"bad number for {k}: {attrs[k]!r}")
    el = dict(attrs, type=kind)
    if kind == "page":
        el.setdefault("bg", "#FFFFFF")
    if kind == "shape":
        for k in ("fill", "stroke"):
            if el.get(k, "none") == "none":
                el[k] = None
        el.setdefault("sw", 0.0)
        el.setdefault("opacity", 1.0)
    if kind == "text":
        el.setdefault("italic", 0)
        el["text"] = text
    return el


def from_llx(text):
    out = []
    for n, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("%"):
            continue
        try:
            out.append(_parse_line(line))
        except ValueError as err:
            raise ValueError(f"LLX line {n}: {err}") from None
    return out
