---
name: review-instructions-install
description: Installs or updates the code-review-gate instructions (run /codex:review in the background after code changes, triage findings, capped re-review rounds, /code-review fallback) in the current project's CLAUDE.md. Use this skill whenever the user asks to install, add, enable, turn on, update, upgrade, refresh, or sync the "review instructions" or "review gate" for a project — e.g. "install review instructions here", "enable the code review gate for this project", "update the review instructions in CLAUDE.md", "make this repo require a review before commits". Safe to re-run — it creates CLAUDE.md if missing, appends the block if absent, upgrades an older version in place, and does nothing if already current. Do not use it to actually review code — it only writes the instructions.
---

# Review Instructions Install

Writes a versioned, marker-delimited "code review gate" block into the current project's `CLAUDE.md`, or brings an existing block up to date. Running it is always safe: the outcome depends only on what's already in the file.

The canonical block lives in [`assets/review-instructions-block.md`](assets/review-instructions-block.md). That file is the single source of truth — insert its contents **verbatim**. Don't paraphrase, reformat, or "improve" it while installing; any change to the instructions belongs in that asset file, with its version bumped, so every project converges on the same text.

## Why it's built this way

- **Markers + version** (`<!-- review-instructions:start vN -->` … `<!-- review-instructions:end -->`) let a re-run find its own block and replace exactly that span, without touching anything the user wrote around it.
- **`CLAUDE.md`, never `AGENTS.md`.** The block names Claude Code commands (`/codex:review`, `/code-review`). `AGENTS.md` is read by other agents too, and those commands mean nothing there.
- **No project scanning.** This is not `/init`. Creating a `CLAUDE.md` means a file containing only the block — nothing inferred about the codebase.

## Step 1 — Locate the target

The project folder is the current working directory of the session (the folder the chat was started in). Don't walk up to a git root or scan other directories.

Check both standard project-instruction locations for an existing block:

```bash
grep -sn "review-instructions:\(start\|end\)" CLAUDE.md .claude/CLAUDE.md
```

No output means no markers — including when neither file exists; grep's non-zero exit there isn't an error.

- Markers found in one of them → that file is the target (update in place, wherever it is).
- No markers anywhere → the target is `./CLAUDE.md` (created if it doesn't exist).

If markers appear in **both** files, or a file has a start marker without a matching end marker (or multiple blocks), stop and report exactly what you found. Guessing which copy is authoritative could delete the user's edits.

## Step 2 — Read the canonical block

Read `assets/review-instructions-block.md` from this skill's directory. Take the version `N` from its start marker — that's the current version.

## Step 3 — Apply

| Target state | Action | Report |
|---|---|---|
| `./CLAUDE.md` doesn't exist | Create it containing only the block | `created ./CLAUDE.md with review instructions vN` |
| File exists, no markers | Append the block at the end, separated from existing content by one blank line | `appended review instructions vN to <file>` |
| Markers present, version `< N` | Replace everything from the start marker through the end marker (inclusive) with the block | `upgraded review instructions vM → vN in <file>` |
| Markers present, version `= N`, content identical | No change | `review instructions vN already current in <file>` |
| Markers present, version `= N`, content differs | No change — someone edited the block by hand | Report the difference and ask whether to overwrite with the canonical text |
| Markers present, version `> N` | No change — the project has a newer block than this skill | Report it; this copy of the skill is probably stale |

Rules that hold in every case:

- Touch nothing outside the markers. Appending adds content; it never rewrites or reorders what's there. A file that only imports `@AGENTS.md` just gets the block after that line, like any other file.
- Keep LF line endings, and leave the file ending with a single newline.
- Never write to `AGENTS.md`.

## Step 4 — Verify and report

Re-read the target file and confirm it contains exactly one start marker and one end marker with the expected version, and that the text outside the block is unchanged. Then report the one-line outcome from the table.

Don't commit. Whether `CLAUDE.md` is tracked, and whether this change goes into git, is the user's call.
