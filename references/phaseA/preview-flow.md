# Preview Flow

## Purpose

The preview stage lets the user judge a style direction visually before planning the full deck.

## Fixed preview set

Each style direction must generate exactly 3 preview pages as **real image previews**.
Unless the user explicitly asks for another presentation format, those previews must be generated in a `16:9` slide ratio rather than a generic illustration ratio such as `3:2`.
These 3 pages must also preserve strong intra-direction continuity so the user can judge one coherent style system rather than 3 loosely related outputs:

1. `首页`
   - checks first impression
   - checks main visual and composition
   - checks tone and metaphor

2. `目录页`
   - checks structure and hierarchy
   - checks whether the style can support a system page
   - checks the transition from cover into content

3. `正文页`
   - checks whether the style can actually carry information
   - checks readability and emphasis
   - checks whether the visual grammar survives real content

A valid preview page must contain plausible filled content rather than placeholder-only structure.
That means:
- do not generate placeholder text such as “在此输入…”, “title here”, “lorem ipsum”, or empty label boxes intended to be filled later
- do not generate large empty containers, blank dashboard shells, or decorative modules with no real information inside
- do not silently switch to textless image generation just to avoid text rendering problems when the preview page is supposed to demonstrate content structure
- the TOC page should show believable section titles or navigational items
- the body page should show believable headings, bullets, labels, cards, numbers, or relationships with enough content to judge usability
- the cover may stay lighter in information density, but it still should not contain obvious placeholder copy

Text sketches, ASCII boxes, pseudo-layouts, and purely verbal examples do **not** count as previews in this workflow.

If `content_report.md` or another approved content-basis summary exists, preview content must draw from it.
That means:
- the cover should reflect the content thesis or core framing rather than only a decorative topic shell
- the TOC page should reflect the narrative chain or section candidates rather than a generic chapter list
- the body page should use page-content candidates, visualizable content, or report-derived arguments rather than generic filler structure
- do not create a second unrelated topic outline during preview generation when a content basis already exists
- if part of the preview content is inferred rather than user-provided, keep it general and avoid unsupported precise claims

## Comparison principle

The number of style directions may vary by user preference, but all proposed directions should use the same 3 preview page types so the user can compare them fairly.

## Presentation principle

Use the bundled preview shell at `assets/preview_shell/index.html` by default.
Treat it as the required workflow UI shell, not as optional inspiration.
For each style direction, show:
- the lightweight proposal card text
- the 3 preview pages beside or under it

Do not create a replacement preview shell, a lookalike HTML page, or a fresh preview interface from scratch just because it feels easier.
Only depart from the bundled shell if that asset is genuinely unavailable or the user explicitly asks for a different interface, and if that happens, say so clearly.

After the HTML shell is filled, immediately attempt to open that local page for the user so they can compare directions directly instead of opening raw files themselves.
Treat this open action as part of the default preview workflow.
If automatic opening fails, say that explicitly, explain the blocker, and provide the file path as fallback.

## Candidate-picker and review-shell continuity

If the workflow later enters optional multi-candidate final selection, use the bundled candidate-picker shell at `assets/candidate_picker_shell/index.html` by default.
Do not switch to a visually unrelated candidate-selection page, and do not create a visually similar but separate candidate-picker shell from scratch.
The intended continuity is achieved by reusing the bundled candidate-picker shell itself, not by inventing another page that merely resembles the preview shell.

When the workflow later enters final review and retouch, use the bundled review shell at `assets/review_shell/index.html` by default.
Do not switch to a visually unrelated review page, and do not create a visually similar but separate review shell from scratch.
The intended continuity is achieved by reusing the bundled review shell itself, not by inventing another page that merely resembles the preview shell.

The review HTML should:
- preserve the same overall design family, spacing rhythm, panel language, and image presentation logic
- replace style-comparison emphasis with page-by-page review emphasis
- make it easy to inspect one page, leave feedback, and then compare refreshed results after edits
- keep image review primary rather than burying the visuals under large control panels

## Hard rule

Style selection should default to preview-first.
That means:
- do not jump directly from proposal text to asking the user to choose a final direction
- first show the previews when generation is possible
- previews should be generated as real images by default
- if real image previews are not yet available, explicitly tell the user that preview display is part of the workflow and say what is blocking it right now

The user must never be left with the impression that style choice is text-only by default.

## Generation expectation

If an image-generation path is available in the environment, use it for previews.
Prefer whatever image-generation capability is currently available in the environment when preview images are needed, but do not assume a specific model, provider, or tool brand.
The image prompts should inherit both the style direction and the current content basis, rather than only the visual style request.
Do not downgrade to text mockups silently.
Only fall back to text-only examples when:
- the user explicitly asks for rough mockups only, or
- real image generation is unavailable right now and you have clearly told the user so.

## Speed and QA rule

The preview stage is a directional comparison step, not a polishing pass.
That means:
- generate the planned preview set directly instead of repeatedly testing one image at a time unless the generation path itself is unverified
- at most one minimal chain check is enough when the local generation path has not yet been confirmed in the current turn
- after the chain is confirmed, generate the remaining previews in batch without repeated intermediate spot-check loops
- do not regenerate pages just to slightly improve one candidate unless the result is clearly broken, unreadable, or off-direction
- do not run multiple rounds of manual re-checking before showing the user the preview set
- once each direction has a usable `首页 / 目录页 / 正文页`, assemble the preview page and show it
- apply the same speed rule during style refinement rounds; refinement is another comparison loop, not a polishing detour

Favor speed, comparability, and directionality over internal perfectionism at this stage.
