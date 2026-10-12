#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
# © 2026 Design House (https://designhouse.me)
"""Builds the brand book from brand.json.

Usage: python3 build_book.py [brand/brand.json] [--force]

Writes, next to brand.json:
  book/index.html     the interactive brand book (data embedded, opens from disk, prints to PDF)
  labels/<id>.html    one label template per label, ?mode=preview or ?mode=guides
  tokens.css          @font-face and :root tokens (--background, --ink, --ink-2, --line, --accent, …)
                      for a website, a video or anyone who builds with the brand

brand.json is the only source. A built file that was edited by hand is not overwritten
(its checksum no longer matches .build.json); change brand.json instead, or pass --force.

Standard library only, no network. Exit code: 0 when built, 1 when a built file was
edited by hand or the data is unusable, 2 when an input file is missing.
"""
import hashlib
import json
import re
import sys
from pathlib import Path

SKILL = Path(__file__).resolve().parent.parent
FORMATS = {".woff2": "woff2", ".woff": "woff", ".ttf": "truetype", ".otf": "opentype"}


def fail(msg, code=1):
    print(f"ERROR: {msg}")
    sys.exit(code)


def font_faces(families, prefix):
    rules = []
    for fam in families:
        for entry in fam.get("files") or []:
            item = entry if isinstance(entry, dict) else {"file": entry}
            path = item.get("file", "")
            fmt = FORMATS.get(Path(path).suffix.lower())
            if not fmt:
                continue
            weight = item.get("weight", "100 900")
            style = item.get("style", "normal")
            # A width axis value or range ("108%", "75% 125%"): a variable font clamps the used width to it,
            # so one file can serve a wide headline cut under its own family name.
            stretch = f' font-stretch: {item["stretch"]};' if item.get("stretch") else ""
            rules.append(
                f'@font-face {{ font-family: "{fam["family"]}"; src: url("{prefix}{path}") format("{fmt}"); '
                f"font-weight: {weight}; font-style: {style};{stretch} font-display: block; }}"
            )
    return "\n".join(rules)


def embed(data):
    """JSON for a <script> block: '</' would end the script early."""
    return json.dumps(data, ensure_ascii=False, indent=1).replace("</", "<\\/")


def tokens_css(brand, families):
    colours = brand.get("colours") or []
    first = lambda role: next((c["hex"] for c in colours if c.get("role") == role), None)
    lines = [font_faces(families, ""), "", ":root {"]
    roles = {
        "--background": first("background"),
        "--ink": first("text"),
        "--ink-2": first("secondary-text"),
        "--line": first("line"),
        "--accent": first("accent"),
    }
    for name, value in roles.items():
        if value:
            lines.append(f"  {name}: {value};")
    for c in colours:
        lines.append(f"  --colour-{c['id']}: {c['hex']};  /* {c.get('name', '')}, {c.get('role', '')} */")
    for fam in families:
        lines.append(f'  --font-{fam.get("role", "text")}: "{fam["family"]}", {fam.get("fallback") or "system-ui, sans-serif"};')
    lines.append("}")
    return "\n".join(lines) + "\n"


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    src = Path(args[0] if args else "brand/brand.json")
    if not src.is_file():
        fail(f"file not found: {src}", 2)
    try:
        brand = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        fail(f"{src} is not valid JSON: {e}")
    root = src.parent
    meta = brand.get("meta") or {}
    if not meta.get("name"):
        fail("meta.name is missing")
    if not brand.get("colours"):
        fail("colours are missing; the book takes its look from them")
    families = (brand.get("type") or {}).get("families") or []

    # A brand whose system already lives on a site can bring its own template (meta.template, relative to
    # brand.json). It keeps the two placeholders and the render contract in references/data.md, section 9.
    custom = meta.get("template")
    book_path = root / custom if custom else SKILL / "assets" / "book-template.html"
    if not book_path.is_file():
        fail(f"meta.template: file not found: {book_path}", 2)
    book_tpl = book_path.read_text(encoding="utf-8")
    for mark in ("/*__FONT_FACES__*/", "/*__BRAND_DATA__*/"):
        if mark not in book_tpl:
            fail(f"{book_path.name} has no {mark} placeholder; the build would ship a book without data or fonts")
    label_tpl = (SKILL / "assets" / "label-template.html").read_text(encoding="utf-8")

    outputs = {}
    # References are internal: they never reach the book, not even its source.
    book_data = {k: v for k, v in brand.items() if k != "references"}
    book_data["_base"] = "../"
    outputs["book/index.html"] = (
        book_tpl.replace("/*__FONT_FACES__*/", font_faces(families, "../")).replace("/*__BRAND_DATA__*/", embed(book_data))
    )
    shared = {
        "name": meta["name"],
        "language": meta.get("language", "pl"),
        "colours": brand.get("colours"),
        "families": families,
        "logo_variants": (brand.get("logo") or {}).get("variants") or [],
    }
    for label in brand.get("labels") or []:
        lid = str(label.get("id", ""))
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]*", lid):
            fail(f"label id {lid!r}: use lowercase letters, digits and hyphens (it becomes a file name)")
        data = {"label": label, "brand": shared, "_base": "../"}
        outputs[f"labels/{lid}.html"] = (
            label_tpl.replace("/*__FONT_FACES__*/", font_faces(families, "../")).replace("/*__LABEL_DATA__*/", embed(data))
        )
    outputs["tokens.css"] = tokens_css(brand, families)

    record_path = root / ".build.json"
    record = json.loads(record_path.read_text(encoding="utf-8")) if record_path.is_file() else {}
    edited = []
    for rel in outputs:
        target = root / rel
        if not target.is_file():
            continue
        current = hashlib.sha256(target.read_bytes()).hexdigest()
        if record.get(rel) != current:
            edited.append(rel)
    if edited and not force:
        fail(
            "these files were changed after the last build (or weren't built by this script): "
            + ", ".join(edited)
            + ". Put the change into brand.json and rebuild, or pass --force to overwrite."
        )
    for rel, text in outputs.items():
        target = root / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(text, encoding="utf-8")
        record[rel] = hashlib.sha256(target.read_bytes()).hexdigest()
    record_path.write_text(json.dumps(record, indent=1, sort_keys=True), encoding="utf-8")
    labels = len(brand.get("labels") or [])
    print(f"Built: book/index.html, {labels} {'label' if labels == 1 else 'labels'}, tokens.css in {root}/.")


if __name__ == "__main__":
    main()
