# Photography direction and generated images

Read when you write `imagery` in `brand.json` and before you generate any image. A sentence like "photos should be natural and warm" tells a photographer nothing; the book gives rules they can follow, and every generated image is honest about what it is.

## Contents

1. [Six parameters](#1-six-parameters)
2. [The AI section of the book](#2-the-ai-section-of-the-book)
3. [The product in a generated image](#3-the-product-in-a-generated-image)
4. [Prompts, references and logs](#4-prompts-references-and-logs)
5. [Checking a generated image](#5-checking-a-generated-image)
6. [Codex as the engine](#6-codex-as-the-engine)
7. [Placing images in the book](#7-placing-images-in-the-book)

## 1. Six parameters

Each parameter gets a rule and, where you have images, an example of right and wrong:

| Parameter | Write |
|---|---|
| `light` | the source and the time ("daylight from a side window, no flash"), never just "natural" |
| `composition` | what tells the story (people, hands, the product in use), what's never in the frame |
| `casting` | who appears, as a sentence: "people who really make the product, in work clothes", not three adjectives |
| `props` | what belongs to the brand's world and what doesn't |
| `styling` | clothes, hair, make-up, surfaces |
| `grading` | warm or cool, contrast, saturation, how it relates to the palette |

Add the types of picture the brand needs (product, people, details) and a recognisability test: would someone know it's this brand without the logo?

## 2. The AI section of the book

`imagery.ai` becomes a page of the book with: what AI may be used for (sketches of shots for a real shoot, backgrounds for mockups), what it may not (people presented as real employees or customers, "before and after" effects, a product doing something it doesn't), the caption under every generated image, and who approves each one.

Why it's needed:

- **Disclosure.** Article 50 of the EU AI Act applies from 2 August 2026: whoever publishes a generated image that resembles real people, objects or places and could pass as authentic must disclose that it's artificial. A clearly artistic or fictional image needs a disclosure that doesn't spoil it.
- **Rights.** The US Copyright Office (January 2025) found that prompts alone don't give enough human control for copyright. A logo, a mascot and key assets are made by a person; AI is for scenes, backgrounds and drafts. EU and Polish law on this wasn't checked.
- **People.** A generated person is a sketch. A campaign needs a real shoot with model releases; write that in `01-verify.md`.

The book names generated images in the footer of each slide that holds one ("Billboard przy targu · Wizualizacja", from `imagery.ai.label`), not as a badge on the photo. A generated image published on its own (a post, a website, a print) needs its own disclosure there.

## 3. The product in a generated image

Models change products. In a 2026 benchmark summary by Lamina (a tool vendor, using research by Photoroom and Masonry), the best product-preservation rate across 850 products was 29%, all four models tested drew barcodes that won't scan, and every one invented a supplement facts panel. So:

- **Freeze the labels first.** Generate product shots only after the label templates are approved. When a label changes later, list every image made from the old one as outdated.
- **The label comes from the approved render.** Use `render.mjs labels` output: the front cropped to what is visible from the camera, one image per product, in the order they stand in the shot.
- **Never publish a generated barcode or regulated panel.** If the shot shows the back, composite the real artwork or keep it out of frame.
- **Give the physical sizes** of the packs in millimetres and their relative scale in words; without technical drawings, proportions are a guess, and that goes into `01-verify.md`.

## 4. Prompts, references and logs

For each shot keep three files in `prompts/`:

- `<shot>.txt`: the prompt in English for the tool, in a fixed order: the role of each reference image ("Reference 1 is the approved hero photo: match its light, backdrop and colour grade"), the scene, the product and its exact text in quotes ("every word on the label exactly as in reference 2, with Polish letters"), physical sizes, light, camera and lens, texture, mood, space left for a headline when the image is for a layout, and an AVOID line (other brands, invented text, plastic sheen).
- `<shot>.refs`: one path per line, and for each label reference its version (the date of the label template or a hash), so an outdated reference can be found.
- `<shot>.log`: every attempt, appended, with why it was rejected (a typo on the pack, a content filter, wrong proportions). Never overwrite the log.

The first approved shot becomes the style anchor for the rest: reference it with its role in every later prompt. For continuity of a person across shots, use an earlier portrait as a reference. Write prompts so they can run in another tool unchanged; the engine is whatever the environment has.

## 5. Checking a generated image

Before an image goes into the book: the text on every pack letter by letter (including accented letters); hands and fingers; the pack's shape, cap and proportions; the resolution against what the layout needs (a model's 1–2 megapixels is not a billboard); the label version against the current one; no other brand's logo or name. Record the result in the log. Images that fail stay out of the book.

## 6. Codex as the engine

Look for an image tool before you tell the user there is none. Codex has one: the `codex` CLI, or the copy inside the ChatGPT app on a Mac (`/Applications/ChatGPT.app/Contents/Resources/codex-cli/bin/codex`). Check that `codex features list` shows `image_generation` as true. One shot:

```bash
codex exec -C brand -s workspace-write --skip-git-repo-check --image=images/refs/<id>-front.png \
  "Use your image generation tool to create the image described in prompts/<shot>.txt: read the file and pass its full content as the prompt. The attached image is a reference input: pass it to the image tool as a reference. Generate exactly one image. Copy the generated PNG to images/gen/<shot>-<n>.png. Reply with only the path of the original generated file." < /dev/null
```

- `< /dev/null`, or `exec` waits for more input on stdin.
- `--image=<file>` with the equals sign, once per reference: `-i` takes several values and swallows the prompt.
- About 40 seconds per image, 1536 × 1024 or 1024 × 1536 (ask for 3:2 or 2:3 in the prompt). Three runs side by side worked. The original stays in `~/.codex/generated_images/<session>/`; write that path into the log.
- A label reference is the front zone cropped from `out/labels/<id>-preview.png` (the preview includes the bleed, so the zone starts at `x_mm + bleed_mm`). Render the labels again after any change to them, before you crop.

**An artistic cover.** When the cover has to be striking and the brand forbids staged photos of its work, the cover can be an artwork instead: a screen-print, linocut or poster in the brand's two or three colours, the subject on one side, the other side dark and calm for the title. It may not pose as a photo of the brand's work, it is labelled like any generated image, and `imagery.ai.allowed` says so. In one project the owner called a photo cover that copied the website's hero "weak and boring"; a two-colour poster of the machine as a monument against a huge yellow sun was approved. Generate three styles side by side, check each at full size for letters, logos and impossible parts, and keep the one whose title side stays clear.

## 7. Placing images in the book

Convert each approved PNG to JPEG for the book and keep the PNG in `images/gen/` as the log's source: a deck of fourteen PNGs is over 30 MB.

```bash
sips -s format jpeg -s formatOptions 82 images/gen/<shot>-<n>.png --out images/<shot>.jpg
```

Then fill the slots (`references/data.md`, section 6): `imagery.images[]` with `slot` `cover` (landscape) and `intro` (portrait), the rest into the mood mosaic; `imagery.worlds[]` with a landscape `image` and a portrait `detail` per variant colour; `labels[].image` (portrait product shot); an application of kind `billboard` (landscape, calm space for the headline). Every generated one gets `generated: true`, so the book captions it. When the brand's `imagery.ai` forbids what the book now shows, such as a tin with a label, change the rule and record the decision, never leave the book breaking its own rule.

