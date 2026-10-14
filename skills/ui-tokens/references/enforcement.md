# Keeping the scale enforced

Rules in a prompt leak; a check that runs on every edit doesn't. Everything here changes the project, so set it up only when the user agrees, and only for the families whose tokens are complete. Enforcing spacing before the scale exists makes the model invent token names, which is worse than a literal (Builder.io's field report).

## Contents

1. [Claude Code hook](#1-claude-code-hook)
2. [Plain CSS: Stylelint](#2-plain-css-stylelint)
3. [Tailwind v4: theme reset and ESLint](#3-tailwind-v4-theme-reset-and-eslint)
4. [Protecting the token file](#4-protecting-the-token-file)

## 1. Claude Code hook

The script's `--hook` mode reads the PostToolUse payload on stdin, checks the edited file (only lines changed since the last commit, or the whole file outside git) and exits 2 with the errors on stderr. Claude sees them right after the edit and fixes them in the next step. A PostToolUse hook can't undo the write; it only makes sure the model sees the problem. Files that aren't UI code, and edits with no errors, pass silently.

For a team, copy the script into the project so everyone runs the same version, and register it in `.claude/settings.json` (shared) or `.claude/settings.local.json` (only on this machine):

```bash
mkdir -p .claude/hooks && cp PATH_TO_THIS_SKILL/scripts/check_tokens.py .claude/hooks/
```

```json
{
  "hooks": {
    "PostToolUse": [
      {
        "matcher": "Edit|Write|MultiEdit",
        "hooks": [
          { "type": "command", "command": "python3 \"$CLAUDE_PROJECT_DIR\"/.claude/hooks/check_tokens.py --hook" }
        ]
      }
    ]
  }
}
```

Merge this into an existing settings file instead of replacing it. Add `--allow --brand-` for custom properties a library sets at runtime, or `--tokens path/to/tokens.css` when the token file has a name the script doesn't recognise. Test it once: make an edit with `padding: 13px` and check that the error comes back.

## 2. Plain CSS: Stylelint

For CI, or for a team that already runs Stylelint. Three core rules, no plugins; checked on Stylelint 17.16.0 (`referenceFiles` is experimental, added in 17.9.0):

```js
// stylelint.config.mjs
export default {
  referenceFiles: 'src/styles/tokens.css',
  rules: {
    'no-unknown-custom-properties': true,
    'declaration-property-unit-allowed-list': [{
      '/^(margin|padding|gap|row-gap|column-gap|inset)/': [],
      '/^font(-size)?$/': [],
    }],
    'property-disallowed-list': [['/^--/'], { message: 'Define custom properties only in tokens.css' }],
  },
  overrides: [{ files: ['src/styles/tokens.css'],
    rules: { 'property-disallowed-list': null, 'declaration-property-unit-allowed-list': null } }],
};
```

What it catches: `padding: 13px`, `calc(13px + 1rem)`, the `13px` in `var(--space-2, 13px)`, `var(--space-7)` when tokens.css doesn't declare it, a local `--gap: 13px`, and the px in a `font:` shorthand. What passes: `margin: 0 auto`, `calc(var(--space-2) * 2)`.

- **Strict on purpose.** `property-disallowed-list` puts every custom property in tokens.css. If the project keeps component tokens next to components, allow a second file in `overrides`.
- **Percentages.** If `inset` should accept `%`, add it to that property's list.
- **Colour.** Colour literals need a separate rule, e.g. `color-no-hex` plus `function-disallowed-list` for `rgb`, `hsl` and `oklch` outside tokens.css.
- **Popular plugins have holes.** `stylelint-declaration-strict-value` accepts any `var()`, even an undeclared one. `stylelint-scales` silently passes units missing from its config.

## 3. Tailwind v4: theme reset and ESLint

The default theme allows any multiple of 0.25rem (`p-13`, `p-17`), and a bracket value (`m-[13px]`) always works. To keep only the project's steps, reset the namespaces and declare the steps:

```css
@import "tailwindcss";
@theme {
  --spacing-*: initial;   /* removes p-4, p-13, -mt-4 and also p-0: declare every step you keep */
  --spacing-0: 0px; --spacing-1: 0.25rem; --spacing-2: 0.5rem; --spacing-3: 0.75rem; --spacing-4: 1rem;
  --spacing-6: 1.5rem; --spacing-8: 2rem; --spacing-12: 3rem; --spacing-16: 4rem; --spacing-24: 6rem;
  --text-*: initial;      /* the namespace is --text-*, not --font-size-* (that one does nothing) */
  --text-small: 0.875rem; --text-body: 1rem; --text-h2: 2rem; --text-h1: 2.5rem;
}
```

A reset only removes CSS output. An off-scale class then fails silently, so pair it with a linter that reads the CSS entry point. Checked with eslint-plugin-better-tailwindcss 4.9.1:

```js
// eslint.config.mjs (excerpt)
settings: { "better-tailwindcss": { entryPoint: "src/app.css" } },
rules: {
  "better-tailwindcss/no-unknown-classes": "error",
  "better-tailwindcss/no-restricted-classes": ["error", { restrict: [
    { pattern: "\\[([^\\[\\]]*?)\\](?!:)", message: "Arbitrary value: use a theme token" },
    { pattern: "-\\(--[^)]*\\)$", message: "Custom-property shorthand: add the value to @theme" } ] }],
  "react/forbid-dom-props": ["error", { forbid: ["style"] }],
}
```

`eslint-plugin-tailwindcss` 4.x (`no-custom-classname` with `no-arbitrary-value`) catches the same off-scale and bracket classes, but not `p-(--x)`. Neither plugin sees inline `style`, hence `react/forbid-dom-props`. In Tailwind v3, put `spacing` and `fontSize` directly under `theme` instead of `theme.extend` to replace the defaults; bracket values still need the linter.

## 4. Protecting the token file

The token file changes only when the task is the scale. If it keeps changing as a side effect of other edits, add a deny rule for edits to that file in the project's Claude Code permissions (see the permissions docs for the path syntax) and edit it by hand, or through a task that is explicitly about the scale. Review any diff to the token file on its own: one changed value moves every element that uses it.
