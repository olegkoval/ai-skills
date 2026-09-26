# ai-skills — Tech Stack

## Language / Runtime

- **Language:** None — this repo is pure Markdown (`SKILL.md` files + reference docs) consumed by Claude Code. No compiled or interpreted source.
- **Framework:** N/A

## Dependency Management

- **Manifest / lockfile:** None. No package manager is used; there is nothing to install.
- **Requirements to use this repo:** Git, and a Claude Code–compatible client (CLI, desktop app, or web).

## Key Dependencies

None to install. Skills reference Claude Code extensions they don't own but assume may exist in a consuming environment:
- `superpowers:executing-plans` / `superpowers:using-git-worktrees` — referenced by `sdd-ticket-start`'s implementation-handoff section. Only relevant if the consuming project also has the `superpowers` plugin installed.
- `/codex:review` (the `openai-codex` plugin) — preferred reviewer in `review-instructions-install`'s block. Optional.
- `/code-review` (built into Claude Code) — the block's fallback reviewer when Codex isn't available.

## Tooling

- **Test runner:** None currently. Skills are validated by manual review/dogfooding, not automated tests.
- **Linter / formatter:** None currently — Markdown is hand-formatted.
- **CI:** None configured.

## Infrastructure

- **Hosting:** GitHub, public repository (`github.com/olegkoval/ai-skills`).
- **Remote protocol:** SSH (`git@github.com:olegkoval/ai-skills.git`) — see `branching-strategy.md`.
