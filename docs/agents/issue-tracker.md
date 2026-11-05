# Issue tracker: Local Markdown

Issues and specs live in `.scratch/` and are versioned with the project.

## Conventions

- One feature per directory: `.scratch/<feature-slug>/`.
- Feature spec: `.scratch/<feature-slug>/spec.md`.
- One implementation ticket per file: `.scratch/<feature-slug>/issues/<NN>-<slug>.md`, numbered from `01`.
- Record triage state near the top as `Status:` using the roles in `triage-labels.md`.
- Append discussion under `## Comments`.
- Include acceptance criteria and dependencies in each implementation ticket.

## Publish and fetch

When a skill says to publish, write the appropriate local file. When it says to fetch, read the referenced file; resolve a number within its feature directory. Ask for the feature when a number is ambiguous.

## Wayfinding operations

For `/wayfinder`, use `.scratch/<effort>/map.md` for Notes, Decisions-so-far, and Fog; create one child ticket per question in `.scratch/<effort>/issues/NN-<slug>.md`.

Child tickets record `Type: research|prototype|grilling|task`, a workflow `Status: open|claimed|resolved`, and optional `Blocked by: NN, NN`. These workflow states apply to wayfinding children rather than implementation-ticket triage roles.

Choose the lowest-numbered open, unblocked child; save `Status: claimed` before starting. On completion, append `## Answer`, set `Status: resolved`, and add a summary and link under the map's Decisions-so-far. A child is unblocked when all listed dependencies are resolved.
