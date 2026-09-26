# ai-skills — Branching Strategy

## Branches

- **Base / integration branch:** `main` — this repo has no separate `develop`/integration branch; it's a single-branch repo.
- **Production branch:** `main` — same branch; there is no separate deploy step, since "shipping" a skill here just means it's merged to `main`.
- **Ticket branch prefix:** `feature/` — only relevant if `sdd-ticket-start` is ever run against this repo itself (e.g. to add a new skill). Full branch name: `feature/<TICKET-CODE>`.

## Remote

- **Type:** SSH (`git@github.com:olegkoval/ai-skills.git`). `git pull`/`git push` work non-interactively when the maintainer's SSH key is unlocked, so the agent may run them when explicitly asked. If one fails for auth, ask the maintainer to run it rather than retrying.

## Merge Policy

- **How work lands on `main`:** Direct commit or PR, maintainer's discretion — no formal review process yet (single maintainer).
- **How `main` reaches "production":** N/A — there is no deploy; `main` is the only meaningful state.
- **Local branch cleanup:** Same rule as any project using `sdd-ticket-close`: delete a fully-merged ticket branch with `git branch -d` only, never `-D`.

## Specs Versioning

- **`.claude/specs/` is tracked in git** via `.gitignore`'s `.claude/*` plus `!.claude/specs/`; the rest of `.claude/` stays ignored.
- **All spec updates are committed to `main`**, including constitution revisions — this is a single-branch repo.

## Environments

None — this is a documentation/skills repo, not a deployed application. `workflow.md` accordingly has no environment mapping.
