---
name: ui-evidence-to-spec
description: "Turns screenshots, recordings, mockups, or observed interfaces into an implementable UI specification grounded in evidence. Use for reproducing, improving, or debugging user interfaces without inventing hidden behavior or design decisions."
license: MIT
metadata:
  author: ai-engineering-powerkit
  version: "0.1.0"
  profile: specialist
---

# UI Evidence to Specification

## Purpose

Translate visual evidence into a precise implementation target while clearly separating what is visible from what must still be decided.

## Extract visible evidence

Capture:

- Layout hierarchy, spacing, alignment, and responsive clues.
- Typography roles and emphasis.
- Components, controls, states, and affordances.
- Color, material, border, shadow, and elevation behavior.
- Content hierarchy and labels.
- Interaction hints, focus, selection, disabled, hover, and error states.
- Platform conventions.
- Accessibility issues visible from the evidence.
- Assets, icons, imagery, and aspect ratios.

## Separate evidence from inference

Label:

- **Observed** — directly visible.
- **Repository-supported** — consistent with existing components or tokens.
- **Safe inference** — conventional and reversible.
- **Decision required** — materially changes interaction, data, or product behavior.

Do not infer backend behavior from a screenshot.

## Method

1. Inspect all supplied visual evidence and relevant existing UI code.
2. Identify the owning design system components and tokens.
3. Describe the user flow and state model.
4. Define responsive and accessibility behavior.
5. Specify missing states needed for a production implementation.
6. Produce acceptance criteria that can be checked in the running UI.
7. Preserve intentional visual character while avoiding pixel-level overfitting to one viewport.

## Output

Provide:

- Screen or component structure.
- State and interaction model.
- Design-system mapping.
- Responsive behavior.
- Accessibility requirements.
- Assets and content.
- Unknowns.
- Runtime acceptance checklist.

## Avoid

- Vague words such as “modern” without observable criteria.
- Inventing product logic.
- Replacing an established design system with custom one-off styling.
- Treating a static image as proof of keyboard or screen-reader behavior.
