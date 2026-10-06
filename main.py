"""pdf2html CLI: PDF -> layout.llx -> golden.html -> output.html (Ollama)."""
import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

from extract import extract
from llx import from_llx, to_llx
from plot import build_html


def main():
    ap = argparse.ArgumentParser(description="Convert a one-page PDF to HTML.")
    ap.add_argument("pdf", help="path to the PDF (quote it if it has spaces)")
    ap.add_argument("--no-llm", action="store_true", help="skip the Ollama step")
    ap.add_argument("--out", default="out", help="output folder (default: out)")
    args = ap.parse_args()

    load_dotenv(Path(__file__).resolve().parent / ".env")
    host = os.getenv("OLLAMA_HOST", "http://192.168.10.50:11434")
    model = os.getenv("MODEL", "qwen2.5-coder:7b")
    num_ctx = int(os.getenv("NUM_CTX", "16384"))

    src = Path(args.pdf)
    if not src.is_file():
        sys.exit(f"File not found: {src}")
    if src.suffix.lower() != ".pdf":
        sys.exit("Input must be a PDF. A PNG or other image will not work.")

    try:
        elements, w, h, info = extract(str(src))
    except Exception as err:
        sys.exit(f"Could not read PDF: {err}")
    if info["pages"] > 1:
        print(f"Note: PDF has {info['pages']} pages, using page 1 only.")
    if info["texts"] == 0:
        print("Warning: no selectable text found. Export again as PDF Standard "
              "without 'Flatten PDF'.")
    if info["skipped_paths"]:
        print(f"Note: {info['skipped_paths']} unsupported vector paths ignored.")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    llx_text = to_llx(elements, w, h)
    (out / "layout.llx").write_text(llx_text, encoding="utf-8")
    parsed = from_llx((out / "layout.llx").read_text(encoding="utf-8"))
    golden = build_html(parsed)  # built from LLX only
    (out / "golden.html").write_text(golden, encoding="utf-8")
    print(f"Wrote {out / 'layout.llx'} and {out / 'golden.html'} "
          f"({info['texts']} text, {info['shapes']} shapes, {info['images']} images)")

    if args.no_llm:
        return
    from llm import refine
    print(f"Calling {model} at {host} ...")
    final, note = refine(golden, host, model, num_ctx)
    (out / "output.html").write_text(final, encoding="utf-8")
    print(note or f"Wrote {out / 'output.html'}")
    if note:
        print(f"Wrote {out / 'output.html'} (copy of golden.html)")


if __name__ == "__main__":
    main()
