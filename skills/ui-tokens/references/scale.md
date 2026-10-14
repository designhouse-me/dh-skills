# A scale for a project that has none

Use these defaults only when the project has no scale and neither the user nor a brand book gives values. They follow what large systems converge on (Tailwind, Material, Carbon, Atlassian, Polaris, GOV.UK) and the typographic canon (Bringhurst, Butterick, Utopia). Snap the values the project already uses to these steps before adding anything new.

## Contents

1. [Spacing](#1-spacing)
2. [Type](#2-type)
3. [Colour and radius](#3-colour-and-radius)
4. [Naming](#4-naming)
5. [Template](#5-template)

## 1. Spacing

- **Base 4px**, with 2px only for hairline details. A 4px base gives the middle steps (12, 20) an 8-only scale lacks.
- **Steps get sparser as they grow.** A linear 4, 8, 12, 16, 20, 24, 28… offers choices too close to tell apart ("When do I use 24 or 28?", Nathan Curtis). Default: 4, 8, 12, 16, 24, 32, 48, 64, 96, 128.
- **Ranges by role** (after Atlassian): 4–8 inside compact controls (icon to label, label to field), 12–24 inside components (card padding, list rows), 32–64 between groups, 64–128 between page sections.
- **Proximity:** space inside a group is smaller than space between groups, and a heading has more space above it than below.
- **Fluid section spacing** is allowed as a token (`--space-section: clamp(…)`) built the same way as fluid type below.

## 2. Type

- **5–7 roles**, not a size per element: caption, small, body, lead, h3, h2, h1, plus a display size for a hero when the design needs one.
- **Ratio:** about 1.125–1.2 for dense UI, 1.25–1.333 for marketing and editorial pages. Multiply from the body size, round to whole pixels, and drop a step that differs from its neighbour by less than about 10%. Material and Tailwind both round and skip by hand; a pure ratio is a starting point, not a rule.
- **Example** (body 16px, ratio 1.25): caption 12, small 14, body 16, lead 20, h3 24, h2 32, h1 40, display 48 and up.
- **Body text** at least 16px on screen (Butterick gives 15–25px); nothing functional below 12px (Apple and Material stop at 11 for labels).
- **Leading and tracking** per role as `ui-without-slop/references/text-hierarchy.md` sets them, stored as unitless tokens (`--leading-tight`, `--leading-body`) so they follow the font size.
- **Measure:** `--measure: 65ch` on running text. Bringhurst gives 45–75 characters, Every Layout caps at 60ch, GOV.UK at 75.
- **Fluid headings** (Utopia's method): choose the size at a small viewport and at a large one, then interpolate:

  ```
  slope     = (max_px - min_px) / (max_vw - min_vw)
  intercept = min_px - slope * min_vw
  clamp(min, intercept + slope * 100vw, max)
  ```

  h1 from 32px at 360px to 48px at 1240px: `--text-h1: clamp(2rem, 1.5909rem + 1.8182vw, 3rem)`. Both ends are steps of the scale, and the token lives in the token file.

## 3. Colour and radius

- **Colour:** the 4–6 named values from the visual decision (`ui-without-slop`), neutrals tinted towards the accent. Components use roles only: `--color-text`, `--color-muted`, `--color-surface`, `--color-accent`, `--color-border`, `--color-focus`. With many shades, keep primitives (`--clay-600`) in the token file and point the roles at them.
- **Radius by role**, not one value for everything: `--radius-control`, `--radius-card`, `--radius-image` (may be 0) and `--radius-pill: 999px`.

## 4. Naming

| Tier | What it holds | Example | Who uses it |
|---|---|---|---|
| primitive | the raw step | `--space-5: 1.5rem` | only other tokens |
| semantic | the role in the interface | `--space-section: var(--space-9)`, `--color-text: var(--ink-900)` | components |
| component | one component's choice | `--card-padding: var(--space-5)` | that component |

Material calls these reference, system and component tokens; Brad Frost calls them tiers 1–3. Number primitives by step (`--space-1`…`--space-10`), never by pixel value (`--space-13px`), so a rescale doesn't make the names lie. Name everything a component touches for its role.

## 5. Template

```css
/* tokens.css: the only file with literal values. Import it before everything else. */
:root {
  /* space: base 4px, sparser as it grows */
  --space-1: 0.25rem;  /* 4 */
  --space-2: 0.5rem;   /* 8 */
  --space-3: 0.75rem;  /* 12 */
  --space-4: 1rem;     /* 16 */
  --space-5: 1.5rem;   /* 24 */
  --space-6: 2rem;     /* 32 */
  --space-7: 3rem;     /* 48 */
  --space-8: 4rem;     /* 64 */
  --space-9: 6rem;     /* 96 */
  --space-10: 8rem;    /* 128 */

  /* type roles */
  --text-caption: 0.75rem;
  --text-small: 0.875rem;
  --text-body: 1rem;
  --text-lead: 1.25rem;
  --text-h3: 1.5rem;
  --text-h2: 2rem;
  --text-h1: clamp(2rem, 1.5909rem + 1.8182vw, 3rem);
  --leading-tight: 1;
  --leading-body: 1.5;
  --measure: 65ch;

  /* colour roles (values from the visual decision) */
  --color-text: #1d1d1b;
  --color-muted: #5c5a55;
  --color-surface: #faf8f3;
  --color-accent: #c2410c;
  --color-border: #dcd8cf;
  --color-focus: #c2410c;

  /* radius by role */
  --radius-control: 6px;
  --radius-card: 12px;
  --radius-pill: 999px;
}
```

In Tailwind v4 the same values go in `@theme` under the `--spacing-*`, `--text-*`, `--color-*` and `--radius-*` namespaces, so they become utilities (`p-4`, `text-body`, `bg-surface`, `rounded-card`). To make them the only steps, reset each namespace first: see `enforcement.md`.
