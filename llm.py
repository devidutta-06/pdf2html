"""Golden HTML -> semantic, responsive HTML via a local Ollama model."""
import re

SYSTEM_PROMPT = """You are an HTML refactoring tool. Do exactly this:
1. Replace generic div/span with semantic elements (header, main, section,
   footer, h1-h3, p, ul/li) where the role is clear.
2. Make it responsive: flexbox/grid, max-width, rem or % instead of fixed
   pixels and absolute positioning. Keep the same look .
   Add one @media (max-width: 768px) block.
3. Keep all CSS in the single <style> block. No style="" attributes.
4. Do not change, add or remove any text.
5. Keep every element with class "img-placeholder" as an empty block.
Output only the complete HTML, no explanation."""


def estimate_tokens(s):
    return int(len(s) / 3.5)


def strip_fences(s):
    s = s.strip()
    m = re.search(r"```(?:html)?[ \t]*\n(.*?)```", s, re.S)
    if m:
        return m.group(1).strip()
    s = re.sub(r"^```(?:html)?[ \t]*\n?", "", s)  # opening fence, no closing (cut off)
    return re.sub(r"\n?```\s*$", "", s).strip()


def refine(golden, host, model, num_ctx):
    """Return (html, note). note is None on success, else why golden was returned."""
    est = estimate_tokens(golden)
    if est > num_ctx:
        return golden, f"HTML is about {est} tokens, over NUM_CTX={num_ctx}; saved golden HTML."
    try:
        import ollama
        client = ollama.Client(host=host, timeout=900)
        resp = client.chat(
            model=model,
            messages=[{"role": "system", "content": SYSTEM_PROMPT},
                      {"role": "user", "content": golden}],
            options={"num_ctx": num_ctx, "temperature": 0.1},
        )
        reply = resp["message"]["content"]
        cut = getattr(resp, "done_reason", None) == "length"
    except Exception as err:  # connection, missing model, missing package
        return golden, f"Ollama call failed ({type(err).__name__}: {err}); saved golden HTML."
    out = strip_fences(reply)
    if cut or "</html>" not in out.lower():
        return golden, "Model reply was cut off or incomplete; saved golden HTML."
    return out + "\n", None
