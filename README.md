<a href="https://designhouse.me"><img src=".github/banner.svg" alt="Design House. Skills for AI agents: research, websites, motion design." width="100%"></a>

# Design House Skills

Skills for AI agents from [Design House](https://designhouse.me). They work in Claude, ChatGPT, Codex, Cursor and other tools that support the [Agent Skills](https://agentskills.io) format.

How we wrote them: [Skills for AI. How to teach Claude and ChatGPT your job](https://designhouse.me/wiedza/skille-dla-ai-jak-pisac) (in Polish).

## Installation

```bash
npx skills add designhouseme/AdvancedSkills
```

Manually:

```bash
git clone https://github.com/designhouseme/AdvancedSkills.git
mkdir -p ~/.claude/skills
cp -r AdvancedSkills/skills/* ~/.claude/skills/
```

In Codex and Cursor, use `~/.agents/skills` instead of `~/.claude/skills`.

## Skills

You don't have to name a skill. Describe the task and the agent picks the right one.

| You want to | Say, for example | Skill |
|---|---|---|
| get a whole website for a local business | "make a website for Nowak Joinery from York, tel. …" | `business-website` |
| know a company before a meeting or a proposal | "research Nowak Joinery, we meet them on Thursday" | `company-research` |
| plan a site's sections and write its copy | "plan the website from this research" | `website-plan` |
| code a site from an approved plan | "build the site from the plan" | `website-build` |
| get an honest score for a finished site | "review this site before we show it to the client" | `website-review` |
| make an interface stop looking AI-made | "it looks generated: dots everywhere, Inter and Lucide again" | `ui-without-slop` |
| write or fix a text so it doesn't read as AI-made | "this About section sounds like ChatGPT, rewrite it and keep the facts" | `copy-without-slop` |
| make a video or an animation from code | "a 20-second promo for our app, also as a 9:16 reel" | `motion-design` |
| add or fix motion inside a website or app | "make the cart panel animate smoothly even when I close and reopen it quickly" | `ui-motion` |
| edit a recorded talking-head video | "cut repeats and pauses, add captions and a motion insert at this sentence" | `video-edit` |
| get a brand book the owner, the designer and the printer can each use | "a brand book for our herbal teas, the designer needs clear label rules" | `brandbook` |

### A website: four stages in one request

`business-website` doesn't do the work itself. It runs the four skills below in order and keeps their results in the `brief/` folder, so you can stop at any point and pick up in a new session.

| Step | Skill | Result |
|---|---|---|
| 1. Research: what the company really does and what its customers say, every fact with a source and a date | `company-research` | `brief/01-research.md` |
| 2. Plan: 4–7 sections built around the customer's decision, finished copy, the visual direction | `website-plan` | `brief/02-plan.md` |
| You approve the headline and the sections (skipped if you ask for no questions) | | |
| 3. Build: the site in your project's stack or as static HTML, screenshots on mobile and desktop | `website-build` | the site, `brief/screenshots/` |
| 4. Review: an independent score and at most five fixes, then at most two rounds of fixes | `website-review` | `brief/03-review.md` |

Each stage also works on its own, e.g. research before a sales meeting or a review of a client's current site.

The chain follows **proof over promise**: concrete methods, people, materials and documented results support the customer's decision. The plan defines what the hero, a quick scan and a full read should communicate, including the 5/15/30-second priorities, the result, time, effort and next steps. Forms follow the actual process; bonuses, deadlines and guarantees appear only when supported by the offer.

### Interfaces: `ui-without-slop`

Removes the look of AI-made interfaces and replaces each pattern with a design decision. It works on any interface, not only on sites from the chain above (`website-build` runs it before handing over). It covers:

- **decorations:** dots, pills above headings, eyebrows, gradient text, purple gradients, glassmorphism, identical cards;
- **typefaces:** the fonts models reach for by reflex, and how to choose instead, with the licence and accented letters checked;
- **text hierarchy:** reading order, jumps in size and weight, a headline set as one lockup;
- **icons:** when a place needs one at all, and how to choose a set instead of Lucide by default;
- **component kits:** shadcn/ui and Magic UI restyled, with their keyboard behaviour kept.

### Text: `copy-without-slop`

Writes, edits and reviews any text people will read (a website, an email, a post, an ad, a product description, a reply to a review, an article) so it sounds like someone who knows the business wrote it. It works from the facts and the customers' own words, decides the voice before drafting, and only then edits out the patterns that make text read as generated, each replaced with a fact or cut. It covers:

- **invented details:** numbers, years, promises and benefits that aren't in the notes, including numbers written as words;
- **patterns:** contrast with a claim nobody made, reflexive threes, "-ing" tails, ad words, stock openers and closers, polished testimonials, and the substitutes models reach for after a ban;
- **someone else's text:** the smallest change that fixes it, and a text that already works comes back almost unchanged;
- **Polish:** calques, nominal style, ty or Państwo, „…”, dashes;
- **a check script** that lists candidates for a decision and checks numbers against the notes.

`website-plan` uses it for the words of a site.

### Brand book: `brandbook`

Builds a brand book from a brief, the logo and product data. Everything comes from one `brand.json`, so the parts can't drift apart:

- **a quick reference** right after the cover: the logo, the core colours, the typeface and its office substitute, five rules, whom to ask and where the current version lives;
- **text people can use**: positioning from the customer's real alternatives, proof with sources and dates, tone in the situations the business writes in every day, the description in one sentence and in fifty words; field names, build files and tool names never reach the client's text (the checks flag them);
- **an interactive deck** of 16:9 slides in one web page, in two parts, the brand and the rules: photo, colour and type tiles, a "reading as" filter (owner, designer, printer, marketing), colour values to copy, a contrast matrix and label previews; the PDF is the same slides, one per page. Photos make part 1: the client's, or photorealistic visualisations made with Codex when it's on the machine (product shots take the label render as a reference and are read letter by letter); without them it falls back to colour and type;
- **label templates in millimetres** with bleed, safe margin and zones, checked for overflow and for the 1.2 mm x-height of mandatory food text;
- **colour per medium** with the CMYK profile and the status of every print value (proposed, converted, proofed);
- **an internal list to verify** before print, and `tokens.css` for `motion-design` and websites.

It needs Python 3, Node 22+ and Chromium or Chrome on your machine. It flags label law for a regulatory person and doesn't design a logo from nothing.

### Video: `motion-design`

Motion design from code in the brand's colours, fonts and logo: a showreel, a product promo, a logo intro, 9:16 reels. You get an MP4, a version small enough to send and an animated WebP for a README. It needs Node 22+, Python 3, ffmpeg and Chromium or Chrome on your machine.

An optional `film.json` compiles scene timing, cues and hard cuts into one frame-aligned timeline. The renderer checks local assets, can compare captured pixels across reordered seeks, awaits async frame work and keeps short audio from truncating the video. The final-film review scans every decoded frame and produces timestamped sheets and a report tied to the artifact's hash. Visual judgement and audio listening remain separate checks.

### Interface motion: `ui-motion`

Works with an existing interface and its animation stack: CSS or WAAPI for small interactions, Motion for React state/layout, and GSAP for timelines or scroll scenes. It covers interruption, repeated input, component cleanup, keyboard and touch behavior, dynamic reduced-motion preferences and visible static content. It integrates existing Lottie assets; creating them or rendering a standalone film is outside its scope.

### Recorded video: `video-edit`

Edits talking-head footage from a transcript while keeping cuts and motion inserts tied to source timestamps. Repeated source ranges can have segment IDs so an insert targets the intended occurrence. `motion-design` creates a requested insert; `video-edit` places it in the footage. Use its existing transcription and subtitle tooling rather than a second motion renderer.

Behavioral evaluation briefs and routing cases are in `evals/`. Runtime regression tests are in `tests/`; run `python3 -m unittest discover -s tests -v`. Renderer tests require local Chromium, Node 22+, FFmpeg and ffprobe. Evaluation briefs are specifications, not proof that every scenario has been executed.

## License

[CC BY 4.0](LICENSE). When you use them, credit the author: Design House, https://github.com/designhouseme/AdvancedSkills.

Exceptions: the Urbanist font in `skills/motion-design/assets/fonts/` is under the SIL Open Font License 1.1 (`OFL.txt` next to it), and the license doesn't cover the Design House name, mark and logo.

<br>

<p align="center">
  <a href="https://designhouse.me">
    <picture>
      <source media="(prefers-color-scheme: dark)" srcset=".github/logo-white.svg">
      <img src=".github/logo-dark.svg" alt="Design House" height="28">
    </picture>
  </a>
</p>
