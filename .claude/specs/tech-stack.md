# ai-skills — Tech Stack

## Language / Runtime

- **Language:** Markdown skill instructions plus Python 3.9+ (standard library only) for two bundled helpers and their tests: the shared project-sync handoff engine, and `sdd-plan-review`'s deterministic plan gate `gate.py`.
- **Framework:** N/A

## Dependency Management

- **Manifest / lockfile:** None. No package manager is used; there is nothing to install.
- **Requirements to use this repo:** A compatible assistant; Python 3.9+ for project-sync and the plan gate; Git for Git project handoffs and for binding a plan gate to repository state.

## Key Dependencies

None to install. Skills reference Claude Code extensions they don't own but assume may exist in a consuming environment:
- `superpowers:executing-plans` / `superpowers:using-git-worktrees` — referenced by `sdd-ticket-implement`'s handoff. Only relevant if the consuming project also has the `superpowers` plugin installed.
- `/codex:review` (the `openai-codex` plugin) — preferred reviewer in `review-instructions-install`'s block. Optional.
- `/code-review` (built into Claude Code) — the block's fallback reviewer when Codex isn't available.

## Tooling

- **Test runner:** Python unittest for the two helpers: `python3 -m unittest discover -s skills/shared/development/project-sync-save/scripts -p 'test_*.py' -v` and `python3 -m unittest discover -s skills/claude-ai/development/sdd-plan-review/scripts -p 'test_*.py' -v`. Other skills use manual review/dogfooding.
- **Linter / formatter:** None currently — Markdown is hand-formatted.
- **CI:** None configured.

## Infrastructure

- **Hosting:** GitHub, public repository (`github.com/olegkoval/ai-skills`).
- **Remote protocol:** SSH (`git@github.com:olegkoval/ai-skills.git`) — see `branching-strategy.md`.
