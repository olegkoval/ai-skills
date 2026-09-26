# ai-skills — Tech Stack

## Language / Runtime

- **Language:** None — this repo is pure Markdown (`SKILL.md` files + reference docs) consumed by Claude Code. No compiled or interpreted source.
- **Framework:** N/A

## Dependency Management

- **Manifest / lockfile:** None. No package manager is used; there is nothing to install.
- **Requirements to use this repo:** Git, and a Claude Code–compatible client (CLI, desktop app, or web).

## Key Dependencies

None. Skills reference two Claude Code conventions they don't own but assume exist in a consuming environment:
- `superpowers:executing-plans` / `superpowers:using-git-worktrees` — referenced by `sdd-ticket-start`'s implementation-handoff section. Only relevant if the consuming project also has the `superpowers` plugin installed.

## Tooling

- **Test runner:** None currently. Skills are validated by manual review/dogfooding, not automated tests.
- **Linter / formatter:** None currently — Markdown is hand-formatted.
- **CI:** None configured.

## Infrastructure

- **Hosting:** GitHub, public repository (`github.com/olegkoval/ai-skills`).
- **Remote protocol:** SSH (`git@github.com:olegkoval/ai-skills.git`) — see `branching-strategy.md`.
