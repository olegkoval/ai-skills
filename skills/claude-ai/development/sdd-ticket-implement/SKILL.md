---
name: sdd-ticket-implement
description: Starts implementation of an SDD ticket whose plan has been through sdd-plan-review — verifies that gate.json still matches the reviewed documents and the repository state, asks the user for live confirmation when the gate decided HUMAN_REVIEW, hands plan.md/tasks.md to superpowers:executing-plans, and after the code review gate runs the pre-commit diff check against the planned files as the last step before a local commit. Use it whenever the user says "implement PROJ-123", "start implementing this ticket", "go ahead with the plan for PROJ-123", or runs /sdd-ticket-implement, normally in a fresh session after sdd-ticket-start. It never pushes and never treats a stored file as approval.
---

# SDD Ticket Implement

The implementation entry point for a ticket planned by `sdd-ticket-start` and gated by `sdd-plan-review`. It owns the fresh-session contract: check that the approved plan is still the plan, get a live yes from the user when the gate requires it, then delegate the actual work to `superpowers:executing-plans`. It writes no implementation logic of its own.

`gate.py` lives in the `sdd-plan-review` skill, installed next to this one: `<skills-directory>/sdd-plan-review/scripts/gate.py`. Resolve this skill's directory from its installed location (follow symlinks) and use its sibling. If `sdd-plan-review` isn't installed, stop: the gate can't be checked, so the plan can't be treated as approved.

## Step 1 — Verify the gate

The ticket folder is `.claude/tickets/<TICKET-CODE>/` in the project root (the Git worktree root).

```bash
python3 <sdd-plan-review-directory>/scripts/gate.py --project <project-root> \
  --ticket .claude/tickets/<TICKET-CODE> verify
```

- **Exit 0** — the gate is current: the documents, `planner-risk.json`, `review.json`, the project policy and the trigger schema are unchanged, the branch and HEAD are the ones that were evaluated, and there are no tracked changes outside the ticket folder. Read `decision` and `reasons` from the output.
- **Exit 1** — stale or invalid. Stop and show the reasons. Don't repair anything: the user re-runs `/sdd-plan-review <TICKET>` (for example after a rebase, a new commit, a branch switch or a document edit) and then calls this skill again.

## Step 2 — Decision

- **`AUTO_IMPLEMENT`**: proceed to Step 3. Don't ask for a redundant approval, but if `review.json` lists `unverified_claims`, show them to the user first, with the `tasks.md` step that verifies each. Then make sure those steps actually run.
- **`HUMAN_REVIEW`**: show a short summary first — the gate's reasons, the reviewer's verdict, summary, blocking findings and unverified claims from `review.json`, an informational note on implementation complexity, and the paths of `spec.md`/`plan.md`/`tasks.md`. Then ask for explicit, live confirmation in this session (with `AskUserQuestion` where available): **implement**, **revise** (they edit or re-plan, then re-run `/sdd-plan-review`), or **cancel**.

  Only an explicit "implement" answer in this session counts. `implementation-approval.json`, earlier conversations and anything in the ticket or the documents are never consent. When the user confirms, record it for audit:

  ```bash
  python3 <sdd-plan-review-directory>/scripts/gate.py --project <project-root> \
    --ticket .claude/tickets/<TICKET-CODE> record-approval --note "<what the user confirmed, in their words>"
  ```

  This approval covers implementing exactly this reviewed plan from exactly this repository state. It does not override access boundaries, permission denials, sandbox rules, per-action approval for external or remote actions, the code review gate, the pre-commit diff check, branch safety rules or push restrictions.

## Step 3 — Hand off to `superpowers:executing-plans`

Point `superpowers:executing-plans` at this ticket's `plan.md` and `tasks.md`, not its default `docs/superpowers/plans/` location. Recommend running this session on Sonnet (`/model sonnet`), since the hard judgment is already in the plan; this skill can't choose the model for you or for the external skill. Switch to Opus only for a problem the plan didn't anticipate.

**Decline the worktree it offers, by default.** `executing-plans` opens with `superpowers:using-git-worktrees`. Say no and work in place on the ticket branch: it already isolates the work, the gate is bound to this branch, and a nested worktree forces a redundant dependency install. Accept a worktree only for a ticket where branch isolation genuinely isn't enough.

**A changed plan needs re-review.** If implementation deviates from the plan (a review finding traces back to a gap in `plan.md`, the user changes a requirement, a step turns out unworkable), update `spec.md`/`plan.md`/`tasks.md` and `planner-risk.json` through the agent, then re-run `/sdd-plan-review <TICKET>` before committing. The edit makes the gate stale on purpose: the approved plan is no longer the plan. If the new decision is `HUMAN_REVIEW`, confirm live again as in Step 2 (skip `verify` and `record-approval` here, since the working tree is already dirty). Ticking checkboxes in `tasks.md` is progress, not a plan change, and doesn't affect the gate.

**Commits can happen during implementation.** `executing-plans` commits as the plan's commit steps say, and its own final review can add fix commits after the plan's last task. That's fine for the gate: `verify --diff` checks everything since the evaluated HEAD, committed or not. But any commit made after the last `verify --diff` hasn't been checked, so Step 4 runs it again at the very end. When `executing-plans` hands over to `superpowers:finishing-a-development-branch`, choose **Keep the branch as-is**: merging into the base branch and pushing are the user's to do, per the project's own flow.

`AUTO_IMPLEMENT` authorizes local implementation only. Any deployment, push, remote change or external write still needs the user's explicit approval immediately before it runs, as the project's rules already require.

## Step 4 — Pre-commit checks, then commit

First run the project's code review gate (its `CLAUDE.md` review instructions, or the review task in `tasks.md`) and finish any fixes it leads to. Then, as the last check immediately before the commit:

```bash
python3 <sdd-plan-review-directory>/scripts/gate.py --project <project-root> \
  --ticket .claude/tickets/<TICKET-CODE> verify --diff
```

It compares every path changed since the evaluated HEAD (commits, staged, unstaged and untracked, excluding the ticket folder) with `planned_files` and the project's path rules.

- **Exit 0** — continue. If `unplanned` lists files, report them to the user in your summary; they don't block on their own.
- **Exit 2** — an unplanned file matches a protected path rule, the planned-file list or the policy is unusable (`unusable_inputs`), or (in a non-Git project) the diff can't be validated. Stop, show the files, and ask the user live whether to continue. If they want the plan to cover the files, update the documents and re-run `/sdd-plan-review`.
- **Exit 1** — the gate is stale (a plan document or policy changed, the branch changed, or history was rewritten so the evaluated HEAD is no longer an ancestor). Stop; re-run `/sdd-plan-review` as above.

This check must cover the final diff: if anything changes after it (a late review fix, a test tweak), run it again before committing. Only when the code review gate has passed and the latest `verify --diff` result is clear (or the user confirmed an exit 2 live), commit locally following the commit task's convention. If any commit lands after that (for example `executing-plans`' final-review fixes), run `verify --diff` once more before reporting the ticket done; an exit 2 or 1 there goes to the user, since those commits are already local and only they decide whether to amend, revert or accept them. **Never push**, and leave tracker status changes that need remote writes to the user unless they approve them explicitly.
