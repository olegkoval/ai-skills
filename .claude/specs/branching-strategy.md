# ai-skills — Branching Strategy

## Branches

- **Base / integration branch:** `main` — this repo has no separate `develop`/integration branch; it's a single-branch repo.
- **Production branch:** `main` — same branch; there is no separate deploy step, since "shipping" a skill here just means it's merged to `main`.
- **Ticket branch prefix:** `feature/` — only relevant if `sdd-ticket-start` is ever run against this repo itself (e.g. to add a new skill). Full branch name: `feature/<TICKET-CODE>`.

## Remote

- **Type:** SSH (`git@github.com:olegkoval/ai-skills.git`). `git pull`/`git push` require an SSH passphrase this environment can't supply non-interactively — per both SDD skills' own rule, these must be run by the human, never assumed to succeed silently by an agent.

## Merge Policy

- **How work lands on `main`:** Direct commit or PR, maintainer's discretion — no formal review process yet (single maintainer).
- **How `main` reaches "production":** N/A — there is no deploy; `main` is the only meaningful state.
- **Local branch cleanup:** Same rule as any project using `sdd-ticket-close`: delete a fully-merged ticket branch with `git branch -d` only, never `-D`.

## Environments

None — this is a documentation/skills repo, not a deployed application. `workflow.md` accordingly has no environment mapping.
