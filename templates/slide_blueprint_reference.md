# slide_blueprint.md

Use this file to define page-by-page intent after the style direction is confirmed.

## Minimal schema per slide

For each slide, include:
- `slide_id`
- `page_role`
- `title`
- `core_message`
- `content_payload`
- `content_basis_binding`
- `claim_status`
- `page_rhythm`
- `text_visual_balance`
- `visual_strategy`
- `continuity_inheritance`
- `preview_evidence_binding`

## Example

```md
## S03
- page_role: logic
- title: Why this approach is necessary
- core_message: The main issue is not a single defect but the lack of a unified design logic.
- content_payload: current problems + cause breakdown + one conclusion
- content_basis_binding: derive from `content_report.md` narrative body section on current problems and problem-chain analysis
- claim_status: mixed; problem framing is inferred from the synthesized content basis and should avoid unsupported precise numbers unless the user provided them
- page_rhythm: structured
- text_visual_balance: balanced
- visual_strategy: structured grouping with clear hierarchy
- continuity_inheritance: keep bright scientific-board background tendency, inherit light panel container grammar, use deep-blue for structure and cyan-blue only for key data emphasis, do not shift into dark HUD mood
- preview_evidence_binding: inherit the user-confirmed cloud-and-atmosphere semantic field, keep academic answer-defense tone, keep school-context anchor visible in a way suitable for this page role, do not force the cover-only skyline composition onto an inner logic page
```

## Rules

- This file bridges content and style.
- It must be written only after the style direction is confirmed.
- For each slide, `content_basis_binding` should state which part of `content_report.md` or equivalent content basis this page inherits, compresses, or interprets.
- For each slide, `claim_status` should state whether the core assertion is `user_provided`, `inferred`, `needs_confirmation`, or a mix of these.
- For each slide, `continuity_inheritance` should state how this page stays inside the confirmed deck-level continuity anchor, especially for brightness/background tendency, palette role usage, container grammar, and emphasis tone.
- For each slide, `preview_evidence_binding` should state which reverse-engineered preview facts or user-confirmed liked elements this page should inherit, reinterpret locally, or intentionally not carry over.
- Do not write empty phrases such as `keep the style consistent`. State the inherited constraints concretely.
- Any editable overlay that may appear in final assembly must be traceable to explicit fields in this slide entry rather than invented during generation.
- If no such overlay need is explicitly described here, the default assembly behavior is zero post-generation overlays.
- `slide_id` is for planning, filenames, and page mapping only. It should not be copied into the image-generation prompt body.
- If `content_report.md` exists, the slide list should trace back to it rather than inventing a separate generic deck outline.
- It should not contain exact color values, prompt strings, or pixel-level layout instructions.
- It should be lighter than a full design draft, but stronger than a plain outline.
