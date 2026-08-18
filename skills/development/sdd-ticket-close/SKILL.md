---
name: sdd-ticket-close
description: Use this skill when a ticket that went through sdd-ticket-start (has spec.md/plan.md/tasks.md under .claude/tickets/<TICKET>/) has been merged to the project's integration branch and deployed to production, and the user wants its learnings folded back into the project's durable specs (.claude/specs/constitution.md, tech-stack.md, data-model.md, branching-strategy.md, workflow.md). Trigger on phrases like "PROJ-123 is deployed, update the specs", "this ticket shipped, close it out", "fold this ticket into the specs and clean it up", or any request to reconcile a finished ticket's SDD docs against the specs once it's live in production. This is the closing half of the sdd-ticket-start workflow — it verifies the merge actually happened via git, re-diffs the real merged commits against what the ticket's plan.md claimed (rather than trusting the docs at face value), updates specs with what genuinely changed, deletes the ticket's working folder, and removes the local ticket branch if it's fully merged into the production branch. Works with any language, stack, or branching convention.
---

# SDD Ticket Close-Out

The companion to `sdd-ticket-start`: once a ticket's code has actually shipped, its `spec.md`/`plan.md`/`tasks.md` have done their job as planning documents — anything durably worth knowing belongs in the stable specs from here on, not in a ticket folder that will otherwise accumulate indefinitely. This skill reconciles the two, retires the ticket folder, and — since a ticket branch fully merged into production has likewise done its job — cleans up the now-redundant local branch too.

The core discipline here is the same one `sdd-ticket-start` runs on: don't take the ticket's own docs as ground truth about what shipped. `plan.md` describes what was *intended*; verify it against what the merged commits *actually* changed, because implementation sometimes drifts from plan (a bug found mid-implementation, a scope cut, an extra fix bundled in) and the specs should reflect reality, not the original intention.

## Step 1 — Locate the ticket's SDD docs

```bash
ls .claude/tickets/<TICKET-CODE>/
```

Expect `spec.md`, `plan.md`, `tasks.md`. If the folder or any of these is missing, stop and tell the user — this skill has nothing to reconcile without them, and guessing at what a ticket did from git history alone defeats the point of having written the docs in the first place.

## Step 2 — Verify the merge actually happened

Don't take "it's deployed" on faith — confirm it in git, the same way `sdd-ticket-start` itself verifies ticket claims against real tooling rather than paraphrasing them:

```bash
git log --all --oneline --grep="^<TICKET-CODE>"
```

Determine the project's integration branch and production branch from `.claude/specs/branching-strategy.md` if present (illustrative defaults: `develop` and `main`/`master`). For each matching commit, confirm it's an ancestor of **both**:

```bash
git merge-base --is-ancestor <sha> <integration-branch> && echo "in integration branch"
git merge-base --is-ancestor <sha> <production-branch> && echo "in production branch"
```

If no commits are found, or a commit isn't an ancestor of both branches, **stop and tell the user** what's missing rather than proceeding — e.g. "found in the integration branch but not production yet" is a real, useful thing to report back, not a reason to guess. Don't require being currently checked out on either branch; these checks work from wherever the working tree currently is.

## Step 3 — Re-diff the actual merged changes

```bash
git show --stat <sha1> <sha2> ...
git diff <first-parent-before-ticket-work>..<last-ticket-commit> -- <relevant paths>
```

Compare the real file list and the real diff content against what `plan.md` described. Two outcomes:
- **Matches:** proceed using `plan.md`/`spec.md`'s own descriptions as the basis for what to fold into specs — they're already accurate.
- **Diverges** (extra files touched, a described change that didn't ship, an unplanned fix bundled in): the **real diff is the source of truth**, not the plan. Note the divergence plainly when updating specs (e.g. "plan.md described X; the merged code actually did Y — specs updated to reflect Y"). This matters because a future session reading the specs needs them to describe the codebase as it is, not as a plan once imagined it.

## Step 4 — Extract what's durable and update specs

Not everything in a ticket's docs belongs in the specs. Apply the same filter used when this project's specs were first built: fold in facts that are **architecturally durable** — a rule future work needs to respect, a gotcha that would bite someone again, a new entity/table/attribute, a changed dependency, a process lesson. Leave out **one-off debugging narrative** specific to this ticket's implementation (the back-and-forth of getting to the fix, a symptom that won't recur in that exact form) — that's what the commit history is for, not the specs.

Route facts to the file that already owns that kind of content:
- **`constitution.md`** — a new non-negotiable rule, a gotcha tied to an existing Article, a correction to something an Article got wrong.
- **`tech-stack.md`** — a dependency version change, a new package, a tool added/removed. If this ticket changed a version this file documents, update it — don't leave it stale.
- **`data-model.md`** — a new table/entity, a new attribute, a changed relationship, a resolved "known incomplete state" note (update or remove it if this ticket finished that work).
- **`branching-strategy.md` / `workflow.md`** — only if the ticket taught something about the process itself (rare — most tickets are pure implementation).

If a ticket genuinely taught nothing durable beyond what's already in the specs, say so plainly rather than padding an Article with restated or trivial content.

**Fix dangling references as you go.** If any spec or project instructions file pointed at something this ticket changed (a version number, a "not yet implemented" note, a file path that moved), update it in the same pass — don't leave a spec accurate as of the ticket's start but wrong as of its finish.

## Step 5 — Retire the ticket folder

Once its content is folded in:

```bash
rm -r .claude/tickets/<TICKET-CODE>/
```

Confirm the folder contains only the expected `spec.md`/`plan.md`/`tasks.md` (and no unexpected files) before removing it wholesale — if something else is in there, flag it rather than silently deleting it. These files are typically untracked (`.claude/` is commonly gitignored in these projects) — check `git ls-files .claude/tickets/<TICKET-CODE>/` first, and if anything *is* tracked, remove it with `git rm` instead of a plain `rm` so the deletion is a proper commit, not just a filesystem change no one can see.

## Step 6 — Delete the local ticket branch if fully merged into production

Step 2 already confirmed the ticket's commits are ancestors of the production branch. Now check whether the ticket's own local feature branch (`<branch-prefix><TICKET-CODE>`, per `branching-strategy.md`) is itself safe to remove:

```bash
git rev-parse --verify <branch-prefix><TICKET-CODE> 2>/dev/null && echo "exists locally"
```

If it doesn't exist locally (already deleted, or the work happened in a worktree that's since been removed), just note that and move on — nothing to clean up.

If it exists, confirm the branch's own tip — not just the grepped commits — is an ancestor of the production branch:

```bash
git merge-base --is-ancestor <branch-prefix><TICKET-CODE> <production-branch> && echo "fully merged into production"
```

If that succeeds, delete it with a **safe, non-forcing** delete:

```bash
git branch -d <branch-prefix><TICKET-CODE>
```

Always `-d`, never `-D`. `-d` refuses if the branch has commits the production branch can't reach, which is exactly the guard rail wanted here — if it refuses, **stop and tell the user** rather than forcing it; don't reach for `-D` to push past the refusal, since that's precisely the "unmerged work silently discarded" scenario the safety protocol exists to prevent. If the branch is currently checked out, `git branch -d` will also refuse for that reason — tell the user which branch to switch to first rather than switching it for them out from under any uncommitted state.

This is a **local-only** deletion. It never touches the remote copy of the branch or runs any network operation — network operations are for the human to run themselves, since many remotes require interactive auth this environment can't supply. If the user also wants the remote branch gone, say so explicitly and let them do it (or explicitly confirm before doing it on their behalf) rather than deleting it as a side effect of this step.

## Step 7 — Report back

Summarize: which commits were verified on which branches, whether the real diff matched `plan.md` or diverged (and how), which spec files were updated and with what, confirmation the ticket folder was removed, and whether the local ticket branch was deleted (or why not, if it wasn't). If Step 2 stopped early, report exactly that instead — a ticket not actually merged to both branches yet is a normal, expected outcome to surface, not a failure.
