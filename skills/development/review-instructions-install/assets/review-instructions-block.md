<!-- review-instructions:start v3 -->
## Code review gate

Scope: code changes only (e.g. PHP, XML, JS, `composer.json`) — not docs/specs-only edits.

As soon as a code change is done, before reporting it finished:
1. Run `/codex:review --background` on the uncommitted diff. Never wait in the foreground, and never commit before its result has arrived.
2. When results arrive, triage every finding: fix confirmed issues; reject false positives or findings that conflict with this project's standards, with a one-line reason each.
3. After fixes, re-run lint/tests, then re-review. Stop when the review has no findings of `medium` severity or above (or its verdict is `approve`); list any remaining `low` findings in your report instead of fixing them. Also stop early if a round only repeats findings already fixed or rejected. Max 5 re-review rounds as a safety net: if `medium`+ findings remain at the cap, stop and report them with their severity instead of looping.
4. If the Codex plugin or CLI isn't available (the review can't be started, or fails for setup/auth reasons — `/codex:setup` diagnoses this; don't run it on every change), fall back to `/code-review low` for a small diff (1–2 files) or `/code-review medium` otherwise. Always pass the level explicitly — without one, `/code-review` reuses the last level used. Its findings carry no severity field, so judge step 3's threshold yourself: stop once only nitpick-level findings remain.

A clean review is a gate, not a commit trigger — follow this project's usual commit rules.
<!-- review-instructions:end -->
