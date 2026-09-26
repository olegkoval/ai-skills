# ai-skills

A growing collection of reusable [Claude Code](https://claude.com/claude-code) skills, organized by specialization under `skills/<category>/`.

## Skills in this repo

### Development

Spec-driven development (SDD) skills: turning a raw ticket into a verified spec, plan, and task list before any code is written, and folding what shipped back into a project's durable specs once it's live.

Ticket descriptions — vendor bulletins, customer-reported bugs, anything paraphrased secondhand — are frequently vague, wrong, or narrower/broader than they claim. Writing implementation code straight from a ticket means inheriting whatever assumptions the ticket got wrong. SDD, as implemented here, treats a ticket as a *claim to verify*, not a fact to implement:

1. **Kick off** — investigate the ticket against the real codebase and tooling, clarify with you whatever the investigation couldn't settle, then write `spec.md` (what's actually true), `plan.md` (how to fix it, checked against project rules), and `tasks.md` (a concrete checklist) — before writing implementation code.
2. **Implement** — against the approved plan.
3. **Close out** — once shipped, verify what actually merged (not just what the plan intended), and fold any durable lessons back into the project's standing specs so the next ticket starts from an accurate baseline.

| Skill | Use it when |
|---|---|
| [`skills/development/sdd-specs-init`](skills/development/sdd-specs-init) | A project has no `.claude/specs/` yet, or they're out of date. Drafts the five spec files from what the repo shows (manifests, git branches, schema files, stated rules), then asks you only what code can't reveal, such as your team's rules and ticket statuses. On a new project with nothing to derive, it interviews you instead. Safe to re-run. |
| [`skills/development/sdd-ticket-start`](skills/development/sdd-ticket-start) | You're handed a ticket (Jira, Linear, GitHub Issues, or similar) and want to start it with SDD. Creates the branch, investigates the ticket's claims, clarifies open questions with you, produces `spec.md`/`plan.md`/`tasks.md`. |
| [`skills/development/sdd-ticket-close`](skills/development/sdd-ticket-close) | A ticket that went through `sdd-ticket-start` has merged and deployed. Re-verifies the merge via git, reconciles the real diff against the plan, updates the project's durable specs, and cleans up the ticket folder and branch. |

All three are language- and stack-agnostic. Project-specific detail (base branch name, dependency tooling, ticket status names) is read from a project's own `.claude/specs/` files rather than assumed — see [Project specs](#project-specs) below.

A code review gate, switched on per project:

| Skill | Use it when |
|---|---|
| [`skills/development/review-instructions-install`](skills/development/review-instructions-install) | You want a project to require a code review before commits. Writes a versioned block into that project's `CLAUDE.md` (creating the file if needed): run `/codex:review --background` after code changes, triage findings, re-review up to 5 rounds, and fall back to `/code-review low`/`medium` if Codex isn't available. Safe to re-run: it upgrades an older block and leaves a current one alone. |

**Codex plugin: recommended, not required.** The installed instructions prefer the Codex plugin's `/codex:review` (from the `openai-codex` marketplace; run `/codex:setup` to check it's ready). Without it, reviews fall back to Claude Code's built-in `/code-review` at `low` or `medium` level, so the gate still works.

The block's text lives in the skill's [`assets/review-instructions-block.md`](skills/development/review-instructions-install/assets/review-instructions-block.md). To change it, edit that file, bump the version in its start marker, and re-run the skill in each project.

## Installation

Clone this repo once, then link the skill(s) you want. Claude Code supports a skill folder under `~/.claude/skills/<name>/` (or a project's `.claude/skills/<name>/`) being a symlink to a directory elsewhere on disk — it follows the link and reads `SKILL.md` from the target. That means a symlinked skill stays current with a plain `git pull` in this repo, with no re-copying:

```bash
# Personal skills (available in every project) — run from the cloned repo root
ln -s "$(pwd)/skills/development/sdd-specs-init" ~/.claude/skills/sdd-specs-init
ln -s "$(pwd)/skills/development/sdd-ticket-start" ~/.claude/skills/sdd-ticket-start
ln -s "$(pwd)/skills/development/sdd-ticket-close" ~/.claude/skills/sdd-ticket-close
ln -s "$(pwd)/skills/development/review-instructions-install" ~/.claude/skills/review-instructions-install

# Or project-local skills (checked into that project's repo)
ln -s "$(pwd)/skills/development/sdd-specs-init" <your-project>/.claude/skills/sdd-specs-init
ln -s "$(pwd)/skills/development/sdd-ticket-start" <your-project>/.claude/skills/sdd-ticket-start
ln -s "$(pwd)/skills/development/sdd-ticket-close" <your-project>/.claude/skills/sdd-ticket-close
ln -s "$(pwd)/skills/development/review-instructions-install" <your-project>/.claude/skills/review-instructions-install
```

The category folder (`development/`) is only how this repo organizes skills on disk — the symlink's destination name is what Claude Code actually sees, so it's always flat regardless of source nesting. Adding a skill later is one more `ln -s` line; nothing activates automatically just because it exists in the repo.

Since a symlinked skill's instructions take effect the moment you `git pull` — and `SKILL.md` is instructions Claude follows directly — it's worth a quick `git log`/`git diff` glance after pulling to see what changed, the same way you'd review any other update to something that drives Claude's behavior. See the official docs on [symlinked skill entries](https://code.claude.com/docs/en/skills.md#where-skills-live) for how Claude Code resolves these.

**Prefer a frozen snapshot instead of live updates?** Copy instead of linking:

```bash
cp -r skills/development/sdd-specs-init ~/.claude/skills/
cp -r skills/development/sdd-ticket-start ~/.claude/skills/
cp -r skills/development/sdd-ticket-close ~/.claude/skills/
cp -r skills/development/review-instructions-install ~/.claude/skills/
```

Either way, Claude Code discovers skills automatically from either location — no further configuration needed.

## Project specs

`sdd-ticket-start` and `sdd-ticket-close` both read a project's `.claude/specs/` directory for context (technical rules, tech stack, data model, branching convention, ticket workflow) and update it as tickets close out.

The easiest way to create them is to run `/sdd-specs-init` in the project. The templates it fills in are in [`skills/development/sdd-specs-init/assets/specs/`](skills/development/sdd-specs-init/assets/specs), each with inline comments describing exactly what each skill step reads from it. To fill them in by hand instead:

```bash
mkdir -p <your-project>/.claude/specs
cp skills/development/sdd-specs-init/assets/specs/*.md <your-project>/.claude/specs/
```

Fill in the placeholders for your project, then delete the `<!-- comment -->` block at the top of each file. None of the five files are required — a project missing `.claude/specs/` entirely still works with the ticket skills, just with less context to check plans and investigation against.

| File | What it captures |
|---|---|
| `constitution.md` | Non-negotiable technical rules a plan must satisfy (e.g. "never edit vendor code directly") |
| `tech-stack.md` | What's actually installed — language, framework, key dependencies, tooling |
| `data-model.md` | Custom entities/tables and their relationships |
| `branching-strategy.md` | Base branch, ticket-branch prefix, production branch, remote type |
| `workflow.md` | The ticket tracker's status lifecycle and how it maps to branch/environment flow |

## Quick start: SDD ticket workflow

1. Install `sdd-specs-init`, `sdd-ticket-start`, and `sdd-ticket-close` (see above), and optionally run `/sdd-specs-init` in the project to create `.claude/specs/`.
2. Hand Claude a ticket: *"Here's PROJ-123: <description>. Let's use SDD for this."*
3. Review `.claude/tickets/PROJ-123/spec.md` and `plan.md` — these are gates, not rubber stamps. Push back if the investigation looks thin.
4. Once approved, implementation proceeds from `plan.md`/`tasks.md`.
5. After the ticket ships (merged to your production branch), ask Claude to close it out: *"PROJ-123 is deployed, update the specs."* This reconciles the real merged diff against the plan, updates `.claude/specs/`, and removes the ticket folder and branch.

## License

[MIT](LICENSE)
