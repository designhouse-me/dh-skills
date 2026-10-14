---
name: ui-tokens
description: >-
  Keeps spacing, font sizes, colours and corner radii on the project's declared scale when
  adding or changing UI. Finds the existing tokens (CSS variables, Tailwind @theme or config,
  SCSS variables, DESIGN.md), declares a scale in one file when there is none, uses only
  declared values, turns a genuinely new value into a named token, and checks the result with a
  script that flags literal px, rem and hex values, invented var() names and Tailwind arbitrary
  values such as p-[13px]. Use when adding a section, component or element to an existing
  interface or restyling one, and when someone says the spacing is random, font sizes are
  inconsistent, there are magic numbers or hardcoded values, the model "doesn't use variables",
  the design drifts, or asks for design tokens, a spacing or type scale, or a lint or hook that
  enforces them. Choosing the look itself is ui-without-slop, building a site from a plan is
  website-build, and animation is ui-motion.
license: CC-BY-4.0
metadata:
  author: Design House
  version: "1.0"
---

# UI tokens

Models write spacing and type sizes they never looked up. They generate plausible numbers ("if your system uses `--space-200` for 8px, the LLM might write `padding: 12px`"), copy the literals in the file next door, and a rule in the prompt alone still leaks: in Meta's Astryx tests, rules alone left raw CSS in about 11–13% of complex runs. So this skill does three things in order: read the system before editing, use only what it declares, and check the result with a script rather than from memory.

## Rules that always apply

- **The project's system wins.** If tokens exist (a token file, `:root` variables, Tailwind `@theme` or config, SCSS variables, a design-system package, DESIGN.md), use them, even where you'd have picked other numbers. Never add a second scale next to the first: two scales produce 13px and 22px that read as mistakes.
- **No literal values outside the token file** for margin, padding, gap, font-size, colour and border-radius. `0`, `auto`, `inherit`, a 1px hairline and `%` for position are fine. The rule covers `calc()`, `clamp()`, a `var()` fallback, a local `--gap: 13px`, an inline `style` and Tailwind's `p-[13px]` too.
- **Use only names that exist.** Before writing `var(--space-5)`, check that it is declared. An invented token name is worse than a literal: it renders nothing and looks correct in review.
- **A new value is a decision, not a number.** Try the nearest step first; most "it needs 13px" is 12 or 16. When no step fits, add a token to the token file named for its role (`--space-card-inset`, `--text-caption`), pointing at a primitive where one exists, and report it. A value one component needs stays a component token; it joins the global scale once three components need it.
- **Never change a token's value to fix one element.** A token moves every place that uses it. Change the scale only when the task is the scale, and list what it affects.
- **Text is set in roles, not sizes.** Each piece of text maps to a role (display, h1, h2, h3, lead, body, small, caption). A new element reuses a role; a new role needs a reason. Leading and tracking per role follow `ui-without-slop/references/text-hierarchy.md`.
- **The parent spaces its children:** `gap` in flex and grid, or a stack rule (`.stack > * + * { margin-block-start: var(--space-4) }`), not a margin on every child.
- **No suppression comments.** A value that has to stay becomes a named token, not a `stylelint-disable` or `eslint-disable`.
- **Old code isn't yours to rewrite unasked.** Lines you add or change must pass. Literals elsewhere are reported, not refactored, unless the user asks.

## 1. Read the system before editing

```bash
python3 scripts/check_tokens.py --system PROJECT_DIR
```

Run it from this skill's folder or with the full path. It lists the declared tokens by family (spacing, type, colour, radius) with their values in px, where they are declared, the Tailwind version and any theme reset, and a census of the literal values already in use. Open the token file as well: names carry roles the script can't see. Also look for `tailwind.config.*`, a theme object in JS, `_variables.scss`, DESIGN.md and `.interface-design/system.md`.

Don't infer values from names: `space-100` is 4px in Polaris and 8px in Atlassian. Read the number.

## 2. When there is no scale

Before the first UI edit, create one token file (`styles/tokens.css` imported first, or the `@theme` block in Tailwind v4) with spacing on a 4px base whose steps get sparser as they grow, 5–7 type roles, colour roles and radius by role. Derive it from what the project already uses: `--system` shows the most frequent literals; snap them to steps instead of inventing a fresh set. Default numbers, naming and a template are in `references/scale.md`. Values from the user or a brand book win over the defaults.

In a project with hundreds of literals, propose the migration as its own step. For the current task, declare the scale and apply it to the code you touch.

## 3. Edit

Map every new element before writing CSS: paddings and gaps to space steps, each text to a role, colours to colour roles, corners to a radius role. In Tailwind, use theme utilities (`p-4`, `gap-6`, `text-body`), no square-bracket values for these families and no `p-(--x)` to a property the theme doesn't declare. The default Tailwind theme accepts any multiple of 0.25rem (`p-13` is a valid class), so keep to the steps the project already uses.

Fluid sizes are tokens too. A `clamp()` lives in the token file with both ends on the scale, and components use the token.

## 4. Check

```bash
python3 scripts/check_tokens.py --changed PROJECT_DIR
```

`--changed` checks only lines added since the last commit; `--since main` checks a whole branch. In a folder without git, or for a new project, run it without `--changed`. Fix every ERROR: the note names the nearest declared tokens. Give each WARNING and CANDIDATE a decision in the reply (fixed, or kept because…). A clean run proves the values come from the system, not that the design is right.

Then re-read your diff once: replace any literal or bracket value with a token, and any token name you aren't sure of with one from `--system`. In Astryx's tests this one short re-read cut the leaks about fourfold, and a long mandatory audit did no better.

Where you can't run scripts, check the diff against the token file by reading, and say that the script didn't run.

## 5. Keeping it enforced

When the user wants the rule to hold across sessions, or the project keeps drifting, offer what's in `references/enforcement.md`. It changes the project, so set it up only when the user agrees:

- a Claude Code hook that runs this script after every edit and shows the errors to the model;
- Stylelint core rules for plain CSS;
- a Tailwind v4 theme reset with an ESLint plugin, so off-scale classes stop existing.

Turn a check on for a family only once its tokens are complete. Enforcing spacing before the scale exists makes the model invent token names.

## Pitfalls

- **Copying the file next door.** Literals already in the file aren't a precedent. Use the scale even when the neighbours don't, and report the neighbours.
- **The literal with extra steps:** `--gap: 13px` inside a component, `calc(var(--space-1) * 3.25)`, `var(--spacing, 13px)` with a name that doesn't exist, `style={{ padding: 13 }}`. The script flags each one.
- **Names by value.** `--space-13`, `--padding-card-13px`, `--blue-500` used as "the button colour". Primitive steps may be numbered; anything a component uses is named for its role.
- **Matching the parent's literal.** If the parent has `padding: 22px`, the child still gets a token; the parent goes in the report.
- **A fluid size per component.** `font-size: clamp(1.1rem, 2vw, 1.4rem)` written in a component is a type role nobody declared.
- **Classes that silently do nothing.** After a Tailwind theme reset, `p-3` or `text-lg` generate no CSS. The script reports them as removed steps.

## Output

- The tokens the new or changed elements use, and every token you added: name, value, role and why no existing step fit.
- The script result: errors fixed, each warning and candidate with its decision, and the line about older findings (left alone unless asked).
- If you created the scale: the file, its steps, and which existing values were snapped to which step.
