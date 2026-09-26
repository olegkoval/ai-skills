# ai-skills — Constitution

Non-negotiable rules for authoring and maintaining skills in this repo. This is this repo's own meta-constitution — not to be confused with `skills/development/sdd-specs-init/assets/specs/constitution.md`, which is a generic starter file shipped for *adopters* of the SDD skills to fill in for their own projects.

## Article 1 — Stack and host agnosticism

Skills in this repo must not assume a specific language, framework, ticket tracker, or vendor convention unless a skill is explicitly scoped to one. Project-specific detail (base branch name, dependency tooling, ticket status names) is read from the *consuming* project's own `.claude/specs/` files at run time, never hardcoded into a skill. (`sdd-ticket-start` and `sdd-ticket-close` were genericized from Magento/Composer-specific originals for exactly this reason — see their SKILL.md history.)

## Article 2 — SKILL.md structure

Every skill lives at `skills/<category>/<name>/SKILL.md` with YAML frontmatter (`name`, `description`). `<category>` groups skills by specialization/domain (e.g. `development/`) — create a new category folder only once its first real skill actually exists, never speculatively (see Article 6). The category is a repo-organization concept only; it's dropped when a skill is installed into `~/.claude/skills/` or a project's `.claude/skills/`. The `description` is the only thing Claude sees before deciding whether to invoke the skill, so it must be trigger-rich: concrete trigger phrases, when to use it, and — for paired skills — when the companion skill takes over instead.

## Article 3 — Supplementary detail goes in `references/`

Worked examples, document skeletons, and long-form templates that would bloat a `SKILL.md`'s primary instructions belong in `skills/<category>/<name>/references/*.md`, linked from the `SKILL.md` rather than inlined.

## Article 4 — Paired skills document their handoff explicitly

When a skill is one half of a pair (e.g. `sdd-ticket-start` / `sdd-ticket-close`), each `SKILL.md` must state plainly where its own responsibility ends and the other skill's begins. Nothing about the handoff should be left implicit.

## Article 5 — Adopter templates are a separate audience from this repo's own specs

`skills/development/sdd-specs-init/assets/specs/` contains generic, fill-in-the-blank starter files for projects *adopting* these skills. `.claude/specs/` (this directory) documents `ai-skills` itself. The two must not be conflated — a change to one is not automatically a change to the other.

## Article 6 — No fabricated context

If a skill's instructions reference project context that may not exist in the consuming project (e.g. `.claude/specs/constitution.md`), the skill must degrade gracefully: proceed without it and say so plainly. Never invent rules or conventions that aren't actually there, in this repo or any project consuming it.

## Article 7 — Frontmatter must parse as valid YAML

Every `SKILL.md`'s frontmatter must parse with a strict YAML parser, with the full `description` intact. Check it before committing any skill change (e.g. Ruby `YAML.safe_load`, comparing the parsed description's length to the raw line). In an unquoted description, avoid `: ` (starts a new key) and ` #` (starts a comment). Reason: both happened here. `: ` made GitHub fail to render a skill; ` #` silently cut `sdd-ticket-start`'s description to 75 characters, so the text Claude uses to decide when to invoke it was mostly lost.
