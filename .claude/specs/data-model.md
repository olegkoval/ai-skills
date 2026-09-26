# ai-skills — Data Model

No database or persistent runtime state — this repo's only "entities" are the files that structure it.

## Skill

- **Storage:** `skills/<category>/<name>/SKILL.md`, with optional `references/*.md` (worked examples, long templates) and `assets/` (files a skill uses verbatim, like the spec templates or the review block). `<category>` groups by specialization/domain and is dropped at install time (see constitution.md Article 2).
- **Key attributes:** YAML frontmatter `name` + `description` (the trigger text Claude reads to decide whether to invoke it).
- **Relationships:** A skill may be one half of a pair (e.g. `sdd-ticket-start` / `sdd-ticket-close`), in which case each references the other explicitly (see constitution.md Article 4).

## Adopter Template

- **Storage:** `skills/<category>/<skill>/assets/specs/<name>.md` (e.g. `skills/development/sdd-specs-init/assets/specs/constitution.md`) — inside the skill that fills them in, so they travel with it on install.
- **Key attributes:** A generic, fill-in-the-blank version of a file the SDD skills read at run time from a *consuming* project's own `.claude/specs/`.
- **Relationships:** Each template corresponds 1:1 to a file name the skills actually read (`constitution.md`, `tech-stack.md`, `data-model.md`, `branching-strategy.md`, `workflow.md`) — adding a template for a file the skills don't read would be dead weight.

## Known Incomplete State

- No CI validates skill Markdown (frontmatter well-formed, no broken internal links) — currently manual.
- No Claude Code plugin manifest (`.claude-plugin/plugin.json`) yet, so installation is a manual per-skill symlink (or copy, for a frozen snapshot) rather than marketplace install.
