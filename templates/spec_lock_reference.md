# spec_lock.md

Use this file as the execution lock.

## Purpose

This file records only the constraints that generation must not drift away from.

## Suggested sections

### canvas
- format
- ratio (`16:9` by default unless the user explicitly requests another presentation ratio)
- any hard size requirements

### visual_system
- chosen style direction
- reverse-engineered preview facts that are now hard constraints
- user-confirmed deck-wide liked elements
- deck-level continuity anchor
- cover / body continuity rules
- allowed variation range
- fixed brightness range and background tendency

### colors
- only the colors or color roles that must stay fixed
- identify dominant vs supporting roles, not just a loose palette

### typography
- only the type directions or families that must stay fixed

### rhythm
- global rhythm rules
- any page-level hard rhythm tags if needed

### brand_constraints
- strict / light / free
- what is mandatory vs flexible
- which identity anchors must remain visible, referenced, or semantically present

### content_grounding
- content basis source
- allowed claim types
- forbidden claim types
- uncertain-claim policy
- preview-content policy

### forbidden
- things generation must not do
- unapproved post-generation overlays
- explanatory patch boxes or rescue text
- do not upgrade unconfirmed one-off preview details into deck-wide constraints
- do not invent unsupported precise statistics, experiment results, citations, rankings, or institutional conclusions

### generation_metadata
- slide identifiers, candidate codes, filenames, and batch labels stay outside image prompt bodies
- reconnect generated images to slide IDs through filenames or an external mapping table

## Recommended lock style for continuity anchor

Keep the continuity anchor compressed and machine-oriented.
Prefer fixed fields over descriptive prose.

Example:

```md
### visual_system
- chosen_style_direction: atmospheric remote sensing blueprint
- deck_level_continuity_anchor:
  - brightness_world: high-key
  - background_tendency: bright scientific board
  - forbidden_brightness_jump: no full dark control-room pages
  - lighting_model: soft luminous depth with restrained glow
  - material_language: translucent research panel
  - container_grammar: rounded light panels + fine-line data dividers
  - decoration_grammar: contour lines, subtle grid, remote-sensing signal traces
  - emphasis_tone: academic, precise, polished
- cover_body_continuity_rules: same palette roles, same panel language, same signal-line decoration family
- allowed_variation_range: cover can be more atmospheric; body pages can be denser; brightness must stay in the bright range
```

## Rules

- Keep this file machine-oriented.
- Do not explain the rationale here.
- Do not duplicate long narrative content from `design_spec.md`.
- Unless explicitly approved and mapped to blueprint fields, the default post-generation overlay count is zero.
- Keep execution metadata outside image prompt bodies rather than handling it through negative prompt instructions.
- Only put what must stay fixed during execution.
- If a reverse-engineered feature was not confirmed as deck-wide, keep it out of this file or scope it explicitly to the pages that need it.
- If `content_report.md` exists, this file should lock which claim types are safe to use and which must stay generalized or await confirmation.
