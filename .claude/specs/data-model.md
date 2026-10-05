# ai-skills — Data Model

No database. Skills and project-local handoff files structure the repository.

## Skill

- **Storage:** `skills/<compatibility>/<category>/<name>/SKILL.md`, with optional `scripts/`, `references/*.md` (worked examples, long templates) and `assets/` (files a skill uses verbatim, like the spec templates or the review block). `<compatibility>` is `claude-ai` for workflows maintained for Claude Code or `shared` for assistant-neutral or shared workflows, with supported hosts documented per skill. Compatibility and category group source folders and are dropped at install time (see constitution.md Article 2).
- **Key attributes:** YAML frontmatter `name` + `description` (the discovery text assistants read before loading it).
- **Relationships:** A skill may be one half of a pair (e.g. `sdd-ticket-start` / `sdd-ticket-close`), in which case each references the other explicitly (see constitution.md Article 4).

## Adopter Template

- **Storage:** `skills/<compatibility>/<category>/<skill>/assets/specs/<name>.md` (e.g. `skills/shared/development/sdd-specs-init/assets/specs/constitution.md`) — inside the skill that fills them in, so they travel with it on install.
- **Key attributes:** A generic, fill-in-the-blank version of a file the SDD skills read at run time from a *consuming* project's own `.claude/specs/`.
- **Relationships:** Each template corresponds 1:1 to a file name the skills actually read (`constitution.md`, `tech-stack.md`, `data-model.md`, `branching-strategy.md`, `workflow.md`) — adding a template for a file the skills don't read would be dead weight.

## Known Incomplete State

- No CI validates skill Markdown (frontmatter well-formed, no broken internal links) — currently manual.
- No Claude Code plugin manifest (`.claude-plugin/plugin.json`) yet, so installation is a manual per-skill symlink (or copy, for a frozen snapshot) rather than marketplace install.

## Local Assistant Handoff

- **Storage:** Ignored `.ai-sync/`, with immutable `snapshots/<id>/checkpoint.json`, selected artifacts/Git patches, atomic `latest.json`, and state-bound reconciliation receipts.
- **Format:** Shared version 1 engine in `project-sync-save`; `project-sync-load` launches that same engine.
- **Scope:** This project’s assistant handoffs, distinct from committed specs and cross-project communication. No automatic commits or remote services.

## Repository Instructions

- **Shared source:** Root `AGENTS.md` contains common authoring, architecture, installation and review rules.
- **Claude adapter:** Root `CLAUDE.md` imports `AGENTS.md` and retains Claude-specific review commands.
- **Source paths:** Canonical skills live under `skills/claude-ai/` or `skills/shared/`. There are no repository compatibility symlinks; installed links point directly to canonical directories.

## Specs Location

- The general `sdd-specs-init` accepts an optional project-relative specs-directory argument and creates that directory and missing parents. Without an argument it always targets `docs/specs/`; existing locations/configuration do not override the default.
- This repository retains its existing `.claude/specs/`; use `sdd-specs-init .claude/specs` to update it. Current Claude ticket consumers still require that path.
