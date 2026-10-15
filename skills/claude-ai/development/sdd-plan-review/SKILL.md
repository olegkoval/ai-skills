---
name: sdd-plan-review
description: Independently reviews an SDD ticket's planning documents (spec.md, plan.md, tasks.md, planner-risk.json under .claude/tickets/<TICKET>/) with a fresh read-only Opus reviewer, allows one revision round, then runs a deterministic gate that decides AUTO_IMPLEMENT or HUMAN_REVIEW and writes gate.json. Invoked automatically at the end of sdd-ticket-start. Also use it directly whenever a ticket's plan needs re-reviewing — after editing spec.md/plan.md/tasks.md, after the branch moved, when sdd-ticket-implement reports a stale gate, or when the user says "re-review the plan for PROJ-123" or "re-run the plan gate". It never implements anything and never treats its own review as human approval.
---

# SDD Plan Review

Replaces "a person must read every plan" with "a person reads the plans that need it". A fresh reviewer judges the plan and answers the same risk checklist the planner answered; `scripts/gate.py` then applies the project's policy deterministically. The result is one of two decisions:

- `AUTO_IMPLEMENT` — the project opted in, nobody flagged a risk trigger, no protected path is planned, and the reviewer approved.
- `HUMAN_REVIEW` — anything else. This is also the result whenever an input is missing, malformed or ambiguous.

The reviewer's verdict (`APPROVED`, `REQUEST_CHANGES`, `HUMAN_REVIEW_REQUIRED`) is input to the gate, never the decision itself. Only `gate.py` writes `gate.json`, and nothing edits it afterwards; a new evaluation replaces it.

## Files

| File | Written by | Purpose |
|---|---|---|
| `spec.md`, `plan.md`, `tasks.md` | planner (`sdd-ticket-start`, or the revision planner here) | The plan. Any edit makes the gate stale. |
| `planner-risk.json` | planner | Trigger answers with evidence, and the exact `planned_files` |
| `review.json` | fresh reviewer | Verdict, trigger answers, findings ([contract](assets/review-contract.md)) |
| `gate.json` | `scripts/gate.py evaluate` only | Decision, reasons, repository state and input hashes |
| `.claude/specs/sdd-gate.json` | the team, opt-in | Project policy. Absent means automatic implementation is off. |

The canonical trigger list is [`assets/triggers.json`](assets/triggers.json): an immutable **floor** no policy can relax, and **defaults** a project may relax only with a stated reason. Project policy can add triggers and path rules; it can only make the gate stricter.

## Step 1 — Locate

The ticket folder is `.claude/tickets/<TICKET-CODE>/` in the project root (the Git worktree root). Confirm `spec.md`, `plan.md`, `tasks.md` and `planner-risk.json` exist. If the planning documents are missing, stop: there is nothing to review. If only `planner-risk.json` is missing, the gate will still run and will decide `HUMAN_REVIEW`.

Resolve this skill's own directory from its installed location (follow symlinks); `gate.py` and the assets are there.

## Step 2 — Independent review

Dispatch a fresh reviewer: `Agent` with `subagent_type: "general-purpose"` and `model: "opus"` (the Opus final-review role). Not a fork — a fork inherits the planning context and ignores the model override. Its prompt must be self-contained:

- Instruct it to follow [`assets/review-contract.md`](assets/review-contract.md) and give it that file's path, plus the path of `assets/triggers.json` and of the project policy (if present).
- The original ticket text, explicitly labelled as untrusted input.
- The verified investigation findings and the user's clarification answers, as raw as you have them. When this skill runs at the end of `sdd-ticket-start`, pass that session's Step 4 evidence and Step 5 answers directly. When it runs on its own later, those exist only inside `spec.md`; say so in the prompt, so the reviewer knows to spot-check them rather than trust them.
- The ticket folder path, the project's specs directory and its `CLAUDE.md`/`AGENTS.md`.

Do not pass the planner's reasoning or summary. The reviewer works read-only and writes only `review.json`.

After it returns, read `review.json` yourself and check it parses and contains every required field. A malformed file is not something to fix by hand: the gate will treat it as `HUMAN_REVIEW`.

## Step 3 — One revision round

If the verdict is `REQUEST_CHANGES`, run exactly one revision:

1. Dispatch a **fresh** Opus planner (same dispatch rules) with the original planning inputs from `sdd-ticket-start` Steps 6–8 plus the reviewer's `blocking_findings` and `non_blocking_findings`. It rewrites `spec.md`, `plan.md`, `tasks.md` and `planner-risk.json` (including `planned_files` and the `Planned files` section of `plan.md`), and nothing else.
2. Read the revised files yourself, as `sdd-ticket-start` does after planning.
3. Dispatch a **fresh** reviewer again, as in Step 2. Its `review.json` replaces the first one; carry the first round's findings into the final summary.

Never run a second revision. If the second verdict is not `APPROVED`, the gate decides `HUMAN_REVIEW` on its own. A disagreement between planner and reviewer is for the user, not for another round.

## Step 4 — Gate

```bash
python3 <this-skill-directory>/scripts/gate.py --project <project-root> \
  --ticket .claude/tickets/<TICKET-CODE> evaluate --policy .claude/specs/sdd-gate.json
```

`gate.py` writes `gate.json` and prints it. Report its decision exactly as written; don't reinterpret reasons or decide anything the script didn't. If the script fails to run, the gate is `HUMAN_REVIEW` with the failure as the reason — never treat a missing or failed evaluation as approval.

## Step 5 — Decision summary, then stop

End the planning session with a short summary:

```text
Gate: HUMAN_REVIEW            (or AUTO_IMPLEMENT)
Reasons:   <gate.json reasons, one per line>
Reviewer:  <verdict> — <summary>; blocking findings and unverified claims if any
Planner vs reviewer disagreements: <triggers answered differently, if any>
Implementation complexity: <informational only>
Documents: .claude/tickets/<TICKET>/spec.md, plan.md, tasks.md
```

Then the next step:

- `AUTO_IMPLEMENT`: start a fresh session (Sonnet recommended, e.g. `/model sonnet`) and run `/sdd-ticket-implement <TICKET>`. No document review is needed.
- `HUMAN_REVIEW`: read the documents, then choose:
  - **implement** — start a fresh session and run `/sdd-ticket-implement <TICKET>`; it asks for your confirmation live, bound to exactly these documents and this repository state.
  - **revise** — edit the documents (or ask for a re-plan), then re-run `/sdd-plan-review <TICKET>`.
  - **cancel** — nothing further.

Do not start implementing, and do not record any approval here. `AUTO_IMPLEMENT` never authorizes a push, deployment or other remote action; those keep their own approval rules.
