# ai-skills

Reusable skills for Claude Code, Codex and other assistants with access to project files, organized by supported assistant and specialization.

## General skills

### Development

| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Skill&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Use it when | Assistant support |
|---|---|---|
| [`sdd-specs-init`](skills/shared/development/sdd-specs-init) | Create or refresh a project constitution, tech stack, data model, branching strategy, workflow and optional mission. Derives facts from repository evidence and asks only about missing decisions. Accepts an optional specs-directory argument, creates the folder if missing, and uses `docs/specs/` when omitted. | Claude Code, Codex and other assistants with file access; no specific plugin, model or question tool. |
| [`project-sync-save`](skills/shared/development/project-sync-save) | Save task context, decisions, authorization, unfinished operations, verification artifacts and current files/Git state before pausing or switching assistants. | Shared Claude Code/Codex workflow. |
| [`project-sync-load`](skills/shared/development/project-sync-load) | Compare a checkpoint with actual project state, reconcile differences and continue within existing authorization. | Shared Claude Code/Codex workflow. |

`sdd-specs-init` is a general workflow. The handoff pair is shared between Claude Code and Codex; its engine currently accepts those two assistant identifiers. Other assistants can read the format, but broader save identifiers have not yet been implemented. See [Project specs](#project-specs) and [Project handoffs](#project-handoffs) for details.

## AI-specific skills

### Claude Code — Development

| &nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;Skill&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp;&nbsp; | Use it when |
|---|---|
| [`sdd-ticket-start`](skills/claude-ai/development/sdd-ticket-start) | Investigate a ticket against the real codebase, clarify its scope, create a branch, and write `spec.md`, `plan.md`, `tasks.md` and `planner-risk.json`, then run `sdd-plan-review`'s independent review and gate. Uses Claude model/delegation conventions. |
| [`sdd-plan-review`](skills/claude-ai/development/sdd-plan-review) | Independently review a ticket's plan with a fresh read-only Opus reviewer (one revision round at most), then run a deterministic gate that decides `AUTO_IMPLEMENT` or `HUMAN_REVIEW`. Runs at the end of `sdd-ticket-start`; re-run it after editing a plan. |
| [`sdd-ticket-implement`](skills/claude-ai/development/sdd-ticket-implement) | Start implementing a gated ticket in a fresh session: verify the gate is still current, confirm live when it decided `HUMAN_REVIEW`, hand off to `superpowers:executing-plans`, and check the actual diff against the planned files before commit. Never pushes. |
| [`sdd-ticket-close`](skills/claude-ai/development/sdd-ticket-close) | After a ticket has merged and shipped, verify the actual commits, reconcile the delivered work against its plan, update durable specs and safely clean up ticket files and the local branch. Uses a Claude reconciliation agent. |
| [`review-instructions-install`](skills/claude-ai/development/review-instructions-install) | Install or update the versioned Claude review-gate block in a project's `CLAUDE.md`. Runs safely again, upgrading older blocks while preserving surrounding text. |

The ticket skills treat a ticket as a claim to verify. Ticket descriptions, vendor bulletins and secondhand bug reports can be vague or wrong; investigation must establish what actually needs to change before planning. The workflow is investigation and planning, an independent plan review and gate, implementation in a fresh session, then reconciliation after shipping.

**The plan gate.** A person reads only the plans that need it. Both the planner and a fresh reviewer answer the same risk checklist in [`triggers.json`](skills/claude-ai/development/sdd-plan-review/assets/triggers.json), then `gate.py` applies the project's policy and decides:
- **`AUTO_IMPLEMENT`** only when the project opted in, nobody flagged a risk trigger (`unknown` counts as flagged), no protected path is planned, and the reviewer approved.
- **`HUMAN_REVIEW`** otherwise, including whenever an input is missing or malformed.

The triggers come in three layers:
- **Floor triggers** can never be relaxed: security-sensitive runtime changes, authentication/authorization, secrets, security controls, irreversible data changes, external actions by the agent, open decisions and incomplete investigation.
- **Default triggers** can be relaxed by the project with a stated reason: framework core, schema, public contracts, dependencies, global config, integrations, payments/PII.
- **Project additions:** your own triggers and protected-path globs.

Opt in with `.claude/specs/sdd-gate.json`, starting from the [template](skills/shared/development/sdd-specs-init/assets/sdd-gate.json). Without that file, every plan still gets a human review. The gate only reads that policy path and only accepts ticket folders at `.claude/tickets/<TICKET-CODE>`, so neither can be swapped for another location.

#### `.claude/specs/sdd-gate.json` format

A JSON object with these keys. Any other key, or any invalid value, makes the whole policy invalid, and every plan gets `HUMAN_REVIEW`.

| Key | Required | Value |
|---|---|---|
| `schema` | yes | Always `1`. |
| `description` | no | Free text for people; the gate ignores it. |
| `auto_implement` | no | `true` or `false` (default `false`). Only `true` allows `AUTO_IMPLEMENT`. |
| `relax` | no | Object mapping a **default** trigger ID to a non-empty reason. That trigger then no longer forces human review. Allowed IDs: `framework_core`, `schema_change`, `public_contract`, `dependency_change`, `global_config`, `integration_change`, `payments_pii`. Floor triggers can't be relaxed. |
| `additional_triggers` | no | Object mapping your own trigger ID to its definition. IDs use lowercase letters, digits and `_`, start with a letter, and can't reuse a canonical ID. The planner and reviewer must answer each one; `yes` or `unknown` forces human review. |
| `path_rules` | no | Array of protected-path globs, relative to the project root: no leading `/`, no `..`, forward slashes only. `**` matches any number of directories, `*` matches within one directory, `?` matches one character. Patterns are anchored at the root, so use `**/name` to match at any depth. A planned file matching a rule forces human review. At commit time, an unplanned changed file matching a rule stops for your confirmation. |

Example for a Magento project:

```json
{
  "schema": 1,
  "description": "Auto-implement routine custom-module work; anything touching patches or core config needs a person.",
  "auto_implement": true,
  "relax": {
    "dependency_change": "Lockfile-only bumps of dev tooling are routine here and covered by CI."
  },
  "additional_triggers": {
    "cache_layout": "The change alters full-page cache keys, tags or invalidation."
  },
  "path_rules": ["m2-hotfixes/**", "app/etc/**", "**/etc/db_schema.xml", "**/etc/acl.xml"]
}
```

The file is hashed into each `gate.json`, so editing it makes existing gates stale until `sdd-plan-review` runs again. Track it in Git so the whole team shares one policy.

`gate.py` needs Python 3.9+ (standard library only), and Git to bind a decision to the branch and commit; non-Git projects always get `HUMAN_REVIEW`. Validate gate changes with:

```bash
python3 -m unittest discover -s skills/claude-ai/development/sdd-plan-review/scripts -p 'test_*.py' -v
```

These workflows are language- and stack-agnostic, but remain Claude-oriented. Project details such as base branch, dependency tooling and ticket statuses come from `.claude/specs/`; assistant-specific commands and model aliases stay in their skill definitions. There are currently no Codex-only or Copilot-only skills in this repository.

The review installer writes `/codex:review --background`, finding triage, re-review until no `medium`+ severity findings remain (max 5 rounds), and a `/code-review low`/`medium` fallback into `CLAUDE.md`. If no reviewer can run, the gate is reported as unmet, never passed. The Codex plugin is recommended but optional for that workflow. The canonical block lives in [`assets/review-instructions-block.md`](skills/claude-ai/development/review-instructions-install/assets/review-instructions-block.md); edit it and bump its marker version to change the installed instructions.

## Repository layout

```text
AGENTS.md                              Shared repository instructions
CLAUDE.md                              Imports AGENTS.md; Claude review adapter
skills/shared/development/             General specs initialization and shared handoffs
skills/claude-ai/development/          Claude ticket and review workflows
```

Common authoring, architecture, installation and review rules live in [`AGENTS.md`](AGENTS.md). [`CLAUDE.md`](CLAUDE.md) imports them with `@AGENTS.md`, using [Claude's documented import syntax](https://code.claude.com/docs/en/memory#import-additional-files), and keeps Claude-specific review commands. This repository's own `.claude/specs/` stays in place.

Compatibility and category folders organize source files; installed skill names stay flat. The repository contains canonical directories only, with no compatibility symlinks. The old `skills/development/` paths and `skills/claude-ai/development/sdd-specs-init` have been retired; existing installed symlinks need to point to the current canonical folder. Frozen copies remain usable until explicitly refreshed.

## Installation

Clone this repository once and install complete skill folders. Use symlinks for updates through `git pull`, or copy for a frozen snapshot. Inspect existing entries before replacing them; never overwrite an unrelated directory or skill.

### General and shared skills

Claude Code uses `~/.claude/skills/`; Codex uses `~/.agents/skills/` and supports symlinked folders ([official documentation](https://learn.chatgpt.com/docs/build-skills)). From the cloned repository root:

```bash
mkdir -p ~/.claude/skills ~/.agents/skills
for skill in sdd-specs-init project-sync-save project-sync-load; do
  ln -s "$(pwd)/skills/shared/development/$skill" "$HOME/.claude/skills/$skill"
  ln -s "$(pwd)/skills/shared/development/$skill" "$HOME/.agents/skills/$skill"
done
```

Install the handoff pair together as sibling folders. For project-local discovery use `.claude/skills/` and `.agents/skills/` in the consuming project. Other assistants should use their supported installation mechanism, or be given the complete skill folder and asked to follow `SKILL.md`; automatic discovery depends on the host.

To copy instead of symlink, for example:

```bash
cp -r skills/shared/development/sdd-specs-init ~/.claude/skills/
cp -r skills/shared/development/sdd-specs-init ~/.agents/skills/
```

For handoffs, copy both complete folders into the same skill directory. Templates and references travel inside the skill folders; no package manager or plugin manifest is required.

### Claude-specific skills

```bash
mkdir -p ~/.claude/skills
for skill in sdd-ticket-start sdd-plan-review sdd-ticket-implement sdd-ticket-close review-instructions-install; do
  ln -s "$(pwd)/skills/claude-ai/development/$skill" "$HOME/.claude/skills/$skill"
done
```

Use the same canonical folders for project-local symlinks or frozen copies. Symlinked instructions update when this repository is pulled, so review relevant changes just as you would any other update to instructions an assistant follows.

### Migrate existing symlink installations

Run from this repository root. These commands update symlinks only, leaving copied directories alone:

```bash
for skill in sdd-specs-init project-sync-save project-sync-load; do
  for destination in "$HOME/.claude/skills" "$HOME/.agents/skills"; do
    if [ -L "$destination/$skill" ]; then
      ln -sfn "$(pwd)/skills/shared/development/$skill" "$destination/$skill"
    fi
  done
done
for skill in sdd-ticket-start sdd-plan-review sdd-ticket-implement sdd-ticket-close review-instructions-install; do
  if [ -L "$HOME/.claude/skills/$skill" ]; then
    ln -sfn "$(pwd)/skills/claude-ai/development/$skill" "$HOME/.claude/skills/$skill"
  fi
done
```

Project-local installed symlinks need the same update under their `.claude/skills/` or `.agents/skills/` directory.

## Project specs

Run `sdd-specs-init` with one optional project-relative directory. The selected folder and missing parents are created if needed. Without an argument, the destination is always `docs/specs/`.

For Claude Code:

```text
/sdd-specs-init                    # docs/specs/
/sdd-specs-init .claude/specs       # .claude/specs/
/sdd-specs-init design/specs        # design/specs/
/sdd-specs-init "project docs/specs" # project docs/specs/
```

Claude Code passes trailing skill arguments through its [documented argument mechanism](https://code.claude.com/docs/en/skills#pass-arguments-to-skills). In Codex or another assistant, invoke or mention the skill with the same directory in your request. Arguments are local directory paths, not web URLs or commands; they must stay within the selected project.

Existing specs and configuration do not change the no-argument default. The Claude ticket skills (`sdd-ticket-start`, `sdd-plan-review`, `sdd-ticket-implement`, `sdd-ticket-close`) read `.claude/specs/`: initialize or update their specs with `/sdd-specs-init .claude/specs`. Files in other specs directories remain in place, and existing files in the selected directory are updated rather than replaced wholesale.

The [bundled templates](skills/shared/development/sdd-specs-init/assets/specs) contain guidance comments and placeholders. The skill fills them from evidence and user decisions; it records unknowns instead of inventing rules. If working manually, copy the templates to the project's chosen specs directory, fill them in and remove the guidance comments.

| File | What it captures |
|---|---|
| `constitution.md` | Explicit technical rules a plan must satisfy, with reasons and sources |
| `tech-stack.md` | Language, framework, dependencies and tooling, distinguishing verified versions from constraints |
| `data-model.md` | Custom entities, storage, relationships and known incomplete work |
| `branching-strategy.md` | Versioning arrangement, branch roles, prefixes, merge policy and environments |
| `workflow.md` | Ticket lifecycle and its branch/environment mapping, if the project has one |
| `mission.md` (optional) | Purpose, audience, scope, success criteria and business constraints |
| `sdd-gate.json` (optional, `.claude/specs/` only) | Opt-in policy for the plan gate: `auto_implement`, default-trigger relaxations with reasons, extra triggers, protected-path globs. Created only when you ask. |

Specs are team memory and should be tracked when Git is used. The skill checks the selected path against actual ignore rules and proposes any needed change. Git is optional; projects without it can keep local specs and document their sharing arrangement. Installed tooling is used where available, with unavailable evidence reported as unverified. No fixed assistant API or model is needed.

## Project handoffs

The save/load pair uses one Python 3.9+ standard-library engine and one versioned checkpoint format. Git is needed only for Git projects. Handoffs live locally in ignored `.ai-sync/`, with atomic retained snapshots and selected logs/scripts copied into durable storage. Git saves capture branch, HEAD, index/worktree patches and untracked inventory without committing. Loading compares reality and requires a recorded reconciliation before resuming; processes and locks are inspected without automatically stopping or releasing them. It refuses a `.ai-sync/` that is tracked or not ignored in Git, and symlinked handoff files, so a handoff committed to a repository you cloned is never presented as yours.

In Claude Code invoke `/project-sync-save` or `/project-sync-load`; in Codex invoke `$project-sync-save` or `$project-sync-load`. The user chooses when to switch. There is no usage monitoring, automatic switching, cloud storage or private chat-history requirement. Cross-project communication uses the project's separate established mechanism.

The assistant supplies semantic context from the conversation; scripts capture observable state. Optional `.ai-sync.json` supplies extra rule paths, otherwise ignored files and excluded non-Git directory names. See the [shared protocol](skills/shared/development/project-sync-save/references/protocol.md) for schemas, CLI commands, comparison coverage, exit codes and recovery. Source contents are preserved only through Git patches and selected artifacts.

Validate the engine after code changes:

```bash
python3 -m unittest discover -s skills/shared/development/project-sync-save/scripts -p 'test_*.py' -v
```

## Quick start: Claude SDD ticket workflow

1. Install the general `sdd-specs-init` and the Claude `sdd-ticket-start`, `sdd-plan-review`, `sdd-ticket-implement` and `sdd-ticket-close` skills. Run `/sdd-specs-init .claude/specs` to initialize specs for these ticket consumers. To allow automatic implementation of low-risk plans, add `.claude/specs/sdd-gate.json` with `"auto_implement": true`.
2. Give Claude a ticket: *"Here's PROJ-123: <description>. Let's use SDD for this."* It ends with the gate's decision.
3. On `HUMAN_REVIEW`, read `.claude/tickets/PROJ-123/spec.md` and `plan.md` and the listed reasons. On `AUTO_IMPLEMENT`, no document review is needed.
4. In a fresh session (Sonnet recommended), run `/sdd-ticket-implement PROJ-123`. It re-verifies the gate, asks you to confirm if a human review was required, implements, and checks the diff before a local commit. Edit the plan only through the agent, then re-run `/sdd-plan-review`.
5. After shipping, ask Claude to close out the ticket. It verifies merged work, updates `.claude/specs/` and performs the authorized ticket-file/branch cleanup.

## Safety boundaries

The skills treat a permission or policy denial as a stopping point, not something to work around. A refused command, a missing credential or a hook rejection is reported to you rather than retried by another route. Actions that change something outside your working tree, such as `git push`, deleting a remote branch, publishing or deploying, wait for your explicit approval; read-only lookups don't. Some skills go further: `sdd-ticket-start` never pushes at all, and asks you to run the push yourself.

Those are instructions, not enforcement. For real enforcement, configure your project's permission rules. For example, in `.claude/settings.json` (shared with the team) or `~/.claude/settings.json` (all your projects):

```json
{
  "permissions": {
    "ask": ["Bash(git push *)", "Bash(git branch -D *)"]
  }
}
```

`ask` and `deny` rules are checked before `allow` and don't need workspace trust ([permissions](https://code.claude.com/docs/en/permissions)). Permission rules match the command string, so an equivalent form like `git -C . push` doesn't match `Bash(git push *)`. Treat them as a strong default, not a sandbox, and add entries for your own deploy and publish commands.

This repository ships no hooks, for three reasons:
- **Hooks only fail closed on recent versions.** `onFailure: "block"` needs Claude Code v2.1.295 or later. On older versions a hook that crashes or times out lets the action through, and these skills can't know which version your project runs.
- **A hook defined in a skill stays active for the rest of the session**, so it would also block actions you approve later.
- **Good validation is project-specific.** A `PreToolUse` hook receives the tool input as structured data, so unlike a permission rule it can parse a command and catch equivalent forms such as `git -C . push`. Its `if` filter is only a best-effort string match, though, so the hook script has to do that validation itself. Writing it well means knowing which commands and environments matter, and a generic skill can't.

If your project wants a hook-based guard, configure it in the project's own settings with `onFailure: "block"`. Treat it as a stronger check than a permission rule, not a complete security boundary.

## License

[MIT](LICENSE)
