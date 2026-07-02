# PPT Craft Editable

English | [简体中文](README_zh.md)

---

This is an AI skill for making PPT presentations. You only need to provide the topic, materials, and preferences, and it will first help you create a highly polished image-based PPT. If you need to edit the text later, you can also continue to generate a text-editable PPTX.

Suitable for these scenarios:

- Formal PPTs such as reports, thesis defenses, roadshows, training sessions, course lectures, and proposals.
- Having only a topic and wanting the AI to help you complete the structure and content.
- Already having reports, papers, lecture drafts, or outlines, and wanting to convert them into PPTs with higher visual fidelity.
- Wishing the final text to remain editable in PowerPoint / Keynote.
- **Converting existing PDF presentations into editable PPTX format.**

---

## What You Get

By default, you will first get a set of image-based PPT:

- Finalized slide images for each page
- Image-based PPTX
- Content and visual planning documents

If you choose to continue and make the text-editable version, you will also get:

- Text-editable PPTX
- Background images without text for each page
- `deck.json`, which records the position, font, font size, and color of each text box
- Optional preview images for easy verification of the final layout

If you upload a PDF presentation, you will get:

- Content extraction preview in browser
- Text-editable PPTX with preserved or rebuilt backgrounds
- All text content as editable text boxes

In the text-editable version, the background is an image, while the titles, body text, numbers, dates, signatures, etc., are real text boxes in the PPT and can be edited directly.

---

## Three Ways to Use

### Method 1: Make the image-based version first, then decide whether to make the text-editable version

This is the default method.

You can say directly:

```text
Help me make a PPT about "New Employee Onboarding Process", under 10 pages, aimed at newly joined colleagues.
```

The skill will complete the image-based PPT first. After delivery, it will actively ask if you need the text-editable version. Once you agree, it will enter the text-editable workflow. The editable version uses the approved image deck as a visual reference, then regenerates text-free backgrounds and overlays editable text boxes; it is not a pixel-exact text removal pass, so the background may differ slightly from the image-based version.

### Method 2: Start with the text-editable version only

If you explicitly do not want to make the image-based version first, you can say directly:

```text
Only make the text-editable PPTX, do not make the image-based version first. The topic is "Annual Operations Review", under 12 pages.
```

At this point, it will directly enter the editable workflow. It will first confirm the outline of each page, then make a 1-2 page lightweight preview. After confirmation, it will batch-generate the entire set.

### Method 3: Convert PDF presentation to editable PPTX

If you have an existing PDF presentation and want to make it editable:

```text
Convert this PDF presentation to an editable PPTX where I can modify the text.
```

The skill will:
1. Extract content from each page (using multimodal AI for image-based PDFs)
2. Show you an interactive preview to confirm/edit the extracted text
3. Generate clean backgrounds (either by removing text or rebuilding)
4. Create an editable PPTX with text boxes

For repository-local execution, the current MVP Phase D flow is:

```bash
# 1) Extract reviewable content from the PDF
python3 scripts/pdf_extract_multimodal.py input.pdf -o phaseD/extraction.json

# 2) Build the review HTML
python3 scripts/inject_extraction_review.py \
    --shell assets/phaseD_extraction_review_shell/index.html \
    --data phaseD/extraction.json \
    --out phaseD/extraction_review.html

# Contract: page_image inside phaseD/extraction.json must be relative to the
# phaseD directory itself, e.g. work/page_images/01.png

# 3) Open phaseD/extraction_review.html in a browser, edit text boxes,
#    then copy the exported sentinel package back into:
#    phaseD/extraction_confirmed.json or any .txt file

# 4) Generate Phase C backgrounds from the confirmed extraction
python3 scripts/generate_backgrounds_from_pdf.py \
    --input phaseD/extraction_confirmed.json \
    --output-dir phaseC/backgrounds

# 5) Convert confirmed extraction into Phase C deck + editor
python3 scripts/extraction_to_deck.py \
    --input phaseD/extraction_confirmed.json \
    --output phaseC/deck.json \
    --editor-out phaseC/editor.html

# 6) After the user confirms/export the final deck in phaseC/editor.html,
#    render the PPTX
python3 scripts/json_to_pptx.py phaseC/deck.json \
    -o phaseC/<topic>-editable.pptx \
    --preview-dir phaseC/preview
```

Notes:
- `scripts/generate_backgrounds_from_pdf.py` and `scripts/extraction_to_deck.py` both accept either raw JSON or the full sentinel-wrapped export text from the review page.
- `image_only` / `rebuild` pages currently use a deterministic local MVP: the script removes detected text regions with local inpainting, and any remaining visual cleanup goes through the existing Phase C editor / review / retouch flow.

---

## Process

### 1. Requirements Confirmation

You first provide the topic, purpose, audience, page range, and existing materials. Materials can be very rough, such as a few paragraphs of text, a table of contents, meeting minutes, paper abstracts, or report content.

The skill will first organize its understanding and ask you to confirm if the direction is correct.

### 2. Slide Outline Confirmation

Before formal design, it will first confirm "what text to put on each page". This step will generate:

- `slide_outline.md`
- `ppt大纲.md`

You can modify titles, delete pages, add pages, adjust the order, or supplement real data in the file. Once confirmed, subsequent previews and generation will follow this outline.

### 3. Style Preview

The skill will generate multiple style directions and put real preview images into the HTML preview page. You view the effects in the browser, choose the style you like, or ask to blend or modify them.

### 4. Image-Based PPT Generation

After confirming the style and pre-generation planning, the skill will generate the full set of final slide images and let you confirm page-by-page using the HTML review page. If any edits are needed, you can point out the issues and request revisions.

Once the image-based version is completed, it will deliver:

- `phaseA/slides/`: final slide images for each page
- Image-based PPTX
- Planning files such as `content_report.md`, `design_spec.md`, `slide_blueprint.md`, and `spec_lock.md`

### 5. Text-Editable Version Generation

If you need the text-editable version, the skill will split each page into "background image + editable text boxes". The background is regenerated as a text-free version based on the confirmed visual draft, not extracted by precisely cutting text out of the original image; textures, decorations, or layout details may vary slightly.

If you chose to do the editable version from the start, it will first generate a C0 lightweight preview. This preview is for confirming the overall effect of the newly generated text-free background plus editable text boxes:

- `phaseC/c0/editor.html`: open to see the overlay effect of the text-free background and editable text
- `phaseC/c0/preview/`: static preview images
- `phaseC/c0/deck.json`: temporary preview data

After confirmation, it will batch-generate the formal backgrounds and the editor.

### 6. Tweak Text and Feedback Background in the Editor

The text-editable version will generate:

- `phaseC/editor.html`

You open it and can:

- Modify text
- Drag text boxes
- Resize text boxes
- Change font, font size, color, and alignment
- Add or delete text boxes
- Switch to background feedback mode to draw regions of the background that need modification

Once satisfied, click export and paste the entire content back into the conversation. The skill will continue to generate the PPTX based on the exported content; if you marked background issues, it will fix the background first and let you confirm again.

### 7. Final Delivery

The final editable version will generate:

- `phaseC/<Topic>-editable.pptx`
- `phaseC/deck.json`
- `phaseC/backgrounds/`
- `phaseC/preview/` (optional)

---

## What You Need to Prepare

The more complete, the better, but you can start even with incomplete information.

Recommended to provide:

- PPT topic
- Purpose: report, defense, training, roadshow, proposal, etc.
- Audience: leaders, clients, teachers, classmates, employees, etc.
- Page range
- Existing materials: reports, drafts, outlines, data, papers, meeting minutes, etc.
- Style preferences: formal, tech, warm, minimalist, academic, business, etc.
- Whether you need the text-editable version

If you have no ideas about the style, you don't need to specify it; the skill will first show you several directions.

---

## Common Sayings

Make default image-based version:

```text
Help me make a set of "AI Product Operations Review" PPT, for the weekly department meeting, around 10 pages.
```

Make text-editable version directly:

```text
Only make text-editable PPTX, skip the image version. Topic is "New Employee Onboarding Process", around 8 pages.
```

Provide existing materials:

```text
I will paste a report below, please help me organize it into a presentation PPT. It needs to be formal, clear, and suitable for management to review.
```

Request later text editability:

```text
Ultimately I need to be able to modify the title and body text in PowerPoint, please use the text-editable version.
```

---

## File Description

Common files and directories are as follows:

```text
slide_outline.md          Text outline for each slide
ppt大纲.md                Same content outline, convenient for Chinese users to find
content_report.md         Content base, generated when materials are insufficient
design_spec.md            Visual style rules
slide_blueprint.md        Visual and content arrangement for each slide
spec_lock.md              Generation constraints to prevent text from being baked into the background

phaseA/slides/            Final images for each slide in the image-based version
phaseA/review/            Review pages and data for the image-based version
phaseA/*-image-deck.pptx  Image-based PPTX

phaseC/c0/                Lightweight preview of the editable version, only appears in Phase C-only mode
phaseC/backgrounds/       Background images for the editable version
phaseC/deck.json          Core data of the editable version
phaseC/editor.html        Editable text and background feedback editor
phaseC/*-editable.pptx    Text-editable PPTX
```

General users only need to pay attention to:

- `ppt大纲.md`
- `phaseA/*-image-deck.pptx`
- `phaseC/editor.html`
- `phaseC/*-editable.pptx`

---

## Installation and Environment

Put this skill directory into the `skills` directory supported by your AI client.

Common locations:

| AI Client       | skills Directory                                |
| --------------- | ----------------------------------------------- |
| Codex CLI       | `~/.codex/skills/` or `$CODEX_HOME/skills/`     |
| Claude Code CLI | `~/.claude/skills/`                             |

When used for the first time, the skill will automatically run environment preflight checks and install necessary Python packages:

```bash
python3 scripts/preflight.py
```

It will check:

- Python version
- `python-pptx`, Pillow, numpy, opencv-python
- Fonts, disk space, network status
- Optional IOPaint retouch environment

If your client does not run the self-check automatically, you can also enter the skill directory manually and run the command above.

---

## Precautions

- The text in the image-based PPT is part of the image and cannot be modified directly in PowerPoint.
- The text-editable version allows editing text, but the background remains an image.
- Before generating the editable version, you must confirm and export the result in `editor.html`.
- If you mark background issues in the editor, the skill will fix the background first and will not generate the final PPTX directly.
- The retouching feature may require installing IOPaint. The first installation may require several gigabytes of space and take several minutes.

---

## For Maintainers

Detailed workflow and internal rules can be found in:

- `SKILL.md`
- `references/pipeline.md`
- `references/phaseA/workflow.md`
- `references/phaseC/workflow.md`

Script entrypoints are concentrated in `scripts/`. Regular users do not need to run these scripts manually unless your AI client does not support automatic execution.

---

## Acknowledgments

Parts of the features in this skill are based on:

- `ppt-image-first`

- 致谢

本项目感谢 Linux.do 社区 对开源分享与传播的推动。
