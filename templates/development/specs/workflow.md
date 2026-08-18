# Workflow

<!--
Consumed by: sdd-ticket-start (Step 6 rollout section, and the tasks.md tracker-status-update task)
and sdd-ticket-close (context for whether a process lesson belongs here per Step 4).

Document this project's ticket status lifecycle and how it maps to the branch/environment flow
from branching-strategy.md. Delete this comment block once filled in.
-->

## Ticket Status Lifecycle

<e.g. To Do → In Progress → In Review → Testing → Done>

| Status | Meaning | Triggered by |
|---|---|---|
| <status> | <what it means for this project> | <e.g. branch created, PR opened, merged to integration branch, deployed to production> |

## Status ↔ Branch/Environment Mapping

<e.g. "Testing" means the ticket's commits are merged into the integration branch and deployed
to the shared test environment; "Done" means merged into production. If there's no such
mapping, say so — not every project ties tracker status to deployment state.>

## Notes

<Any process quirk worth a future session knowing — e.g. a manual step in getting from one
status to the next that isn't obvious from the tracker alone.>
