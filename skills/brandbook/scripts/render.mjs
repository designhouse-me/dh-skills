// SPDX-License-Identifier: CC-BY-4.0
// © 2026 Design House (https://designhouse.me)
//
// Renders and checks the brand book in a local Chromium. No npm packages: Chromium is driven over the
// DevTools Protocol on 127.0.0.1 through the WebSocket built into Node 22+. No internet connection.
//
//   node render.mjs check  brand/book/index.html [brand/labels]   # checks in the rendered page (see below)
//   node render.mjs pdf    brand/book/index.html brand/out/brandbook.pdf
//   node render.mjs shots  brand/book/index.html brand/out/shots  # book-1440.jpg, book-390.jpg, first screens
//   node render.mjs labels brand/labels brand/out/labels          # <id>.pdf at trim + bleed, <id>-preview.png, <id>-guides.png
//   node render.mjs measure client-label.svg --surface 156        # x-height and figure height of live text in a client's SVG
//
// check, book (at 1440 and 390 px): horizontal scroll, images that didn't load, page errors, each brand font
// loaded and covering the language's letters (ą ć ę ł ń ó ś ź ż „ ” for Polish; the text is measured with two
// different fallbacks, equal widths mean no fallback glyph was used), logos in mockups smaller than their own
// min_px, generated images on a slide whose footer doesn't say so, text under 12 px (warning). Text: every strategy
// and voice field the data has is on a slide (a custom template that drops one is an error); field names and
// the skill's files in the slides' text (error); tool names, file paths outside the files and quick reference,
// the agency outside the cover, more than 90 words of prose on a slide or 800 in the book (warnings).
// check, labels: zone overflow in both axes, mandatory text ([data-legal]) x-height measured in the browser
// against 1.2 mm (0.9 mm when the largest surface is under 80 cm²) for food and supplements, the height of the
// net quantity's figures (2/3/4/6 mm by quantity), text contrast on the label colour, fonts, images.
// check, logo files: content outside the SVG's viewBox (clipped letters), live <text> that needs outlining.
// pdf: printed one slide at a time and joined; the page count in total and per section; --max-pages N makes an overrun an error.
//
// Options: --chrome /path/to/chrome, --timeout 120 (seconds per page load; one retry), --max-pages N (pdf),
// --surface cm² and --category food|supplement|cosmetic (measure).
// Exit code: 0 = no errors, 1 = errors or a render error, 2 = bad input.

import { spawn } from "node:child_process";
import { existsSync, mkdirSync, mkdtempSync, readdirSync, rmSync, statSync, writeFileSync } from "node:fs";
import { homedir, tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { pathToFileURL } from "node:url";

const fail = (msg, code = 2) => {
  console.error(`ERROR: ${msg}`);
  process.exit(code);
};
if (typeof WebSocket === "undefined") fail(`Node 22 or newer is required (built-in WebSocket), found ${process.version}.`);
const argv = process.argv.slice(2);
const opt = (name) => { const i = argv.indexOf(`--${name}`); return i >= 0 ? argv.splice(i, 2)[1] : undefined; };
const chromeArg = opt("chrome");
const TIMEOUT = Number(opt("timeout") || 120) * 1000;
const maxPages = opt("max-pages");
const surfaceArg = opt("surface");
const categoryArg = opt("category") || "food";
const [mode, input, output] = argv;
if (!["check", "pdf", "shots", "labels", "measure"].includes(mode) || !input) fail("usage: node render.mjs check|pdf|shots|labels|measure <input> [output]");

function findChrome() {
  if (chromeArg || process.env.CHROME) return chromeArg || process.env.CHROME;
  const fixed = [
    "/usr/bin/chromium", "/usr/bin/chromium-browser", "/usr/bin/google-chrome", "/usr/bin/google-chrome-stable",
    "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome", "/Applications/Chromium.app/Contents/MacOS/Chromium",
  ];
  const found = fixed.find((p) => existsSync(p));
  if (found) return found;
  const cache = join(homedir(), ".cache/ms-playwright");
  const dirs = existsSync(cache) ? readdirSync(cache).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse() : [];
  for (const d of dirs) for (const rel of ["chrome-linux64/chrome", "chrome-linux/chrome"]) if (existsSync(join(cache, d, rel))) return join(cache, d, rel);
  fail("could not find Chromium or Chrome. Give the path: --chrome /path/to/chromium");
}

// ------------------------------------------------------------------ Chromium over the DevTools Protocol
const within = (ms, p, what) => {
  let timer;
  const limit = new Promise((_, reject) => (timer = setTimeout(() => reject(new Error(`${what}: timed out after ${ms / 1000} s`)), ms)));
  return Promise.race([p, limit]).finally(() => clearTimeout(timer));
};
// Chromium's socket path in the profile is limited to ~100 characters; with a long TMPDIR the profile goes to /tmp.
const tmpBase = tmpdir().length > 40 && existsSync("/tmp") ? "/tmp" : tmpdir();
let browser;
process.on("exit", () => browser?.kill());
process.on("SIGINT", () => process.exit(130));

class Chrome {
  static async launch() {
    const profile = mkdtempSync(join(tmpBase, `brandbook-chrome-${process.pid}-`));
    const flags = [
      "--headless=new", "--remote-debugging-port=0", "--remote-debugging-address=127.0.0.1", `--user-data-dir=${profile}`,
      "--no-first-run", "--no-default-browser-check", "--disable-extensions", "--disable-background-networking", "--mute-audio",
      "--hide-scrollbars", "--force-color-profile=srgb", "--allow-file-access-from-files",
      // Without it, headless Chrome on macOS hung in Page.printToPDF on any page with a photo (JPG or PNG).
      "--disable-gpu",
      ...(process.getuid?.() === 0 ? ["--no-sandbox"] : []),
      "about:blank",
    ];
    const proc = spawn(findChrome(), flags, { stdio: ["ignore", "ignore", "pipe"], detached: true });
    const c = new Chrome(proc, profile);
    const ws = await new Promise((res, rej) => {
      let buf = "", found = false;
      proc.stderr.on("data", (d) => {
        if (found) return;
        buf += d;
        const m = buf.match(/DevTools listening on (ws:\/\/\S+)/);
        if (m) { found = true; res(m[1]); }
      });
      proc.on("exit", (code) => !found && rej(new Error(`Chromium exited before startup (code ${code}): ${buf.slice(-300)}`)));
      proc.on("error", rej);
    });
    await c.connect(ws);
    return c;
  }
  constructor(proc, profile) { this.proc = proc; this.profile = profile; this.seq = 0; this.pending = new Map(); this.listeners = new Set(); }
  connect(wsUrl) {
    return new Promise((res, rej) => {
      const ws = new WebSocket(wsUrl);
      ws.onopen = () => res();
      ws.onerror = () => rej(new Error("could not connect to DevTools"));
      ws.onmessage = (ev) => {
        const msg = JSON.parse(ev.data);
        if (msg.id && this.pending.has(msg.id)) {
          const { resolve: ok, reject } = this.pending.get(msg.id);
          this.pending.delete(msg.id);
          msg.error ? reject(new Error(msg.error.message)) : ok(msg.result);
        } else if (msg.method) for (const l of this.listeners) l(msg);
      };
      this.ws = ws;
    });
  }
  send(method, params = {}, sessionId) {
    const id = ++this.seq;
    this.ws.send(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }));
    return new Promise((ok, reject) => this.pending.set(id, { resolve: ok, reject }));
  }
  once(method, sessionId) {
    return new Promise((ok) => {
      const l = (msg) => { if (msg.method === method && msg.sessionId === sessionId) { this.listeners.delete(l); ok(msg.params); } };
      this.listeners.add(l);
    });
  }
  kill() {
    try { this.ws?.close(); } catch {}
    try { process.kill(-this.proc.pid, "SIGKILL"); } catch { try { this.proc.kill("SIGKILL"); } catch {} }
    rmSync(this.profile, { recursive: true, force: true });
  }
}

async function openPage(url, width, height, { mobile = false, scale = 1, media = "screen" } = {}) {
  const { targetId } = await browser.send("Target.createTarget", { url: "about:blank" });
  const { sessionId } = await browser.send("Target.attachToTarget", { targetId, flatten: true });
  const s = (m, p) => browser.send(m, p, sessionId);
  const problems = [];
  browser.listeners.add((msg) => {
    if (msg.sessionId !== sessionId) return;
    if (msg.method === "Runtime.exceptionThrown") problems.push(msg.params.exceptionDetails?.exception?.description ?? msg.params.exceptionDetails?.text);
    if (msg.method === "Runtime.consoleAPICalled" && msg.params.type === "error") problems.push(msg.params.args.map((a) => a.value ?? a.description).join(" "));
    if (msg.method === "Log.entryAdded" && msg.params.entry.level === "error") problems.push(`${msg.params.entry.text} ${msg.params.entry.url ?? ""}`.trim());
  });
  await s("Page.enable"); await s("Runtime.enable"); await s("Log.enable");
  await s("Emulation.setDeviceMetricsOverride", { width, height, deviceScaleFactor: scale, mobile });
  await s("Emulation.setEmulatedMedia", { media });
  const loaded = browser.once("Page.loadEventFired", sessionId);
  await s("Page.navigate", { url });
  await within(TIMEOUT, loaded, `loading ${url}`);
  const evaluate = async (expression) => {
    const r = await s("Runtime.evaluate", { expression, awaitPromise: true, returnByValue: true });
    if (r.exceptionDetails) throw new Error(r.exceptionDetails.exception?.description ?? r.exceptionDetails.text);
    return r.result.value;
  };
  return { s, evaluate, problems, close: () => browser.send("Target.closeTarget", { targetId }) };
}

// A busy machine can stall one load: one retry, and the timeout is an option.
async function openLoaded(url, width, height, opts, what) {
  for (let k = 1; ; k++) {
    const p = await openPage(url, width, height, opts);
    try {
      await within(TIMEOUT, p.evaluate(LOAD_ALL), what);
      return p;
    } catch (e) {
      await p.close().catch(() => {});
      if (k >= 2) throw new Error(`${e.message} (twice; try --timeout 300 on a busy machine)`);
      console.error(`${e.message}, retrying`);
    }
  }
}

// Lazy images and label iframes would stay empty in a PDF or a full-page shot: load them all first.
const LOAD_ALL = `(async () => {
  await (window.__bookReady || window.__labelReady || Promise.resolve());
  for (const el of document.querySelectorAll('[loading="lazy"]')) el.loading = "eager";
  const wait = (el) => new Promise((r) => { if (el.tagName === "IMG" && el.complete) return r(); el.addEventListener("load", r, { once: true }); el.addEventListener("error", r, { once: true }); setTimeout(r, 8000); });
  await Promise.all([...document.images, ...document.querySelectorAll("iframe")].map(wait));
  await document.fonts.ready;
  await new Promise((r) => requestAnimationFrame(() => requestAnimationFrame(r)));
  return true;
})()`;

const errors = [], warnings = [];
const err = (m) => { errors.push(m); console.log(`ERROR: ${m}`); };
const warn = (m) => { warnings.push(m); console.log(`WARNING: ${m}`); };

// In-page probes. FONTS: brand families from the embedded JSON, loaded and covering the language's letters.
const FONT_PROBE = `(() => {
  const el = document.getElementById("brand-data") || document.getElementById("label-data");
  const d = JSON.parse(el.textContent);
  const fams = (d.type && d.type.families) || (d.brand && d.brand.families) || [];
  const lang = (d.meta && d.meta.language) || (d.brand && d.brand.language) || "pl";
  const letters = lang === "en" ? "AaGg“”’" : "ąćęłńóśźżĄĆĘŁŃÓŚŹŻ„”";
  const ctx = document.createElement("canvas").getContext("2d");
  const out = [];
  for (const f of fams) {
    const loaded = [...document.fonts].some((ff) => ff.family.replace(/["']/g, "") === f.family && ff.status === "loaded");
    const missing = [];
    for (const ch of letters) {
      ctx.font = '40px "' + f.family + '", monospace'; const a = ctx.measureText(ch).width;
      ctx.font = '40px "' + f.family + '", serif'; const b = ctx.measureText(ch).width;
      if (Math.abs(a - b) > 0.01) missing.push(ch);
    }
    out.push({ family: f.family, loaded, missing: missing.join(" ") });
  }
  return out;
})()`;

const BOOK_PROBE = `(() => {
  const vw = document.documentElement.clientWidth;
  const wide = [];
  if (document.documentElement.scrollWidth > vw + 1)
    for (const el of document.querySelectorAll("main *")) {
      const r = el.getBoundingClientRect();
      if (r.right > vw + 1 && !el.closest(".scroll") && getComputedStyle(el).position !== "fixed") wide.push(el.tagName.toLowerCase() + (el.className ? "." + String(el.className).split(" ")[0] : "") + " " + Math.round(r.right - vw) + "px");
    }
  const broken = [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute("src"));
  // offsetWidth is the logo's own layout width, before the slide and mockup scaling.
  const logos = [...document.querySelectorAll("[data-logo]")].map((el) => {
    return { w: Math.round(el.offsetWidth), min: Number(el.dataset.minPx), where: el.closest("section")?.id || el.closest(".frame")?.className || "" };
  }).filter((x) => x.min && x.w && x.w + 0.5 < x.min);
  // Text tiles on slides: anything cut off by the tile's edge.
  const cut = [...document.querySelectorAll(".t[data-text]")].filter((el) => el.offsetParent && (el.scrollHeight > el.clientHeight + 2 || el.scrollWidth > el.clientWidth + 2 ||
    [...el.querySelectorAll(".abs")].some((a) => { const r = a.getBoundingClientRect(), b = el.getBoundingClientRect(); return r.bottom > b.bottom + 2 || r.right > b.right + 2; })))
    .map((el) => { const fr = el.closest(".frame"); return "slide " + (fr ? fr.querySelector(".pno")?.textContent : "?") + " (" + (el.closest("section")?.id || "cover") + "): " + JSON.stringify(el.textContent.trim().slice(0, 50)); });
  const d = JSON.parse(document.getElementById("brand-data").textContent);
  const label = (d.imagery && d.imagery.ai && d.imagery.ai.label) || "";
  const uncaptioned = [...document.querySelectorAll('figure[data-generated="true"]')].filter((f) => {
    const t = ((f.querySelector("figcaption") || {}).textContent || "") + " " + ((f.closest(".slide")?.querySelector(".foot[data-ai]") || {}).textContent || "");
    return !(label ? t.includes(label) : /wizualizacja|visuali[sz]ation/i.test(t));
  }).map((f) => f.querySelector("img")?.getAttribute("src"));
  let small = 0; const smallEx = [];
  const walker = document.createTreeWalker(document.getElementById("main"), NodeFilter.SHOW_TEXT);
  while (walker.nextNode()) {
    const n = walker.currentNode, p = n.parentElement;
    if (!n.textContent.trim() || !p || p.closest(".mock, iframe, .no-print") || !p.offsetParent) continue;
    const fs = parseFloat(getComputedStyle(p).fontSize);
    if (fs < 12) { small++; if (smallEx.length < 3) smallEx.push(n.textContent.trim().slice(0, 30) + " (" + fs + "px)"); }
  }
  return { wide: wide.slice(0, 6), broken, logos, uncaptioned, small, smallEx, cut };
})()`;

// TEXT: the data's strategy and voice fields found in the slides (textContent, so CSS case changes don't matter),
// and the build showing through in what a reader sees (innerText per slide).
const TEXT_PROBE = `(() => {
  const d = JSON.parse(document.getElementById("brand-data").textContent);
  const main = document.getElementById("main");
  const norm = (s) => String(s || "").replace(/[„”“"«»‚’'\\u00a0]/g, " ").replace(/\\s+/g, " ").trim().toLowerCase();
  const all = norm(main.textContent);
  const s = d.strategy || {}, v = d.voice || {}, m = d.meta || {}, co = m.company || {};
  const one = (x) => (Array.isArray(x) ? x[0] : x);
  const p0 = one(s.proof), sit0 = one(v.situations) || {};
  const want = [
    ["strategy.purpose", s.purpose], ["strategy.audience", s.audience],
    ["strategy.instead_of", (s.alternatives || []).length ? null : s.instead_of], ["strategy.alternatives", (one(s.alternatives) || {}).alternative],
    ["strategy.proof", p0 && (typeof p0 === "string" ? p0 : p0.fact)], ["quickref.rules", one((d.quickref || {}).rules)],
    ["voice.situations", sit0.example || sit0.moment], ["voice.boilerplate.line", (v.boilerplate || {}).line], ["voice.boilerplate.short", (v.boilerplate || {}).short],
    ["voice.fixed_lines", (one(v.fixed_lines) || {}).text], ["voice.name_rule", v.name_rule], ["meta.company", co.tax_id || co.name], ["meta.home", m.home]
  ];
  const missing = want.filter(([, t]) => t && !all.includes(norm(t).slice(0, 48))).map(([k]) => k);
  const FIELD = /\\b[a-z]+(?:_[a-z0-9]+)+\\b|\\b(?:meta|strategy|voice|logo|colours|imagery|labels|print|decisions|sections|quickref)\\.(?!(?:png|svg|jpe?g|pdf|ttf|otf|woff2?|webp|css|html)\\b)[a-z_]+|brand\\.json|build_book|check_brand|render\\.mjs|\\?reader=|\\b0[0-2]-(?:input|verify|system)\\b/;
  const TOOL = /\\b(OpenAI|ImageGen|gpt-image|DALL[·-]?E|Midjourney|Stable Diffusion|Codex|ChatGPT|Gemini|Firefly|Ideogram)\\b/i;
  const PATH = /(?:^|\\s)[a-z][a-z0-9_.-]{2,}\\/[\\w.-]{3,}|\\b[\\w-]+\\.(?:json|css|html|mjs|py|log)\\b/;
  const agency = String(m.made_by || "").trim().toLowerCase();
  const fields = [], tools = [], paths = [], named = [];
  for (const f of main.querySelectorAll(".frame")) {
    const t = f.innerText || "", where = "slide " + (f.querySelector(".pno")?.textContent || "?");
    const sec = f.closest("section")?.id || (f.classList.contains("cover") ? "cover" : "");
    const a = t.match(FIELD); if (a) fields.push(where + ": " + a[0]);
    const b = t.match(TOOL); if (b) tools.push(where + ": " + b[0]);
    const c = !["files", "start"].includes(sec) && t.match(PATH); if (c) paths.push(where + ": " + c[0].trim());
    if (agency && !["cover", "decisions"].includes(sec) && !f.classList.contains("closing") && t.toLowerCase().includes(agency)) named.push(where);
  }
  // Prose per slide: tables of values, mockups, photos, footers, the label checklist and text meant to be pasted (.paste) don't count.
  const prose = [], per = [];
  let total = 0;
  for (const f of main.querySelectorAll(".frame")) {
    const c = f.cloneNode(true);
    c.querySelectorAll("table, .mock, .bcard, .sig, figure, .foot, .pno, .vals, .paste, .chk, iframe, script, style").forEach((x) => x.remove());
    const n = (c.textContent.match(/[\\p{L}\\p{N}][\\p{L}\\p{N}'’.,%–-]*/gu) || []).length;
    total += n;
    per.push([f.querySelector(".pno")?.textContent || "?", n]);
    if (n > 90) prose.push("slide " + (f.querySelector(".pno")?.textContent || "?") + " (" + n + ")");
  }
  return { missing, fields, tools, paths, named, prose, total, per };
})()`;

const LABEL_PROBE = `(() => {
  const d = JSON.parse(document.getElementById("label-data").textContent);
  const L = d.label, f = L.format;
  const pxmm = 96 / 25.4;
  const over = [...document.querySelectorAll(".inner")].map((el) => ({
    zone: el.parentElement.dataset.zone,
    v: (el.scrollHeight - el.clientHeight) / pxmm, h: (el.scrollWidth - el.clientWidth) / pxmm
  })).filter((o) => o.v > 0.2 || o.h > 0.2);
  const ctx = document.createElement("canvas").getContext("2d");
  const xs = [...document.querySelectorAll("[data-legal]")].filter((el) => el.dataset.legal !== "info").map((el) => {
    const cs = getComputedStyle(el);
    ctx.font = cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    const xh = ctx.measureText("x").actualBoundingBoxAscent / pxmm;
    return { key: el.dataset.legal, xh, pt: parseFloat(cs.fontSize) * 0.75 };
  });
  const netEl = document.querySelector('[data-legal="net"]');
  let net = null;
  if (netEl) {
    const cs = getComputedStyle(netEl);
    ctx.font = cs.fontWeight + " " + cs.fontSize + " " + cs.fontFamily;
    const digits = (netEl.textContent.match(/[0-9]/g) || ["0"]).join("");
    const m = netEl.textContent.match(/([0-9]+(?:[.,][0-9]+)?)[^0-9a-z]{0,2}(kg|mg|ml|cl|g|l)(?![a-z])/i);
    const q = m ? parseFloat(m[1].replace(",", ".")) * ({ kg: 1000, l: 1000, cl: 10, mg: 0.001 }[m[2].toLowerCase()] || 1) : null;
    net = { text: netEl.textContent.trim(), mm: ctx.measureText(digits).actualBoundingBoxAscent / pxmm, pt: parseFloat(cs.fontSize) * 0.75, q };
  }
  const broken = [...document.images].filter((i) => i.complete && i.naturalWidth === 0).map((i) => i.getAttribute("src"));
  const rgb = (s) => (s.match(/[0-9.]+/g) || []).slice(0, 3).map(Number);
  const lin = (c) => { c /= 255; return c <= 0.04045 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4; };
  const lum = (s) => { const [r, g, b] = rgb(s); return 0.2126 * lin(r) + 0.7152 * lin(g) + 0.0722 * lin(b); };
  const sheet = getComputedStyle(document.querySelector(".sheet"));
  const [la, lb] = [lum(sheet.color), lum(sheet.backgroundColor)].sort((a, b) => b - a);
  return { id: L.id, category: L.category, surface: f.largest_surface_cm2, over, xs, net, broken, contrast: (la + 0.05) / (lb + 0.05) };
})()`;

function fontReport(fonts, where) {
  for (const f of fonts) {
    if (!f.loaded) err(`${where}: the font "${f.family}" did not load (check the file path in type.families and @font-face)`);
    else if (f.missing) err(`${where}: "${f.family}" has no glyphs for: ${f.missing} (the text falls back to another font)`);
  }
}

async function checkBook(file) {
  const url = pathToFileURL(file).href;
  for (const [w, hgt, mobile] of [[1440, 900, false], [390, 844, true]]) {
    const p = await openLoaded(url, w, hgt, { mobile }, "loading the book");
    const r = await p.evaluate(BOOK_PROBE);
    const where = `book at ${w} px`;
    if (r.wide.length) err(`${where}: the page scrolls sideways; too wide: ${r.wide.join(", ")}`);
    if (w === 1440) {
      fontReport(await p.evaluate(FONT_PROBE), "book");
      for (const b of r.broken) err(`book: image did not load: ${b}`);
      for (const l of r.logos) err(`book: a logo in "${l.where.trim().slice(0, 40)}" is ${l.w} px wide at full size, below its own minimum of ${l.min} px`);
      for (const u of r.uncaptioned) err(`book: generated image on a slide whose footer doesn't name it (imagery.ai.label): ${u}`);
      for (const c of r.cut) err(`book: text runs out of its tile on ${c}; shorten it in brand.json`);
      if (r.small) warn(`book: ${r.small} text fragments under 12 px, e.g. ${r.smallEx.join("; ")}`);
      const tx = await p.evaluate(TEXT_PROBE);
      for (const k of tx.missing) err(`book: ${k} is in brand.json but on no slide; the template must show every strategy and voice field (references/data.md, section 9)`);
      for (const f of tx.fields) err(`book: the build shows through on ${f}; write it for the reader in brand.json`);
      for (const f of tx.tools) warn(`book: a tool is named on ${f}; mark generated images with imagery.ai.label, keep the tool in prompts/`);
      for (const f of tx.paths) warn(`book: a file path on ${f}; paths belong on the files slide`);
      if (tx.named.length) warn(`book: the agency is named on ${tx.named.join(", ")}; the book speaks for the brand, the agency signs the cover`);
      if (tx.prose.length) warn(`book: more than 90 words of prose on ${tx.prose.join(", ")}; one rule per slide, show it instead of explaining it (tables of values don't count)`);
      const top = tx.per.slice().sort((a, b) => b[1] - a[1]).slice(0, 4).map(([pn, n]) => `slide ${pn} (${n})`).join(", ");
      if (tx.total > 800) warn(`book: ${tx.total} words of prose; a small brand's book stays under about 800. The longest: ${top}`);
      else console.log(`book: ${tx.total} words of prose on the slides; the longest: ${top}`);
      for (const pr of [...new Set(p.problems)]) err(`book: page error: ${pr}`);
    }
    await p.close();
  }
}

async function checkLabels(dir) {
  const files = readdirSync(dir).filter((f) => f.endsWith(".html")).sort();
  if (!files.length) warn(`no label files in ${dir}`);
  for (const f of files) {
    const p = await openLoaded(`${pathToFileURL(join(dir, f)).href}?mode=preview`, 1200, 1200, {}, `loading ${f}`);
    const r = await p.evaluate(LABEL_PROBE);
    fontReport(await p.evaluate(FONT_PROBE), `label ${r.id}`);
    for (const o of r.over) err(`label ${r.id}, zone ${o.zone}: content overflows by ${o.v > 0.2 ? `${o.v.toFixed(1)} mm vertically` : ""}${o.v > 0.2 && o.h > 0.2 ? " and " : ""}${o.h > 0.2 ? `${o.h.toFixed(1)} mm horizontally` : ""}; shorten optional text or change the format, don't shrink mandatory text`);
    for (const b of r.broken) err(`label ${r.id}: image did not load: ${b}`);
    if (r.contrast < 4.5) warn(`label ${r.id}: text on the label colour has a contrast of ${r.contrast.toFixed(1)}:1; small print needs at least 4.5:1 to stay legible (WCAG is not a print norm, but the threshold works)`);
    const legalCat = ["food", "supplement"].includes(r.category);
    const need = r.surface && r.surface < 80 ? 0.9 : 1.2;
    const low = r.xs.filter((x) => x.xh + 0.005 < need);
    if (low.length) {
      const worst = low.reduce((a, b) => (a.xh < b.xh ? a : b));
      const pt = (need / (worst.xh / worst.pt)).toFixed(1);
      const msg = `label ${r.id}: x-height of mandatory text is ${worst.xh.toFixed(2)} mm (${low.map((x) => x.key).join(", ")}), needs ${need} mm${r.surface ? ` (largest surface ${r.surface} cm²)` : ""}: set legal_pt to at least ${pt}`;
      legalCat ? err(`${msg} (Regulation (EU) 1169/2011, art. 13)`) : warn(`${msg}; not a legal minimum for this category, but below it the text is hard to read`);
    } else if (r.xs.length) {
      const min = Math.min(...r.xs.map((x) => x.xh));
      console.log(`label ${r.id}: smallest mandatory x-height ${min.toFixed(2)} mm (needs ${need} mm)`);
    }
    // Directive 76/211/EEC, Annex I 3.1 (applied in Poland by the law on prepackaged goods): minimum figure height.
    if (r.net && r.net.q !== null && ["food", "supplement", "cosmetic"].includes(r.category)) {
      const needNet = r.net.q <= 50 ? 2 : r.net.q <= 200 ? 3 : r.net.q <= 1000 ? 4 : 6;
      if (r.net.mm + 0.02 < needNet) err(`label ${r.id}: the figures of the net quantity "${r.net.text}" are ${r.net.mm.toFixed(2)} mm high, need ${needNet} mm for this quantity: set net_pt to at least ${(needNet / (r.net.mm / r.net.pt)).toFixed(1)} (Directive 76/211/EEC, Annex I 3.1; confirm with the regulatory person)`);
    }
    for (const pr of [...new Set(p.problems)]) err(`label ${r.id}: page error: ${pr}`);
    await p.close();
  }
}

// Logo files: letters cut off by a too-small viewBox, and live text that a print file can't carry.
const LOGO_PROBE = `(() => {
  const s = document.documentElement;
  if (!s || s.tagName.toLowerCase() !== "svg") return { svg: false };
  const vb = s.viewBox && s.viewBox.baseVal;
  const bb = s.getBBox();
  return { svg: true, vb: vb && vb.width ? { x: vb.x, y: vb.y, w: vb.width, h: vb.height } : null, bb: { x: bb.x, y: bb.y, w: bb.width, h: bb.height }, texts: s.querySelectorAll("text").length };
})()`;

async function checkLogos(bookFile) {
  const html = (await import("node:fs")).readFileSync(bookFile, "utf8");
  const m = html.match(/<script id="brand-data" type="application\/json">([\s\S]*?)<\/script>/);
  if (!m) return;
  const data = JSON.parse(m[1].replace(/<\\\//g, "</"));
  const root = resolve(bookFile, "../..");
  for (const v of (data.logo && data.logo.variants) || []) {
    const file = resolve(root, v.file || "");
    if (!existsSync(file)) continue;
    if (!/\.svg$/i.test(file)) { warn(`logo ${v.id}: ${v.file} is not a vector (SVG); ask the client for the vector file`); continue; }
    const p = await openPage(pathToFileURL(file).href, 800, 600);
    const r = await p.evaluate(LOGO_PROBE);
    await p.close();
    if (!r.svg) continue;
    if (!r.vb) warn(`logo ${v.id}: ${v.file} has no viewBox; it won't scale predictably`);
    else {
      const tol = 0.005 * Math.max(r.vb.w, r.vb.h);
      if (r.bb.x < r.vb.x - tol || r.bb.y < r.vb.y - tol || r.bb.x + r.bb.w > r.vb.x + r.vb.w + tol || r.bb.y + r.bb.h > r.vb.y + r.vb.h + tol)
        err(`logo ${v.id}: the drawing (${r.bb.x.toFixed(0)} ${r.bb.y.toFixed(0)} ${r.bb.w.toFixed(0)}×${r.bb.h.toFixed(0)}) runs outside the viewBox (${r.vb.x} ${r.vb.y} ${r.vb.w}×${r.vb.h}), so part of it is cut off wherever the file is used; widen the viewBox in a copy and record the fix`);
    }
    if (r.texts) warn(`logo ${v.id}: ${v.file} contains ${r.texts} live <text> element(s); the letters depend on installed fonts and a printer can't use it. A designer outlines the text (the shapes stay the same)`);
  }
}

const countPages = (buf) => (buf.toString("latin1").match(/\/Type\s*\/Page[^s]/g) || []).length;

// Chrome stalls in printToPDF on a document with photos on several pages, while one slide takes about
// a second. So the deck is printed one slide at a time and the parts are joined here.
// Chrome writes PDF 1.4 with a classic xref table and no object streams, which keeps the join simple:
// every object is copied with new numbers, and one page tree points at all the pages.
function parsePdf(buf) {
  const s = buf.toString("latin1");
  const sx = s.lastIndexOf("startxref");
  const xrefAt = parseInt(s.slice(sx + 9).trim(), 10);
  if (!s.startsWith("xref", xrefAt)) throw new Error("unexpected PDF structure (no classic xref table)");
  const lines = s.slice(xrefAt, sx).split(/\r?\n/);
  const offsets = new Map();
  let i = 1;
  while (i < lines.length && !lines[i].startsWith("trailer")) {
    const [start, count] = lines[i].trim().split(/\s+/).map(Number);
    i++;
    for (let k = 0; k < count; k++, i++) {
      const [off, , type] = lines[i].trim().split(/\s+/);
      if (type === "n") offsets.set(start + k, Number(off));
    }
  }
  const trailer = s.slice(s.indexOf("trailer", xrefAt), sx);
  const root = Number(trailer.match(/\/Root (\d+) 0 R/)[1]);
  const info = (trailer.match(/\/Info (\d+) 0 R/) || [])[1];
  const bodyOf = (n) => { const off = offsets.get(n); const head = s.indexOf("obj", off) + 3; return { off, head }; };
  const objs = new Map();
  for (const n of offsets.keys()) {
    const { head } = bodyOf(n);
    const endAt = s.indexOf("endobj", head), streamAt = s.indexOf("stream", head);
    if (streamAt !== -1 && streamAt < endAt) {
      const dict = s.slice(head, streamAt);
      const m = dict.match(/\/Length (\d+)( 0 R)?/);
      let len = Number(m[1]);
      if (m[2]) { const lh = bodyOf(len).head; len = parseInt(s.slice(lh, s.indexOf("endobj", lh)).trim(), 10); }
      let at = streamAt + 6;
      if (s[at] === "\r") at++;
      if (s[at] === "\n") at++;
      objs.set(n, { dict, stream: buf.subarray(at, at + len) });
    } else objs.set(n, { dict: s.slice(head, endAt), stream: null });
  }
  return { objs, root, info: info ? Number(info) : null };
}

function mergePdfs(parts) {
  let next = 1;
  const out = [], kids = [];
  for (const part of parts) {
    const { objs, root, info } = parsePdf(part);
    const pagesRef = Number(objs.get(root).dict.match(/\/Pages (\d+) 0 R/)[1]);
    const leaf = (n) => {
      const d = objs.get(n).dict;
      return /\/Type\s*\/Pages/.test(d) ? [...d.match(/\/Kids\s*\[([^\]]*)\]/)[1].matchAll(/(\d+) 0 R/g)].flatMap((x) => leaf(Number(x[1]))) : [n];
    };
    const pages = leaf(pagesRef);
    const skip = new Set([root, info, ...[...objs.keys()].filter((n) => /\/Type\s*\/Pages/.test(objs.get(n).dict))]);
    const map = new Map();
    for (const n of objs.keys()) if (!skip.has(n)) map.set(n, next++);
    for (const [n, o] of objs) {
      if (skip.has(n)) continue;
      const dict = o.dict.replace(/(\d+) 0 R/g, (m, x) => (map.has(Number(x)) ? `${map.get(Number(x))} 0 R` : skip.has(Number(x)) ? "@PAGES@" : m));
      out.push({ id: map.get(n), dict, stream: o.stream });
    }
    kids.push(...pages.map((n) => map.get(n)));
  }
  const pagesId = next++, catalogId = next++;
  const chunks = [Buffer.from("%PDF-1.4\n%\xE2\xE3\xCF\xD3\n", "latin1")];
  let pos = chunks[0].length;
  const offs = [];
  const push = (b) => { chunks.push(b); pos += b.length; };
  for (const o of out.sort((a, b) => a.id - b.id)) {
    offs[o.id] = pos;
    push(Buffer.from(`${o.id} 0 obj${o.dict.replace(/@PAGES@/g, `${pagesId} 0 R`)}`, "latin1"));
    if (o.stream) { push(Buffer.from("stream\n", "latin1")); push(o.stream); push(Buffer.from("\nendstream", "latin1")); }
    push(Buffer.from("\nendobj\n", "latin1"));
  }
  offs[pagesId] = pos;
  push(Buffer.from(`${pagesId} 0 obj\n<</Type /Pages /Count ${kids.length} /Kids [${kids.map((k) => `${k} 0 R`).join(" ")}]>>\nendobj\n`, "latin1"));
  offs[catalogId] = pos;
  push(Buffer.from(`${catalogId} 0 obj\n<</Type /Catalog /Pages ${pagesId} 0 R>>\nendobj\n`, "latin1"));
  const xrefAt = pos;
  let xref = `xref\n0 ${next}\n0000000000 65535 f \n`;
  for (let n = 1; n < next; n++) xref += `${String(offs[n] || 0).padStart(10, "0")} 00000 n \n`;
  push(Buffer.from(`${xref}trailer\n<</Size ${next} /Root ${catalogId} 0 R>>\nstartxref\n${xrefAt}\n%%EOF\n`, "latin1"));
  return Buffer.concat(chunks);
}

async function pdf(file, out) {
  const p = await openLoaded(pathToFileURL(file).href, 1440, 900, { media: "print" }, "loading for PDF");
  await p.evaluate(`(window.dispatchEvent(new Event("beforeprint")), true)`);
  const n = await p.evaluate(`document.querySelectorAll(".frame").length`);
  const printRange = async (from, to) => {
    // The printed slide alone, without its page break (it would add a blank page).
    await p.evaluate(`(document.querySelectorAll(".frame").forEach((f, k) => { f.style.display = k >= ${from} && k < ${to} ? "" : "none"; f.style.breakAfter = k === ${to} - 1 ? "auto" : ""; }), true)`);
    const r = await within(Math.min(TIMEOUT, 60000), p.s("Page.printToPDF", { printBackground: true, preferCSSPageSize: true }), `printing slides ${from + 1}–${to}`);
    return Buffer.from(r.data, "base64");
  };
  const parts = [];
  for (let k = 0; k < n; k++) parts.push(await printRange(k, k + 1));
  const per = await p.evaluate(`[...document.querySelectorAll("main > .cover, main > section.s")].map((el) => (el.id === "top" ? "cover" : el.id) + " " + (el.classList.contains("frame") ? 1 : el.querySelectorAll(".frame").length))`);
  await p.close();
  const merged = parts.length === 1 ? parts[0] : mergePdfs(parts);
  mkdirSync(dirname(out), { recursive: true });
  writeFileSync(out, merged);
  const pages = countPages(merged);
  console.log(`${out}: ${pages} pages, ${(statSync(out).size / 1e6).toFixed(1)} MB`);
  console.log(`pages per section: ${per.join(", ")}`);
  if (statSync(out).size > 20e6) warn(`${out} is over 20 MB; too big to email`);
  if (maxPages && pages > Number(maxPages)) err(`the PDF has ${pages} pages, the budget is ${maxPages}: cut part 1 in this order: the mood photos (imagery.images with slot other), the billboard, then the worlds (the overview goes with the last one), then the longest sections above; never the rules`);
}

async function shots(file, dir) {
  mkdirSync(dir, { recursive: true });
  for (const [w, hgt, mobile] of [[1440, 900, false], [390, 844, true]]) {
    const p = await openLoaded(pathToFileURL(file).href, w, hgt, { mobile }, "loading the book");
    const first = await p.s("Page.captureScreenshot", { format: "png" });
    writeFileSync(join(dir, `first-${w}.png`), Buffer.from(first.data, "base64"));
    const height = await p.evaluate("document.documentElement.scrollHeight");
    const full = Math.min(height, 60000);
    if (height > full) console.log(`book-${w}.jpg is cut at ${full} px of ${height}; the section images below cover the rest`);
    await p.evaluate(`(document.getElementById("toast")?.remove(), document.querySelector(".bar") && (document.querySelector(".bar").style.position = "static"), true)`);
    const { data } = await p.s("Page.captureScreenshot", { format: "jpeg", quality: 80, captureBeyondViewport: true, clip: { x: 0, y: 0, width: w, height: full, scale: 1 } });
    writeFileSync(join(dir, `book-${w}.jpg`), Buffer.from(data, "base64"));
    console.log(join(dir, `book-${w}.jpg`), `${w} × ${full}`);
    // One image per section: a whole book in one picture is too small to read.
    mkdirSync(join(dir, "sections"), { recursive: true });
    const rects = await p.evaluate(`[...document.querySelectorAll(".cover, section.s")].map((el) => { const r = el.getBoundingClientRect(); return { id: el.id === "top" || !el.id ? "cover" : el.id, x: r.left, y: r.top + scrollY, w: r.width, h: Math.min(r.height, 6000) }; })`);
    for (const r of rects) {
      const shot = await p.s("Page.captureScreenshot", { format: "jpeg", quality: 82, captureBeyondViewport: true, clip: { x: Math.max(0, r.x - 16), y: Math.max(0, r.y - 8), width: Math.min(w, r.w + 32), height: r.h + 16, scale: 1 } });
      writeFileSync(join(dir, "sections", `${r.id}-${w}.jpg`), Buffer.from(shot.data, "base64"));
    }
    console.log(`${join(dir, "sections")}/: ${rects.length} sections at ${w} px`);
    await p.close();
  }
}

async function labels(dir, out) {
  mkdirSync(out, { recursive: true });
  for (const f of readdirSync(dir).filter((x) => x.endsWith(".html")).sort()) {
    const id = basename(f, ".html");
    for (const m of ["preview", "guides"]) {
      const url = `${pathToFileURL(join(dir, f)).href}?mode=${m}`;
      const p = await openLoaded(url, 1200, 1200, { media: m === "preview" ? "print" : "screen" }, `loading ${f}`);
      const size = await p.evaluate(`(() => { const r = document.getElementById("page").getBoundingClientRect(); return { w: r.width, h: r.height }; })()`);
      const shot = await p.s("Page.captureScreenshot", { format: "png", captureBeyondViewport: true, clip: { x: 0, y: 0, width: size.w, height: size.h, scale: 4 } });
      writeFileSync(join(out, `${id}-${m}.png`), Buffer.from(shot.data, "base64"));
      const { data } = await p.s("Page.printToPDF", { printBackground: true, preferCSSPageSize: true });
      writeFileSync(join(out, m === "preview" ? `${id}.pdf` : `${id}-guides.pdf`), Buffer.from(data, "base64"));
      await p.close();
    }
    console.log(`${join(out, id)}.pdf, -preview.png, -guides.png, -guides.pdf`);
  }
}

// measure: live text in a client's SVG label (width/height in mm and a viewBox). Outlined text can't be measured.
const MEASURE_PROBE = `(() => {
  const svg = document.documentElement;
  if (svg.tagName.toLowerCase() !== "svg") return { error: "not an SVG document" };
  const unit = (v) => { const m = String(v || "").trim().match(/^([0-9.]+)\\s*(mm|cm|in|pt|px)?$/); if (!m) return null; const n = parseFloat(m[1]); return ({ mm: n, cm: n * 10, in: n * 25.4, pt: n * 25.4 / 72, px: n * 25.4 / 96 })[m[2] || "px"]; };
  const vb = svg.viewBox && svg.viewBox.baseVal && svg.viewBox.baseVal.width ? svg.viewBox.baseVal : null;
  const wmm = unit(svg.getAttribute("width"));
  if (!vb || !wmm) return { error: "the SVG needs a viewBox and a width in a physical unit (e.g. width=\\"260mm\\")" };
  const mmPerUnit = wmm / vb.width;
  const rootScale = Math.hypot(svg.getScreenCTM().a, svg.getScreenCTM().b);
  const ctx = new OffscreenCanvas(8, 8).getContext("2d"); // an SVG document has no HTML canvas element
  const rows = [];
  for (const el of svg.querySelectorAll("text")) {
    const text = el.textContent.replace(/\\s+/g, " ").trim();
    if (!text) continue;
    const cs = getComputedStyle(el);
    const rel = Math.hypot(el.getScreenCTM().a, el.getScreenCTM().b) / rootScale;
    const sizeMm = parseFloat(cs.fontSize) * rel * mmPerUnit;
    ctx.font = cs.fontWeight + " 100px " + cs.fontFamily;
    const xh = ctx.measureText("x").actualBoundingBoxAscent / 100, fig = ctx.measureText("0").actualBoundingBoxAscent / 100;
    rows.push({ text: text.slice(0, 60), family: cs.fontFamily, sizeMm, xMm: sizeMm * xh, figMm: sizeMm * fig });
  }
  return { wmm, rows, outlined: !rows.length && !!svg.querySelector("path") };
})()`;

async function measure(file) {
  const p = await openLoaded(pathToFileURL(file).href, 1600, 1000, {}, `loading ${file}`);
  const r = await p.evaluate(MEASURE_PROBE);
  await p.close();
  if (r.error) return err(`${file}: ${r.error}`);
  if (r.outlined) return warn(`${file}: no live text (outlined or an image); measure the x-height from the vector by hand`);
  const need = surfaceArg && Number(surfaceArg) < 80 ? 0.9 : 1.2;
  console.log(`${basename(file)}: ${r.wmm} mm wide, ${r.rows.length} text lines; mandatory text needs ${need} mm x-height${surfaceArg ? ` (largest surface ${surfaceArg} cm²)` : " (pass --surface to apply 0.9 mm under 80 cm²)"}`);
  for (const row of r.rows) {
    const q = row.text.match(/([0-9]+(?:[.,][0-9]+)?)\s*(kg|mg|ml|cl|g|l)\b/i);
    const qty = q ? parseFloat(q[1].replace(",", ".")) * ({ kg: 1000, l: 1000, cl: 10, mg: 0.001 }[q[2].toLowerCase()] || 1) : null;
    const needFig = qty === null ? null : qty <= 50 ? 2 : qty <= 200 ? 3 : qty <= 1000 ? 4 : 6;
    const flags = [row.xMm + 0.005 < need ? `x-height below ${need} mm` : "", needFig && row.figMm + 0.02 < needFig ? `figures below ${needFig} mm for ${q[0]}` : ""].filter(Boolean).join("; ");
    console.log(`${flags ? "WARNING: " : "  "}${row.xMm.toFixed(2)} mm x-height, ${row.figMm.toFixed(2)} mm figures, ${row.sizeMm.toFixed(2)} mm size: "${row.text}"${flags ? ` (${flags}; only matters if this line is mandatory for ${categoryArg})` : ""}`);
    if (flags) warnings.push(row.text);
  }
  console.log("The font is the one installed here; with a substitute, give the tolerance (measure with each candidate face).");
}

const src = resolve(input);
if (!existsSync(src)) fail(`not found: ${src}`);
try {
  browser = await within(60000, Chrome.launch(), "Chromium start");
  if (mode === "check") {
    await checkBook(src);
    await checkLogos(src);
    const labelDir = output ? resolve(output) : resolve(src, "../../labels");
    if (existsSync(labelDir)) await checkLabels(labelDir);
    console.log(`Checked: the book${existsSync(labelDir) ? " and labels" : ""}. Result: ${errors.length} ${errors.length === 1 ? "error" : "errors"}, ${warnings.length} ${warnings.length === 1 ? "warning" : "warnings"}.`);
  } else if (mode === "pdf") await pdf(src, resolve(output ?? "brandbook.pdf"));
  else if (mode === "shots") await shots(src, resolve(output ?? "shots"));
  else if (mode === "labels") await labels(src, resolve(output ?? "labels-out"));
  else if (mode === "measure") await measure(src);
} catch (e) {
  console.error(`ERROR: ${e.message}`);
  browser?.kill();
  process.exit(1);
}
browser.kill();
process.exit(errors.length ? 1 : 0);
