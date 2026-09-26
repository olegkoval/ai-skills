---
name: sdd-ticket-start
description: Use this skill whenever the user hands over a ticket (a code like PROJ-123, a GitHub issue number, or similar, plus a description) from any tracker — Jira, Linear, GitHub Issues, or otherwise — and wants to start working on it using spec-driven development (SDD). Trigger on phrases like "here's a new ticket", "I have a ticket, PROJ-123, description is...", "let's start on this ticket", "create a branch and spec for this", or a pasted ticket screenshot/description with a ticket code. Also trigger when the user says they want to use spec-driven development (SDD) for a task and gives a ticket identifier. This skill creates the feature branch, investigates the ticket's claims against the real codebase and tooling rather than trusting the ticket text at face value, clarifies whatever is still open with the user, and produces spec.md/plan.md/tasks.md under .claude/tickets/<TICKET>/ — all before any implementation code is written. Works with any language, stack, or tracker convention.
---

# SDD Ticket Start

Turns a raw ticket (code + description) into a working branch and three grounded planning documents — spec, plan, tasks — before any implementation begins. The point of this skill is not paperwork for its own sake: it's that ticket descriptions (especially vendor bulletins, customer-reported bugs, or anything paraphrased secondhand) are frequently vague, wrong, or narrower/broader than they claim. A spec built by actually checking the codebase catches that before a single line of implementation code gets written on a wrong assumption.

This skill is stack-agnostic. Where a step needs project-specific detail (base branch name, dependency tooling, ticket status names), it reads that from this project's `.claude/specs/` files rather than assuming any particular language or stack. If this project doesn't have them yet, the `sdd-specs-init` skill creates them (its templates are in `skills/development/sdd-specs-init/assets/specs/` in the `ai-skills` repo).

## When you're given a ticket

You'll typically get a ticket code (e.g. `PROJ-123`) and a description (pasted text, a screenshot, or both). Before writing anything to disk, work through these steps in order.

## Step 1 — Confirm repo state

```bash
git status
git branch --show-current
```

Confirm the base branch to branch from: check `.claude/specs/branching-strategy.md` if present — it names the project's base branch (e.g. `develop`, `main`) and ticket-branch prefix (e.g. `feature/`). If `branching-strategy.md` doesn't exist, ask the user which branch to branch from rather than assuming.

- The working tree is clean. If it isn't, **stop and tell the user** what's uncommitted rather than switching branches out from under their in-progress work — creating a branch is safe, but jumping base branches with dirty state is not something to do silently.

If the project has a dependency manifest and lockfile (e.g. `composer.json`/`composer.lock`, `package.json`/`package-lock.json` or `yarn.lock`/`pnpm-lock.yaml`, `Gemfile`/`Gemfile.lock`, `pyproject.toml`/`poetry.lock`), verify the installed dependencies match the lockfile using the project's own tooling (e.g. `composer install --dry-run`, `npm ci --dry-run`, `bundle check`, `poetry check`) before touching anything else.

Dependency directories (`vendor/`, `node_modules/`, `.venv/`, etc.) are normally gitignored, so their on-disk state is whatever was last installed in this folder — not necessarily what the currently checked-out branch's lockfile declares, especially in a folder reused across multiple tickets. If the check reports drift, install/sync properly (e.g. `composer install`, `npm ci`) rather than an "update" command, so any dependency work later in this ticket starts from a state that actually matches the lockfile — otherwise a later update can end up "correcting" drift you didn't cause instead of just applying your intended change, producing a much larger and scarier diff than expected.

**Then check the platform/framework version specifically, not just "is there drift".** On a Composer project, compare the version actually installed against the version this branch's `composer.lock` pins — installed side from `vendor/composer/installed.json` (or `composer show <package>`), pinned side from `composer.lock` — for the framework/platform package (e.g. `magento/product-enterprise-edition`, `magento/framework`, `laravel/framework`, `symfony/framework-bundle`) and for any vendor package whose source this ticket will read. Same idea for `package.json`/`node_modules`, `Gemfile.lock`, `poetry.lock`. A multi-patch-release gap shows up in `install --dry-run` as just another line in a wall of up/downgrades and is very easy to skim past.

**If the installed codebase doesn't match the lockfile, get it matching before going further.** Run the sync yourself (`composer install`, `npm ci`, …). If you don't have the rights to — the command is blocked, needs credentials you don't have, or touches an environment you can't reach — **ask the user to run it and wait for their explicit confirmation that the codebase now matches** before continuing. Don't proceed on the assumption it happened, and don't plan around the mismatch.

Once the sync has run, **re-check `git status` before continuing.** On projects that commit framework files into the repo alongside Composer (Magento Cloud is the common case: `app/`, `lib/`, `pub/`, `setup/`, `dev/` are all tracked *and* delivered by a package), a version change can leave thousands of tracked files deleted in the working tree — including entry points like `pub/index.php` and `app/bootstrap.php`. If the sync left deletions of tracked files that nothing in the ticket touches, restore them from `HEAD` (e.g. `git restore .`, safe when nothing tracked is *modified*) and confirm the tree is clean again before writing any code. A commit made without noticing would record those deletions as part of the ticket.

This matters because **a design derived from reading `vendor/` source is only valid for the version that source came from.** If the installed tree is ahead of or behind the branch's lockfile, the file paths, line numbers, method signatures and behaviour cited in `spec.md`/`plan.md` may not describe what the branch actually ships. When the versions differ and the plan leans on that source, either sync first, or fetch the pinned version into a scratch directory and **diff the exact files the design hooks into** — then record in `spec.md` which version the trace was verified against and what differed. Don't take the project's own docs as the answer either: `CLAUDE.md`/`README` version claims go stale. The lockfile is what the branch ships, the installed tree is what you're reading, and the docs are a third, independent claim — reconcile all three before trusting a citation.

## Step 2 — Create the ticket branch

```bash
git checkout <base-branch>
git checkout -b <branch-prefix><TICKET-CODE>
```

Use the base branch and prefix confirmed in Step 1 (illustrative default: `develop` and `feature/`, if nothing else is specified). Do this automatically — it's a reversible, local operation and matches the project's own convention when one exists. If a branch with that name already exists, tell the user rather than silently overwriting or reusing it (it may be prior in-progress work).

**Never run `git pull` or `git push` yourself.** Many remotes require interactive authentication (an SSH passphrase, a 2FA-gated HTTPS prompt) that this environment can't supply, so both commands can hang or fail non-interactively. Instead, ask the user to run the command themselves (e.g. "Can you run `git pull` on `<base-branch>` so it's current before I branch?") and wait for their confirmation before continuing — don't proceed as if it happened. If the base branch might be stale, say so and ask rather than assuming the local copy is current.

This branch isn't meant to live forever: once the ticket ships, `sdd-ticket-close` checks whether it's fully merged into the project's production branch and deletes it locally as part of closing the ticket out — no need to clean it up by hand.

## Step 3 — Gather project context

Read whatever exists, and don't fail if something doesn't:

- `.claude/specs/constitution.md` — the technical rules any plan must respect. If present, every rule in `plan.md` gets checked against it explicitly (see Steps 6–8).
- `.claude/specs/tech-stack.md` — what's actually installed and at what version, so you're not guessing.
- `.claude/specs/data-model.md` — custom entities/tables, so you know what a change might touch.
- `.claude/specs/branching-strategy.md` — confirms the branch convention used in Step 2, and the base branch if it's not the default.
- `.claude/specs/workflow.md` — the ticket's status lifecycle, useful context for the plan's rollout section.
- `.claude/specs/mission.md` (optional) — the project's purpose, audience and scope, used in Step 5 to judge whether the ticket's scope fits the project.
- The project's root `CLAUDE.md`/`AGENTS.md` and the user's global instructions file.

**If `.claude/specs/` doesn't exist in this project:** suggest running `sdd-specs-init` first to create it. If the user declines, don't stop, and don't invent constitution-style rules that aren't there. Proceed using whatever project-level instructions exist plus direct investigation of the codebase, and say plainly in `spec.md` that these weren't available — a gap noted honestly is fine; a fabricated one isn't.

## Step 4 — Investigate, don't paraphrase

This is the actual point of the skill. A ticket description is a claim, not a fact. Before scoping anything:

- If the ticket claims something is broken, outdated, or missing — check it directly. Run the real tooling (a dependency-outdated check, `grep` for the actual code path, the actual failing command) rather than restating the ticket's framing in your own words.
- If the ticket is vague ("update all X", "fix the Y bug") — figure out what's actually true, even if that narrows or widens the apparent scope. A ticket that says "update all vendor packages" might mean one package needs a version bump, or it might mean nine — you don't know until you check each one individually, because wildcard/bulk checks can silently miss things (verify with a targeted per-item check if a bulk check's result seems surprising, e.g. "nothing to do" for a ticket that clearly implies something is needed).
- If investigating the stated problem surfaces a *different*, more serious problem (e.g. a vendor security bulletin turns out to be a non-issue for this codebase, but tracing the code path reveals this project's own code has an unrelated, unpatched vulnerability) — that discovery belongs in the spec. Don't discard it just because it wasn't what the ticket asked for; flag it prominently.
- Cite what you found concretely: file paths, line numbers, command output, version numbers. "Verified X" should be followed by how you verified it, not just an assertion.

Take as long as this needs. A spec built on an unverified assumption is worse than no spec.

## Step 5 — Clarify with the user

Step 4 settles what the code says; it can't settle what the user wants. Resolve what the ticket and the investigation left open before any planning document is written. This runs here, in the main session, because the planning subagent in Steps 6–8 can't ask the user anything. If nothing is open, say so and move on.

Ask only what you can't find out yourself: investigate first, and never ask what the code, docs, or git history already answer.
1. **Confirm, don't ask, what you inferred.** Present derived facts for correction ("Step 4 found X; correct?").
2. **Ask the real gaps in one grouped round.** Use `AskUserQuestion` (or the host's equivalent; up to 4 questions, 2–4 options each, "Other" is added automatically) for a small natural set of options, recommended option first. Use open conversation for anything that needs the user's own words.
3. **Probe the reasons behind scope-setting answers.** When an answer sets scope or a rule, ask why; the underlying goal often changes the right answer.
4. **Allow one follow-up round at most.** Record anything still unresolved, or answered "don't know", as an explicit open question in `spec.md`; never invent an answer.
5. **Write the answers into the file that uses them**: pass them to the planning subagent so they land in `spec.md`.

Topics, as needed:
- **Outcome** — what "done" looks like from the user's side, where the ticket is vague.
- **Scope** — confirm in/out, especially where Step 4 widened or narrowed the ticket's framing, or where the ticket seems to fall outside `mission.md`'s scope.
- **Constraints** — deadlines, version/compatibility requirements, anything that must not change.
- **Decisions** — choices between viable approaches that Step 4 surfaced and only the user can make.
- **Risk and rollout** — acceptable risk, testing expectations, rollout/rollback needs.
- **Contradictions** — anything Step 4 found that contradicts the ticket, and how to handle it.

## Steps 6–8 — Planning stage: dispatch to an Opus subagent

`spec.md`, `plan.md`, and `tasks.md` are this skill's actual planning output, and they benefit from the deepest reasoning available — dispatch them to a subagent pinned to Opus rather than writing them inline in whatever model is running this session.

- Use `Agent` with `subagent_type: "general-purpose"` and `model: "opus"`. **Do not use `subagent_type: "fork"`** — a fork always runs on the parent session's model and ignores a `model` override, which defeats the point here.
- A fresh (non-fork) agent starts with zero context, so the prompt must be fully self-contained. Include, inline in the prompt:
  - The ticket code and the full ticket text/description as given (don't paraphrase it away).
  - The confirmed base branch and branch prefix from Step 1, and the branch already created in Step 2.
  - The complete findings from Step 4's investigation — every claim verified, with the evidence (file paths, line numbers, command output, version numbers) exactly as gathered. This is the substance the plan must be grounded in; a fresh agent re-investigating from scratch defeats the purpose and risks a different, unreconciled set of findings.
  - The user's answers from Step 5, as given, plus anything left open there.
  - The contents (or exact file paths to read, since the subagent shares this project's working directory and can read them itself) of `.claude/specs/constitution.md`, `tech-stack.md`, `data-model.md`, `branching-strategy.md`, `workflow.md` — whichever exist.
  - The project's root `CLAUDE.md`/`AGENTS.md`.
  - The exact structural requirements for each file (below, and in `references/templates.md`, which the subagent can also read directly).
- Instruct the subagent to write the three files in order — `spec.md` first, then `plan.md` (informed by the finished `spec.md`), then `tasks.md` (derived from the finished `plan.md`) — to `.claude/tickets/<TICKET-CODE>/`, and to report back a short summary plus any open questions.
- **After it returns, read the three files yourself** before moving to Step 9. Confirm they actually landed, are structurally complete, and don't contradict Step 4's findings or Step 5's answers — an agent's summary describes what it intended to write, not necessarily what it wrote.

### `spec.md`

Create `.claude/tickets/<TICKET-CODE>/spec.md`. See `references/templates.md` for the exact structure and a worked example. In short, it covers:
- **Problem** — the ticket as given (quote it, don't summarize away details that might matter).
- **What was actually verified** — the investigation from Step 4, with evidence.
- **Clarified with the user** — the Step 5 questions and answers, one line each; these feed Scope and Acceptance criteria.
- **Why it matters** — especially if investigation changed the picture from what the ticket implied.
- **Scope** — explicit in/out, and why anything plausible-sounding was excluded.
- **Acceptance criteria** — concrete, checkable statements.
- **Open questions** — anything genuinely blocking that needs the user's input (missing credentials, a decision only they can make, information you have no way to obtain). Don't list questions you could answer yourself by looking harder.

### `plan.md`

Create `.claude/tickets/<TICKET-CODE>/plan.md`. It covers:
- **Approach** — the technical shape of the change, in enough detail that someone else could implement it from this document alone.
- **Steps** — concrete, in order, with exact commands/file paths where relevant.
- **Constitution compliance** — if `constitution.md` exists, check the plan against every Article explicitly and state which apply and why the plan satisfies them. If a step must deviate from an Article, say so plainly and justify it — don't quietly go around it.
- **Verification** — how the change will actually be tested, tied to what Step 4 found (if you found 8 call sites/consumers of the code you're changing, list testing all 8, not "test the feature").
- **Risks / rollback** — what could go wrong and how to undo it.
- **Rollout** — how this ticket moves through the project's branch/environment flow (per `branching-strategy.md`/`workflow.md` if present), and anything specific to this change worth calling out there (e.g. a shared-test-environment interference risk for this particular kind of change).

### `tasks.md`

Create `.claude/tickets/<TICKET-CODE>/tasks.md` — a checkbox list derived directly from `plan.md`'s steps, ordered, concrete enough that checking off the last box means the ticket is actually done (including the verification steps, not just the code change).

Include a review task immediately before the commit task: an independent code review of the ticket's diff, with findings addressed before committing. Don't hardcode a specific reviewer tool — this project may or may not have one installed. Word the task as: use `/codex:review` (or an equivalent review plugin/command) if one is available in the session, otherwise dispatch a code-review subagent over the diff. Treat this as one review pass, not both every time — reserve running more than one independent reviewer for a change large or risky enough that a single pass isn't enough confidence.

Include a commit task using this project's convention (see `branching-strategy.md` if present): the commit message MUST start with the ticket code as its first token, and MUST be a single short subject line with no body/explanation paragraphs, even when the change touched multiple concerns — e.g. `PROJ-123 upgrade payment SDK and fix cart total rounding`, not that same subject followed by paragraphs explaining what and why. That detail belongs in `spec.md`/`plan.md`, which already exist for exactly this purpose — don't duplicate it into the commit body. Not `Fix for PROJ-123: ...` either — the ticket code is always the first token, not buried mid-sentence.

```markdown
# PROJ-XXX — Tasks

- [ ] Step description, specific enough to act on
- [ ] ...
- [ ] Review the ticket's diff (`/codex:review` or equivalent if available, otherwise a review subagent) and address findings
- [ ] Commit with message `PROJ-XXX <description>`
- [ ] Update the ticket's tracker status per workflow.md's lifecycle, if defined
```

## Step 9 — Stop and hand back

This skill produces planning artifacts only. **Do not start writing implementation code after `tasks.md`.** End by telling the user:
- The branch that was created.
- A short summary of what Step 4's investigation actually found (especially anything that changed the scope from the ticket's original framing).
- That `spec.md`/`plan.md`/`tasks.md` are ready for their review, and implementation starts once they've looked them over.
- That the three docs are self-contained, so implementation can start in a fresh session. That keeps the context budget for the work and makes the specs, not chat memory, carry the intent.

If something in Step 4 turned out to be more urgent or differently-scoped than the ticket implied, say so plainly in this final summary — don't bury a real finding (like a live security issue) at the bottom of a long document where it might get skimmed past.

## After Approval — Implementation Handoff

This skill's job ends at `tasks.md`. Once the user has reviewed and approved it, implementation proceeds via `superpowers:executing-plans`, pointed at this ticket's `plan.md`/`tasks.md` — not its default `docs/superpowers/plans/` location.

**Keep the docs in sync while implementing.** When implementation deviates from the plan — a review finding traces back to a gap in `plan.md`, the user changes a requirement, or a step turns out unworkable — update `spec.md`/`plan.md`/`tasks.md` in the same step as the code, not afterwards. Make those changes through the agent rather than by hand, so related docs don't drift apart. `sdd-ticket-close` still reconciles against the real diff at the end, but it shouldn't have to discover every deviation from scratch.

**Decline the worktree it offers, by default.** `executing-plans` opens with `superpowers:using-git-worktrees`, which asks to create an isolated worktree. Say no and work in place on the ticket branch from Step 2 — it already isolates this work, and nesting a worktree on top forces a redundant dependency install (e.g. `composer install`/`npm ci`) for no added safety. Only accept the worktree offer for a ticket large or risky enough that branch isolation genuinely isn't sufficient.
