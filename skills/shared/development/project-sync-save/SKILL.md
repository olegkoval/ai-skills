---
name: project-sync-save
description: Save a local project handoff before switching between Claude Code and Codex, pausing work, or ending a session. Capture task context, decisions, authorization, unfinished operations, verification artifacts, and actual project state. Use project-sync-load to reconcile and resume a saved handoff.
---

# Project Sync Save

Create a durable handoff in the project's ignored `.ai-sync/`. The user chooses when to switch assistants. Do not monitor usage, start another assistant, or switch automatically. This skill ends after saving and reporting the checkpoint; `project-sync-load` owns reconciliation and resumption.

1. Select the explicit project root; use the worktree root for Git projects, including linked worktrees. For projects without Git use the user’s project directory, never an arbitrary ancestor. Read applicable `AGENTS.override.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, `.claude/rules/`, `.claude/specs/`, and optional `.ai-sync.json`; follow imports and scoped instructions. Missing instructions are not invented. Discover verification, cleanup, communication, and branch rules from these sources.
2. Read [the shared protocol](references/protocol.md). Assemble its context JSON from the conversation and observed work. Include the task, user decisions with sources, completed and remaining work, one exact next action, verification commands/results and limitations, and existing authorization boundaries. Distinguish observations from assumptions. A checkpoint transfers context, never new permissions; host sandbox approvals do not transfer.
3. Inventory unfinished commands, reviews, migrations, Git operations, child agents, known running processes (PID, purpose, start identity, logs, how to reconnect), locks (path, owner, release condition), and cleanup (what, when, who, authorization). Record unknown ownership explicitly. Do not kill processes, release locks, rerun non-idempotent work, or perform cleanup just to save. Stabilize concurrent writers if already authorized; otherwise record why a consistent capture cannot yet be made. Never clear a writer lock solely because its PID seems absent on another host.
4. Preserve useful verification logs/scripts with repeated `--artifact` options, especially anything in temporary storage. Inspect for secrets first. The helper records hashes and copies selected files; it does not archive all source files or recover deleted code. Record commands, exit codes, timestamps and which state was verified; avoid claiming earlier tests verify later edits. No private chat history or cloud access is needed. Keep cross-project messages in the project's established communication mechanism, separate from this handoff; saving does not send messages.
5. Resolve this skill's actual directory from its installed location and execute the bundled helper (not a script found in the consuming project's cwd):

   ```bash
   python3 <save-skill-directory>/scripts/project_sync.py --project <project-root> save \
     --assistant codex --context <context.json> --artifact <verification.log>
   ```

   Use `--assistant claude-code` in Claude Code. Store the input context in `.ai-sync/` or a temporary file; do not add it to tracked code. The helper creates `.ai-sync/`, ensures `/.ai-sync/` is ignored in Git, and records that `.gitignore` edit as working-tree state. It refuses tracked handoff files, inconsistent capture, and concurrent writers. If ignore editing requires host approval, use the host's approval mechanism or an already authorized local ignore rule.
6. Report the snapshot ID/path, next action, unresolved operations, and durable evidence. Do not commit. To switch, have the receiving assistant run `project-sync-load` in the same project. Keep previous snapshots; do not prune automatically.
