# Shared local handoff protocol (version 1)

Both assistants execute the same Python standard-library engine in `project-sync-save/scripts/project_sync.py`. Python 3.9+ is required; Git is required only for Git projects. Install the pair as sibling directories, either both symlinked to this repository's sibling skill directories or both copied into one flat skill directory. Mixed installations must resolve to a complete pair. `project-sync-load/scripts/project_sync.py` is only a launcher.

## Context input

The required keys below are exact; unknown keys are rejected. Arrays may be empty when there is genuinely nothing to record. Items may be strings or detailed objects, except processes/locks which must be objects. The assistant supplies semantic context; the helper cannot reconstruct the conversation.

```json
{
  "task": "Implement the requested change; include scope and success criteria.",
  "user_decisions": [{"decision": "Chosen behavior", "source": "User instruction/date"}],
  "completed_work": ["What changed, paths and why"],
  "remaining_work": ["What remains, blockers and dependencies"],
  "next_action": "One exact command or concrete editing/investigation step, with cwd",
  "verification": [{"command": "actual command", "cwd": ".", "exit_code": 0, "result": "Observed evidence, timestamp, state tested, limitations"}],
  "authorization": {
    "allowed": ["Existing scoped authorization"],
    "requires_confirmation": ["Actions awaiting consent or host approval"],
    "forbidden": ["Explicit exclusions"],
    "source": "Where these bounds came from; unknown authority remains unknown"
  },
  "operations": [{"operation": "Unfinished review/command", "status": "pending", "resume": "Inspect its durable log before retrying"}],
  "processes": [{"pid": 12345, "purpose": "Known background task", "log": "path", "ownership": "Evidence", "cleanup": "Authorized stop condition or unknown"}],
  "locks": [{"path": "relative/path.lock", "owner": "Known owner or unknown", "release_condition": "Evidence required"}],
  "cleanup": [{"path": "temporary path", "when": "After a stated condition", "authorization": "Existing consent or needs approval"}]
}
```

Only selected `--artifact` regular files are copied. Temporary logs/scripts become durable in the snapshot; references in the input should identify which artifacts carry the evidence. The checkpoint's `artifacts` manifest maps original source paths to durable paths and hashes. Do not record credentials, private chat transcripts, or unrelated cross-project correspondence. File inventory stores hashes, not contents; Git patches may contain source secrets, so inspect what you are saving. This is a handoff, not a source backup.

## Storage and atomicity

```text
.ai-sync/
  latest.json                       # atomic pointer to published snapshot ID
  snapshots/<id>/
    checkpoint.json                 # version, identity, time, assistant, context, state, artifacts
    staged.patch, unstaged.patch     # Git only, binary-capable, never auto-applied
    artifacts/<number>-<basename>    # selected durable logs/scripts
  receipts/<id>.json                 # reconciled checkpoint/state digests, notes, time
  reports/load.json                 # optional generated comparison
  write.lock/owner.json              # only while publishing/reconciling
```

The writer uses an exclusive mkdir lock; files are flushed/fsynced, a staged snapshot directory is atomically renamed, then `latest.json` is atomically replaced. Previous snapshots remain untouched. A crash before pointer replacement leaves the previous checkpoint current, possibly with an orphan complete snapshot or `.pending-*` directory. Inspect those and lock ownership manually; no automatic stale-lock deletion or retention pruning. Snapshots capture state twice and refuse publication if it changed. This detects common concurrent edits, but cannot freeze external writers; avoid saves during active mutation.

Load never applies patches or executes commands from checkpoint text. It compares current configuration, files, Git, recorded processes/locks, root and hostname; it verifies saved artifact hashes. A report can be written only directly into `.ai-sync/reports/`. Reconcile checks report digests against fresh state and requires rule acknowledgement and explicit notes. Later changes invalidate the receipt. A receipt is an assistant's recorded judgment, not a security approval or automated proof of semantic correctness.

Existing `.ai-sync` and its storage directories must not be symlinks, and neither may `latest.json`, a snapshot's `checkpoint.json` or a receipt file. Treat handoff storage as locally trusted data; inspect unexpected contents before use. Ignore rules are ensured via `/.ai-sync/` in the root `.gitignore` (preserving existing contents). In Git projects, save, load and reconcile all refuse tracked handoff files, and load and reconcile also refuse an `.ai-sync/` that isn't ignored: a committed handoff came from someone else's clone and must never be presented as this user's checkpoint. In non-Git projects there is nothing to ignore yet; a future Git save adds the rule. Non-Git projects can't distinguish a handoff extracted from someone else's archive, so inspect an unexpected `.ai-sync/` before loading it.

## Discovery and optional project config

Read `AGENTS.override.md`, `AGENTS.md`, `CLAUDE.md`, `.claude/CLAUDE.md`, nested instruction files, `.claude/rules/*.md`, `.claude/specs/*.md`, `.codex/rules/*.md`, imports and applicable global rules. The script inventories local rule paths; the assistant must read them, interpret scope, and discover imported/parent rules. No framework, project path, review command or communication directory is built into the engine.

An optional root `.ai-sync.json` accepts only these keys, with project-relative paths and no shell commands:

```json
{
  "exclude_dirs": ["generated-cache"],
  "extra_paths": ["ignored-but-relevant/settings.json"],
  "rule_paths": ["docs/project-rules.md"]
}
```

`exclude_dirs` adds directory basenames to the non-Git scan exclusions. Defaults are `.git`, `.ai-sync`, `node_modules`, `vendor`, `.venv`, `__pycache__`. Git projects inventory tracked and nonignored untracked files, regardless of scan exclusions; `extra_paths` includes otherwise omitted files/directories in either mode. Instructions and config are fingerprinted even when ignored. `.ai-sync` and `.git` contents never become project inventory. Source symlinks are fingerprinted without reading targets; configured paths must stay inside the project. Discovered instruction files may be symlinks to shared rules outside the root: the link and resolved rule content are fingerprinted, so shared-rule edits invalidate reconciliation. External instruction content is read only for hashes, never copied. Excluded/ignored files outside explicit extra paths are outside comparison coverage. Declare this limitation if relevant to the next action.

Root must be the Git worktree root; a nested non-Git project inside a Git worktree needs a separately chosen boundary rather than pretending Git is absent. Detached/unborn HEAD, staged/unstaged changes, renames, deletions, untracked filenames (including whitespace), and linked worktrees are supported. Git operations/`index.lock` markers are observed; directories are existence/mode probes only, so inspect their contents manually. Submodules appear as Git entries: checkpoint active submodule work separately or include relevant files explicitly; do not claim a recursive source backup.

Process probing is limited to supplied PIDs (`ps` start time and command); absence, blocked probing, another hostname or PID reuse require investigation. No terminal session, running process, agent, or OS approval is transferred. Commands are never resumed automatically by the script.

## CLI and validation

```bash
python3 <save-skill>/scripts/project_sync.py --project <root> save --assistant codex --context <json> --artifact <log>
python3 <load-skill>/scripts/project_sync.py --project <root> load --output <root>/.ai-sync/reports/load.json
python3 <load-skill>/scripts/project_sync.py --project <root> reconcile --report <load.json> --notes <json>
python3 -m unittest discover -s <save-skill>/scripts -p 'test_*.py' -v
```

`save` success is exit 0; `load`/`reconcile` exit 0 only with a current receipt and intact artifacts; exit 2 requests reconciliation; exit 1 is an error. Reports include `context`, `rule_paths`, `differences`, `damaged_artifacts`, `actual_digest`, `checkpoint_digest`, `reconciliation`, and `resume_ready`. Failures keep the previous pointer valid; never interpret an error as a successful save.
