---
name: sdd-specs-init
description: Creates or updates a project's spec-driven development (SDD) specs under .claude/specs/ (constitution.md, tech-stack.md, data-model.md, branching-strategy.md, workflow.md) — drafting each file from what the repo actually shows (manifests, lockfiles, git branches, schema files, existing CLAUDE.md/AGENTS.md/README rules), then asking the user only what code can't reveal, such as the team's non-negotiable rules, ticket statuses, and merge policy. Use this skill whenever the user wants to set up, create, init, bootstrap, fill in, or update the project specs or a project constitution — e.g. "create a constitution for this project", "set up .claude/specs", "we don't have specs yet", "update the tech stack spec", "fill in the SDD templates" — and suggest it when starting SDD (sdd-ticket-start) in a project with no .claude/specs/. Safe to re-run — existing files are updated in place, never overwritten wholesale. Works with any language, stack, or tracker.
---

# SDD Specs Init

Creates or updates the five durable spec files that `sdd-ticket-start` and `sdd-ticket-close` read from `.claude/specs/`. The principle is the same one those skills follow: don't guess. Most of a spec can be read straight from the repo, so draft that part first. Then ask the user only what code genuinely can't tell you. A constitution, in particular, is the team's rules, and those can't be inferred.

The templates live in [`assets/specs/`](assets/specs/). Each one opens with a `<!-- comment -->` block explaining what the file holds and which skill step reads it. Treat that block as your guide for the file, and remove it only once the file is filled in.

## Step 1 — Locate

The target is `.claude/specs/` in the session's current working directory. For each of the five files, note whether it's **missing** (create it from the template) or **exists** (update mode, Step 5). If the user named specific files ("just the constitution"), limit the run to those.

## Step 2 — Derive (read-only)

Draft as much as the repo supports, citing where each fact came from:

| File | Derive from the repo | Must ask |
|---|---|---|
| `tech-stack.md` | Manifests and lockfiles, with versions verified via the project's own tooling (e.g. `composer show`, `npm ls`); test runner, linter and CI config files | Hosting/environments, if nothing in the repo shows them |
| `branching-strategy.md` | `git branch -a`, `git remote -v`, default branch via `git symbolic-ref refs/remotes/origin/HEAD`, prefixes seen in existing branch names | Merge policy; whether the remote can be used non-interactively; confirm base vs. production branch |
| `data-model.md` | Custom entities only, from schema/migration/model files; summarize rather than dump columns | Known incomplete state (mid-migration, deferred work) |
| `constitution.md` | Candidate rules already stated in `CLAUDE.md`/`AGENTS.md`/`README`, and standards enforced by linter configs, each citing its source | The team's non-negotiable rules; keep or drop each candidate |
| `workflow.md` | Rarely anything; maybe a PR template or CI deploy trigger | Ticket statuses, what triggers each, and how they map to branches/environments |

If the folder isn't a git repo, skip the git commands and ask the branching questions directly. On a new, near-empty project (greenfield) there's little or nothing to derive: say so, and run Step 3 as an interview covering all five files instead. The protocol still applies, so recommend a default for each choice. If versions can't be verified (no lockfile, dependencies not installed), record the manifest's constraints and say plainly that they're unverified.

A constitution candidate needs a source that *states* or *enforces* the rule: project docs, or a linter/CI config. A pattern you merely observe in the code (e.g. "all schema changes happen to use migrations") is not a rule, and neither is a framework best practice you know from elsewhere. Turn those into questions for Step 3, not candidates.

## Step 3 — Clarify with the user

Ask only what you can't find out yourself: investigate first, and never ask what the code, docs, or git history already answer.
1. **Confirm, don't ask, what you inferred.** Present a compact summary of the derived drafts for correction ("I found X; correct?").
2. **Ask the real gaps in one grouped round.** Use `AskUserQuestion` (or the host's equivalent; up to 4 questions, 2–4 options each, "Other" is added automatically) for a small natural set of options, recommended option first. Use open conversation for anything that needs the user's own words — constitution rules usually do.
3. **Probe the reasons behind scope-setting answers.** When an answer sets a rule, ask why; the reason belongs in the Article, and it often sharpens the rule itself.
4. **Allow one follow-up round at most.** Record anything still unresolved, or answered "don't know", as `TBD — <question>`; never invent an answer.
5. **Write the answers into the file that uses them**, not just into the chat.

## Step 4 — Write

Follow each template's structure:
- Remove the guidance comment block, and drop template placeholders (like example Articles) that nothing supports. `TBD` is for real open questions, not for keeping empty placeholders around.
- Constitution Articles come only from rules the user confirmed or from Step 2 candidates with a cited source. Never add a plausible-sounding rule of your own; a speculative Article gets enforced against every future plan.
- A candidate the user hasn't confirmed (they didn't answer, or said "don't know") keeps an `(unconfirmed — source: <file>)` marker in its heading, so nobody mistakes it for an agreed rule. A later run removes the marker once it's confirmed.
- Mark unknowns as `TBD — <question>` so the next session can see what's missing. In `constitution.md`, collect them under a final `## Open Questions` section, not as numbered Articles: `sdd-ticket-start` checks every plan against every Article, and an unanswered question isn't a rule.
- Replace template instruction lines (like the constitution's `**Status:** Draft — fill in…`) with the file's real status.
- Keep LF line endings.

## Step 5 — Update mode (file already exists)

- Fill remaining placeholders and missing sections.
- Leave already-filled content alone, unless a derived fact contradicts it (e.g. a version that changed). In that case, show the diff and ask before changing it.
- Re-running is always safe; a file that's already complete and accurate stays unchanged.

## Step 6 — Report

Per file: created, updated (what changed), or unchanged, plus any open `TBD`s.

Specs are meant to be tracked in git, so the team shares them and they're versioned with the code. Check with `git check-ignore -v .claude/specs/constitution.md`. If they're ignored, show the user the matching `.gitignore` rule and the change that un-ignores them (e.g. `.claude/` becomes `.claude/*` plus `!.claude/specs/`, which keeps the rest of `.claude/` ignored), and apply it once they agree. Then tell the user the specs are ready to commit; the commit itself follows the project's usual commit rules.
