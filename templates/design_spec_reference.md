# design_spec.md

Use this file for the global deck rationale.

## Required sections

### I. Project Information
- project name
- deck goal
- audience
- use case
- page range
- language
- content basis source (`content_report.md` / user-provided report / extracted summary / none)
- identity anchors such as school / company / laboratory / research group / course / brand entity
- ratio (`16:9` by default unless explicitly overridden)

### II. Narrative Spine
- what the deck is trying to prove or deliver
- the top-level story arc
- how this narrative inherits or compresses the current content basis
- which major points are user-provided vs inferred vs still need confirmation

### III. Style Direction
- chosen style proposal
- one-line positioning
- cover direction
- body-page visual grammar
- why this direction fits the deck
- reverse-engineered preview facts
- user-confirmed liked elements to preserve
- elements that should stay local or should not be hard-locked deck-wide
- deck-level continuity anchor

### IV. Global Design Principles
- density and rhythm principles
- text–visual balance tendency
- brand constraint level
- image strategy
- base brightness and background mood policy

### V. Content Structure
- section breakdown
- intended page flow
- where the major emphasis points occur
- what part of the structure comes from `content_report.md` or equivalent content-basis extraction
- which claims need restrained wording because they are not fully confirmed

### VI. Preview-to-Deck Continuity
- how the confirmed style previews should extend into the full deck
- which reverse-engineered facts came from the actual previews rather than only from the prompt
- what must remain consistent
- which liked elements become deck-wide anchors
- which liked elements stay local to specific page roles only
- where page variation is encouraged

### VII. Constraints
- hard requirements
- things to avoid
- post-generation overlay policy
- unsupported-claim policy
- source-grounding policy

## Recommended continuity-anchor format

When writing `deck-level continuity anchor`, prefer a short structured block instead of a vague paragraph.
Cover at least:
- base brightness world
- background mood policy
- dominant palette roles
- lighting / depth model
- material language
- container grammar
- emphasis tone
- allowed variation range

Example:

```md
### deck-level continuity anchor
- brightness_world: high-key bright scientific board
- background_mood: bright, clean, research-led; do not drift into dark control-room mood
- palette_roles: white/light-cyan base, deep-blue as structure color, cyan-blue as data highlight, warm accent only for sparse emphasis
- lighting_depth: soft luminous depth, restrained glow, no heavy neon contrast
- material_language: translucent research panels + clean diagram surfaces
- container_grammar: rounded rectangular panels, fine-line dividers, light overlays, no heavy HUD frames
- emphasis_tone: precise, academic, polished, readable
- allowed_variation: cover may be slightly more atmospheric; data-heavy pages may deepen contrast slightly; full dark-background slides are not allowed
```

## Notes

- This file explains the deck at the global level.
- Do not turn it into a page-by-page blueprint.
- Do not put machine-execution parameters here unless they are needed for human reasoning.
- If the confirmed previews reveal stronger or more specific style facts than the original prompt wording, write the stronger reverse-engineered version here.
- If a feature was liked only in one preview page and was not confirmed as deck-wide, mark that scope explicitly instead of silently upgrading it into a global rule.
