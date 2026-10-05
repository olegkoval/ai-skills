# AGENTS.md

Shared repository instructions for Codex, Claude Code, and other coding assistants. `CLAUDE.md` imports this file and supplies Claude-specific review commands.

## What this repo is

A collection of reusable skills organized by supported assistant and specialization under `skills/<compatibility>/<category>/`. `claude-ai/` contains workflows maintained for Claude Code; `shared/` contains assistant-neutral workflows and shared implementations; each skill documents its supported hosts and required capabilities. Currently home to spec-driven development (SDD) skills under `skills/claude-ai/development/` — verifying a ticket's claims against the real codebase before writing `spec.md`/`plan.md`/`tasks.md`, then folding what actually shipped back into a project's durable specs — with other categories to follow as they're added. Most skills are Markdown instructions consumed by an assistant with project file access. The general `sdd-specs-init` supports Claude Code, Codex and other file-capable assistants. The paired `project-sync-save`/`project-sync-load` skills also support Codex and bundle a Python 3.9+ standard-library checkpoint engine and unittest suite; no package installation or compilation is needed.

## Architecture: two parallel "specs" directories, do not conflate them

This is the one thing that requires cross-file context to get right, since both directories use the same five core filenames (`constitution.md`, `tech-stack.md`, `data-model.md`, `branching-strategy.md`, `workflow.md`), plus an optional `mission.md` (a template exists; this repo's own specs don't have one):

- **`skills/shared/development/sdd-specs-init/assets/specs/`** — committed, public-facing, generic fill-in-the-blank templates. These ship *to adopters*: the general `sdd-specs-init` skill fills them into a project-selected specs directory (or an adopter copies them by hand). An optional project-relative argument selects the directory; without it the destination is `docs/specs/`. The selected folder is created if missing. Editing these files changes what every future adopter starts from. They live inside `sdd-specs-init` so they travel with it, whether it's installed by symlink or copy.
- **`.claude/specs/`** (this repo's own, tracked in git) — the actual constitution/specs *for ai-skills itself*, written the same way any project using these skills would write its own. Editing these only affects how `sdd-ticket-start`/`sdd-ticket-close` behave if run against this repo directly (e.g. to add a new skill here).

A change describing "how this repo works" belongs in `.claude/specs/`. A change describing "what an adopter's blank template should say" belongs in `skills/shared/development/sdd-specs-init/assets/specs/`. See `.claude/specs/constitution.md` Article 5.

## Architecture: skill folder structure

Each canonical skill is `skills/<compatibility>/<category>/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). Compatibility (`claude-ai/` or `shared/`) states the supported workflows; category (e.g. `development/`) groups skills by specialization as the collection grows — both are repository organization only and are dropped when a skill is installed (see "Installation model" below). Only create a new category folder once its first real skill exists; don't scaffold empty placeholder categories speculatively. The `description` is the discovery text assistants see before loading the skill, so it carries all the trigger phrasing — treat it as load-bearing, not boilerplate. Long-form content that would bloat the primary instructions (worked examples, document skeletons) lives in `skills/<compatibility>/<category>/<name>/references/*.md` and is linked from `SKILL.md`, not inlined.

`sdd-specs-init` accepts one optional project-relative specs-directory argument and creates it if missing. Without the argument it always uses `docs/specs/`; existing locations or configuration do not override that default. The current Claude ticket skills still read `.claude/specs/`, so initialization for those consumers must pass `.claude/specs` explicitly. `sdd-ticket-start` and `sdd-ticket-close` are a paired start/close-out skill: each `SKILL.md` states explicitly where its own responsibility ends and the other's begins (`sdd-ticket-start` stops at `tasks.md` and hands off to `superpowers:executing-plans`; `sdd-ticket-close` only runs after a ticket has actually merged to production, verified via git, not taken on faith).

## Design constraint: stack and host agnosticism

Both skills read project-specific detail (base branch name, dependency-manager tooling, ticket status names) from the *consuming* project's own `.claude/specs/` files at run time — nothing about a specific language, framework, or vendor is hardcoded into a skill. This was a deliberate generalization from earlier Magento/Composer-specific originals; when editing either skill, avoid reintroducing stack-specific assumptions into the shared instructions (illustrative examples in `references/templates.md` are fine — logic in `SKILL.md` is not).

## Project handoffs

`project-sync-save` owns the shared Python engine, protocol reference and tests. `project-sync-load` has a thin launcher that resolves the adjacent save skill. Install both as sibling symlinks or complete copied folders; Claude Code uses `~/.claude/skills/`, Codex uses `~/.agents/skills/`. `.ai-sync/` is local ignored handoff state, separate from project specs and cross-project communication. No automatic commits, assistant switching or usage monitoring. Run `python3 -m unittest discover -s skills/shared/development/project-sync-save/scripts -p 'test_*.py' -v` after engine changes.

## Model roles in Claude-only skills

For workflows in `skills/claude-ai/`, pin a Claude model only where a skill actually dispatches an agent, and document the role next to that dispatch, not in a policy section per skill:

- **Opus** (`model: "opus"`) for synthesis and judgment: planning, reconciling conflicting evidence, deciding what's durable, final review. Currently: `sdd-ticket-start`'s planning subagent and fallback review subagent, and `sdd-ticket-close`'s reconciliation subagent.
- **Sonnet** (`model: "sonnet"`) for parallel evidence collection and implementation workers.
- **No `model`** (inherit) for everything else, including the main-session steps and deterministic skills like `review-instructions-install`.

`opus` and `sonnet` are Claude Code's aliases for the latest model in each family, so skills never name a version. A pinned model needs a fresh (non-fork) agent, because a fork ignores the `model` override. External skills and plugins (`superpowers:executing-plans`, `/codex:review`, `/code-review`) choose their own models; skills can only recommend a session model for them, not set one.

## Installation model

There is no package manager or plugin manifest. Install each complete skill folder under a flat name: Claude Code uses `~/.claude/skills/<name>` (or a project's `.claude/skills/<name>`); Codex uses `~/.agents/skills/<name>` (or `.agents/skills/<name>`). Symlink to the canonical source directory for live updates via `git pull`, or copy for a frozen snapshot. Install both project-sync skills as siblings. Claude-only workflows are not advertised as Codex-compatible merely because they use Markdown.

The repository contains only canonical skill directories, with no compatibility symlinks. Existing installed links must point directly to `skills/claude-ai/development/<name>` or `skills/shared/development/<name>`. Keep installed names flat and use the canonical paths in documentation. See README.md for installation and migration commands.

## Shared code review gate

For code changes, start an independent review of the uncommitted diff in the background before reporting completion or committing. Codex uses `codex review --uncommitted`; Claude Code uses the adapter in `CLAUDE.md`. Use an available equivalent if the preferred reviewer is unavailable; if no reviewer can run, report the unmet gate instead of claiming a clean review.

Triage every finding: fix confirmed issues and explain rejected findings. After fixes rerun appropriate checks and review again. Stop when no medium-or-higher findings remain (or the reviewer approves), when a round only repeats already fixed/rejected findings, or after five review rounds. Report remaining findings and severity at the cap; report remaining low findings without expanding scope to fix them. A clean review does not authorize a commit. Documentation-only edits do not require this gate.
