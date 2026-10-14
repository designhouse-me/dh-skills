---
name: website-build
description: Codes a short business website from the approved plan in brief/02-plan.md, then checks the render on mobile and desktop. Use when the website plan is ready and the site needs to be built, or when changes are needed in the code of a site built from that plan (layout, responsiveness, images), including fixes from a review. Doesn't write new copy (that's website-plan), doesn't assess the finished site (that's website-review), doesn't do SEO audits and isn't for general fixes or debugging of other projects.
license: CC-BY-4.0
metadata:
  author: Design House
  version: "1.6"
---

# Website build

The plan is a contract. The build translates it into code faithfully and checks the result on a real render, not on what the code claims.

## Rules that always apply

- **Take the copy from the plan verbatim.** If a text doesn't work in the layout or a section seems redundant, go back to website-plan. Don't add promises in the code.
- **Contact details 1:1 from the plan**, which means from the user. Never from the internet.
- **Images match their truth status.** Stock or generated images never go where the slot is marked as a project, the team or the company's premises. Flag a missing photo in the output instead of substituting fiction.
- **No deploying to a server, buying domains or sending forms to external addresses**, unless the user explicitly asks for it.
- **Don't announce that the site "looks good" if you haven't seen the render.** Without a screenshot tool, say so plainly.

Input: `brief/02-plan.md`. If `brief/03-review.md` exists with status `NEEDS_CHANGES`, fix only the items assigned to website-build.

## 1. Stack

Use the stack already in the project and its conventions. In an empty folder, build a static site: `index.html`, `styles.css`, an `images/` folder, and JavaScript only where it's genuinely needed. A site like that works without installation and can go on any hosting.

## 2. Hero first

The hero accounts for most of the first impression. Build it first, take screenshots at 375×812 and 1440×900 and run the 5-second test: what the company does, for whom or where, why to consider it, what to click. The H1, clarification, CTA and at least part of the proof or image are visible without scrolling. Only then build the remaining sections in the plan's order. Polished sections further down won't fix a weak first screen.

## 3. Rules of this process

- **One plan section is one `section` with one `h2`**, in the plan's order. Menu anchors offset for the sticky header.
- **CTAs are real links** (`tel:`, `mailto:`, booking). A form only when the plan sets it as the main channel.
- **Forms follow the plan's lead goal.** Collect only fields needed for the next step or justified qualification. Reuse available visitor data instead of asking for it again, and retain entered values after validation errors. Show a sent confirmation only after a successful submission response; a demo or form without a configured backend must clearly say it does not send. The confirmation explains the completed action and the next step specified in the plan.
- **Design mobile separately**, don't just collapse desktop into one column: the order, image size and CTA placement may differ.
- **Make the evidence readable when scanning.** Headings, meaningful images, captions and CTAs carry the plan's argument; keep proof visibly connected to the claim it supports. Follow planned layout variation at important points to renew attention without making the reading order unclear or adding motion for its own sake.
- **Typography and colours follow the visual direction in the plan.** Fonts self-hosted as WOFF2 with the language's accented letters, not loaded from Google's servers at runtime. Icons: the project's own set if it has one; otherwise first check whether the place needs an icon at all, then choose the set as the ui-without-slop skill describes, not Lucide by reflex. Never hand-drawn or Unicode characters.
- **Values come from tokens.** Spacing, font sizes, colours and radii are declared once in a token file and the sections use only those tokens; a value no step fits becomes a new named token. The ui-tokens skill has the default scale and the check.
- **Photos stored locally in the project**, no hotlinking. Record origin and licences in `brief/media.md`, not on the site. The logo always comes from the company's original file, never recreated with a font.
- **Motion only where it explains something** (feedback, a change of state, where something came from), not the same fade-up on every section. About 100 ms for feedback and 200–300 ms for a panel are starting points; choose timing from the task and travel distance. Prefer `transform` and `opacity`, then measure the affected path; compositing alone does not guarantee smoothness. Use `ui-motion` for substantial interaction, layout or scroll choreography while this skill keeps ownership of the approved site's build.
- **Motion that respects the visitor.** Content and CTAs are visible without JavaScript and without waiting for an entrance animation; an element at `opacity: 0` doesn't count as the page's main content (LCP) until it appears. With `prefers-reduced-motion`, keep the same state changes while removing unnecessary travel and loops; an immediate update or small fade may fit. Handle preference changes while the page is open. Auto-started moving content that lasts over 5 s alongside other content needs a pause, stop or hide mechanism unless essential, as WCAG 2.2.2 requires. Don't take over scrolling, and don't use parallax as decoration.
- **JSON-LD `LocalBusiness` with data 1:1 from the user.** Opening hours only if you know them.

## 4. Verification before handoff

Copy this list into your reply and tick it off:

```md
- [ ] lint and build pass (if the stack has them); no console errors
- [ ] full-page screenshots at 375×812 and 1440×900 in brief/screenshots/ (also 768 and 1024 for layouts with absolute or sticky elements or large SVGs)
- [ ] the H1, H2s, meaningful images/captions and CTAs alone in the screenshots make the same argument as the scan test in the plan
- [ ] the strongest proof is before the halfway point of the page
- [ ] numbers in tel: and addresses in mailto: match the plan
- [ ] no horizontal scrolling; anchors don't hide under the header; the mobile menu works with a keyboard
- [ ] real content and states: the longest heading and the email address fit at 375 px; the form (if any) retains input after errors and shows a truthful success or demo state with the planned next step
- [ ] one h1; every image has alt (empty if decorative), width and height; the hero image isn't lazy-loaded
- [ ] text contrast at least 4.5:1; visible focus; form fields have labels
- [ ] lang, title and meta description from the plan; Open Graph
- [ ] no em dash (—) in visible copy
- [ ] the ui-tokens check reports no errors: spacing, font sizes, colours and radii come from the token file
- [ ] run the ui-without-slop skill: no decorative dots, pills above headings, eyebrows, gradient text, identical cards, decorative icons or a component kit at its default theme
- [ ] motion: repeated input and interruptions settle in the correct state; reduced motion works at load and when changed; long automatic motion has a pause where required; the hero remains visible without animation JavaScript
- [ ] LCP and CLS without obvious problems (if you have a measuring tool)
```

Don't mask problems by shrinking the font or using `overflow: hidden`. Fix the grid, the widths or the breakpoint.

## Pitfalls

- **A screenshot taken too early** shows unloaded images or a frame of an entrance animation. A screenshot like that isn't evidence. Wait for the images and for animations to finish.
- **A full-page screenshot with a sticky header** can duplicate the header in several places. Turn off sticky for the screenshot or capture screen by screen.
- **Pause on hover isn't a pause on a phone.** A marquee or carousel that stops only under the cursor keeps moving on touch screens. Give it a button, or stop it after one pass.
- **"Full width" applies to the section background, not the paragraphs.** Put `max-width` and centring on an inner wrapper, not on the section itself.
- **Text over a photo** can be readable at 375 and 1440 and overlap the subject at 768–1024. With text over a photo, check the in-between widths too.

## Output

- The site code and a command to view it locally.
- `brief/screenshots/` with the screenshots and `brief/media.md` with the list of images used (file, source, licence, truth status).
- A short list of what couldn't be done (e.g. no project photos, no screenshot tool).

Next stage: website-review, ideally in a fresh context, if you're working in the business-website chain.
