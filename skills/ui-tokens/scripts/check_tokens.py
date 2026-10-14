#!/usr/bin/env python3
# SPDX-License-Identifier: CC-BY-4.0
# © 2026 Design House (https://designhouse.me)
"""Finds spacing, font-size, colour and radius values that bypass the project's tokens.

Usage:
  python3 check_tokens.py [PATH ...] [--root DIR] [--tokens FILE ...] [--changed | --since REF] [--allow PREFIX ...]
                          [--json]
  python3 check_tokens.py --system [PATH ...]   the declared tokens per family and the literals in use; run it first
  python3 check_tokens.py --hook                Claude Code PostToolUse: reads the hook JSON on stdin

PATH       files or folders to check (default: the root).
--root     where declarations are collected from (default: the first PATH when it is a folder, else the git
           top level, else the current folder).
--tokens   token files: every value in them is allowed. Without it: files named tokens, variables, vars or
           theme (.css .scss .less), plus custom properties declared in :root, html, :host, @theme, .dark,
           .light and [data-theme] blocks anywhere.
--changed  only lines added since the last commit must pass; untracked files count whole. Findings on older
           lines become one REPORT line, so legacy code isn't rewritten unasked.
--since    the same against REF (a branch, a tag, a commit), e.g. --since main.
--allow    a custom-property prefix that comes from a library (e.g. --allow --brand-). Repeatable.
--json     the findings as JSON, for evals.

Levels:
  ERROR      a literal length in margin, padding or gap, a literal font-size, colour or border-radius outside
             the token layer; var() of a property declared nowhere; the same through a local custom property;
             a Tailwind arbitrary value for those families; a Tailwind step the theme removed.
             Fix it: the suggested token, or a new token with a role name in the token file.
  WARNING    a custom property holding a literal outside the token layer; a literal offset (top, left, inset);
             a font-size in em or %; a line-height with a unit; % padding; var() of an undeclared property
             with a fallback. Fix it or say why not.
  CANDIDATE  a Tailwind multiplier off the default steps (p-13); token arithmetic with an odd factor.
             Give each one a decision.
  REPORT     tokens declared, literals in use, unique font sizes, findings left on unchanged lines.

Out of scope: widths and heights, letter-spacing, border widths, SVG attributes, values computed in JS,
Tailwind v3 config files. Line based heuristics, standard library only, no network.
Exit code: 0 when there are no errors, 1 when there are errors, 2 when a path is missing.
--hook exits 2 with the errors on stderr, so Claude sees them after the edit, and 0 otherwise.
"""
import argparse
import bisect
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

EXT_CSS = {".css", ".scss", ".less"}
EXT_MARKUP = {".html", ".htm", ".vue", ".svelte", ".astro"}
EXT_JS = {".js", ".jsx", ".ts", ".tsx", ".mjs", ".cjs"}
EXTS = EXT_CSS | EXT_MARKUP | EXT_JS
SKIP_DIRS = {"node_modules", ".git", "dist", "build", "out", ".next", ".nuxt", ".svelte-kit", ".astro", ".output",
             "coverage", "vendor", ".turbo", ".cache", ".vercel", "__pycache__", ".venv", "venv", ".claude"}
MAX_BYTES = 1_000_000

TOKEN_FILE = re.compile(r"(?:^|[/_.-])(?:tokens?|design-tokens|variables|vars|theme)\.(?:css|scss|less)$", re.I)
TOKEN_SEL = re.compile(r"^(?:@theme\b|:root\b|html\b|:host\b|\.(?:dark|light)\b)|\[data-(?:theme|mode|color-scheme)", re.I)
ROOT_SEL = re.compile(r"^(?::root|html)$", re.I)
LIB_PREFIXES = ("--tw-", "--radix-", "--chakra-", "--mantine-", "--bs-", "--wp--", "--swiper-", "--fa-",
                "--vp-", "--docsearch-", "--sl-", "--rdp-", "--toastify-")
TW4_DEFAULTS = ("spacing", "text", "font", "color", "radius", "shadow", "inset-shadow", "drop-shadow",
                "text-shadow", "blur", "perspective", "aspect", "ease", "animate", "breakpoint", "container",
                "leading", "tracking", "default")
TW_STEPS = {"0", "0.5", "1", "1.5", "2", "2.5", "3", "3.5", "4", "5", "6", "7", "8", "9", "10", "11", "12", "14",
            "16", "20", "24", "28", "32", "36", "40", "44", "48", "52", "56", "60", "64", "72", "80", "96"}
TW_TEXT = {"xs", "sm", "base", "lg", "xl", "2xl", "3xl", "4xl", "5xl", "6xl", "7xl", "8xl", "9xl"}
SCALE_WORDS = TW_TEXT | {"2xs", "3xs", "md", "none"}
TW_TEXT_PX = {"xs": 12, "sm": 14, "base": 16, "lg": 18, "xl": 20, "2xl": 24, "3xl": 30, "4xl": 36, "5xl": 48,
              "6xl": 60, "7xl": 72, "8xl": 96, "9xl": 128}

UNITS = r"px|rem|em|vh|vw|vmin|vmax|svh|lvh|dvh|svw|lvw|dvw|ch|ex|lh|rlh|pt|pc|cm|mm|in|cqw|cqh|cqi|cqb|cqmin|cqmax"
LEN = re.compile(rf"(?<![\w.#-])(-?(?:\d+\.?\d*|\.\d+))({UNITS})\b", re.I)
PCT = re.compile(r"(?<![\w.#-])(-?(?:\d+\.?\d*|\.\d+))%")
HEX = re.compile(r"(?<![\w&$])#(?:[0-9a-fA-F]{8}|[0-9a-fA-F]{6}|[0-9a-fA-F]{3,4})\b")
COLOR_FN = re.compile(r"\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color)\(", re.I)
VAR = re.compile(r"var\(\s*(--[\w-]+)\s*(,)?")
COLOR_PROP = re.compile(r"color|background|border|outline|fill|stroke|shadow|accent|caret|decoration", re.I)
ODD_FACTOR = re.compile(r"var\(--[\w-]+\)\s*\*\s*(-?\d*\.\d+)|(-?\d*\.\d+)\s*\*\s*var\(--")

TW_SPACE = r"p[xytrblse]?|m[xytrblse]?|gap(?:-[xy])?|space-[xy]|scroll-[mp][xytrblse]?"
TW_OFFSET = r"inset(?:-[xy])?|top|right|bottom|left|start|end"
TW_UTIL = rf"{TW_SPACE}|{TW_OFFSET}|text|leading|rounded(?:-(?:[trblse]|tl|tr|bl|br|ss|se|es|ee))?|bg|border(?:-[xytrblse])?|ring|outline|fill|stroke|decoration|from|via|to|shadow|accent|caret"
TW_ARB = re.compile(rf"(?<![\w\[-])-?({TW_UTIL})-\[([^\]\s]+)\](?!:)")
TW_VARSHORT = re.compile(rf"(?<![\w\[-])-?({TW_UTIL})-\((--[\w-]+)\)")
TW_STEP = re.compile(rf"(?<![\w\[./-])-?({TW_SPACE}|{TW_OFFSET})-(\d+(?:\.\d+)?|[a-z][\w-]*)(?![\w./\[(-])")
TW_TEXTSIZE = re.compile(r"(?<![\w\[./-])text-(xs|sm|base|lg|xl|[2-9]xl)(?![\w./\[(-])")

LEVELS = ("ERROR", "WARNING", "CANDIDATE")


# ---------- reading ----------

def read(path):
    try:
        if path.stat().st_size > MAX_BYTES:
            return None
        return path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return None


def walk(paths):
    for p in paths:
        if p.is_file():
            if p.suffix.lower() in EXTS and ".min." not in p.name:
                yield p
            continue
        for dirpath, dirs, files in os.walk(p):
            dirs[:] = [d for d in dirs if d not in SKIP_DIRS]
            for f in files:
                fp = Path(dirpath) / f
                if fp.suffix.lower() in EXTS and ".min." not in f:
                    yield fp


def git(root, *args):
    try:
        r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, timeout=20)
    except (OSError, subprocess.SubprocessError):
        return None
    return r.stdout if r.returncode == 0 else None


def find_root(start):
    top = git(start, "rev-parse", "--show-toplevel")
    return Path(top.strip()) if top else Path(start)


def changed_lines(root, path, ref):
    """Set of added line numbers since ref, None when every line counts (untracked, or no git)."""
    path = str(Path(path).resolve())
    if git(root, "ls-files", "--error-unmatch", path) is None:
        return None
    out = git(root, "diff", "-U0", "--no-color", "--no-ext-diff", ref, "--", path)
    if out is None:
        return None
    lines = set()
    for m in re.finditer(r"^@@ -\d+(?:,\d+)? \+(\d+)(?:,(\d+))? @@", out, re.M):
        start, count = int(m.group(1)), int(m.group(2) or 1)
        lines.update(range(start, start + count))
    return lines


# ---------- CSS regions and declarations ----------

def fill(chars, a, b):
    for k in range(a, b):
        if chars[k] != "\n":
            chars[k] = " "


def blank(text):
    """Comments, string contents and url() contents to spaces, offsets kept."""
    out, i, n = list(text), 0, len(text)
    while i < n:
        if text[i:i + 4].lower() == "url(" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] in "-_")):
            j = text.find(")", i + 4)
            j = n if j < 0 else j
            fill(out, i + 4, j)
            i = j
        elif text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n if j < 0 else j + 2
            fill(out, i, j)
            i = j
        elif text.startswith("//", i) and (i == 0 or text[i - 1] not in ":\\"):
            j = text.find("\n", i)
            j = n if j < 0 else j
            fill(out, i, j)
            i = j
        elif text[i] in "\"'":
            q, j = text[i], i + 1
            while j < n and text[j] != q and text[j] != "\n":
                j += 2 if text[j] == "\\" else 1
            fill(out, i + 1, min(j, n))
            i = j + 1
        else:
            i += 1
    return "".join(out)


DECL = re.compile(r"\s*(--[\w-]+\*?|\$[\w-]+|-?[a-zA-Z][\w-]*)\s*:(?!:)(.*)$", re.S)


def css_decls(text, base, stack=()):
    """(prop, value, offset, preludes) for each declaration in a CSS region."""
    s = blank(text)
    out, stack = [], list(stack)
    seg, paren, interp = 0, 0, 0

    def take(end):
        m = DECL.match(s[seg:end])
        if m and "{" not in m.group(2):
            value = re.sub(r"!\s*important", "", m.group(2)).strip()
            out.append((m.group(1), value, base + seg + m.start(1), tuple(stack)))

    for i, c in enumerate(s):
        if c == "(":
            paren += 1
        elif c == ")":
            paren = max(0, paren - 1)
        elif c == "{" and i and s[i - 1] == "#":
            interp += 1
        elif c == "}" and interp:
            interp -= 1
        elif paren == 0 and c == "{":
            stack.append(" ".join(s[seg:i].split()))
            seg = i + 1
        elif paren == 0 and c in ";}":
            take(i)
            if c == "}" and stack:
                stack.pop()
            seg = i + 1
    take(len(s))
    return out


def kebab(name):
    return re.sub(r"[A-Z]", lambda m: "-" + m.group(0).lower(), name)


NUMERIC_PX = {"margin", "padding", "gap", "row-gap", "column-gap", "font-size", "border-radius", "top", "right",
              "bottom", "left", "inset"}


def object_decls(body, base):
    """Declarations from a JS style object body such as `padding: 13, fontSize: '15px'`."""
    out = []
    for m in re.finditer(r"""(?:^|[,{\s])(['"]?)(--[\w-]+|[A-Za-z][\w]*)\1\s*:\s*(`[^`]*`|'[^'\n]*'|"[^"\n]*"|-?\d+(?:\.\d+)?)(?=\s*[,}\n]|\s*$)""", body):
        key, raw = m.group(2), m.group(3)
        prop = key if key.startswith("--") else kebab(key)
        if raw[0] in "'\"`":
            value = raw[1:-1]
        elif raw != "0" and (prop in NUMERIC_PX or re.match(r"(margin|padding|border-.*radius|inset)-", prop)):
            value = raw + "px"
        else:
            continue
        out.append((prop, value, base + m.start(2), ()))
    return out


def matching(text, i, open_c="{", close_c="}"):
    depth = 0
    for j in range(i, len(text)):
        if text[j] == open_c:
            depth += 1
        elif text[j] == close_c:
            depth -= 1
            if depth == 0:
                return j
    return len(text)


CSS_IN_JS = re.compile(r"(?:\bstyled(?:\.\w+|\([^)]*\))(?:\.attrs\([^)]*\))?|\bcss|\bcreateGlobalStyle|\binjectGlobal|\bkeyframes)\s*`")


def declarations(path, text):
    ext = path.suffix.lower()
    if ext in EXT_CSS:
        return css_decls(text, 0)
    out = []
    if ext in EXT_MARKUP:
        for m in re.finditer(r"<style\b[^>]*>(.*?)</style>", text, re.S | re.I):
            out += css_decls(m.group(1), m.start(1))
        for m in re.finditer(r"""(?<![:\w-])style\s*=\s*(["'])(.*?)\1""", text, re.S):
            out += css_decls(m.group(2), m.start(2))
        for m in re.finditer(r"""\bstyle:([\w-]+)\s*=\s*(["'])([^"']*)\2""", text):
            out.append((m.group(1), m.group(3), m.start(1), ()))
        for m in re.finditer(r"""(?::|v-bind:)style\s*=\s*"\s*\{""", text):
            start = text.index("{", m.start())
            out += object_decls(text[start + 1:matching(text, start)], start + 1)
    for m in re.finditer(r"\bstyle\s*=\s*\{\s*\{", text):
        start = text.index("{", m.end() - 1)
        out += object_decls(text[start + 1:matching(text, start)], start + 1)
    if ext in EXT_JS or ext in {".vue", ".svelte", ".astro"}:
        for m in CSS_IN_JS.finditer(text):
            end = text.find("`", m.end())
            end = len(text) if end < 0 else end
            body = re.sub(r"\$\{[^}]*\}", lambda x: " " * len(x.group(0)), text[m.end():end])
            out += css_decls(body, m.end())
    return out


# ---------- values ----------

def px(num, unit):
    unit = unit.lower()
    factor = {"px": 1, "rem": 16, "em": 16, "pt": 4 / 3}.get(unit)
    return None if factor is None else float(num) * factor


def fmt(v):
    return f"{v:g}px"


def hex_rgb(h):
    h = h.lstrip("#")
    if len(h) in (3, 4):
        h = "".join(c * 2 for c in h[:3])
    return tuple(int(h[k:k + 2], 16) for k in (0, 2, 4))


def color_literals(value):
    """Hex and colour functions that don't take a var()."""
    found = [m.group(0) for m in HEX.finditer(value)]
    for m in COLOR_FN.finditer(value):
        end = matching(value, m.end() - 1, "(", ")")
        call = value[m.start():end + 1]
        if "var(" not in call:
            found.append(call)
    return found


def is_color(value):
    v = value.strip()
    return bool(HEX.fullmatch(v) or COLOR_FN.match(v) or re.match(r"(?:color-mix|light-dark)\(", v, re.I))


def lengths(value):
    return [(m.group(0), px(m.group(1), m.group(2)), m.group(2).lower()) for m in LEN.finditer(value)]


def family(prop):
    p = prop.lower()
    if re.match(r"(?:margin|padding)(?:-|$)|(?:row-|column-|grid-|grid-row-|grid-column-)?gap$|scroll-(?:margin|padding)", p):
        return "space"
    if re.match(r"inset(?:-|$)|(?:top|right|bottom|left)$", p):
        return "offset"
    if p == "font-size":
        return "font-size"
    if p == "font":
        return "font"
    if p == "line-height":
        return "line-height"
    if re.match(r"border(?:-(?:top|right|bottom|left|start|end|start-start|start-end|end-start|end-end))?-radius$", p):
        return "radius"
    return "other"


def token_family(name, value):
    if is_color(value):
        return "color"
    n = name.lower()
    sized = bool(LEN.search(value)) or value.strip().startswith("clamp(")
    if re.search(r"radius|rounded|corner", n):
        return "radius"
    if re.search(r"shadow|blur|ease|duration|delay|z-?index|opacity|breakpoint|container|width|height|weight|"
                 r"family|tracking|letter|border|stroke|outline|ring", n):
        return "other"
    if re.search(r"leading|line-height", n):
        return "line-height"
    if re.search(r"font|text|type|step|heading|display|body|caption|title|fs\b", n):
        return "font-size" if sized else "other"
    if sized and re.search(r"space|spacing|gap|gutter|pad|margin|inset|stack|^--s-?\d|^--sp-|^--size-", n):
        return "space"
    return "length" if sized else "other"


# ---------- the project ----------

class Project:
    def __init__(self, root, token_files, allow):
        self.root = root
        self.token_files = {p.resolve() for p in token_files}
        self.allow = tuple(allow)
        self.tokens = {}          # name -> (value, file) declared in the token layer
        self.local = {}           # name -> value declared outside it
        self.js_vars = set()      # set from JS: style.setProperty('--x') or {'--x': ...}
        self.tailwind = None      # None, 3 or 4
        self.resets = set()       # Tailwind v4 namespaces reset with --name-*: initial
        self.theme_steps = set()  # --spacing-<step> declared in @theme
        self.theme_text = set()   # --text-<name> declared in @theme

    def is_token_file(self, path):
        return path.resolve() in self.token_files or (not self.token_files and bool(TOKEN_FILE.search(path.name)))

    def collect(self):
        for path in walk([self.root]):
            text = read(path)
            if text is None:
                continue
            if "tailwind" in text:
                if re.search(r"""@import\s+["']tailwindcss""", text):
                    self.tailwind = 4
                elif re.search(r"@tailwind\s+(?:base|utilities)", text) and self.tailwind is None:
                    self.tailwind = 3
            if path.name.startswith("tailwind.config.") and self.tailwind is None:
                self.tailwind = 3
            if "@theme" in text:
                self.tailwind = self.tailwind or 4
                self.resets |= {m.group(1) for m in re.finditer(r"--([\w-]*?)-?\*\s*:\s*initial", text)}
            if "--" not in text:
                continue
            self.js_vars |= set(re.findall(r"""setProperty\(\s*['"](--[\w-]+)""", text))
            if path.suffix.lower() not in EXT_CSS:
                # style="--i: ${i}", style={{'--x': 1}}, class="[--cell:…]": set per element at runtime
                self.js_vars |= set(re.findall(r"(--[\w-]+)['\"]?\s*:", text))
            token_file = self.is_token_file(path)
            for prop, value, _, stack in declarations(path, text):
                if not prop.startswith("--") or prop.endswith("*"):
                    continue
                if token_file or any(TOKEN_SEL.search(p) for p in stack):
                    self.tokens.setdefault(prop, (value, path))
                    if any(p.startswith("@theme") for p in stack):
                        if prop.startswith("--spacing-"):
                            self.theme_steps.add(prop[len("--spacing-"):])
                        elif prop.startswith("--text-") and "--" not in prop[7:]:
                            self.theme_text.add(prop[len("--text-"):])
                else:
                    self.local.setdefault(prop, value)

    def reset(self, ns):
        return "" in self.resets or ns in self.resets

    def known(self, name):
        if name in self.tokens or name in self.local or name in self.js_vars:
            return True
        if name.startswith(LIB_PREFIXES + self.allow):
            return True
        if self.tailwind == 4:
            for ns in TW4_DEFAULTS:
                if (name == f"--{ns}" or name.startswith(f"--{ns}-")) and not self.reset(ns):
                    return True
        return False

    def resolve(self, value, depth=0):
        m = re.fullmatch(r"\s*var\(\s*(--[\w-]+)\s*(?:,[^)]*)?\)\s*", value)
        if m and depth < 6:
            hit = self.tokens.get(m.group(1))
            if hit:
                return self.resolve(hit[0], depth + 1)
        return value.strip()

    def scale(self):
        """family -> [(name, value, px or None)] for the declared tokens."""
        if getattr(self, "_scale", None) is not None:
            return self._scale
        out = defaultdict(list)
        for name, (value, _) in self.tokens.items():
            v = self.resolve(value)
            fam = token_family(name, v)
            m = re.fullmatch(rf"(-?(?:\d+\.?\d*|\.\d+))({UNITS})", v, re.I)
            out[fam].append((name, v, px(m.group(1), m.group(2)) if m else None))
        for fam in out:
            out[fam].sort(key=lambda t: (t[2] is None, t[2] or 0, t[0]))
        self._scale = out
        return out

    def nearest(self, fam, value_px):
        scale = self.scale()
        pool = [t for t in scale.get(fam, []) if t[2] is not None]
        if value_px is None:
            return ""
        if not pool and self.tailwind == 4 and fam == "space" and not self.reset("spacing"):
            near = min(TW_STEPS, key=lambda s: abs(float(s) * 4 - value_px))
            return f"nearest Tailwind step: {near} ({fmt(float(near) * 4)}), calc(var(--spacing) * {near}) in CSS"
        if not pool and self.tailwind == 4 and fam == "font-size" and not self.reset("text"):
            name = min(TW_TEXT_PX, key=lambda k: abs(TW_TEXT_PX[k] - value_px))
            return f"nearest Tailwind size: var(--text-{name}) {fmt(TW_TEXT_PX[name])} (text-{name})"
        if not pool and scale.get(fam):
            return "the scale is fluid; pick by role: " + ", ".join(f"var({n})" for n, _, _ in scale[fam][:8])
        if not pool:
            return ""
        same = [t for t in pool if abs(t[2] - value_px) < 0.01]
        if same:
            return f"use var({same[0][0]}), the same value"
        below = [t for t in pool if t[2] < value_px]
        above = [t for t in pool if t[2] > value_px]
        picks = ([max(below, key=lambda t: t[2])] if below else []) + ([min(above, key=lambda t: t[2])] if above else [])
        return "nearest: " + ", ".join(f"var({n}) {fmt(p)}" for n, _, p in picks)

    def nearest_color(self, literal):
        if not HEX.fullmatch(literal):
            return "use a colour token, or add one with a role name"
        rgb = hex_rgb(literal)
        pool = []
        for name, v, _ in self.scale().get("color", []):
            if HEX.fullmatch(v):
                d = sum((a - b) ** 2 for a, b in zip(rgb, hex_rgb(v))) ** 0.5
                pool.append((d, name, v))
        if not pool:
            return "no colour tokens declared: add this colour to the token file with a role name"
        d, name, v = min(pool)
        if d < 1:
            return f"use var({name}), the same colour"
        if d < 20:
            return f"close to var({name}) {v}: use it unless the difference is intended"
        return f"no token has this colour; closest var({name}) {v}. A new role gets a new token"


# ---------- checks ----------

def finding(level, rule, line, excerpt, note=""):
    return {"level": level, "rule": rule, "line": line, "excerpt": excerpt.strip()[:90], "note": note}


FLUID = {"vw", "vh", "vmin", "vmax", "svh", "lvh", "dvh", "svw", "lvw", "dvw", "cqw", "cqh", "cqi", "cqb", "cqmin",
         "cqmax"}
EMPTY = {"space": "no spacing tokens declared: declare the scale in the token file first",
         "font-size": "no type tokens declared: declare the type scale in the token file first",
         "radius": "no radius tokens declared: add them to the token file"}


def hint(proj, fam, lit, v, unit, value, fallback=None):
    if "clamp(" in value or unit in FLUID:
        return "a fluid value belongs in the token file as clamp() with both ends on the scale"
    if v is None:
        return f"{lit}: use a token"
    near = proj.nearest(fam, v)
    return f"{lit}: {near}" if near else (fallback or EMPTY[fam])


def check_decl(proj, prop, value, line, stack, census):
    found = []
    if prop.startswith("$"):
        prop = "--" + prop[1:]
    in_root = any(ROOT_SEL.match(p) for p in stack)
    excerpt = f"{prop}: {value}"

    if prop.startswith("--"):
        for name, comma in VAR.findall(value):
            if not proj.known(name) and not comma:
                found.append(finding("ERROR", "unknown-token", line, excerpt,
                                     f"{name} is declared nowhere; alias a declared token"))
        lits = [l for l, _, _ in lengths(value)] + color_literals(value)
        if lits:
            found.append(finding("WARNING", "local-token", line, excerpt,
                                 "a token outside the token layer: move it to the token file, or alias an existing "
                                 f"token ({prop}: var(--…))"))
        return found

    fam = family(prop)
    scoped = fam in ("space", "font-size", "font", "radius") or bool(COLOR_PROP.search(prop))
    for name, comma in VAR.findall(value):
        if not proj.known(name):
            if comma or not scoped:
                found.append(finding("WARNING", "unknown-token", line, excerpt,
                                     f"{name} is declared nowhere" + (", so the fallback is what renders" if comma
                                                                     else "; check the name")))
            else:
                found.append(finding("ERROR", "unknown-token", line, excerpt,
                                     f"{name} is declared nowhere; use a declared token (run --system to list them)"))
        elif name in proj.local and name not in proj.tokens:
            v = proj.local[name]
            literal_len = bool(LEN.search(v)) and fam in ("space", "font-size", "font", "radius")
            if literal_len or color_literals(v):
                found.append(finding("ERROR", "via-local-token", line, excerpt,
                                     f"{name} is a literal ({v}) declared outside the token layer; same as "
                                     "writing the number here"))

    cols = color_literals(value)
    for lit in cols:
        census["color"][lit.lower()] += 1
    if cols:
        notes = [f"{lit}: {proj.nearest_color(lit)}" for lit in dict.fromkeys(cols)]
        found.append(finding("ERROR", "raw-color", line, excerpt,
                             "; ".join(notes[:3]) + (f"; and {len(notes) - 3} more" if len(notes) > 3 else "")))

    lens = lengths(value)
    groups = defaultdict(list)

    def add(level, rule, note):
        groups[(level, rule)].append(note)

    if fam == "space":
        for lit, v, unit in lens:
            if v is not None and abs(v) <= 1:
                continue
            census["space"][lit] += 1
            add("ERROR", "raw-space", hint(proj, "space", lit, v, unit, value))
        if PCT.search(value):
            add("WARNING", "percent-space", "percentage padding or margin follows the container width")
    elif fam == "offset":
        for lit, v, unit in lens:
            if v is not None and abs(v) <= 1:
                continue
            census["offset"][lit] += 1
            add("WARNING", "raw-offset", hint(proj, "space", lit, v, unit, value, "an offset that isn't a token"))
    elif fam in ("font-size", "font"):
        sized = False
        for lit, v, unit in lens:
            if fam == "font" and re.search(rf"/\s*{re.escape(lit)}", value):
                continue
            if unit == "em":
                if abs(float(lit[:-2]) - 1) > 1e-9:
                    add("WARNING", "relative-font-size", "em sizes compound when nested; use a type token unless "
                        "it is a deliberate relative size (sup, small)")
                continue
            sized = True
            add("ERROR", "raw-font-size", hint(proj, "font-size", lit, v, unit, value))
        if sized:
            census["font-size"][value] += 1
        if fam == "font-size" and not in_root and PCT.search(value):
            add("WARNING", "relative-font-size", "a % size outside :root/html")
        if fam == "font-size" and "var(" in value:
            census["font-size-token"][value] += 1
    elif fam == "line-height":
        if lens:
            add("WARNING", "unit-line-height", "make it unitless (or a token) so it follows the font size")
    elif fam == "radius":
        for lit, v, unit in lens:
            if v is not None and (abs(v) <= 1 or v >= 999):
                continue
            census["radius"][lit] += 1
            add("ERROR", "raw-radius", hint(proj, "radius", lit, v, unit, value))
    for (level, rule), notes in groups.items():
        found.append(finding(level, rule, line, excerpt, "; ".join(dict.fromkeys(notes))))

    if fam in ("space", "offset", "font-size", "radius"):
        for m in ODD_FACTOR.finditer(value):
            factor = float(m.group(1) or m.group(2))
            if abs(factor * 2 - round(factor * 2)) > 1e-9:
                found.append(finding("CANDIDATE", "token-arithmetic", line, excerpt,
                                     f"x{factor:g} lands between steps; a value the scale lacks is a new token, "
                                     "not arithmetic"))
    return found


def check_classes(proj, text, line_of, census):
    found = []
    for m in TW_ARB.finditer(text):
        util, raw = m.group(1), m.group(2).replace("_", " ")
        raw = re.sub(r"^(?:length|color|size|percentage|number):", "", raw)
        line, ex = line_of(m.start()), m.group(0)
        for name in re.findall(r"(--[\w-]+)", raw):
            if not proj.known(name):
                found.append(finding("ERROR", "unknown-token", line, ex, f"{name} is declared nowhere"))
        if "var(" in raw or raw.startswith("--"):
            continue
        cols = color_literals(raw)
        if cols:
            census["color"][cols[0].lower()] += 1
            found.append(finding("ERROR", "tw-arbitrary", line, ex, proj.nearest_color(cols[0])))
            continue
        lens = lengths(raw)
        if not lens:
            continue
        lit, v, _ = lens[0]
        fam = ("space" if re.fullmatch(TW_SPACE, util) else "offset" if re.fullmatch(TW_OFFSET, util) else
               "font-size" if util == "text" else "radius" if util.startswith("rounded") else None)
        if fam:
            census[fam][lit] += 1
        if re.fullmatch(TW_SPACE, util):
            hint = tw_step_hint(proj, v) or proj.nearest("space", v)
            found.append(finding("ERROR", "tw-arbitrary", line, ex, f"{lit}: {hint or 'add the step to @theme'}"))
        elif re.fullmatch(TW_OFFSET, util):
            found.append(finding("WARNING", "tw-arbitrary", line, ex, f"{lit}: an offset that isn't a theme step"))
        elif util == "text":
            note = ("a fluid size belongs in the theme as clamp() with both ends on the scale" if "clamp(" in raw
                    else f"{lit}: use a text size from the theme" + tw_text_hint(proj, v))
            found.append(finding("ERROR", "tw-arbitrary", line, ex, note))
        elif util == "leading" and lens:
            found.append(finding("WARNING", "tw-arbitrary", line, ex, "leading with a unit; unitless or a theme value"))
        elif util.startswith("rounded"):
            found.append(finding("ERROR", "tw-arbitrary", line, ex, f"{lit}: use a radius from the theme"))
    for m in TW_VARSHORT.finditer(text):
        if not proj.known(m.group(2)):
            found.append(finding("ERROR", "unknown-token", line_of(m.start()), m.group(0),
                                 f"{m.group(2)} is declared nowhere"))
    for m in TW_STEP.finditer(text):
        util, step = m.group(1), m.group(2)
        if step in ("auto", "px", "full", "screen", "reverse", "min", "max", "fit", "none") or "/" in step:
            continue
        line, ex = line_of(m.start()), m.group(0)
        if proj.tailwind == 4 and proj.reset("spacing"):
            if step not in proj.theme_steps and (step[0].isdigit() or step in SCALE_WORDS):
                found.append(finding("ERROR", "tw-removed-step", line, ex,
                                     f"the theme reset spacing, so {util}-{step} generates no CSS; declared steps: "
                                     + (", ".join(sorted(proj.theme_steps, key=step_key)) or "none")))
        elif step[0].isdigit() and step not in TW_STEPS:
            why = ("valid in Tailwind v4 but off the default steps" if proj.tailwind == 4 else
                   "not a default Tailwind v3 step, so it generates no CSS unless the config adds it")
            found.append(finding("CANDIDATE", "tw-off-step", line, ex,
                                 f"{util}-{step} is {why}; keep to the steps the project already uses"))
    if proj.tailwind == 4 and proj.reset("text"):
        for m in TW_TEXTSIZE.finditer(text):
            if m.group(1) not in proj.theme_text:
                found.append(finding("ERROR", "tw-removed-step", line_of(m.start()), m.group(0),
                                     "the theme reset text sizes" + tw_text_hint(proj)))
    return found


def step_key(s):
    try:
        return (0, float(s), s)
    except ValueError:
        return (1, 0.0, s)


def tw_step_hint(proj, v):
    if v is None:
        return ""
    steps = []
    if proj.tailwind == 4 and proj.reset("spacing"):
        for st in proj.theme_steps:
            hit = proj.tokens.get(f"--spacing-{st}")
            ls = lengths(proj.resolve(hit[0])) if hit else []
            if ls and ls[0][1] is not None:
                steps.append((ls[0][1], st))
        kind = "declared"
    else:
        steps = [(float(st) * 4, st) for st in TW_STEPS]
        kind = "default"
    if not steps:
        return ""
    below = [t for t in steps if t[0] <= v]
    above = [t for t in steps if t[0] > v]
    picks = ([max(below)] if below else []) + ([min(above)] if above else [])
    return f"nearest {kind} steps: " + ", ".join(f"{st} ({fmt(sv)})" for sv, st in picks)


def tw_text_hint(proj, v=None):
    if proj.tailwind == 4 and proj.reset("text"):
        return "; declared: " + (", ".join(f"text-{t}" for t in sorted(proj.theme_text)) or "none")
    if v is not None:
        below = [k for k in TW_TEXT_PX if TW_TEXT_PX[k] <= v]
        above = [k for k in TW_TEXT_PX if TW_TEXT_PX[k] > v]
        picks = ([max(below, key=TW_TEXT_PX.get)] if below else []) + ([min(above, key=TW_TEXT_PX.get)] if above else [])
        return "; nearest: " + ", ".join(f"text-{k} ({TW_TEXT_PX[k]}px)" for k in picks)
    return ""


def check_file(proj, path, text, census):
    starts = [0] + [m.end() for m in re.finditer(r"\n", text)]

    def line_of(off):
        return bisect.bisect_right(starts, off)

    if proj.is_token_file(path):
        return []
    found = []
    for prop, value, off, stack in declarations(path, text):
        if prop.endswith("*"):
            continue
        if prop.startswith("--") and any(TOKEN_SEL.search(p) for p in stack):
            continue
        found += check_decl(proj, prop, value, line_of(off), stack, census)
    if proj.tailwind:
        if path.suffix.lower() in EXT_CSS:
            for m in re.finditer(r"@apply\s+([^;}\n]+)", text):
                found += check_classes(proj, " " + m.group(1), lambda o, b=m.start(1) - 1: line_of(b + o), census)
        else:
            found += check_classes(proj, text, line_of, census)
    return found


# ---------- output ----------

def rel_path(path, root):
    try:
        return str(path.resolve().relative_to(root.resolve()))
    except ValueError:
        return str(path)


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def census_lines(census):
    out = []
    for fam in ("space", "font-size", "color", "radius", "offset"):
        c = census.get(fam)
        if c:
            top = ", ".join(f"{v} x{n}" for v, n in c.most_common(12))
            out.append(f"REPORT: literal {fam} values outside the token layer: {sum(c.values())} uses, "
                       f"{len(c)} unique ({top})")
    sizes = set(census.get("font-size", {})) | set(census.get("font-size-token", {}))
    if sizes:
        out.append(f"REPORT: {len(sizes)} unique font sizes in use (literals and tokens)")
    return out


def system_lines(proj):
    out = ["Tokens declared in the token layer:"]
    scale = proj.scale()
    for fam in ("space", "font-size", "line-height", "color", "radius", "length", "other"):
        rows = scale.get(fam)
        if not rows:
            continue
        shown = ", ".join(n if fam == "other" else f"{n} {v}" + (f" ({fmt(p)})" if p is not None and
                                                                     not v.endswith("px") else "")
                          for n, v, p in rows[:40])
        out.append(f"  {fam} ({len(rows)}): {shown}" + (" …" if len(rows) > 40 else ""))
    if not proj.tokens and proj.tailwind:
        out.append("  none in the project: the Tailwind default theme is the scale (spacing steps of 0.25rem, "
                   "text-xs to text-9xl); keep to the steps the code already uses")
    elif not proj.tokens:
        out.append("  none: declare the scale in one token file before the first UI edit")
    files = sorted({rel_path(f, proj.root) for _, f in proj.tokens.values()})
    if files:
        out.append("Declared in: " + ", ".join(files[:10]))
    if proj.local:
        out.append(f"Custom properties declared outside the token layer: {len(proj.local)} "
                   f"({', '.join(sorted(proj.local)[:15])})")
    if proj.tailwind:
        tw = f"Tailwind v{proj.tailwind}"
        if proj.resets:
            tw += "; namespaces reset: " + ", ".join(sorted(r or "*" for r in proj.resets))
        if proj.theme_steps:
            tw += "; spacing steps: " + ", ".join(sorted(proj.theme_steps, key=step_key))
        if proj.theme_text:
            tw += "; text sizes: " + ", ".join(sorted(proj.theme_text))
        out.append(tw)
    return out


def run(paths, root, token_files, allow, ref):
    proj = Project(root, token_files, allow)
    proj.collect()
    census = defaultdict(Counter)
    found, older = [], 0
    for path in walk(paths):
        text = read(path)
        if text is None:
            continue
        rel = rel_path(path, root)
        hits = check_file(proj, path, text, census)
        keep = None if ref is None else changed_lines(root, path, ref)
        for f in hits:
            if keep is not None and f["line"] not in keep:
                older += 1
                continue
            f["file"] = rel
            found.append(f)
    found.sort(key=lambda f: (f["file"], f["line"]))
    return proj, found, census, older


def main():
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("paths", nargs="*")
    ap.add_argument("--root")
    ap.add_argument("--tokens", nargs="+", default=[])
    ap.add_argument("--changed", action="store_true")
    ap.add_argument("--since", metavar="REF")
    ap.add_argument("--allow", action="append", default=[])
    ap.add_argument("--system", action="store_true")
    ap.add_argument("--hook", action="store_true")
    ap.add_argument("--json", action="store_true")
    args = ap.parse_args()

    if args.hook:
        return hook(args)

    paths = [Path(p) for p in args.paths]
    for p in paths:
        if not p.exists():
            print(f"ERROR: path not found: {p}")
            sys.exit(2)
    if args.root:
        root = Path(args.root)
    elif paths and paths[0].is_dir():
        root = paths[0]
    else:
        root = find_root(paths[0].parent if paths else Path.cwd())
    tokens = [Path(t) for t in args.tokens]
    for t in tokens:
        if not t.exists():
            print(f"ERROR: token file not found: {t}")
            sys.exit(2)
    ref = args.since or ("HEAD" if args.changed else None)
    proj, found, census, older = run(paths or [root], root, tokens, args.allow, ref)

    report = census_lines(census)
    if ref is not None:
        report.append(f"REPORT: {older} findings on lines not changed since {ref} (not required)")
    if args.system:
        print("\n".join(system_lines(proj) + report))
        sys.exit(0)
    if args.json:
        print(json.dumps({"findings": found, "report": report, "tailwind": proj.tailwind,
                          "tokens": len(proj.tokens)}, ensure_ascii=False, indent=2))
    else:
        order = {lvl: k for k, lvl in enumerate(LEVELS)}
        for f in sorted(found, key=lambda f: (order[f["level"]], f["file"], f["line"])):
            note = f"; {f['note']}" if f["note"] else ""
            print(f"{f['level']}: {f['file']}:{f['line']} {f['rule']} \"{f['excerpt']}\"{note}")
        for line in report:
            print(line)
        counts = {lvl: sum(f["level"] == lvl for f in found) for lvl in LEVELS}
        print(f"Result: {plural(counts['ERROR'], 'error')}, {plural(counts['WARNING'], 'warning')}, "
              f"{plural(counts['CANDIDATE'], 'candidate')}. Fix every error with a declared token or a new token "
              "in the token file; give each warning and candidate a decision.")
    sys.exit(1 if any(f["level"] == "ERROR" for f in found) else 0)


def hook(args):
    try:
        data = json.load(sys.stdin)
    except (ValueError, OSError):
        sys.exit(0)
    fp = (data.get("tool_input") or {}).get("file_path") or ""
    path = Path(fp)
    if not fp or path.suffix.lower() not in EXTS or not path.is_file():
        sys.exit(0)
    env_root = os.environ.get("CLAUDE_PROJECT_DIR")
    root = Path(env_root) if env_root and path.resolve().is_relative_to(Path(env_root).resolve()) \
        else find_root(path.parent)
    proj, found, _, _ = run([path], root, [Path(t) for t in args.tokens], args.allow, "HEAD")
    errors = [f for f in found if f["level"] == "ERROR"]
    if not errors:
        sys.exit(0)
    lines = [f"{f['file']}:{f['line']} {f['rule']} \"{f['excerpt']}\"; {f['note']}" for f in errors[:20]]
    if len(errors) > 20:
        lines.append(f"… and {len(errors) - 20} more")
    print("ui-tokens: values that bypass the project's tokens on lines you just wrote:\n" + "\n".join(lines) +
          "\nUse a declared token. A value no step fits becomes a new token with a role name in the token file. "
          "Don't change an existing token's value to make one element fit.", file=sys.stderr)
    sys.exit(2)


if __name__ == "__main__":
    main()
