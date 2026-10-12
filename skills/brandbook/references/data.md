# brand.json, field by field

Read when you fill or change `brand.json`. Start from `assets/brand.example.json`, a fictional coffee roastery that uses every field except the photographs (a fictional brand has none; the image fields are below). JSON has no comments, so the rules for each field are here. Paths in the file are relative to the folder that holds `brand.json`.

## Contents

1. [meta and sections](#1-meta-and-sections)
2. [strategy and voice](#2-strategy-and-voice)
3. [logo](#3-logo)
4. [colours and pairs](#4-colours-and-pairs)
5. [type](#5-type)
6. [imagery and applications](#6-imagery-and-applications)
7. [labels](#7-labels)
8. [print, files, decisions, references, changelog](#8-print-files-decisions-references-changelog)
9. [A brand's own template](#9-a-brands-own-template)

## 1. meta and sections

- `meta.name`: the exact spelling. `name_confirmed`: true only after the user confirmed it.
- `meta.language`: `pl` or `en`, the language of the book's own labels ("Czytam jako", "Pobierz"). The content is in whatever language you write it.
- `meta.version`, `date` (YYYY-MM-DD), `owner` (who answers questions about the book), `contact`, `status` (`draft` or `approved`), optional `made_by`.
- `meta.cover_colour` (optional): the colour id for the dark feature tiles, the "Rules" divider and the closing slide; by default the accent when text on it reads, otherwise the text colour.
- `meta.radius` (optional): the tile corner radius in px on a 1920 × 1080 slide; 20 by default, 0 for a hard-edged brand.
- `meta.label_approver`: the person who approves labels before print (the regulatory role); `"(do wskazania)"` until someone is named. The book prints it under every label.
- `meta.home`: where the current version of the book and the files lives (a link or a shared folder), shown on the quick reference. The most common reason a brand book goes unused is that nobody can find it; without `home`, `check_brand.py` warns.
- `meta.company` (optional): the data that goes on offers, letters and the e-mail footer: `name` (the registered name), `tax_id` (NIP), `address`, `register` (KRS and court, share capital: only for a company that has them; a sole trader shows the NIP and the address). A missing value is a placeholder listed in `01-verify.md`, never a guess.
- `sections`: one headline per section, "Topic: rule" in plain words ("Kolory: żółty tylko na przyciskach i ważnych liczbach"), up to about eight words, no wordplay. Keys: `start`, `strategy`, `positioning`, `voice`, `applications`, `logo`, `colour`, `type`, `imagery`, `labels`, `print`. A missing key falls back to the topic name, and `check_brand.py` warns.
- `quickref.rules`: up to five rules someone needs on their first day, written as instructions ("Take the logo from the files, never from a screenshot"). The quick reference slide comes right after the cover with the logo, the core colours, the typeface and its substitute, these rules, the contact and `meta.home`. Without `rules` it falls back to the section headlines.

## 2. strategy and voice

The text people copy is in this section, so every field is a rule or a sentence someone can use, not a description of the brand. Three tests before a sentence goes in: could a competitor say it with their name in it; does it rule anything out; is there a fact behind it. A sentence that fails all three goes. Keep every item to one line (about 12 words); the book is read, not studied.

- `strategy.tagline`: the brand's line, short (best under 35 characters); it is the cover and the quick reference. Without it the cover shows the name.
- `strategy.purpose`: one or two sentences, why the brand exists, said as what it does for whom; the intro slide leads with it.
- `strategy.story` (optional): two or three sentences under the purpose. `strategy.fact` (optional): `{value, label}`, one big true number or fact from the brief ("od 2019", "4 sezony").
- `audience`: who gets the most from the brand, in their situation ("owners of small firms who need a machine, including those turned down by a bank"), not "everyone who…".
- `instead_of`: what the customer would do without the brand, in one or two sentences. `alternatives[]` (optional) is the same as a comparison, which positioning starts from: `alternative` (what the customer does instead: a bank, a dealer's finance, doing it themselves, nothing), `problem` (what goes wrong there), `we` (what the brand does about it). With `alternatives` or dated `proof` the book adds a positioning slide; `sections.positioning` is its headline.
- `category` (optional): the frame in which the customer compares the brand ("a leasing broker for small firms"), one phrase.
- `proof[]`: facts from the brief and the client's data only, each `{fact, source, date}` (a brand's own template may add `value`, the big number, and `top`, the question above it, and show proof as stat cards; `fact` is then the card's label under the number, so it reads as a fact only next to `value`, and such data needs that template, not the default one's proof list); a plain string still works, but `check_brand.py` warns that a number without a source and a date can't be checked or refreshed. Ratings, counts and records go stale: the date is part of the fact.
- `values` (`value` + `behaviour`: what people do, not an adjective), `decision_rules` (2–3 for cases the book doesn't cover), `signature` (the one element that belongs only to this brand).
- `rejected`: looks and habits the brand avoids, each written as a don't for whoever makes materials, with the reason in the brand ("Navy and gold like a bank: we are not a bank"). The client reads this list: the reasoning against model defaults (cream with terracotta, near-black with an acid accent) stays in `02-system.md`.
- `voice.traits`: pairs `is` / `is_not` ("plainly", "not dryly"). `tone`: per channel, `how` and a real `example`. `words_use`, `words_avoid`, `before_after`, `name_rule`.
- `voice.situations[]`: the moments where tone matters most, 3–6 from the brand's real work (an enquiry, a quote, waiting for a decision, a refusal, a bad review): `moment`, `example` (a line as the brand writes it), `avoid` (the line it doesn't write), optional `rule` only when the example doesn't show it. The pair of lines teaches more than a rule. The book shows them with `before_after` on the "In practice" slide.
- `voice.boilerplate`: the description people paste into a profile, a listing, an offer or a press note: `line` (one sentence, up to about 25 words) and `short` (about 50 words). Facts from `proof`, no adjectives a competitor could use.
- `voice.fixed_lines[]` (optional): lines that always appear in a given place, `text` and `where` ("We are an intermediary, not a bank": every ad that names terms). When the line may be a legal duty, the rule says where it goes and `01-verify.md` asks who confirms the duty; the book never states the law.
- `voice.editorial[]` (optional): up to three house-style rules, one line each: quotation marks, dashes, numbers, currency, dates, non-breaking spaces (in Polish „…”, a spaced en dash, `15–30%`, `1 200 zł`, a non-breaking space after one-letter words).
- `voice.claims`: health or nutrition claims the brand may use, each with `register_ref` (the EU register entry). Without one, `check_brand.py` errors. Leave it empty rather than invent.

## 3. logo

- `variants[]`: `id`, `name`, `file` (SVG from the client, never redrawn), `use`, `min_px` (screen), `min_mm` (print), `on` (colour ids of backgrounds it may sit on). The first variant is the primary. A variant whose id contains `neg`, `white`, `light` or `inverse` is used on dark backgrounds when `on` doesn't decide.
- `clear_space`: `defined_as` (a part of the mark: "the height of the letter O") and `ratio` (its share of the logo height, used to draw the diagram). Never mm or px.
- `dont[]`: `rule` (a short imperative) and optional `demo`: `stretch`, `squeeze`, `rotate`, `shadow`, `recolor`, `busy` or `on-accent` (the primary logo on the accent colour, for a logo whose own colour disappears there), drawn on the primary logo. The book shows the first four.
- `finish` (optional): `type` (`foil`, `emboss`, `none`), `min_line_mm`, `min_mm`.
- `partners` (optional, when the brand shows other companies' logos: lenders, suppliers, sponsors): `rule` (how the logos stand next to the brand's: where, how large, in which colour; the sender leads and the identities never blend) and `dont[]`. Whether the brand may use those logos at all is a question for `01-verify.md`, with who confirms it.

## 4. colours and pairs

- `colours[]`: `id` (lowercase, used everywhere else), `name` (the brand's own name for it), `role` (`background`, `text`, `secondary-text`, `accent`, `line`, `support`), `hex`, `share` (percent of use), `cmyk` (`value` [c, m, y, k], `profile`, `status`, `source`, `date` when proofed), `pantone` (`c`, `u`, `status`).
- The book takes its own look from the roles: the first `background`, `text`, `secondary-text`, `line` and `accent`. So do `tokens.css` and the label text colour.
- `pairs[]`: text and background ids with their `use`. Name at least body text on the background. The book draws a contrast matrix of all text and background colours and outlines the declared pairs.

## 5. type

- `families[]` (one or two): `family` (the CSS name), optional `name` (what the reader sees on the type slide, when the CSS name is an alias), `role` (`display`, `text`, `numerals`), `fallback` (the CSS stack after it, e.g. `Georgia, serif` for a serif; default `system-ui, sans-serif`), `files` (paths, or objects `{file, weight, style, stretch}` for static weights; a plain path is treated as a variable font 100–900), `weights`, `licence`, `licence_file`, `source`, `why` (one sentence, this brand), `office_substitute` (a font available in Word, Google Docs and Canva), `reflex_reason` (only when the family is on the reflex list). One variable family can give two cuts: a second entry with its own CSS `family` (an alias), the same file, a fixed `weight` ("600") and `stretch` ("108%"), and `name` saying what it is ("Archivo SemiBold 108%"); the browser clamps the axes to these values, so every headline in the book is set in that cut.
- `scale[]`: `level`, `role`, `px`, `pt`, `line`, `use`.
- `sample`: a sentence with the language's accented letters, shown in every face.

## 6. imagery and applications

- `imagery`: `light`, `composition`, `casting`, `props`, `styling`, `grading` (all six, each a rule a photographer can follow), `do[]`, `dont[]`, `ai` (`allowed`, `banned`, `label`, `approver`).
- `imagery.mood_headline` (optional): the headline of the photo mosaic slide, when its photos say more than the topic name ("Tylko prawdziwe odbiory").
- `imagery.images[]`: `file`, `alt`, `generated` (the slide footer then says `imagery.ai.label`), `caption` (optional text on the photo), `pos` (CSS object-position), `slot`: `cover` (the cover photo, landscape), `intro` (the intro slide, portrait), anything else goes into the photo mosaic. `imagery.hero_on`: the colour id closest to the part of the cover photo under the logo (top left), so the book picks the variant that reads there: a light id for a bright window or sky, a dark one for shadow. Look at the cover after the build; the book can't measure a photo opened from disk.
- `imagery.worlds[]` (optional, the strongest slides when the brand has variants): `name`, `colour` (id), `image` (a scene in that colour, landscape), `detail` (a portrait or close-up), `line`, `generated`. One overview slide and one slide per world, up to four.
- `applications[]`: `id`, `kind` (`post`, `card`, `email`, `web`, `billboard`), `title`, `headline`, `text`, optional `background` (a colour id; a post defaults to the text colour, the rest to the background) and `image` (covers the mockup). A `billboard` needs an `image` and gets a full slide with the headline and the logo: `headline_at` (`top` or `bottom`, where the photo is calm; at the top the logo sits under the headline, at the bottom it takes the top right corner), `text_colour` (a colour id or HEX; white by default) and `logo_on` (the colour id the logo variant should suit). The book draws each one at its real size from the tokens and places the logo at no less than its minimum, so a mockup can't break the book's own rule.

## 7. labels

- `id` (lowercase letters, digits, hyphens: it becomes the file name), `product`, `category` (`food`, `supplement`, `cosmetic`, `other`), `colour` (a colour id for the label field), `status` (`template`), optional `image` (a product photo for the product-line slide; without it the slide shows the label template on its colour).
- `format`: `name`, `w_mm`, `h_mm` (trim size), `bleed_mm`, `safe_mm`, `largest_surface_cm2` (decides 1.2 or 0.9 mm x-height), and for a wrap-around label `overlap_mm` and `overlap_side` (`left` or `right`: the end the other one covers). Zones may span the full width; the template keeps content out of the overlap and hatches it in the guides.
- `zones[]`: `id`, `role` (`front`, `info`, `legal`), `x_mm`, `w_mm`, laid left to right across the width (a wrap-around label: legal, front, info). One `front` zone carries everything when there is nothing else; then the net quantity sits under the name.
- `front`: `name`, `variant`, `benefit`, `net`. `info[]`: `label` + `text` (usage, origin, roast date). `legal[]`: `key` + `label` + `text`; the keys per category are in `references/labels-eu.md`.
- `nutrition_exempt_reason` when a food is exempt from the nutrition declaration (with the legal basis, to confirm).
- `barcode`: `ean` (13 digits from the client, or null) and `note`. The template draws a box with the size, never bars.
- `legal_pt`, optional `name_pt`, `variant_pt`, `net_pt`: type sizes in points. `render.mjs check` measures the real x-height of the mandatory text and the height of the net quantity's figures, and tells you the size to set.

## 8. print, files, decisions, references, changelog

- `print`: `printer` (null until chosen), `technology`, `pdf`, `profile`, `bleed_mm`, `safe_mm`, `small_text`, `finishes[]` (`type`, `colour`, `layer`), `proof`.
- `files[]`: `path` (a file or a folder), `what`, `print_ready` (true only for files a printer can use as they are; leave it out for files where the question doesn't apply). Not a slide: `check_brand.py` checks the files exist, the print slide lists the print-ready ones, the quick reference links the logo. Built and rendered files (`book/`, `labels/`, `out/`, `tokens.css`) only warn until they exist.
- `decisions[]`: `what`, `who`, `by` (date), `recommendation`, optional `blocks: true` for a decision that stops someone using the book (no print logo, no printer). Every open question gets your recommendation, so the client confirms or overrides instead of starting from nothing. The deck doesn't show them: they are the handover list in `01-verify.md` and in the reply, the blocking ones first. Recommendations are written for the client: no field names, file paths or tools.
- `references[]`: `name`, `layer` (`structure`, `presentation`, `photography`), `borrow`, `not`. Internal: never shown in the book.
- `changelog[]`: `version`, `date`, `change`, written as what changed for the reader ("real photos instead of visualisations"), not who asked for it.

## 9. A brand's own template

The default deck is a neutral mosaic. When the brand already has a working system (a live site with its own type, grid and components) and the client says the book doesn't look like the brand, the book takes the site's system instead: `meta.template` points to an HTML file next to `brand.json` (e.g. `template/book.html`), built from the default template's contract and the site's CSS, not from the mosaic.

The template keeps:

- the placeholders `/*__FONT_FACES__*/` and `/*__BRAND_DATA__*/` (the build refuses a template without them);
- `<script id="brand-data">`, `<main id="main">` and `window.__bookReady` (resolves after fonts and images);
- every slide as `.frame > .slide` at 1920 × 1080, the cover as `main > .frame.cover#top`, each topic as `main > section.s[id]` with `data-readers`, a `.pno` page number per slide, and print CSS `@page { size: 1920px 1080px }` with `.frame { break-after: page }`;
- `[data-logo][data-min-px]` on every logo image, `figure[data-generated="true"]` on generated images with the slide's `.foot[data-ai]` naming them, `.t[data-text]` on fixed-size text boxes so `render.mjs check` measures overflow;
- the quick reference right after the cover (`section.s#start`), and every strategy and voice field the data has: `purpose`, `audience`, `instead_of` or `alternatives`, `proof`, `quickref.rules`, `voice.situations`, `voice.boilerplate`, `voice.fixed_lines`, `voice.name_rule`, `meta.company`. `render.mjs check` looks for the start of each in the rendered text and errors on a field the template drops; a custom template that lost the audience is how a book ends up without saying whom it is for.

Data the default template doesn't read (a comparison, case cards, an illustration set) goes into `brand.json` under the section it belongs to, so the one-source rule still holds; `check_brand.py` ignores keys it doesn't know. Keep `imagery.images` listing every photograph the custom template shows (with `generated` and a caption), even when the template reads its own list such as `imagery.cases`: the checks and the AI captions work from `imagery.images`, so the two lists name the same files and change together. Copy values from the site's CSS (colours, radii, sizes, weights), not impressions of it, and record in `02-system.md` that the book follows the site.

