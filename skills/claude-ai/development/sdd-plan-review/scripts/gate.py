#!/usr/bin/env python3
"""Deterministic SDD plan gate: aggregate planner/reviewer risk declarations under project policy.

evaluate        write gate.json (AUTO_IMPLEMENT or HUMAN_REVIEW) for a ticket folder
verify          check that gate.json still matches the documents, policy and repository state
verify --diff   pre-commit check of actual changed paths against planned files and path rules
record-approval append an audit record of a live human confirmation (never reusable consent)

Pure evaluator: no Git writes, no network, no project source changes. Invalid input fails closed.
"""
import argparse
import datetime as dt
import fnmatch
import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile

SCHEMA = 1
TRIGGERS = Path(__file__).resolve().parent.parent / 'assets' / 'triggers.json'
DEFAULT_POLICY = '.claude/specs/sdd-gate.json'
DOCS = ('spec.md', 'plan.md', 'tasks.md', 'planner-risk.json', 'review.json')
VERDICTS = {'APPROVED', 'REQUEST_CHANGES', 'HUMAN_REVIEW_REQUIRED'}
ANSWERS = {'yes', 'no', 'unknown'}
DECISIONS = {'AUTO_IMPLEMENT', 'HUMAN_REVIEW'}
ID_PATTERN = re.compile(r'^[a-z][a-z0-9_]{0,63}$')
POLICY_KEYS = {'schema', 'description', 'auto_implement', 'relax', 'additional_triggers', 'path_rules'}
CHECKBOX = re.compile(rb'(?m)^(\s*[-*+]\s+)\[[ xX]\]')


class GateError(ValueError):
    pass


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat(timespec='seconds')


def read_input(path):
    """Bytes of a regular file, None if absent; symlinks and other kinds are invalid."""
    if path.is_symlink():
        raise GateError(f'{path.name} must not be a symlink')
    if not path.exists():
        return None
    if not path.is_file():
        raise GateError(f'{path.name} must be a regular file')
    return path.read_bytes()


def file_hash(path, normalize_checkboxes=False):
    data = read_input(path)
    if data is None:
        return None
    if normalize_checkboxes:
        # Ticking tasks.md checkboxes during implementation is progress, not a plan change.
        data = CHECKBOX.sub(rb'\1[ ]', data)
    return hashlib.sha256(data).hexdigest()


def load_json(path, label):
    data = read_input(path)
    if data is None:
        raise GateError(f'{label} is missing')
    try:
        return json.loads(data)
    except (ValueError, UnicodeDecodeError) as error:
        raise GateError(f'{label} is not valid JSON: {error}') from None


def relative_path(value, label, allow_glob):
    if not isinstance(value, str) or not value or value != value.strip():
        raise GateError(f'{label} must be a non-empty project-relative path')
    if '\\' in value or value.startswith('/') or value.endswith('/'):
        raise GateError(f'{label} must be a project-relative POSIX path: {value}')
    parts = value.split('/')
    if any(part in {'', '.', '..'} for part in parts):
        raise GateError(f'{label} must be normalized and stay inside the project: {value}')
    if not allow_glob and set(value) & set('*?['):
        raise GateError(f'{label} must be an exact path, not a pattern: {value}')
    return value


def glob_match(pattern, path):
    """Anchored at the project root; '**' spans any number of path segments, '*' stays within one."""
    def match(pat, parts):
        if not pat:
            return not parts
        if pat[0] == '**':
            return any(match(pat[1:], parts[i:]) for i in range(len(parts) + 1))
        return bool(parts) and fnmatch.fnmatchcase(parts[0], pat[0]) and match(pat[1:], parts[1:])
    return match(pattern.split('/'), path.split('/'))


def load_triggers():
    value = load_json(TRIGGERS, 'canonical trigger schema')
    if not isinstance(value, dict) or value.get('schema') != SCHEMA:
        raise GateError('canonical trigger schema has an unsupported format')
    floor, defaults = value.get('floor'), value.get('defaults')
    if not isinstance(floor, dict) or not isinstance(defaults, dict) or set(floor) & set(defaults):
        raise GateError('canonical trigger schema needs disjoint floor and defaults maps')
    for name in list(floor) + list(defaults):
        if not ID_PATTERN.match(name):
            raise GateError(f'canonical trigger id is invalid: {name}')
    return set(floor), set(defaults)


def load_policy(path, floor, defaults):
    """Validated policy dict, or None when absent. Any invalid content raises (fail closed)."""
    if read_input(path) is None:
        return None
    value = load_json(path, 'project gate policy')
    if not isinstance(value, dict):
        raise GateError('project gate policy must be a JSON object')
    unknown = set(value) - POLICY_KEYS
    if unknown:
        raise GateError(f'project gate policy has unknown keys: {sorted(unknown)}')
    if value.get('schema') != SCHEMA:
        raise GateError('project gate policy must declare "schema": 1')
    auto = value.get('auto_implement', False)
    if not isinstance(auto, bool):
        raise GateError('auto_implement must be true or false')
    relax = value.get('relax', {})
    if not isinstance(relax, dict):
        raise GateError('relax must map default trigger ids to reasons')
    for name, reason in relax.items():
        if name in floor:
            raise GateError(f'floor trigger cannot be relaxed: {name}')
        if name not in defaults:
            raise GateError(f'only default triggers can be relaxed: {name}')
        if not isinstance(reason, str) or not reason.strip():
            raise GateError(f'relaxing {name} needs a non-empty reason')
    added = value.get('additional_triggers', {})
    if not isinstance(added, dict):
        raise GateError('additional_triggers must map trigger ids to definitions')
    for name, definition in added.items():
        if not ID_PATTERN.match(name) or name in floor or name in defaults:
            raise GateError(f'additional trigger id is invalid or collides with a canonical id: {name}')
        if not isinstance(definition, str) or not definition.strip():
            raise GateError(f'additional trigger {name} needs a definition')
    rules = value.get('path_rules', [])
    if not isinstance(rules, list):
        raise GateError('path_rules must be a list of glob patterns')
    rules = [relative_path(rule, 'path rule', allow_glob=True) for rule in rules]
    return {'auto_implement': auto, 'relax': set(relax), 'additional': set(added), 'path_rules': rules}


def load_declaration(path, label, known):
    """Return (answers, notes). Missing or malformed entries become 'unknown' with a note."""
    value = load_json(path, path.name)
    if not isinstance(value, dict) or value.get('schema') != SCHEMA or not isinstance(value.get('triggers'), dict):
        raise GateError(f'{label} must be an object with "schema": 1 and a "triggers" map')
    answers, notes = {}, []
    for name, entry in value['triggers'].items():
        if name not in known:
            raise GateError(f'{label} declares an unknown trigger: {name}')
        answer = entry.get('answer') if isinstance(entry, dict) else None
        evidence = entry.get('evidence') if isinstance(entry, dict) else None
        if not isinstance(answer, str) or answer not in ANSWERS or not isinstance(evidence, str) or not evidence.strip():
            notes.append(f'{label}: {name} has no valid answer with evidence; treated as unknown')
            answer = 'unknown'
        answers[name] = answer
    for name in sorted(known - set(answers)):
        notes.append(f'{label}: {name} is not declared; treated as unknown')
        answers[name] = 'unknown'
    return value, answers, notes


def git(root, *args, ok=False):
    result = subprocess.run(['git', '-c', 'core.fsmonitor=false', *args], cwd=root, stdout=subprocess.PIPE,
                            stderr=subprocess.PIPE, env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, timeout=60)
    if result.returncode and not ok:
        raise GateError(f'git {args[0]} failed: {result.stderr.decode(errors="replace").strip()}')
    return result


def repository_state(root):
    """{'branch', 'head'} for a Git worktree root, None for a non-Git project."""
    if not shutil.which('git'):
        if (root / '.git').exists():
            raise GateError('Git project detected but git is unavailable')
        return None
    top = git(root, 'rev-parse', '--show-toplevel', ok=True)
    if top.returncode:
        if (root / '.git').exists():
            raise GateError('cannot inspect Git project')
        return None
    if Path(os.fsdecode(top.stdout).strip()).resolve() != root:
        raise GateError('project must be the Git worktree root')
    branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', ok=True)
    head = git(root, 'rev-parse', '--verify', 'HEAD', ok=True)
    branch_name = os.fsdecode(branch.stdout).strip() if branch.returncode == 0 else ''
    head_sha = os.fsdecode(head.stdout).strip() if head.returncode == 0 else ''
    return {'branch': branch_name or None, 'head': head_sha or None}


def nul_paths(data):
    return [os.fsdecode(p) for p in data.split(b'\0') if p]


def under(path, folder):
    return path == folder or path.startswith(folder + '/')


def tracked_changes(root, ticket):
    entries = git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=no').stdout.split(b'\0')
    paths, index = [], 0
    while index < len(entries):
        entry = entries[index]
        index += 1
        if not entry:
            continue
        status, path = entry[:2].decode(), os.fsdecode(entry[3:])
        paths.append(path)
        if 'R' in status or 'C' in status:
            paths.append(os.fsdecode(entries[index]))
            index += 1
    return sorted(p for p in paths if not under(p, ticket))


def changed_paths(root, base, ticket):
    # Working tree and index are compared separately: a staged change whose working copy was later
    # reverted is invisible to the working-tree diff but would still be committed.
    options = ('--name-only', '--no-renames', '--no-ext-diff', '-z')
    worktree = git(root, 'diff', *options, base, '--').stdout
    staged = git(root, 'diff', '--cached', *options, base, '--').stdout
    untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
    paths = set(nul_paths(worktree) + nul_paths(staged) + nul_paths(untracked))
    return sorted(p for p in paths if not under(p, ticket))


def ticket_folder(root, ticket):
    ticket = relative_path(ticket, 'ticket folder', allow_glob=False)
    folder = root / ticket
    if folder.is_symlink() or not folder.is_dir():
        raise GateError(f'ticket folder must be a real directory: {ticket}')
    return ticket, folder


def input_hashes(root, folder, policy_rel, errors=None):
    """Hash every gate input. With errors=None an invalid input raises; otherwise it is recorded as None."""
    paths = {name: folder / name for name in DOCS}
    paths.update({'policy': root / policy_rel, 'triggers': TRIGGERS})
    hashes = {}
    for name, path in paths.items():
        try:
            hashes[name] = file_hash(path, normalize_checkboxes=name == 'tasks.md')
        except GateError as error:
            if errors is None:
                raise
            errors.append(f'cannot hash {name}: {error}')
            hashes[name] = None
    return hashes


def atomic_json(path, value):
    if path.is_symlink():
        raise GateError(f'{path.name} must not be a symlink')
    fd, name = tempfile.mkstemp(prefix='.gate-', dir=path.parent)
    try:
        with os.fdopen(fd, 'w') as stream:
            json.dump(value, stream, indent=2, sort_keys=True)
            stream.write('\n')
        os.replace(name, path)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def evaluate(root, ticket, policy_rel):
    gate = compute_gate(root, ticket, policy_rel)
    atomic_json(root / gate['ticket_dir'] / 'gate.json', gate)
    return gate


def compute_gate(root, ticket, policy_rel):
    """The deterministic gate for the current inputs, without writing anything."""
    ticket, folder = ticket_folder(root, ticket)
    policy_rel = relative_path(policy_rel, 'policy path', allow_glob=False)
    reasons = []
    review_verdict = None
    try:
        floor, defaults = load_triggers()
    except GateError as error:
        floor = defaults = None
        reasons.append(str(error))
    policy = None
    if floor is not None:
        try:
            policy = load_policy(root / policy_rel, floor, defaults)
            if policy is None:
                reasons.append(f'no project gate policy at {policy_rel}; automatic implementation is not enabled')
            elif not policy['auto_implement']:
                reasons.append('project gate policy does not enable auto_implement')
        except GateError as error:
            reasons.append(f'invalid project gate policy: {error}')
    for name in ('spec.md', 'plan.md', 'tasks.md'):
        try:
            if read_input(folder / name) is None:
                reasons.append(f'{name} is missing')
        except GateError as error:
            reasons.append(str(error))
    if floor is not None:
        known = floor | defaults | (policy['additional'] if policy else set())
        relaxed = policy['relax'] if policy else set()
        sides = {}
        for label, name in (('planner', 'planner-risk.json'), ('reviewer', 'review.json')):
            try:
                value, answers, notes = load_declaration(folder / name, label, known)
                sides[label] = (value, answers)
                reasons.extend(notes)
            except GateError as error:
                reasons.append(str(error))
        if 'planner' in sides:
            planned = sides['planner'][0].get('planned_files')
            try:
                if not isinstance(planned, list) or not planned:
                    raise GateError('planner-risk.json needs a non-empty planned_files list')
                planned = [relative_path(p, 'planned file', allow_glob=False) for p in planned]
                for rule in (policy['path_rules'] if policy else []):
                    reasons.extend(f'path rule {rule} matches planned file {p}' for p in planned if glob_match(rule, p))
            except GateError as error:
                reasons.append(str(error))
        if 'reviewer' in sides:
            review = sides['reviewer'][0]
            review_verdict = review.get('verdict')
            lists_ok = all(isinstance(review.get(key), list) and all(isinstance(i, str) for i in review[key])
                           for key in ('blocking_findings', 'non_blocking_findings', 'unverified_claims'))
            verdict_ok = isinstance(review_verdict, str) and review_verdict in VERDICTS
            if verdict_ok and lists_ok:
                # The contract ties findings to the verdict; a contradictory review is not a usable review.
                blocking = bool(review['blocking_findings'])
                verdict_ok = not (review_verdict == 'APPROVED' and blocking) and \
                    not (review_verdict == 'REQUEST_CHANGES' and not blocking)
            if not verdict_ok or not lists_ok or not isinstance(review.get('summary'), str):
                reasons.append('review.json does not follow the reviewer output contract')
                review_verdict = None
            elif review_verdict != 'APPROVED':
                reasons.append(f'reviewer verdict is {review_verdict}')
        for name in sorted(known - relaxed):
            triggered = {label: side[1][name] for label, side in sides.items() if side[1][name] != 'no'}
            if triggered:
                reasons.append(f'{name}: ' + ', '.join(f'{k}={v}' for k, v in sorted(triggered.items())))
    try:
        repository = repository_state(root)
        if repository is None:
            reasons.append('not a Git project; repository state cannot be bound')
        elif not repository['branch'] or not repository['head']:
            reasons.append('repository needs a checked-out branch with at least one commit')
    except GateError as error:
        repository = None
        reasons.append(str(error))
    hashes = input_hashes(root, folder, policy_rel, errors=reasons)
    gate = {'schema': SCHEMA, 'ticket': PurePosixPath(ticket).name, 'ticket_dir': ticket,
            'decision': 'HUMAN_REVIEW' if reasons else 'AUTO_IMPLEMENT', 'review_verdict': review_verdict,
            'reasons': reasons, 'repository': repository, 'policy_path': policy_rel, 'hashes': hashes,
            'evaluated_at': now()}
    return gate


def load_gate(root, ticket):
    ticket, folder = ticket_folder(root, ticket)
    gate = load_json(folder / 'gate.json', 'gate.json')
    required = {'schema', 'ticket', 'ticket_dir', 'decision', 'review_verdict', 'reasons', 'repository',
                'policy_path', 'hashes', 'evaluated_at'}
    if not isinstance(gate, dict) or set(gate) != required or gate['schema'] != SCHEMA:
        raise GateError('gate.json has an unsupported format; re-run sdd-plan-review')
    if gate['decision'] not in DECISIONS or gate['ticket_dir'] != ticket:
        raise GateError('gate.json does not belong to this ticket folder or has an invalid decision')
    repository = gate['repository']
    if not isinstance(gate['hashes'], dict) or not isinstance(gate['reasons'], list) or not (
            repository is None or (isinstance(repository, dict) and set(repository) == {'branch', 'head'})):
        raise GateError('gate.json has malformed hashes, reasons or repository fields')
    relative_path(gate['policy_path'], 'policy path', allow_glob=False)
    return ticket, folder, gate


def verify(root, ticket, diff=False):
    """Return (exit_code, result). 0 valid, 1 stale or invalid, 2 human review required (diff mode)."""
    ticket, folder, gate = load_gate(root, ticket)
    stale = [f'{name} changed since evaluation' for name, value in
             input_hashes(root, folder, gate['policy_path']).items() if gate['hashes'].get(name) != value]
    if not stale:
        # gate.json itself is not hashed; re-deriving the decision from the verified inputs means a
        # hand-edited decision, reason or verdict can't pass as an approved gate.
        fresh = compute_gate(root, ticket, gate['policy_path'])
        if any(fresh[key] != gate[key] for key in ('decision', 'reasons', 'review_verdict')):
            stale.append('gate.json decision does not match a fresh evaluation of the same inputs')
    result = {'decision': gate['decision'], 'reasons': gate['reasons'],
              'gate_sha256': file_hash(folder / 'gate.json'), 'stale': stale}
    bound = gate['repository']
    current = repository_state(root)
    if bound is None:
        if current is not None:
            stale.append('gate was evaluated without Git binding but the project is a Git repository')
        elif diff:
            result['diff'] = 'deterministic Git diff validation is unavailable for a non-Git project'
            return (1 if stale else 2), result
        return (1 if stale else 0), result
    if current is None:
        stale.append('project is no longer a Git repository')
        return 1, result
    if current['branch'] != bound['branch']:
        stale.append(f'branch is {current["branch"]}, evaluated on {bound["branch"]}')
    if not diff:
        if current['head'] != bound['head']:
            stale.append(f'HEAD is {current["head"]}, evaluated at {bound["head"]}')
        changes = tracked_changes(root, ticket)
        if changes:
            stale.append('tracked changes outside the ticket folder: ' + ', '.join(changes))
        return (1 if stale else 0), result
    ancestor = git(root, 'merge-base', '--is-ancestor', bound['head'], 'HEAD', ok=True).returncode == 0
    if not ancestor:
        stale.append(f'evaluated HEAD {bound["head"]} is not an ancestor of the current HEAD')
    if stale:
        return 1, result
    # A HUMAN_REVIEW gate may have been approved despite unusable inputs; that must route to the human
    # again, not dead-end as "stale" (the hashes already proved nothing changed).
    unusable = []
    try:
        planner = load_json(folder / 'planner-risk.json', 'planner-risk.json')
        planned = planner.get('planned_files') if isinstance(planner, dict) else None
        if not isinstance(planned, list):
            raise GateError('planner-risk.json has no planned_files list')
        planned = {relative_path(p, 'planned file', allow_glob=False) for p in planned}
    except GateError as error:
        unusable.append(f'planned files unavailable ({error}); every change is treated as unplanned')
        planned = set()
    try:
        policy = load_policy(root / gate['policy_path'], *load_triggers())
        rules = policy['path_rules'] if policy else []
    except GateError as error:
        unusable.append(f'path rules unavailable ({error}); protected paths cannot be checked')
        rules = []
    changed = changed_paths(root, bound['head'], ticket)
    unplanned = [p for p in changed if p not in planned]
    protected = [f'{p} (path rule {r})' for p in unplanned for r in rules if glob_match(r, p)]
    result.update({'changed': changed, 'unplanned': unplanned, 'unplanned_protected': protected,
                   'planned_unchanged': sorted(planned - set(changed)), 'unusable_inputs': unusable})
    return (2 if protected or unusable else 0), result


def record_approval(root, ticket, note):
    if not isinstance(note, str) or not note.strip():
        raise GateError('approval note must describe the live confirmation')
    code, result = verify(root, ticket)
    if code:
        raise GateError('gate is stale or invalid; re-run sdd-plan-review before approving')
    _, folder, gate = load_gate(root, ticket)
    path = folder / 'implementation-approval.json'
    record = load_json(path, 'implementation-approval.json') if read_input(path) is not None else {
        'schema': SCHEMA, 'purpose': 'Audit log only. Never proof of consent for a later session.', 'approvals': []}
    if not isinstance(record, dict) or not isinstance(record.get('approvals'), list):
        raise GateError('implementation-approval.json has an unsupported format')
    repository = gate['repository'] or {}
    record['approvals'].append({'gate_sha256': result['gate_sha256'], 'decision': gate['decision'],
                                'branch': repository.get('branch'), 'head': repository.get('head'),
                                'approved_at': now(), 'note': note.strip()})
    atomic_json(path, record)
    return record['approvals'][-1]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--project', required=True, help='Project root (the Git worktree root for Git projects)')
    parser.add_argument('--ticket', required=True, help='Project-relative ticket folder, e.g. .claude/tickets/PROJ-123')
    commands = parser.add_subparsers(dest='command', required=True)
    evaluate_parser = commands.add_parser('evaluate')
    evaluate_parser.add_argument('--policy', default=DEFAULT_POLICY, help='Project-relative gate policy path')
    verify_parser = commands.add_parser('verify')
    verify_parser.add_argument('--diff', action='store_true', help='Pre-commit check of actual changed paths')
    approval_parser = commands.add_parser('record-approval')
    approval_parser.add_argument('--note', required=True)
    args = parser.parse_args(argv)
    root = Path(args.project).resolve(strict=True)
    if args.command == 'evaluate':
        result, code = evaluate(root, args.ticket, args.policy), 0
    elif args.command == 'verify':
        code, result = verify(root, args.ticket, args.diff)
    else:
        result, code = record_approval(root, args.ticket, args.note), 0
    print(json.dumps(result, indent=2, sort_keys=True))
    return code


if __name__ == '__main__':
    try:
        sys.exit(main())
    except Exception as error:  # Fail closed on anything unexpected; a crash is never a pass.
        print(f'gate: {error}', file=sys.stderr)
        sys.exit(1)
