# Branching Strategy

<!--
Consumed by: sdd-ticket-start (Step 1-2 — which branch to branch from, and the ticket-branch prefix)
and sdd-ticket-close (Step 2 and Step 6 — which branches a merge must land on, and which local
branch is safe to delete once fully merged).

Fill in this project's actual convention. Delete this comment block once filled in.
-->

## Branches

- **Base / integration branch:** <e.g. `develop`> — new ticket branches are created from here.
- **Production branch:** <e.g. `main` or `master`> — a ticket is only "shipped" once its commits are an ancestor of this branch.
- **Ticket branch prefix:** <e.g. `feature/`> — full branch name is `<prefix><TICKET-CODE>`.

## Remote

- **Type:** <e.g. SSH, HTTPS with 2FA> — note whether `git pull`/`git push` can run non-interactively in an agent's environment. If not, those commands must be run by a human, not the agent.

## Merge Policy

- **How tickets land on the integration branch:** <e.g. squash-merge via PR, direct merge>
- **How the integration branch reaches production:** <e.g. release branch cut weekly, merge on demand>
- **Local branch cleanup:** <confirm: safe to delete a ticket's local branch once fully merged into the production branch, via `git branch -d` only — never `-D`.>

## Specs Versioning

- **`.claude/specs/` is tracked in git**, shared with the team and versioned with the code it describes. If `.claude/` is gitignored, the ignore rule must be `.claude/*` plus `!.claude/specs/`: git can't re-include a path whose parent directory is excluded, so `.claude/` plus `!.claude/specs/` doesn't work.
- **Spec updates from `sdd-ticket-close`** are committed on the integration branch, since the ticket branch is already merged by then.
- **Larger constitution revisions** go on their own branch, so it's clear which version of the rules produced which code.

## Environments (if relevant)

<Any additional environment/branch mapping beyond integration → production — e.g. a shared test
environment tied to a specific branch naming convention. See workflow.md for how ticket status
maps to these.>
