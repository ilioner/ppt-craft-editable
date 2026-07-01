# Style System

## Core principle

Do not rely on rigid templates as the primary style system for PPT visual design.
Use a parameterized style vector internally, then synthesize multiple coherent style proposals.

This rule is about the deck's visual language, not about workflow UI files.
The bundled preview/review HTML shells in `assets/preview_shell/index.html` and `assets/review_shell/index.html` remain mandatory workflow assets unless unavailable or explicitly overridden by the user.

## Style vectors

- `V1` Layout System
- `V2` Texture & Material
- `V3` Lighting & Depth
- `V4` Color Palette
- `V5` Containers & Motifs
- `V6` Density & Rhythm
- `V7` Text–Visual Balance
- `V8` Brand Constraint Level

## Control split

### User-controlled dimensions
These should primarily follow the user's intent or hard constraints:
- `V6` Density & Rhythm
- `V7` Text–Visual Balance
- `V8` Brand Constraint Level
- `V4` Color Palette when brand or industry constraints are explicit

### AI-proposed dimensions
These should be synthesized by the agent into candidate directions:
- `V1` Layout System
- `V2` Texture & Material
- `V3` Lighting & Depth
- `V5` Containers & Motifs

## V5 rule

`V5` must use two different grammars:
- **Cover pages** → visual metaphors
- **Body pages** → information containers

Do not describe body pages as one fixed layout. Describe the body-page **visual grammar** instead:
- how information is organized
- where unity comes from
- how different page types vary while staying in one system

## Intra-direction continuity

Within one style direction, the 3 preview pages must read as one visual family rather than 3 loosely related images.

This continuity should come from a shared visual system, including as appropriate:
- the same or clearly related color palette
- the same lighting logic and depth behavior
- the same material language
- the same container language and edge treatment
- the same decorative grammar
- the same title / label / emphasis tone
- the same level of restraint or expressiveness

Allowed variation:
- the cover may be more atmospheric and metaphor-driven
- the table-of-contents page may be more structural
- the body page may be more informational

Not allowed:
- changing the style language so much that the 3 pages look like different template families
- introducing a new material system or illustration language only on one page
- making the cover futuristic, the TOC editorial, and the body dashboard-heavy unless that transition still clearly belongs to one shared system

Think of each direction as one deck identity expressed across 3 page roles, not 3 separate design attempts.

## Deck-level continuity anchor

After one style direction is confirmed, do one short reverse-engineering pass on the selected `首页 / 目录页 / 正文页` before writing planning files or generating final visuals.

Use that pass to infer what the chosen direction became in the actual images, not just what the prompt originally asked for.
The confirmed continuity anchor should therefore be based on:
- the selected preview images as the primary evidence
- the original generation prompt as supporting context
- the user's confirmation of which extracted elements they actually want to preserve

After that, convert the direction into a single deck-level continuity anchor.

This anchor must be explicit enough that every later slide can inherit it.
At minimum it should lock:
- base brightness range and background tendency
- dominant palette and secondary palette roles
- lighting model and depth strength
- material language
- container grammar and edge treatment
- decoration grammar
- title / label / emphasis tone
- restraint vs expressiveness level

Use this anchor to prevent "same style but different mood" drift.
For example, do not let one slide become dark, glossy, and high-contrast while the next becomes bright, airy, and nearly flat unless that range was explicitly defined as part of the confirmed system.

The continuity anchor is not a long image prompt.
It is the stable deck identity that all per-slide image prompts, page blueprints, and execution constraints must inherit.

Per-slide prompts may vary by page role and content, but they must stay inside the same anchor.
Do not treat slides as independent prompt-writing tasks.

## Proposal card

Each style proposal must stay lightweight:
- proposal name
- one-line positioning
- cover direction
- body-page visual grammar
- suitable scenarios
- risk note

The proposal card is only the presentation interface. It must not constrain the creative generation process.
