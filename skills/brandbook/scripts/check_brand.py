#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
# © 2026 Design House (https://designhouse.me)
"""Checks brand.json (and the built book next to it) before anything is shown or sent.

Usage: python3 check_brand.py [brand/brand.json]

Colours: valid HEX, CMYK with a named profile and a status (proposed, converted, proofed; proofed
needs a date or source), Pantone either given or a decision with a person and a date. Contrast of the
declared pairs and of body text on the background (WCAG 2.2). Model-default palettes (warning).
Logo: files exist, clear space defined by a part of the mark (not mm or px), minimum size in px and mm.
Type: one or two families, each with a reason, licence file, office substitute; Polish letters in TTF
and OTF files (WOFF2 is measured by render.mjs check); typefaces from the reflex list need a reason.
Labels: mandatory content by category (food, supplement, cosmetic), net quantity on the front, zones
inside the format, claims only with a register reference, a valid EAN-13 when given, placeholders
listed. References never named outside the internal list. Files, decisions, em dashes, a stale build.
Text: where the current version lives, the quick reference rules, audience and alternatives, proof with a
source and a date, 3–8 situations, the description in one and fifty words; field names, build files and
tools in text the client reads (errors), the agency named outside the cover (warning).

Standard library only, no network. Exit code: 0 when there are no errors, 1 when there are errors,
2 when brand.json is missing or not valid JSON.
"""
import hashlib
import json
import re
import struct
import sys
from pathlib import Path

errors, warnings = [], []
REQUIRED = {  # keep in sync with REQUIRED in assets/book-template.html
    "food": ["ingredients", "best_before", "storage", "operator", "lot"],
    "supplement": ["ingredients", "best_before", "storage", "operator", "lot", "nutrient_categories", "daily_dose",
                   "dose_warning", "diet_statement", "children_warning", "amounts_per_dose"],
    "cosmetic": ["responsible_person", "nominal_content", "durability_or_pao", "precautions", "batch", "function",
                 "ingredients_inci"],
}
ROLES = {"background", "text", "secondary-text", "accent", "line", "support"}
STATUSES = {"proposed", "converted", "proofed"}
# references/type.md, section 1: fine typefaces that models reach for without a reason.
REFLEX = {
    "inter", "roboto", "open sans", "lato", "montserrat", "poppins", "nunito", "raleway", "work sans", "geist",
    "space grotesk", "dm sans", "manrope", "plus jakarta sans", "outfit", "sora", "urbanist", "figtree", "lexend",
    "satoshi", "general sans", "cabinet grotesk", "clash display", "bricolage grotesque", "syne", "unbounded",
    "pp neue montreal", "bebas neue", "anton", "oswald", "fraunces", "instrument serif", "playfair display",
    "cormorant", "dm serif display", "lora", "pp editorial new", "jetbrains mono", "ibm plex mono", "space mono",
    "geist mono", "fira code",
}
PL_LETTERS = "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ"
PLACEHOLDER = re.compile(r"\b(x{2,}|X{2,}|TBD|TODO|DO USTALENIA|lorem ipsum|\?\?+)\b|xx\.", re.I)
# The build showing through in text the client reads: field names, data paths, the skill's own files.
PROCESS = re.compile(r"\b[a-z]+(?:_[a-z0-9]+)+\b|\b(?:meta|strategy|voice|logo|colours|imagery|labels|print|decisions|sections|quickref)"
                     r"\.(?!(?:png|svg|jpe?g|pdf|ttf|otf|woff2?|webp|css|html)\b)[a-z_]+"
                     r"|brand\.json|build_book|check_brand|render\.mjs|\?reader=|\b0[0-2]-(?:input|verify|system)\b")
TOOLS = re.compile(r"\b(OpenAI|ImageGen|gpt-image|DALL[·-]?E|Midjourney|Stable Diffusion|Codex|ChatGPT|Gemini|Firefly|Ideogram)\b", re.I)
# Data that is never shown as prose: ids, files, positions, internal lists.
TECHNICAL = ("references", "files", "pairs", "colours", "type.families", "logo.variants")
TECH_KEYS = {"id", "file", "path", "image", "detail", "thumb", "card", "photo", "licence_file", "template", "pos", "pos_detail",
             "background", "colour", "on", "role", "kind", "slot", "demo", "category", "key", "level", "icon", "family",
             "fallback", "status", "profile", "logo_on", "text_colour", "headline_at", "hero_on", "cover_colour", "language", "date", "by"}


def error(msg):
    errors.append(msg)
    print(f"ERROR: {msg}")


def warn(msg):
    warnings.append(msg)
    print(f"WARNING: {msg}")


def rgb(hex_):
    h = hex_.lstrip("#")
    return [int(h[i:i + 2], 16) for i in (0, 2, 4)]


def lum(hex_):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = rgb(hex_)
    return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b)


def contrast(a, b):
    x, y = sorted([lum(a), lum(b)], reverse=True)
    return (x + 0.05) / (y + 0.05)


def near(hex_, target, tol=40):
    return sum((p - q) ** 2 for p, q in zip(rgb(hex_), rgb(target))) ** 0.5 < tol


def strings(node, path=""):
    """Every string in the data with its path, for placeholder, dash and leak checks."""
    if isinstance(node, dict):
        for k, v in node.items():
            yield from strings(v, f"{path}.{k}" if path else k)
    elif isinstance(node, list):
        for i, v in enumerate(node):
            yield from strings(v, f"{path}[{i}]")
    elif isinstance(node, str):
        yield path, node


def cmap_codepoints(font_path):
    """Code points in a TTF/OTF cmap (formats 4 and 12). None when the file can't be read this way."""
    data = font_path.read_bytes()
    if data[:4] not in (b"\x00\x01\x00\x00", b"OTTO", b"true"):
        return None
    num = struct.unpack(">H", data[4:6])[0]
    tables = {data[12 + 16 * i:16 + 16 * i]: struct.unpack(">II", data[20 + 16 * i:28 + 16 * i]) for i in range(num)}
    if b"cmap" not in tables:
        return None
    base = tables[b"cmap"][0]
    count = struct.unpack(">H", data[base + 2:base + 4])[0]
    points = set()
    for i in range(count):
        offset = struct.unpack(">I", data[base + 8 + 8 * i:base + 12 + 8 * i])[0]
        sub = base + offset
        fmt = struct.unpack(">H", data[sub:sub + 2])[0]
        if fmt == 4:
            segs = struct.unpack(">H", data[sub + 6:sub + 8])[0] // 2
            ends = struct.unpack(f">{segs}H", data[sub + 14:sub + 14 + 2 * segs])
            starts = struct.unpack(f">{segs}H", data[sub + 16 + 2 * segs:sub + 16 + 4 * segs])
            for s, e in zip(starts, ends):
                points.update(range(s, e + 1))
        elif fmt == 12:
            groups = struct.unpack(">I", data[sub + 12:sub + 16])[0]
            for g in range(groups):
                s, e, _ = struct.unpack(">III", data[sub + 16 + 12 * g:sub + 28 + 12 * g])
                points.update(range(s, e + 1))
    return points


def ean13_ok(code):
    if not re.fullmatch(r"\d{13}", code):
        return False
    digits = [int(c) for c in code]
    return (10 - sum(d * (3 if i % 2 else 1) for i, d in enumerate(digits[:12])) % 10) % 10 == digits[12]


def check(brand, root):
    meta = brand.get("meta") or {}
    for key in ("name", "version", "date", "owner"):
        if not meta.get(key):
            error(f"meta.{key} is missing")
    if meta.get("date") and not re.fullmatch(r"\d{4}-\d{2}-\d{2}", str(meta["date"])):
        warn(f"meta.date {meta['date']!r}: use YYYY-MM-DD")
    if not meta.get("name_confirmed"):
        warn(f"the spelling of the name {meta.get('name')!r} is not confirmed (meta.name_confirmed); ask in the first message")
    lang = meta.get("language", "pl")

    sections = brand.get("sections") or {}
    purpose = str((brand.get("strategy") or {}).get("purpose", "")).strip().rstrip(".").lower()
    if purpose and str(sections.get("strategy", "")).strip().rstrip(".").lower() == purpose:
        warn("sections.strategy repeats strategy.purpose, so the purpose shows three times (cover, headline, lead); write the strategy headline as a different rule")
    if brand.get("labels") and not meta.get("label_approver"):
        warn("meta.label_approver is missing: name who approves labels before print; if nobody is named yet, write \"(do wskazania)\" and ask in the reply")
    present = {"strategy": brand.get("strategy"), "voice": brand.get("voice"), "applications": brand.get("applications"),
               "logo": brand.get("logo"), "colour": brand.get("colours"), "type": brand.get("type"),
               "imagery": brand.get("imagery"), "labels": brand.get("labels"), "print": brand.get("print"),
               "files": brand.get("files"), "decisions": brand.get("decisions")}
    for sid, data in present.items():
        if data and not sections.get(sid):
            warn(f"sections.{sid}: no headline; write the rule as a statement (\"The variant changes the colour, not the layout\"), not the topic")
    if not meta.get("home"):
        warn("meta.home is missing: say where the current version of the book and the files lives (a link or a shared folder); a book nobody can find goes unused")
    rules = (brand.get("quickref") or {}).get("rules") or []
    if not rules:
        warn("quickref.rules is missing: the quick reference falls back to the section headlines; write up to five rules someone needs on the first day")
    elif len(rules) > 5:
        warn(f"quickref.rules has {len(rules)} rules; the quick reference shows five")

    # strategy and voice: the text people copy
    strategy, voice = brand.get("strategy") or {}, brand.get("voice") or {}
    if strategy:
        if not strategy.get("audience"):
            warn("strategy.audience is missing: whom the brand serves best, in their situation")
        if not strategy.get("instead_of") and not strategy.get("alternatives"):
            warn("strategy.instead_of (or alternatives) is missing: what the customer would do without the brand; positioning starts there")
        for i, p in enumerate(strategy.get("proof") or []):
            if isinstance(p, str):
                warn(f"strategy.proof[{i}] is a plain string; give {{fact, source, date}} so the number can be checked and refreshed: {p[:50]!r}")
            elif not (p.get("source") and p.get("date")):
                warn(f"strategy.proof[{i}] has no source or date: {str(p.get('fact', ''))[:50]!r}")
    if voice:
        situations = voice.get("situations") or []
        if len(situations) < 3:
            warn(f"voice.situations has {len(situations)}; write 3–8 moments from the brand's real work (an enquiry, a quote, a refusal, a complaint), each with the line the brand writes and the one it doesn't")
        for i, s in enumerate(situations):
            for key in ("moment", "example"):
                if not s.get(key):
                    warn(f"voice.situations[{i}].{key} is missing")
        bp = voice.get("boilerplate") or {}
        if not (bp.get("line") and bp.get("short")):
            warn("voice.boilerplate needs line (one sentence) and short (about fifty words): the description people paste into a profile, a listing or an offer")
        else:
            n1, n2 = len(bp["line"].split()), len(bp["short"].split())
            if n1 > 30:
                warn(f"voice.boilerplate.line has {n1} words; one sentence of up to about 25")
            if not 30 <= n2 <= 80:
                warn(f"voice.boilerplate.short has {n2} words; about fifty")
        for i, f in enumerate(voice.get("fixed_lines") or []):
            if not (f.get("text") and f.get("where")):
                warn(f"voice.fixed_lines[{i}] needs text and where")

    # colours
    colours = brand.get("colours") or []
    ids = [c.get("id") for c in colours]
    by_id = {c.get("id"): c for c in colours}
    if len(ids) != len(set(ids)):
        error("colour ids repeat")
    for c in colours:
        cid = c.get("id")
        if not re.fullmatch(r"#[0-9a-fA-F]{6}", str(c.get("hex", ""))):
            error(f"colour {cid}: hex {c.get('hex')!r} is not #RRGGBB")
            continue
        if c.get("role") not in ROLES:
            error(f"colour {cid}: role {c.get('role')!r}, expected one of {', '.join(sorted(ROLES))}")
        cm = c.get("cmyk") or {}
        if not cm.get("value") or len(cm["value"]) != 4 or not all(0 <= float(v) <= 100 for v in cm["value"]):
            error(f"colour {cid}: CMYK missing or not four values 0–100")
        if not cm.get("profile"):
            error(f"colour {cid}: CMYK without a profile (FOGRA39, FOGRA51, FOGRA52…); the same numbers print differently on different paper")
        if cm.get("status") not in STATUSES:
            error(f"colour {cid}: CMYK status {cm.get('status')!r}, expected proposed, converted or proofed")
        if cm.get("status") == "proofed" and not (cm.get("date") or cm.get("source")):
            error(f"colour {cid}: CMYK marked proofed without a date or source of the proof")
        pt = c.get("pantone") or {}
        if not (pt.get("c") or pt.get("u")):
            if not any("pantone" in str(d.get("what", "")).lower() for d in brand.get("decisions") or []):
                warn(f"colour {cid}: no Pantone and no decision about it; add a decision with a person and a date, or the value")
    roles = {c.get("role") for c in colours}
    for need in ("background", "text"):
        if need not in roles:
            error(f"no colour with the role {need}")
    hexes = [c["hex"] for c in colours if re.fullmatch(r"#[0-9a-fA-F]{6}", str(c.get("hex", "")))]
    if any(near(x, "#F4F1EA", 30) for x in hexes) and any(near(x, "#D97757", 45) for x in hexes):
        warn("the palette is close to the model default (warm cream with a terracotta accent); keep it only with a reason from the brand, recorded in 02-system.md (not in the book: the client doesn't need the model's defaults)")
    bg_dark = [x for x in hexes if lum(x) < 0.02]
    acid = [x for x in hexes if max(rgb(x)) > 200 and (max(rgb(x)) - min(rgb(x))) > 150 and lum(x) > 0.5]
    if bg_dark and acid:
        warn("the palette is close to the model default (near-black with one acid accent); keep it only with a reason from the brand, recorded in 02-system.md")

    pairs = brand.get("pairs") or []
    if not pairs:
        warn("no pairs declared; name at least the body text pair (text on background)")
    for p in pairs:
        t, b = by_id.get(p.get("text")), by_id.get(p.get("background"))
        if not t or not b:
            error(f"pair {p.get('text')}/{p.get('background')}: unknown colour id")
            continue
        r = contrast(t["hex"], b["hex"])
        if r < 3:
            error(f"pair {t['name']} on {b['name']} ({p.get('use', '')}): contrast {r:.1f}:1, below 3:1 even for large text")
        elif r < 4.5:
            warn(f"pair {t['name']} on {b['name']} ({p.get('use', '')}): contrast {r:.1f}:1, large text only (18 pt, or 14 pt bold)")
    text = next((c for c in colours if c.get("role") == "text"), None)
    bgc = next((c for c in colours if c.get("role") == "background"), None)
    if text and bgc and re.fullmatch(r"#[0-9a-fA-F]{6}", text["hex"]) and re.fullmatch(r"#[0-9a-fA-F]{6}", bgc["hex"]):
        r = contrast(text["hex"], bgc["hex"])
        if r < 4.5:
            error(f"body text ({text['name']} on {bgc['name']}) has a contrast of {r:.1f}:1, needs 4.5:1 (WCAG 2.2)")

    # logo
    logo = brand.get("logo") or {}
    variants = logo.get("variants") or []
    if not variants:
        error("logo.variants is empty; without a logo file, set the name in the display typeface as a wordmark and say so")
    for v in variants:
        f = root / str(v.get("file", ""))
        if not f.is_file():
            error(f"logo {v.get('id')}: file not found: {v.get('file')}")
        if not (isinstance(v.get("min_px"), (int, float)) and v["min_px"] > 0 and isinstance(v.get("min_mm"), (int, float)) and v["min_mm"] > 0):
            error(f"logo {v.get('id')}: minimum size needs both min_px (screen) and min_mm (print)")
        for on in v.get("on") or []:
            if on not in by_id:
                error(f"logo {v.get('id')}: background {on!r} is not a colour id")
    cs = logo.get("clear_space") or {}
    if not cs.get("defined_as") or not isinstance(cs.get("ratio"), (int, float)) or not 0 < cs["ratio"] <= 2:
        error("logo.clear_space needs defined_as (a part of the mark, e.g. the height of the letter O) and ratio (share of the logo height)")
    elif re.search(r"\d\s*(mm|px)\b", str(cs.get("defined_as"))):
        error("logo.clear_space is given in mm or px; define it by a part of the mark, so it scales with the logo")
    if variants and len(logo.get("dont") or []) < 3:
        warn("fewer than 3 logo don'ts; show the common ones (stretch, rotate, shadow, busy background)")

    # type
    families = (brand.get("type") or {}).get("families") or []
    if not families:
        error("type.families is empty")
    if len(families) > 2:
        warn(f"{len(families)} typeface families; one or two that differ in structure are enough")
    for fam in families:
        name = fam.get("family", "?")
        for key in ("role", "why", "licence", "office_substitute"):
            if not fam.get(key):
                error(f"typeface {name}: {key} is missing")
        if fam.get("why") and len(fam["why"]) < 20:
            warn(f"typeface {name}: the reason is one or two words; say why it fits this brand")
        lic = fam.get("licence_file")
        if not lic or not (root / lic).is_file():
            error(f"typeface {name}: licence file not found ({lic}); keep the licence next to the fonts")
        if name.lower() in REFLEX and not fam.get("reflex_reason"):
            warn(f"typeface {name} is on the reflex list (references/type.md); keep it only with reflex_reason (the brand's or client's font, a tested reason)")
        for entry in fam.get("files") or []:
            path = root / (entry["file"] if isinstance(entry, dict) else entry)
            if not path.is_file():
                error(f"typeface {name}: font file not found: {path.relative_to(root)}")
                continue
            if lang == "pl" and path.suffix.lower() in (".ttf", ".otf"):
                points = cmap_codepoints(path)
                if points is not None:
                    missing = [ch for ch in PL_LETTERS if ord(ch) not in points]
                    if missing:
                        error(f"typeface {name} ({path.name}) has no glyphs for: {' '.join(missing)}")

    # imagery
    imagery = brand.get("imagery") or {}
    ai = imagery.get("ai") or {}
    for img in imagery.get("images") or []:
        if not (root / str(img.get("file", ""))).is_file():
            error(f"image not found: {img.get('file')}")
        if img.get("generated") and not (img.get("caption") or ai.get("label")):
            error(f"generated image {img.get('file')} has no caption; label it (e.g. \"Wizualizacja\")")
    for w in imagery.get("worlds") or []:
        for key in ("image", "detail"):
            if w.get(key) and not (root / str(w[key])).is_file():
                error(f"world {w.get('name')}: {key} not found: {w[key]}")
        if w.get("colour") and w["colour"] not in by_id:
            error(f"world {w.get('name')}: colour {w['colour']!r} is not a colour id")
    for a in brand.get("applications") or []:
        if a.get("image") and not (root / str(a["image"])).is_file():
            error(f"application {a.get('id')}: image not found: {a['image']}")
        if a.get("kind") == "billboard" and not a.get("image"):
            error(f"application {a.get('id')}: a billboard needs an image")
    for l in brand.get("labels") or []:
        if l.get("image") and not (root / str(l["image"])).is_file():
            error(f"label {l.get('id')}: image not found: {l['image']}")
    tagline = str((brand.get("strategy") or {}).get("tagline", ""))
    if not tagline:
        warn("strategy.tagline is missing; the cover and the closing slide show only the name")
    elif len(tagline) > 60:
        warn(f"strategy.tagline has {len(tagline)} characters; the cover sets it large, keep it under about 35")
    if not imagery.get("images") and not imagery.get("worlds") and not any(l.get("image") for l in brand.get("labels") or []):
        warn("no photographs at all: the deck falls back to colour and type. Ask the client for photos or generate visualisations; look for an image tool first, e.g. Codex (references/images.md, section 6)")
    if any(i.get("generated") for i in imagery.get("images") or []) and not ai:
        error("the book uses generated images but imagery.ai (allowed, banned, label, approver) is missing")
    for key in ("light", "composition", "casting", "props", "styling", "grading"):
        if imagery and not imagery.get(key):
            warn(f"imagery.{key} is missing; a photographer needs all six: light, composition, people, props, styling, grading")

    # labels
    claims = list((brand.get("voice") or {}).get("claims") or [])
    for label in brand.get("labels") or []:
        lid = label.get("id", "?")
        cat = label.get("category")
        fmt = label.get("format") or {}
        claims += label.get("claims") or []
        if cat not in (*REQUIRED, "other"):
            error(f"label {lid}: category {cat!r}, expected food, supplement, cosmetic or other")
        for key in ("w_mm", "h_mm", "bleed_mm", "safe_mm"):
            if not isinstance(fmt.get(key), (int, float)):
                error(f"label {lid}: format.{key} is missing")
        if cat in ("food", "supplement") and not isinstance(fmt.get("largest_surface_cm2"), (int, float)):
            warn(f"label {lid}: format.largest_surface_cm2 is missing; it decides between 1.2 and 0.9 mm x-height")
        w = fmt.get("w_mm") or 0
        for z in label.get("zones") or []:
            if z.get("role") not in ("front", "info", "legal"):
                error(f"label {lid}: zone {z.get('id')} has the role {z.get('role')!r}; use front, info or legal (an overlap is format.overlap_mm, not a zone)")
            if z.get("x_mm", 0) < 0 or z.get("x_mm", 0) + z.get("w_mm", 0) > w + 0.01:
                error(f"label {lid}: zone {z.get('id')} lies outside the {w} mm width")
        if fmt.get("overlap_mm") is not None:
            if not isinstance(fmt["overlap_mm"], (int, float)) or fmt["overlap_mm"] < 0 or fmt.get("overlap_side") not in ("left", "right"):
                error(f"label {lid}: overlap_mm needs a number and overlap_side left or right")
        elif len(label.get("zones") or []) > 2:
            warn(f"label {lid}: looks like a wrap-around label but has no overlap_mm; ask the printer which end is covered and by how much")
        front = label.get("front") or {}
        if not front.get("name"):
            error(f"label {lid}: front.name is missing")
        if cat in ("food", "supplement") and not front.get("net"):
            error(f"label {lid}: no net quantity on the front; it must be in the same field of vision as the name (1169/2011, art. 13)")
        keys = {x.get("key") for x in label.get("legal") or [] if str(x.get("text", "")).strip()}
        missing = [k for k in REQUIRED.get(cat, []) if k not in keys]
        if missing:
            error(f"label {lid}: mandatory content missing for {cat}: {', '.join(missing)}")
        if cat == "food" and "nutrition" not in keys and not label.get("nutrition_exempt_reason"):
            error(f"label {lid}: no nutrition declaration (key nutrition) and no nutrition_exempt_reason")
        ean = (label.get("barcode") or {}).get("ean")
        if ean and not ean13_ok(str(ean)):
            error(f"label {lid}: EAN {ean} is not a valid EAN-13 (check digit)")
        if label.get("legal_pt") and label["legal_pt"] < 6:
            warn(f"label {lid}: legal_pt {label['legal_pt']} is very small; render.mjs check measures the x-height")
        if label.get("colour") and label["colour"] not in by_id:
            error(f"label {lid}: colour {label['colour']!r} is not a colour id")
        elif label.get("colour") and variants and not any(label["colour"] in (v.get("on") or []) for v in variants):
            warn(f"label {lid}: no logo variant lists the label colour {label['colour']!r} in `on`; check the logo is legible on it")
        for path, value in strings(label):
            if PLACEHOLDER.search(value):
                warn(f"label {lid}: placeholder in {path}: {value!r}; fine in a template, but list it in 01-verify.md")
    for c in claims:
        if not c.get("register_ref"):
            error(f"claim {c.get('text')!r} has no register_ref; health and nutrition claims only in the wording of the EU register, checked by the regulatory person")

    # print, files, decisions, references
    pr = brand.get("print") or {}
    if brand.get("labels") and not pr:
        error("labels without a print section (profile, PDF standard, bleed)")
    for key in ("profile", "pdf", "bleed_mm"):
        if pr and pr.get(key) in (None, ""):
            error(f"print.{key} is missing")
    if pr and not pr.get("printer"):
        warn("no printer chosen: the profile, bleed and finishes are defaults to confirm with them")
    for fin in pr.get("finishes") or []:
        if not fin.get("layer"):
            warn(f"finish {fin.get('type')}: no layer name; finishes go on separate named spot layers")
    for f in brand.get("files") or []:
        rel = str(f.get("path", ""))
        if not (root / rel).exists():
            # Built and rendered files appear after build_book.py and render.mjs; anything else is missing.
            if rel == "tokens.css" or rel.split("/")[0] in ("book", "labels", "out"):
                warn(f"{rel} is listed but not built or rendered yet; run build_book.py and render.mjs, then check again")
            else:
                error(f"file listed but not found: {rel}")
    decisions = brand.get("decisions") or []
    for d in decisions:
        if not d.get("who") or not d.get("by"):
            warn(f"decision {d.get('what')!r} has no person or date")
    if len(decisions) > 6 and not any(d.get("blocks") for d in decisions):
        warn(f"{len(decisions)} decisions and none marked blocks: the book shows the first six and counts the rest; mark the ones that stop someone using the book")
    made_by = str(meta.get("made_by") or "").strip().lower()
    for path, value in strings({k: v for k, v in brand.items() if k != "references"}):
        leaf = re.sub(r"\[\d+\]", "", path).split(".")[-1]
        if path.startswith(TECHNICAL) or leaf in TECH_KEYS or re.fullmatch(r"[\w./:@?=&%#-]+", value) and ("/" in value or "." in value):
            continue
        m = PROCESS.search(value)
        if m:
            error(f"{path} shows the build to the client ({m.group(0)!r}); write it for the reader and keep field names, files and notes in 01-verify.md or 02-system.md")
        t = TOOLS.search(value)
        if t:
            warn(f"{path} names a tool ({t.group(0)!r}); generated images are marked with imagery.ai.label, the tool stays in prompts/")
        if made_by and made_by in value.lower() and not path.startswith("meta.") and not path.endswith(".who"):
            warn(f"{path} names {meta.get('made_by')}: the book speaks for the brand, the agency signs the cover")
    ref_names = [r.get("name") for r in brand.get("references") or [] if r.get("name")]
    for path, value in strings({k: v for k, v in brand.items() if k != "references"}):
        for n in ref_names:
            if n.lower() in value.lower():
                error(f"the reference {n!r} is named in {path}; references stay internal")
        if "—" in value:
            warn(f"em dash in {path}; use a comma, colon or full stop")
        if not path.startswith(("voice.words_avoid", "imagery.dont", "imagery.ai.banned", "strategy.rejected")) and re.search(r"\b(eko|bio|ekologiczn\w*|organic|organiczn\w*)\b", value, re.I):
            warn(f"{path} uses an organic term ({value[:50]!r}); eko, bio and ekologiczny are protected for certified products (Regulation (EU) 2018/848)")
    if not brand.get("changelog"):
        warn("no changelog; the book needs a version history")

    # the built book
    book = root / "book" / "index.html"
    record = root / ".build.json"
    src = root / "brand.json"
    if not book.is_file():
        warn("book/index.html not built yet: python3 build_book.py brand/brand.json")
    else:
        if src.is_file() and src.stat().st_mtime > book.stat().st_mtime + 1:
            warn("brand.json is newer than the book; rebuild")
        if record.is_file():
            rec = json.loads(record.read_text(encoding="utf-8"))
            if rec.get("book/index.html") != hashlib.sha256(book.read_bytes()).hexdigest():
                warn("book/index.html was edited by hand after the build; move the change into brand.json")
        html = book.read_text(encoding="utf-8")
        for n in ref_names:
            if n.lower() in html.lower():
                error(f"the reference {n!r} appears in the built book; rebuild with the current build_book.py")


def main():
    src = Path(sys.argv[1] if len(sys.argv) > 1 else "brand/brand.json")
    if not src.is_file():
        print(f"ERROR: file not found: {src}")
        sys.exit(2)
    try:
        brand = json.loads(src.read_text(encoding="utf-8"))
    except json.JSONDecodeError as e:
        print(f"ERROR: {src} is not valid JSON: {e}")
        sys.exit(2)
    check(brand, src.parent)
    e, w = len(errors), len(warnings)
    print(f"Checked: {src}. Result: {e} {'error' if e == 1 else 'errors'}, {w} {'warning' if w == 1 else 'warnings'}.")
    sys.exit(1 if errors else 0)


if __name__ == "__main__":
    main()
