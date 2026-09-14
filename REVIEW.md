# Auto-review-before-commit hook — research handoff

Status as of this handoff: **pure research/design, nothing implemented anywhere.**
One prototype was written into `~/.claude/settings.json` during the research
conversation and was explicitly reverted on request — there is currently no trace of
this feature in any settings file, plugin, or repo. This file is meant to be moved
into whatever project folder a fresh Claude Code session should pick this up in; it
does not depend on anything specific to the Magento project it was written in.

## Goal

Automatically run a code review before code changes get committed, in a way that
works the same across any project, not just one repo. Two review backends should be
supported:

1. **Preferred**: the `codex` plugin's `/codex:review` (an external CLI reviewer,
   invoked today as `node "<codex plugin dir>/scripts/codex-companion.mjs" review`).
2. **Fallback**: Claude Code's own built-in `/review` skill, at `medium` or `low`
   effort, for a machine/project where the codex plugin isn't installed.

## Design evolution (what was tried, what was rejected, and why)

### Rejected: gate on every Edit/Write

First prototype (built, pipe-tested, then reverted): a `PostToolUse` hook on matcher
`Write|Edit` touches a session-scoped marker file
(`/tmp/claude-code-review-pending/<session_id>`); a `Stop` hook checks
`stop_hook_active` (to avoid an infinite block-loop — Claude Code sets this true when
the current stop attempt is itself the result of a previous block in the same turn)
and, if the marker exists, deletes it and returns
`{"decision":"block","reason":"...run codex or /review..."}` to force Claude to run
the review before it's allowed to finish.

**Why this was dropped**: it fires the check on *every single edit*, which is noisy
and wasteful for trivial changes, and it needs non-trivial state (marker file +
`stop_hook_active` check) purely to avoid looping. The user (correctly) suggested
gating on the commit instead.

### Current direction: gate on `git commit`

Trigger a `PreToolUse` hook on matcher `Bash`, filtered with
`"if": "Bash(git commit:*)"` (permission-rule syntax — matches only Bash commands
starting with `git commit`, so the hook script isn't even spawned for unrelated Bash
calls). This only fires at the moment work is about to become permanent, which kills
the noise problem outright — no marker-file bookkeeping needed just to avoid
re-checking every edit.

Two sub-cases depending on whether the review can run unattended:

- **Codex is installed** → use `"asyncRewake": true` on the hook. The commit proceeds
  immediately (no added latency); the review command runs in the *background*; if it
  exits with code **2**, Claude Code "wakes" the model afterward with the hook's
  `rewakeMessage`, injected as context, so Claude can address findings and continue —
  without ever having blocked the original commit. This mirrors the officially
  shipped `security-guidance` plugin's pattern for reviewing `git push` (see
  "Reference implementation" below) almost exactly, just swapped to `git commit` and a
  different backend command.

- **Codex is not installed** → cannot use `asyncRewake` for this branch, because
  `asyncRewake` can only run an external CLI/script in the background; it **cannot**
  autonomously invoke a Claude Code *skill* like the built-in `/review`, since skills
  only execute inside Claude's own agent turn, not from a detached background
  process. This branch has to be a **synchronous** block instead:
  `hookSpecificOutput.permissionDecision: "deny"` with a
  `permissionDecisionReason` telling Claude to run `/review` at medium or low effort
  itself before the commit is allowed to proceed.

So the same `git commit`-triggered hook needs to branch on "is codex installed" and
behave differently (async/non-blocking vs. sync/blocking) in each branch.

## Key technical facts (verified via context7 against `/anthropics/claude-code`, and by direct pipe-testing)

- `PreToolUse` hooks return `{"hookSpecificOutput": {"permissionDecision": "allow"|"deny"|"ask", ...}, "systemMessage": "..."}` to control whether the tool call proceeds.
- A hook entry's `"if"` field takes the same permission-rule syntax as
  `permissions.allow/deny` (e.g. `"Bash(git commit:*)"`, `"Bash(git push:*)"`) and
  restricts *when the hook script is even run*, not just what it's allowed to decide.
- `"asyncRewake": true` implies async (background) execution. Exit code **2** from
  the backgrounded command is what triggers the "wake the model" behavior; exit 0
  means no issues, nothing surfaces to Claude.
- **Compound-command caveat**: a command like `git commit -m x && git push` can match
  *multiple* `if` filters at once (e.g. both a `Bash(git commit:*)` and a
  `Bash(git push:*)` hook), and Claude Code will spawn the hook script **once per
  matching filter**, all sharing the same `tool_use_id`. If more than one git
  subcommand is ever gated, a dedup step is needed (see reference implementation
  below for the actual pattern Anthropic uses: a filesystem sentinel file named after
  the `tool_use_id`, first writer wins, stale sentinels garbage-collected after 5
  minutes).
- `if` filtering historically had bugs with compound commands and env-var-prefixed
  commands (`FOO=bar git push`) — reportedly fixed, but worth a quick sanity check
  against the current Claude Code version when implementing, since this session did
  not verify the fix directly.

## Reference implementation to study before building

The **`security-guidance`** plugin (already installed and enabled in this user's own
`~/.claude/settings.json`, so it's available locally) implements almost exactly this
shape, but for `git push` and a security scan rather than `git commit` and a code
review:

- `plugins/security-guidance/hooks/hooks.json` — the hook registration, using
  `if: "Bash(git push:*)"`, `asyncRewake: true`, `rewakeMessage`, `rewakeSummary`.
- `plugins/security-guidance/hooks/security_reminder_hook.py` — the actual script,
  including the `_claim_bash_hook_once()` dedup-by-`tool_use_id` function mentioned
  above.

Both are in the `anthropics/claude-code` GitHub repo and were surfaced via context7
(`resolve-library-id` → `/anthropics/claude-code`, then `query-docs`). Re-fetch and
read these two files directly at the start of the next session — they're a working,
shipped example of this exact mechanism, not just documentation.

## Codex-installed detection

The prototype used:
```bash
compgen -G "$HOME/.claude/plugins/cache/openai-codex/codex/*/scripts/codex-companion.mjs" > /dev/null 2>&1
```
This works (pipe-tested against both presence and absence, via a temporary `$HOME`
override) but hardcodes today's plugin-cache path shape and a version-numbered
directory segment. For a properly shared/distributable version, consider a more
robust check — e.g. not pinning to `codex-companion.mjs` specifically, or reading the
user's own `enabledPlugins` map in `~/.claude/settings.json`, or simply attempting the
invocation and falling back cleanly on failure — rather than trusting one hardcoded
glob to keep matching across codex plugin versions.

## Distribution scope — two options discussed, neither built yet

**Option A — personal, this machine only, no packaging.** Add the hooks directly to
`~/.claude/settings.json`. User-level settings apply to every project automatically.
Fastest to build, but not versioned, shareable, or installable elsewhere.

**Option B — a real, distributable Claude Code plugin.** A directory with
`.claude-plugin/plugin.json` + `hooks/hooks.json` (+ any bundled scripts, referenced
via the `${CLAUDE_PLUGIN_ROOT}` placeholder so they're self-contained regardless of
which project invokes them), pushed to its own git repo, registered as a marketplace
(`claude plugin marketplace add <repo>`, or declaratively via `extraKnownMarketplaces`
in `~/.claude/settings.json` — same shape as this user's existing `openai-codex` and
`karpathy-skills` entries), then enabled once at the **user** level
(`enabledPlugins: {"name@marketplace": true}`). This is the option that actually
satisfies "committed in a git repo and used globally for any project" — Option A does
not produce anything git-trackable on its own unless dotfiles are separately
version-controlled.

No decision was made between A and B — that's an open question for the next session.

## Suggested next steps

1. Re-read the two `security-guidance` reference files directly (paths above).
2. Decide A vs. B with the user.
3. Design the exact hook JSON (trigger, `if` filter, async vs. sync branch, exit-code
   convention, `rewakeMessage` wording).
4. Follow the standard hook-construction discipline: pipe-test the raw command against
   synthesized stdin JSON (`echo '{...}' | <cmd>`) before writing it into any
   settings/plugin file, then validate with `jq -e '...' <file>`, then prove it fires
   correctly, before treating it as done. (This discipline is documented in Claude
   Code's own `update-config` skill / hook-development plugin skill, not specific to
   this project.)
5. If Option B: scaffold `.claude-plugin/plugin.json`, `hooks/hooks.json`,
   `hooks/review-gate.sh` (or similar), init a git repo, decide hosting, and only then
   register it as a marketplace.

## Original user framing (for context on intent)

> How we can start a /codex:review for your changes after any of your code changes
> (if /codex:review plugin was not installed then use built-in /review medium/low)?
> Create some hook which will works for any project?

Follow-up refinement from the same user, which is what produced the current
direction:

> maybe make sense to use "before commit" event? So, run review before committing
> (and do not use "edit" event to prevent infinite review loop)?
