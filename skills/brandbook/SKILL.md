---
name: brandbook
description: Builds a brand book from a brief, logo files and product data, delivered as a 16:9 deck of photo, colour and type tiles in one interactive web page that the owner, designers, printers and marketing can browse (filtered by reader, values to copy, live contrast, label previews) and a PDF of the same slides, plus label templates in millimetres with bleed and zones, design tokens and an internal list of what to verify before print. Use when someone asks for a brand book, brandbook, brand guidelines, a style guide, a visual identity manual or "księga znaku", label or packaging guidelines for designers, or a change to such a brand book (a new product or colour, a page, another presentation). Not for designing a logo from nothing, a legal opinion on a label (it only lists what to check and who decides), a website or a video (separate skills), or one-off social graphics.
license: CC-BY-4.0
metadata:
  author: Design House
  version: "1.1"
---

# Brand book

Goal: a brand book that the person who uses it after the designer has left can work from without calling anyone. Everything comes from one file, `brand/brand.json`: the scripts in `scripts/` build it into a deck of 1920 × 1080 slides in one web page (part 1 the brand, part 2 the rules), label templates in millimetres and `tokens.css`, then print the PDF one slide per page and check the result in a local Chromium.

## Rules that always apply

- **Write for the user, not the designer.** The reader is a marketing coordinator, a printer or an agency hired in two years. Every page answers one question for a named reader; a page that answers none goes. Headlines are rules ("The variant changes the colour, not the layout"), not topics; the number of the section stays only for finding it.
- **One source, two parts.** The story and the rules are built from the same data, never written twice. In a 2026 project the presentation and the technical manual were two hand-written PDFs; they drifted, and the shorter one lost a mandatory label item. Change `brand.json` and rebuild: `build_book.py` refuses to overwrite a file edited by hand.
- **Direction before pages.** One stop for the user: directions, a recommendation, the page budget. In the same project five directions were built in one day, because every new reference restarted the book.
- **A reference gives one layer, never assets.** The structure, the way of presenting or the photo style; write what you borrow and what not in `references[]`. Never copy its colours, type or copy, and never name it in anything the client sees (the build leaves `references` out; `check_brand.py` errors on a leak).
- **Only what exists.** Products, facts, ingredients, certificates and contacts come from the brief and the data. A concept is marked as a concept, a missing value is a placeholder listed in `01-verify.md`. Never invent a claim, a barcode or a regulated panel.
- **Print values carry their status.** CMYK always with its profile and status (`proposed`, `converted`, `proofed`), never converted by a formula; Pantone given, or a decision with a person and a date. A label template is not a print file, and it says so on itself.
- **The law is flagged, not advised.** Mandatory content by category, an x-height of at least 1.2 mm (0.9 mm under 80 cm²) for food and supplements, claims only with a register reference: `references/labels-eu.md`. When the text doesn't fit, change the format or cut optional text, never shrink mandatory text. A named regulatory person approves every label.
- **Photographs carry part 1.** The slides are mosaics of rounded tiles, and the strongest ones are images: the cover, the intro, one scene per variant colour (a "world"), the product line, a billboard. Without photographs the deck falls back to colour and type and reads like a spec sheet, so plan the images at the direction stop and get them from the client's shoot or an image tool; when neither exists, list what's missing in `01-verify.md` with who supplies it. Never fill a slot with stock that poses as the brand.
- **Labels first, images second.** In the 2026 project the labels changed after the photos were generated, and the photos showed outdated fronts. Generated images are named in the slide footer with `imagery.ai.label` (no badge on the photo), people stay sketches until a real shoot with model releases, and the product comes from the approved label render.
- **Type and colour are decisions.** Choose the typeface with `references/type.md` (method, sources, licences for print and packaging) or record the client's reason in `reflex_reason`; check the palette against the model defaults (cream with terracotta, near-black with an acid accent). Every face must have the language's accented letters.
- **The name is one parameter.** Three spellings in the brief, the data and the logo are a question for your first message, not a silent choice.
- **The client's logo stays the client's.** Fix only a technical fault, in a copy, and record it: a viewBox that cuts letters off, a negative made by recolouring. Never change the shapes; live text in a logo file goes to a designer to outline. Without a logo, set the name in the display face as a temporary wordmark and say a designer should draw the mark.

## Workflow

Working files live in `brand/` (pick another folder only if the project has one), in the user's language: `00-input.md` (the brief verbatim, a "was / now" table of renamed client files), `01-verify.md` (inconsistencies, legal flags, placeholders, each with who decides; internal when the user is the agency, so offer a clean version when the user is the brand owner), `02-system.md` (the decisions with reasons), `brand.json`, and `input/` (the client's originals, untouched), `logo/`, `fonts/`, `images/`, `prompts/`.

### 1. Intake and audit

Copy the client's files into `brand/input/` and working copies under readable names. Compare them with each other and with `references/labels-eu.md`: spellings, numbers, the content and x-height of any existing label (`node $SK/scripts/render.mjs measure label.svg --surface 156` measures live text in an SVG), claims, missing data. When nobody is named to approve labels, write `"label_approver": "(do wskazania)"` and ask. Write `01-verify.md`.

### 2. Direction (the one stop)

Read `references/canon.md`. Write the reader matrix (page, question, reader), three default looks you reject, then 2–3 directions: palette with roles, typeface pair with a reason, the signature element, how the label system varies. Recommend one and propose the page budget: one slide per PDF page, about 18 for a brand with one label (cover, part 1, the "Rules" divider, part 2, closing), plus one per further label, one per variant world and one overview, one per ten more colours; the web book shows the same slides. List the image slots with their source (the client, generated, missing): a landscape cover, a portrait intro, a scene and a detail per world, a photo per product, a billboard. Show the user the directions, your recommendation, the budget, the image plan and the spelling question, and wait. With "no questions" or nobody at the keyboard, choose and record the assumptions.

### 3. System

Fill `brand.json` field by field with `references/data.md`, starting from `assets/brand.example.json` (a fictional brand). Colours and print with `references/print.md`, labels with `references/labels-eu.md`, photography and AI with `references/images.md`. Write `02-system.md`.

```bash
SK=<this skill's folder>
python3 $SK/scripts/build_book.py brand/brand.json         # book/index.html, labels/*.html, tokens.css
python3 $SK/scripts/check_brand.py brand/brand.json        # data: colours, contrast, logo, type, labels, leaks
node $SK/scripts/render.mjs check brand/book/index.html    # render: overflow, fonts, x-height, net figures, logo files
```

Requirements: Python 3, Node 22+ and Chrome or Chromium; no npm packages, no network.

### 4. Labels

One entry per label in `labels[]`: format with bleed, safe margin and largest surface, zones by role, front, info, legal content, `legal_pt`. Fix every overflow and x-height error from `render.mjs check` by changing the format or the optional text. Then render and look at the guides image of each label:

```bash
node $SK/scripts/render.mjs labels brand/labels brand/out/labels
```

### 5. Images

Client photos go into `images/` under readable names and into their slots: `imagery.images[]` with `slot` `cover` or `intro` (the rest fill the mood mosaic), `imagery.worlds[]` (`image`, `detail`), `labels[].image`, an application of kind `billboard`. Look for an image tool before you say there is none (Codex has one: `references/images.md`, section 6). With a tool, follow `references/images.md`: prompts in `prompts/` with the label version in the `.refs` file, every attempt logged, `generated: true` so the slide footer names it. Product shots take the label front from the render as a reference and the exact words in the prompt; zoom into every pack and read it letter by letter before it goes in. Convert to JPEG and fill the slots (`references/images.md`, section 7). Without photos or a tool, leave the prompts ready, show no fake photos in the book and say so: `check_brand.py` warns that the deck has no photographs.

### 6. Review and PDF

```bash
node $SK/scripts/render.mjs shots brand/book/index.html brand/out/shots   # sections/<id>-1440.jpg and -390.jpg
node $SK/scripts/render.mjs pdf brand/book/index.html brand/out/brandbook.pdf --max-pages 20   # pages per section
```

Look at every section at 1440 px and at the PDF's slides side by side (the deck is read on a laptop, a tablet or a projector; at 390 px the slides only shrink, so that shot shows the page doesn't break, not that it reads): a slide that is mostly empty or set in one small block of text is a slide to merge or to give an image. When the PDF is over budget, cut in the order the `pdf` error gives: part 1's photo slides first, then the longest sections it lists, never the rules. Copy this into the reply and tick it off:

```md
- [ ] direction chosen at the stop (or assumptions recorded); page budget kept
- [ ] check_brand.py and render.mjs check without errors; every warning fixed or explained
- [ ] every section viewed at 1440 px, the PDF's slides side by side; label guides viewed
- [ ] every colour with CMYK profile and status, Pantone or a dated decision
- [ ] typefaces with reasons, licences and the language's letters
- [ ] 01-verify.md lists every inconsistency, legal flag and placeholder, each with who decides
- [ ] no reference named in the book; no invented product data, claim or barcode
- [ ] the name in the confirmed spelling
```

## Changes after feedback

| Request | Change |
|---|---|
| "add a product" | a new entry in `labels[]` (and a colour if it is a new variant), rebuild; the book and labels change together; list photos with the old label as outdated |
| "change this colour" | the HEX, CMYK back to `converted` or `proposed`, rebuild, read the contrast matrix again |
| "make it like this case study" | only the presentation changes (headlines, order of part 1, images); the rules and values stay, the reference stays unnamed |
| "it's boring" | images first: cover, intro, worlds, product photos, billboard; then `meta.cover_colour` and `strategy.tagline`; the layout stays the template's |
| "it doesn't look like our site" / "it looks generated" | the brand's own template (`meta.template`, `references/data.md` section 9) in the site's system, real photos before generated ones; archive the old PDF, bump the version |
| "too long" | cut part 1 first, slide by slide: the mood photos (`slot` `other`), the billboard, then the worlds (both parts come from the same data, so they leave the web book too); send a designer the link with `?reader=designer` |
| "the printer wants the file" | the designer prepares it from the print section; `labels/*.pdf` are templates |
| "the proof is back" | CMYK `proofed` with the date, Pantone values, close the decision |
| "is this label legal?" | no verdict and no brand book: measure it (`render.mjs measure`), audit it with `references/labels-eu.md` section 7 and answer in the shape given there |

## Pitfalls

- **Asking the owner for HEX codes.** Take colours from their files, logo or site; ask in plain words ("which of these is closer?").
- **A gradient that imitates foil** goes to print as flat ink. Foil is a separate spot layer in the print section; the template only shows it.
- **A fallback font without a warning.** `render.mjs check` measures each face with two fallbacks; a missing "ł" shows as an error, not as a slightly different letter.
- **An example that breaks the book's own norms**, such as the client's current label shown as "the layout", needs the words "layout only" next to it.
- **A colour used but not defined**: the label text colour, a photo background. Every colour used anywhere is in `colours[]`.
- **A brand without packaging** (a service, a broker, a studio): `labels` stays empty, and the book drops the label slides and doesn't mention labels on the "Rules" divider. The print section stays, for cards, signage, roll-ups and vehicle graphics; the product-line slot goes to the services, shown as `imagery.worlds`.
- **A logo that exists only as a raster** (a PNG from the website): the variants are pixel recolourings and crops of that file, recorded as working copies, never a trace or a redraw; the vector master and a flat print version are decisions with a person and a date.

## Output

- `brand/`: `brand.json`, `book/index.html` (opens from disk, arrow keys move between slides; `?reader=designer` opens the designer's view), `labels/*.html`, `tokens.css` (the colour and type roles for a website or a video), `out/brandbook.pdf`, `out/labels/`, `out/shots/`, `00-input.md`, `01-verify.md` (internal), `02-system.md`.
- In the reply: the chosen direction and why; the palette and typefaces and where they come from; what each reader finds; the placeholders and open decisions with people and dates; what wasn't checked (a printer's proof, the legal review, image generation); the commands to rebuild.
