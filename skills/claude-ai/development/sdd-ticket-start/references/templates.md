# SDD Ticket Templates

Skeletons for `spec.md`, `plan.md`, and `tasks.md`, followed by a trimmed real-world example showing the rigor bar — concrete evidence over assumptions, findings that correct the ticket's own framing, explicit compliance checks. The example happens to come from a PHP/Composer project; the mechanics generalize to any language or stack.

## `spec.md` skeleton

```markdown
# <TICKET-CODE> — Spec

**Status:** Draft — pending review
**Tracker:** <title, status, assignee/reporter if visible>

## Problem

<Quote or closely paraphrase the ticket as given. Don't summarize away specifics that might matter later.>

## What Was Actually Verified

<The Step 4 investigation. Cite commands run, files read, line numbers, version numbers.
If a bulk/wildcard check and an individual check disagreed, say so — that mismatch is itself
a finding worth recording, not just the corrected number.>

## Clarified With the User

<Question → answer, one line each, from Step 5. If Step 5 was skipped, write "Nothing needed —
ticket and investigation were unambiguous.">

## Why This Matters / Changes the Picture

<Only needed if investigation changed the ticket's apparent scope or severity. If the ticket
was accurate as stated, skip this section rather than padding it.>

## Scope

**In scope:**
- <bullet per concrete thing being done>

**Out of scope:**
- <bullet per plausible-but-excluded thing, with the one-line reason it's excluded>

## Acceptance Criteria

1. <Concrete, checkable statement>
2. ...

## Open Questions

<Only things genuinely blocking that need the user, not things you could resolve yourself
by looking harder. If there are none, write "None — proceeding to plan." and say why.>
```

## `plan.md` skeleton

```markdown
# <TICKET-CODE> — Plan

**Status:** Draft — pending review
**Depends on:** [spec.md](spec.md)

## Approach

<The technical shape of the change, in enough detail someone else could implement it from
this document alone.>

## Step 1 — <name>

<Exact commands / file paths / diffs where relevant.>

## Step 2 — ...

## Constitution Compliance

<Only if constitution.md exists in this project. One line per relevant Article: satisfied,
how, or — if a deviation is unavoidable — stated and justified explicitly.>

## Verification

<Tied to what Step 4 in spec.md found. If the investigation found N call sites/resolvers/
consumers of the thing being changed, list testing all N, not "test the feature".>

## Risks / Rollback

- **Risk:** ... **Mitigation:** ...
- **Rollback:** ...

## Rollout

<How this moves through the project's branch/environment flow, per branching-strategy.md /
workflow.md if present. Note anything specific to this change worth flagging there.>
```

## `tasks.md` skeleton

```markdown
# <TICKET-CODE> — Tasks

- [ ] <Step 1 from plan.md, concrete enough to act on>
- [ ] <Step 2>
- [ ] <verification tasks — one per thing plan.md's Verification section lists, not a single
      "test it" line>
- [ ] Commit with message `<TICKET-CODE> <description>` — a single short subject line, no body.
      The ticket code MUST be the first token, not buried mid-sentence. The detailed why/what
      belongs in this ticket's spec.md/plan.md, not the commit message — don't restate it there.
- [ ] Update the ticket's tracker status per workflow.md's lifecycle, if defined
```

---

## Worked Example (trimmed, illustrative): a Composer-dependency security ticket

Ticket as given: *"Because of security issues request to update all vendor extensions. Dear Customer, ... we have released security updates for several extensions and Composer packages. We strongly recommend updating them to the latest available versions."*

**What actually happened when this was investigated** (this is the level of rigor to aim for, regardless of language or package manager):

1. A first pass used a wildcard check (`composer outdated "vendor/*"`) and it reported only one outdated package. This looked plausible and even matched a first read of the vendor's own admin panel.
2. Checking each of the 17 directly-required packages **individually** (not via the wildcard) revealed the wildcard had silently missed 8 more outdated packages — a correction that only surfaced because the investigation didn't stop at the first plausible-looking answer.
3. For the one package needing a major-version bump, the actual diff between the installed version and the target version was pulled down (into an isolated scratch location, using the project's existing repo credentials) and read line-by-line, because the vendor's package metadata exposed no changelog. This surfaced the *actual* security fix (a broken-access-control issue) rather than guessing from a version number.
4. That same diff-reading process revealed the project's own custom code wrapping that package had **its own, separate, unrelated vulnerability** — a method missing an ownership check that every sibling method in the same class already had. This had nothing to do with which vendor version was installed, and would never have been found by just bumping a version number. It became the most important finding in the spec, called out prominently rather than left as a footnote.

None of this came from re-reading the ticket text more carefully — it came from treating the ticket as a starting claim to verify, checking the real tooling and the real code, and following what that revealed even when it went past the ticket's original framing. The same discipline applies whether the "dependency" in question is a Composer package, an npm module, a gem, or a vendored library in any other ecosystem.
