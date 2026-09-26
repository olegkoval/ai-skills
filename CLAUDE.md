# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A collection of reusable Claude Code skills, organized by specialization under `skills/<category>/`. Currently home to spec-driven development (SDD) skills under `skills/development/` — verifying a ticket's claims against the real codebase before writing `spec.md`/`plan.md`/`tasks.md`, then folding what actually shipped back into a project's durable specs — with other categories to follow as they're added. There is no build, lint, or test tooling — the repo is pure Markdown (`SKILL.md` files and reference docs) consumed directly by Claude Code. There is nothing to install or compile.

## Architecture: two parallel "specs" directories, do not conflate them

This is the one thing that requires cross-file context to get right, since both directories use the same five core filenames (`constitution.md`, `tech-stack.md`, `data-model.md`, `branching-strategy.md`, `workflow.md`), plus an optional `mission.md` (a template exists; this repo's own specs don't have one):

- **`skills/development/sdd-specs-init/assets/specs/`** — committed, public-facing, generic fill-in-the-blank templates. These ship *to adopters*: the `sdd-specs-init` skill fills them into a project's own `.claude/specs/` (or an adopter copies them by hand). Editing these files changes what every future adopter starts from. They live inside `sdd-specs-init` so they travel with it, whether it's installed by symlink or copy.
- **`.claude/specs/`** (this repo's own, tracked in git) — the actual constitution/specs *for ai-skills itself*, written the same way any project using these skills would write its own. Editing these only affects how `sdd-ticket-start`/`sdd-ticket-close` behave if run against this repo directly (e.g. to add a new skill here).

A change describing "how this repo works" belongs in `.claude/specs/`. A change describing "what an adopter's blank template should say" belongs in `skills/development/sdd-specs-init/assets/specs/`. See `.claude/specs/constitution.md` Article 5.

## Architecture: skill folder structure

Each skill is `skills/<category>/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). The category (e.g. `development/`) groups skills by specialization as the collection grows — it's a repo-organization concept only, and is dropped when a skill is installed (see "Installation model" below). Only create a new category folder once its first real skill exists; don't scaffold empty placeholder categories speculatively. The `description` is the only thing Claude sees before deciding to invoke the skill, so it carries all the trigger phrasing — treat it as load-bearing, not boilerplate. Long-form content that would bloat the primary instructions (worked examples, document skeletons) lives in `skills/<category>/<name>/references/*.md` and is linked from `SKILL.md`, not inlined.

`sdd-specs-init` creates or updates a project's `.claude/specs/` that the ticket skills read. `sdd-ticket-start` and `sdd-ticket-close` are a paired start/close-out skill: each `SKILL.md` states explicitly where its own responsibility ends and the other's begins (`sdd-ticket-start` stops at `tasks.md` and hands off to `superpowers:executing-plans`; `sdd-ticket-close` only runs after a ticket has actually merged to production, verified via git, not taken on faith).

## Design constraint: stack and host agnosticism

Both skills read project-specific detail (base branch name, dependency-manager tooling, ticket status names) from the *consuming* project's own `.claude/specs/` files at run time — nothing about a specific language, framework, or vendor is hardcoded into a skill. This was a deliberate generalization from earlier Magento/Composer-specific originals; when editing either skill, avoid reintroducing stack-specific assumptions into the shared instructions (illustrative examples in `references/templates.md` are fine — logic in `SKILL.md` is not).

## Installation model

There's no package manager or plugin manifest yet. The documented, primary installation method is a per-skill symlink: `~/.claude/skills/<name>` (or a project's `.claude/skills/<name>`) can be a symlink to `skills/<category>/<name>/` in a cloned copy of this repo — Claude Code follows it and reads `SKILL.md` from the target, so `git pull` updates the skill live with no re-copy step (see the official docs on [symlinked skill entries](https://code.claude.com/docs/en/skills.md#where-skills-live)). Copying (`cp -r`) is documented as a fallback for a frozen snapshot instead of live updates. Either way the destination is flat, with the category segment dropped — see README.md for the exact commands.

<!-- review-instructions:start v2 -->
## Code review gate

Scope: code changes only (e.g. PHP, XML, JS, `composer.json`) — not docs/specs-only edits.

As soon as a code change is done, before reporting it finished:
1. Run `/codex:review --background` on the uncommitted diff. Never wait in the foreground, and never commit before its result has arrived.
2. When results arrive, triage every finding: fix confirmed issues; reject false positives or findings that conflict with this project's standards, with a one-line reason each.
3. After fixes, re-run lint/tests, then re-review. Max 5 re-review rounds. Stop early if a round only repeats findings already fixed or rejected. If issues remain, stop and report them instead of looping.
4. If the Codex plugin or CLI isn't available (the review can't be started, or fails for setup/auth reasons — `/codex:setup` diagnoses this; don't run it on every change), fall back to `/code-review low` for a small diff (1–2 files) or `/code-review medium` otherwise. Always pass the level explicitly — without one, `/code-review` reuses the last level used.

A clean review is a gate, not a commit trigger — follow this project's usual commit rules.
<!-- review-instructions:end -->
