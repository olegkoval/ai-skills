# ai-skills

Reusable skills for Claude Code, Codex and other assistants with access to project files, organized by supported assistant and specialization.

## General skills

### Development

| Skill | Use it when | Assistant support |
|---|---|---|
| [`sdd-specs-init`](skills/shared/development/sdd-specs-init) | Create or refresh a project constitution, tech stack, data model, branching strategy, workflow and optional mission. Derives facts from repository evidence and asks only about missing decisions. Accepts an optional specs-directory argument, creates the folder if missing, and uses `docs/specs/` when omitted. | Claude Code, Codex and other assistants with file access; no specific plugin, model or question tool. |
| [`project-sync-save`](skills/shared/development/project-sync-save) | Save task context, decisions, authorization, unfinished operations, verification artifacts and current files/Git state before pausing or switching assistants. | Shared Claude Code/Codex workflow. |
| [`project-sync-load`](skills/shared/development/project-sync-load) | Compare a checkpoint with actual project state, reconcile differences and continue within existing authorization. | Shared Claude Code/Codex workflow. |

`sdd-specs-init` is a general workflow. The handoff pair is shared between Claude Code and Codex; its engine currently accepts those two assistant identifiers. Other assistants can read the format, but broader save identifiers have not yet been implemented. See [Project specs](#project-specs) and [Project handoffs](#project-handoffs) for details.

## AI-specific skills

### Claude Code — Development

| Skill | Use it when |
|---|---|
| [`sdd-ticket-start`](skills/claude-ai/development/sdd-ticket-start) | Investigate a ticket against the real codebase, clarify its scope, create a branch, and write `spec.md`, `plan.md` and `tasks.md` before implementation. Uses Claude model/delegation conventions and a Superpowers execution handoff. |
| [`sdd-ticket-close`](skills/claude-ai/development/sdd-ticket-close) | After a ticket has merged and shipped, verify the actual commits, reconcile the delivered work against its plan, update durable specs and safely clean up ticket files and the local branch. Uses a Claude reconciliation agent. |
| [`review-instructions-install`](skills/claude-ai/development/review-instructions-install) | Install or update the versioned Claude review-gate block in a project's `CLAUDE.md`. Runs safely again, upgrading older blocks while preserving surrounding text. |

The ticket skills treat a ticket as a claim to verify. Ticket descriptions, vendor bulletins and secondhand bug reports can be vague or wrong; investigation must establish what actually needs to change before planning. The workflow is investigation and planning, approved implementation, then reconciliation after shipping.

These workflows are language- and stack-agnostic, but remain Claude-oriented. Project details such as base branch, dependency tooling and ticket statuses come from `.claude/specs/`; assistant-specific commands and model aliases stay in their skill definitions. There are currently no Codex-only or Copilot-only skills in this repository.

The review installer writes `/codex:review --background`, finding triage, capped re-review rounds and a `/code-review low`/`medium` fallback into `CLAUDE.md`. The Codex plugin is recommended but optional for that workflow. The canonical block lives in [`assets/review-instructions-block.md`](skills/claude-ai/development/review-instructions-install/assets/review-instructions-block.md); edit it and bump its marker version to change the installed instructions.

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
for skill in sdd-ticket-start sdd-ticket-close review-instructions-install; do
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
for skill in sdd-ticket-start sdd-ticket-close review-instructions-install; do
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

Existing specs and configuration do not change the no-argument default. The current Claude `sdd-ticket-start` and `sdd-ticket-close` skills still read `.claude/specs/`: initialize or update their specs with `/sdd-specs-init .claude/specs`. Files in other specs directories remain in place, and existing files in the selected directory are updated rather than replaced wholesale.

The [bundled templates](skills/shared/development/sdd-specs-init/assets/specs) contain guidance comments and placeholders. The skill fills them from evidence and user decisions; it records unknowns instead of inventing rules. If working manually, copy the templates to the project's chosen specs directory, fill them in and remove the guidance comments.

| File | What it captures |
|---|---|
| `constitution.md` | Explicit technical rules a plan must satisfy, with reasons and sources |
| `tech-stack.md` | Language, framework, dependencies and tooling, distinguishing verified versions from constraints |
| `data-model.md` | Custom entities, storage, relationships and known incomplete work |
| `branching-strategy.md` | Versioning arrangement, branch roles, prefixes, merge policy and environments |
| `workflow.md` | Ticket lifecycle and its branch/environment mapping, if the project has one |
| `mission.md` (optional) | Purpose, audience, scope, success criteria and business constraints |

Specs are team memory and should be tracked when Git is used. The skill checks the selected path against actual ignore rules and proposes any needed change. Git is optional; projects without it can keep local specs and document their sharing arrangement. Installed tooling is used where available, with unavailable evidence reported as unverified. No fixed assistant API or model is needed.

## Project handoffs

The save/load pair uses one Python 3.9+ standard-library engine and one versioned checkpoint format. Git is needed only for Git projects. Handoffs live locally in ignored `.ai-sync/`, with atomic retained snapshots and selected logs/scripts copied into durable storage. Git saves capture branch, HEAD, index/worktree patches and untracked inventory without committing. Loading compares reality and requires a recorded reconciliation before resuming; processes and locks are inspected without automatically stopping or releasing them.

In Claude Code invoke `/project-sync-save` or `/project-sync-load`; in Codex invoke `$project-sync-save` or `$project-sync-load`. The user chooses when to switch. There is no usage monitoring, automatic switching, cloud storage or private chat-history requirement. Cross-project communication uses the project's separate established mechanism.

The assistant supplies semantic context from the conversation; scripts capture observable state. Optional `.ai-sync.json` supplies extra rule paths, otherwise ignored files and excluded non-Git directory names. See the [shared protocol](skills/shared/development/project-sync-save/references/protocol.md) for schemas, CLI commands, comparison coverage, exit codes and recovery. Source contents are preserved only through Git patches and selected artifacts.

Validate the engine after code changes:

```bash
python3 -m unittest discover -s skills/shared/development/project-sync-save/scripts -p 'test_*.py' -v
```

This repository's first practical handoff is in local ignored `.ai-sync/`. Start the receiving assistant in this clone and invoke `project-sync-load` to compare and reconcile it. Local checkpoints are not shipped in Git.

## Quick start: Claude SDD ticket workflow

1. Install the general `sdd-specs-init` and Claude `sdd-ticket-start`/`sdd-ticket-close` skills. Run `/sdd-specs-init .claude/specs` to initialize specs for these ticket consumers.
2. Give Claude a ticket: *"Here's PROJ-123: <description>. Let's use SDD for this."*
3. Review `.claude/tickets/PROJ-123/spec.md` and `plan.md`, including the investigation evidence.
4. After approval, implement against `plan.md`/`tasks.md` and keep them current when the work changes.
5. After shipping, ask Claude to close out the ticket. It verifies merged work, updates `.claude/specs/` and performs the authorized ticket-file/branch cleanup.

## License

[MIT](LICENSE)
