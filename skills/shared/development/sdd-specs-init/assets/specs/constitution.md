# Project Constitution

<!--
Consumed by: sdd-ticket-start (Steps 6–8 check every plan.md against every Article below and states
compliance explicitly) and sdd-ticket-close (Step 4 folds new non-negotiable rules or gotchas
back in here once a ticket ships).

Keep each Article a short, checkable rule — something a plan can concretely satisfy or violate.
Delete this comment block once the file is filled in.
-->

**Status:** Draft — fill in the Articles that actually apply to this project, delete the rest, add ones that are missing.

## Article 1 — <e.g. "No direct writes to vendor/third-party code">

<One or two sentences: the rule, and why it's non-negotiable. Example: "Never modify vendor/
or node_modules/ directly — extend via the framework's own plugin/hook/override mechanism,
or patch via the package manager. Reason: direct vendor edits are silently lost on the next
dependency update.">

## Article 2 — <e.g. "Dependency injection over service location">

<Rule + reason.>

## Article 3 — <e.g. "Declarative schema for database changes">

<Rule + reason. Example: "Schema changes go through the framework's declarative/migration
tooling, never hand-written imperative install/upgrade scripts. Reason: declarative schema is
idempotent and diffable; imperative scripts drift and are hard to audit.">

## Article 4 — <e.g. "Coding standard">

<Which standard (PSR-12, project ESLint config, PEP 8, etc.) and any deviations the team has
explicitly agreed to.>

## Article 5 — <add project-specific Articles as they come up>

<A gotcha discovered during a real ticket belongs here once it's confirmed to be durable —
see sdd-ticket-close Step 4. Don't pre-populate with speculative rules; add them as they're
actually established.>
