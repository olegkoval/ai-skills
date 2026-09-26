# ai-skills — Workflow

## Ticket Status Lifecycle

This repo has no formal ticket tracker (no Jira/Linear project). Work originates from direct conversation/requests rather than tracked tickets. If `sdd-ticket-start` is ever used against this repo itself (e.g. "add a new skill for X"), an informal lifecycle applies:

| Status | Meaning | Triggered by |
|---|---|---|
| Draft | Skill/spec proposed, not yet reviewed | `sdd-ticket-start` produces `spec.md`/`plan.md`/`tasks.md` |
| Reviewed | Maintainer has read and approved the spec/plan | Explicit approval before implementation starts |
| Merged | Implementation committed to `main` | `sdd-ticket-close` verifies the merge and folds learnings back into `.claude/specs/` |

## Status ↔ Branch/Environment Mapping

Not applicable — see `branching-strategy.md`: there's no separate integration/production split or deployment step for this repo.

## Notes

- `.claude/specs/` is tracked in git, like any project using these skills (see branching-strategy.md in the adopter templates); the rest of `.claude/` stays ignored.
- `skills/development/sdd-specs-init/assets/specs/workflow.md` (committed, public-facing) is the generic version of this file for *adopting* projects — don't confuse edits to one for edits to the other (constitution.md Article 5).
