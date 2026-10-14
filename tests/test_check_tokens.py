"""ui-tokens check script: findings on small fixture projects, changed-lines mode and the hook."""

import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "skills/ui-tokens/scripts/check_tokens.py"

TOKENS = """:root {
  --space-1: 0.25rem; --space-2: 0.5rem; --space-3: 0.75rem; --space-4: 1rem; --space-6: 1.5rem;
  --text-sm: 0.875rem; --text-body: 1rem; --text-h2: 1.75rem;
  --ink: #1d1d1b; --paper: #faf8f3;
  --radius-control: 6px;
}
"""


class Fixture:
    def __init__(self, files):
        self.dir = Path(tempfile.mkdtemp(prefix="ui-tokens-"))
        for name, text in files.items():
            path = self.dir / name
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(text, encoding="utf-8")

    def run(self, *args, stdin=None, env=None):
        return subprocess.run([sys.executable, "-I", str(SCRIPT), *args], cwd=self.dir, input=stdin,
                              capture_output=True, text=True, env=env, timeout=60)

    def findings(self, *args):
        r = self.run("--root", ".", "--json", *args)
        return r.returncode, json.loads(r.stdout)

    def git(self, *args):
        subprocess.run(["git", *args], cwd=self.dir, check=True, capture_output=True,
                       env={**os.environ, "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t",
                            "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"})

    def close(self):
        shutil.rmtree(self.dir, ignore_errors=True)


def rules(data, level=None):
    return [(f["rule"], f["line"]) for f in data["findings"] if level is None or f["level"] == level]


class PlainCssTests(unittest.TestCase):
    def check(self, css, files=None):
        fx = Fixture({"tokens.css": TOKENS, "styles.css": css, **(files or {})})
        try:
            return fx.findings()
        finally:
            fx.close()

    def test_literal_spacing_is_an_error_that_names_the_nearest_tokens(self):
        code, data = self.check(".card h3 { margin: 0 0 13px; }\n")
        self.assertEqual(code, 1)
        [f] = data["findings"]
        self.assertEqual((f["level"], f["rule"]), ("ERROR", "raw-space"))
        self.assertIn("var(--space-3) 12px", f["note"])
        self.assertIn("var(--space-4) 16px", f["note"])

    def test_tokens_zero_auto_and_hairlines_pass(self):
        code, data = self.check(".a { padding: var(--space-4); margin: 0 auto; margin-top: -1px; "
                                "border-bottom: 1px solid var(--ink); gap: calc(var(--space-2) * 2); }\n")
        self.assertEqual((code, data["findings"]), (0, []))

    def test_the_token_file_itself_is_not_checked(self):
        code, data = self.check("")
        self.assertEqual(code, 0)
        self.assertEqual(data["findings"], [])

    def test_negative_margin_and_var_fallback_literals_are_errors(self):
        _, data = self.check(".a { margin: 0 -16px; }\n.b { padding: var(--space-4, 13px); }\n")
        self.assertEqual(rules(data, "ERROR"), [("raw-space", 1), ("raw-space", 2)])

    def test_undeclared_token_is_an_error_and_with_fallback_a_warning(self):
        _, data = self.check(".a { margin-top: var(--space-7); }\n.b { color: var(--brand, var(--ink)); }\n")
        self.assertEqual(rules(data), [("unknown-token", 1), ("unknown-token", 2)])
        self.assertEqual([f["level"] for f in data["findings"]], ["ERROR", "WARNING"])

    def test_property_set_per_element_in_markup_counts_as_declared(self):
        _, data = self.check(".tile { gap: var(--i); }\n", {"index.html": '<div class="tile" style="--i: 2"></div>'})
        self.assertNotIn("unknown-token", [r for r, _ in rules(data)])

    def test_local_literal_property_is_caught_where_it_is_used(self):
        _, data = self.check(".a { --gap: 13px; gap: var(--gap); }\n.b { --card-gap: var(--space-4); gap: var(--card-gap); }\n")
        self.assertEqual(rules(data), [("local-token", 1), ("via-local-token", 1)])

    def test_fluid_clamp_in_a_component_is_one_finding(self):
        _, data = self.check(".h { font-size: clamp(1rem, 0.7rem + 1.4vw, 2rem); }\n")
        [f] = data["findings"]
        self.assertEqual(f["rule"], "raw-font-size")
        self.assertIn("token file as clamp()", f["note"])

    def test_font_shorthand_checks_the_size_not_the_line_height(self):
        _, data = self.check(".a { font: 600 15px/22px serif; }\n")
        [f] = data["findings"]
        self.assertEqual(f["rule"], "raw-font-size")
        self.assertTrue(f["note"].startswith("15px"))

    def test_colour_literal_suggests_an_identical_token(self):
        _, data = self.check(".a { background: #1D1D1B; }\n")
        [f] = data["findings"]
        self.assertEqual(f["rule"], "raw-color")
        self.assertIn("var(--ink), the same colour", f["note"])

    def test_colours_in_strings_urls_and_relative_syntax_are_ignored(self):
        _, data = self.check('.a { content: "#1"; background: url(img.svg#a) no-repeat; '
                             "color: rgb(from var(--ink) r g b / 50%); }\n"
                             ".b { background: url(//cdn.example/x.png); padding: 21px; }\n")
        self.assertEqual(rules(data), [("raw-space", 2)])

    def test_offsets_em_sizes_and_unit_line_height_are_warnings(self):
        _, data = self.check(".a { top: 72px; }\n.b { font-size: 0.75em; }\n.c { line-height: 22px; }\n"
                             "html { font-size: 100%; }\n")
        self.assertEqual(rules(data, "WARNING"), [("raw-offset", 1), ("relative-font-size", 2), ("unit-line-height", 3)])
        self.assertEqual(rules(data, "ERROR"), [])

    def test_token_arithmetic_with_an_odd_factor_is_a_candidate(self):
        _, data = self.check(".a { padding: calc(var(--space-1) * 3.25); margin: calc(-1 * var(--space-2)); }\n")
        self.assertEqual(rules(data), [("token-arithmetic", 1)])
        self.assertEqual(data["findings"][0]["level"], "CANDIDATE")

    def test_style_blocks_and_attributes_in_html(self):
        _, data = self.check("", {"index.html": "<style>.y{padding:18px}</style>\n<p style=\"margin-top: 40px\">x</p>\n"})
        self.assertEqual(sorted(rules(data)), [("raw-space", 1), ("raw-space", 2)])

    def test_missing_path_exits_2(self):
        fx = Fixture({"tokens.css": TOKENS})
        try:
            self.assertEqual(fx.run("nope.css").returncode, 2)
        finally:
            fx.close()

    def test_system_lists_the_scale(self):
        fx = Fixture({"tokens.css": TOKENS, "styles.css": ".a { padding: 13px; }\n"})
        try:
            out = fx.run("--system", "--root", ".").stdout
        finally:
            fx.close()
        self.assertIn("space (5): --space-1 0.25rem (4px)", out)
        self.assertIn("color (2)", out)
        self.assertIn("13px x1", out)


class JsTests(unittest.TestCase):
    def test_jsx_style_objects_and_styled_components(self):
        fx = Fixture({"tokens.css": TOKENS, "Card.tsx": (
            'import styled from "styled-components";\n'
            "export const Box = styled.div`\n  padding: 13px ${p => p.pad};\n  gap: var(--space-2);\n`;\n"
            "export const Card = () => <div style={{ padding: 13, lineHeight: 1.4, marginTop: 0, "
            "color: 'var(--ink)' }} />;\n")})
        try:
            _, data = fx.findings()
        finally:
            fx.close()
        self.assertEqual(rules(data), [("raw-space", 3), ("raw-space", 6)])


class TailwindTests(unittest.TestCase):
    THEME = ('@import "tailwindcss";\n@theme {\n  --spacing-*: initial;\n'
             "  --spacing-0: 0px; --spacing-1: 0.25rem; --spacing-2: 0.5rem; --spacing-4: 1rem;\n"
             "  --text-*: initial;\n  --text-body: 1rem; --text-h1: 2.5rem;\n  --color-ink: #1d1d1b;\n}\n")

    def run_page(self, css, html):
        fx = Fixture({"app.css": css, "page.html": html})
        try:
            return fx.findings()
        finally:
            fx.close()

    def test_reset_theme_rejects_removed_steps_and_arbitrary_values(self):
        _, data = self.run_page(self.THEME, '<div class="p-4 -mt-4 mt-3 text-lg text-body text-center '
                                            'md:p-[13px] top-1/2 left-0 text-ink"></div>\n')
        got = sorted((f["rule"], f["excerpt"]) for f in data["findings"])
        self.assertEqual(got, [("tw-arbitrary", "p-[13px]"), ("tw-removed-step", "mt-3"),
                               ("tw-removed-step", "text-lg")])

    def test_arbitrary_colour_and_undeclared_var_shorthand(self):
        _, data = self.run_page(self.THEME, '<div class="bg-[#1d1d1b] p-(--gutter)"></div>\n')
        notes = {f["rule"]: f["note"] for f in data["findings"]}
        self.assertIn("var(--color-ink), the same colour", notes["tw-arbitrary"])
        self.assertIn("--gutter", notes["unknown-token"])

    def test_default_theme_off_step_is_a_candidate(self):
        code, data = self.run_page('@import "tailwindcss";\n', '<div class="p-13 p-4 gap-6 text-lg"></div>\n')
        self.assertEqual(code, 0)
        self.assertEqual([(f["level"], f["excerpt"]) for f in data["findings"]], [("CANDIDATE", "p-13")])

    def test_default_theme_suggests_default_steps(self):
        _, data = self.run_page('@import "tailwindcss";\n', '<div class="p-[13px] text-[15px]"></div>\n')
        notes = " ".join(f["note"] for f in data["findings"])
        self.assertIn("3 (12px)", notes)
        self.assertIn("text-sm (14px)", notes)

    def test_apply_in_css_is_checked(self):
        _, data = self.run_page(self.THEME + ".btn { @apply px-4 py-[13px]; }\n", "<p></p>\n")
        self.assertEqual([(f["rule"], f["line"]) for f in data["findings"]], [("tw-arbitrary", 9)])


@unittest.skipUnless(shutil.which("git"), "git not installed")
class ChangedAndHookTests(unittest.TestCase):
    def setUp(self):
        self.fx = Fixture({"tokens.css": TOKENS, "styles.css": ".old { padding: 13px; }\n"})
        self.fx.git("init", "-q")
        self.fx.git("add", "-A")
        self.fx.git("commit", "-qm", "init")
        with open(self.fx.dir / "styles.css", "a", encoding="utf-8") as f:
            f.write(".new { padding: 14px; margin: var(--space-2); }\n")

    def tearDown(self):
        self.fx.close()

    def test_changed_mode_checks_only_added_lines(self):
        code, data = self.fx.findings("--changed")
        self.assertEqual(code, 1)
        self.assertEqual(rules(data), [("raw-space", 2)])
        self.assertTrue(any("1 findings on lines not changed" in r for r in data["report"]))

    def test_untracked_file_counts_whole(self):
        (self.fx.dir / "extra.css").write_text(".x { gap: 5px; }\n", encoding="utf-8")
        _, data = self.fx.findings("--changed")
        self.assertIn(("raw-space", 1), [(f["rule"], f["line"]) for f in data["findings"] if f["file"] == "extra.css"])

    def hook(self, path):
        payload = json.dumps({"tool_name": "Edit", "tool_input": {"file_path": str(path)}})
        env = {**os.environ, "CLAUDE_PROJECT_DIR": str(self.fx.dir)}
        return self.fx.run("--hook", stdin=payload, env=env)

    def test_hook_reports_new_lines_on_stderr_with_exit_2(self):
        r = self.hook(self.fx.dir / "styles.css")
        self.assertEqual(r.returncode, 2)
        self.assertIn("styles.css:2 raw-space", r.stderr)
        self.assertNotIn(":1 ", r.stderr)

    def test_hook_is_silent_for_clean_edits_and_other_files(self):
        self.fx.git("add", "-A")
        self.fx.git("commit", "-qm", "accept")
        self.assertEqual(self.hook(self.fx.dir / "styles.css").returncode, 0)
        self.assertEqual(self.hook(self.fx.dir / "tokens.css").returncode, 0)
        notes = self.fx.dir / "notes.md"
        notes.write_text("padding: 13px\n", encoding="utf-8")
        self.assertEqual(self.hook(notes).returncode, 0)


if __name__ == "__main__":
    unittest.main()
