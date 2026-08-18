# Data Model

<!--
Consumed by: sdd-ticket-start (Step 3, so a plan knows what a change might touch) and
sdd-ticket-close (Step 4 — add new entities/attributes/relationships a shipped ticket
introduced, and resolve or remove "known incomplete state" notes once that work finishes).

Document custom entities only — not the framework's built-in ones, unless this project
extended them. Delete this comment block once filled in.
-->

## Custom Entities

### <EntityName>

- **Storage:** <table name, collection name, or equivalent>
- **Key attributes:** <the ones that matter for future changes, not an exhaustive column dump>
- **Relationships:** <e.g. belongs to X, has many Y>
- **Notes:** <anything a future change needs to know — a non-obvious constraint, a migration in progress, a deprecated field still in use>

## Known Incomplete State

<Anything mid-migration, partially rolled out, or intentionally deferred. Remove an entry once
the ticket that finishes it ships — see sdd-ticket-close Step 4. If there's nothing incomplete,
write "None currently.">
