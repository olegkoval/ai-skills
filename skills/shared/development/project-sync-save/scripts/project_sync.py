#!/usr/bin/env python3
"""Local assistant checkpoints. Python 3.9+, standard library only."""
import argparse
import contextlib
import datetime as dt
import hashlib
import json
import os
from pathlib import Path
import shutil
import socket
import stat
import subprocess
import sys
import tempfile
import uuid

VERSION = 1
FIELDS = ('task', 'user_decisions', 'completed_work', 'remaining_work', 'next_action',
          'verification', 'authorization', 'operations', 'processes', 'locks', 'cleanup')
DEFAULT_EXCLUDES = {'.git', '.ai-sync', 'node_modules', 'vendor', '.venv', '__pycache__'}


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=True).encode()).hexdigest()


def read_json(path):
    return json.loads(Path(path).read_text())


def flush_dir(path):
    fd = os.open(path, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def write_file(path, data):
    with open(path, 'xb') as stream:
        stream.write(data)
        stream.flush()
        os.fsync(stream.fileno())


def atomic_json(path, value):
    data = (json.dumps(value, indent=2, ensure_ascii=True) + '\n').encode()
    fd, name = tempfile.mkstemp(prefix='.write-', dir=path.parent)
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(data)
            stream.flush()
            os.fsync(stream.fileno())
        os.replace(name, path)
        flush_dir(path.parent)
    finally:
        if os.path.exists(name):
            os.unlink(name)


def run(root, *args, ok=False):
    result = subprocess.run(args, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                            env={**os.environ, 'GIT_OPTIONAL_LOCKS': '0'}, timeout=60)
    if result.returncode and not ok:
        raise ValueError(f'{args[0]} failed: {result.stderr.decode(errors="replace").strip()}')
    return result


def git(root, *args, ok=False):
    return run(root, 'git', '-c', 'core.fsmonitor=false', *args, ok=ok)


def git_root(root):
    if not shutil.which('git'):
        if (root / '.git').exists():
            raise ValueError('Git project detected but git executable is unavailable')
        return None
    result = git(root, 'rev-parse', '--show-toplevel', ok=True)
    if result.returncode:
        if (root / '.git').exists():
            raise ValueError('Cannot inspect Git project')
        return None
    top = Path(os.fsdecode(result.stdout).strip()).resolve()
    if top != root:
        raise ValueError(f'Use the Git worktree root explicitly: {top}')
    return top


def entry_path(root, name):
    path = root / name
    if Path(name).is_absolute() or '..' in Path(name).parts:
        raise ValueError(f'Expected project-relative path: {name}')
    if not path.parent.resolve().is_relative_to(root):
        raise ValueError(f'Parent path escapes project: {name}')
    return path


def local_path(root, name):
    path = entry_path(root, name)
    if not path.resolve().is_relative_to(root):
        raise ValueError(f'Path escapes project: {name}')
    return path


def config(root):
    path = root / '.ai-sync.json'
    value = read_json(path) if path.exists() else {}
    allowed = {'exclude_dirs', 'extra_paths', 'rule_paths'}
    if not isinstance(value, dict) or set(value) - allowed:
        raise ValueError('Unknown .ai-sync.json configuration keys')
    for key in allowed:
        items = value.get(key, [])
        if not isinstance(items, list) or any(not isinstance(x, str) for x in items):
            raise ValueError(f'{key} must be a string array')
        for name in items:
            local_path(root, name)
    return value


def fingerprint(path):
    try:
        info = path.lstat()
    except FileNotFoundError:
        return {'kind': 'missing'}
    mode = stat.S_IMODE(info.st_mode)
    if path.is_symlink():
        return {'kind': 'symlink', 'target': os.readlink(path), 'mode': mode}
    if path.is_file():
        sha = hashlib.sha256()
        with path.open('rb') as stream:
            for block in iter(lambda: stream.read(1024 * 1024), b''):
                sha.update(block)
        after = path.stat()
        if (info.st_size, info.st_mtime_ns, info.st_ino) != (after.st_size, after.st_mtime_ns, after.st_ino):
            raise ValueError(f'File changed during capture: {path}')
        return {'kind': 'file', 'sha256': sha.hexdigest(), 'size': info.st_size, 'mode': mode}
    return {'kind': 'directory' if path.is_dir() else 'special', 'mode': mode}


def discover_rules(root, cfg):
    names = {'CLAUDE.md', 'AGENTS.md', 'AGENTS.override.md', '.claude/CLAUDE.md', '.ai-sync.json'}
    for folder in ('.claude/specs', '.claude/rules', '.codex/rules'):
        base = root / folder
        if base.exists() and not base.is_symlink():
            names.update(str(p.relative_to(root)) for p in base.rglob('*.md'))
    # Nested instructions apply when the next action touches that subtree.
    for base, dirs, files in os.walk(root, followlinks=False):
        dirs[:] = [d for d in dirs if d not in DEFAULT_EXCLUDES and not (Path(base) / d).is_symlink()]
        for name in ('AGENTS.override.md', 'AGENTS.md', 'CLAUDE.md'):
            if name in files:
                names.add(str((Path(base) / name).relative_to(root)))
    names.update(cfg.get('rule_paths', []))
    return sorted(n for n in names if entry_path(root, n).exists() or entry_path(root, n).is_symlink())


def walk_files(root, excluded):
    paths = set()
    for base, dirs, files in os.walk(root, followlinks=False):
        for name in list(dirs):
            path = Path(base) / name
            if name in excluded:
                dirs.remove(name)
            elif path.is_symlink():
                paths.add(str(path.relative_to(root)))
                dirs.remove(name)
        paths.update(str((Path(base) / n).relative_to(root)) for n in files)
    return paths


def process_state(items):
    result = []
    for item in items:
        pid = item.get('pid')
        if not isinstance(pid, int) or isinstance(pid, bool) or pid <= 0:
            raise ValueError('Each process requires a positive integer pid')
        try:
            probe = subprocess.run(['ps', '-p', str(pid), '-o', 'lstart=', '-o', 'args='],
                                   capture_output=True, text=True, timeout=10)
            identity = probe.stdout.strip()
            if probe.stderr.strip():
                result.append({'pid': pid, 'status': 'unknown', 'reason': probe.stderr.strip()})
                continue
            result.append({'pid': pid, 'identity': identity, 'status': 'present' if identity else 'absent'})
        except (OSError, subprocess.TimeoutExpired):
            result.append({'pid': pid, 'status': 'unknown'})
    return result


def capture(root, cfg, context):
    top = git_root(root)
    paths = set()
    git_state = None
    if top:
        status = git(root, 'status', '--porcelain=v1', '-z', '--untracked-files=all').stdout
        tracked = git(root, 'ls-files', '-z').stdout
        untracked = git(root, 'ls-files', '--others', '--exclude-standard', '-z').stdout
        paths.update(os.fsdecode(p) for p in (tracked + untracked).split(b'\0') if p)
        branch = git(root, 'symbolic-ref', '--quiet', '--short', 'HEAD', ok=True)
        head = git(root, 'rev-parse', '--verify', 'HEAD', ok=True)
        patches = [git(root, 'diff', '--binary', '--no-ext-diff', '--no-textconv').stdout,
                   git(root, 'diff', '--cached', '--binary', '--no-ext-diff', '--no-textconv').stdout]
        git_state = {'branch': os.fsdecode(branch.stdout).strip() or None,
                     'head': os.fsdecode(head.stdout).strip() if head.returncode == 0 else None,
                     'status_hex': status.hex(),
                     'untracked': [os.fsdecode(p) for p in untracked.split(b'\0') if p],
                     'patch_sha256': [hashlib.sha256(p).hexdigest() for p in patches]}
        gitdir = Path(os.fsdecode(git(root, 'rev-parse', '--absolute-git-dir').stdout).strip())
        git_state['operations'] = {name: fingerprint(gitdir / name) for name in
                                   ('MERGE_HEAD', 'CHERRY_PICK_HEAD', 'REVERT_HEAD', 'BISECT_LOG',
                                    'rebase-merge', 'rebase-apply', 'index.lock')}
    else:
        patches = []
        paths = walk_files(root, DEFAULT_EXCLUDES | set(cfg.get('exclude_dirs', [])))
    rules = discover_rules(root, cfg)
    paths.update(rules)
    for name in cfg.get('extra_paths', []):
        path = local_path(root, name)
        if path.is_dir() and not path.is_symlink():
            paths.update(str(p.relative_to(root)) for p in path.rglob('*') if not p.is_dir() or p.is_symlink())
        else:
            paths.add(name)
    paths = {p for p in paths if Path(p).parts[0] not in {'.ai-sync', '.git'}}
    files = {}
    for name in sorted(paths):
        # Inventory symlinks themselves; never read their targets.
        path = root / name
        if not path.parent.resolve().is_relative_to(root):
            raise ValueError(f'Parent path escapes project: {name}')
        files[name] = fingerprint(path)
    lock_state = {item['path']: fingerprint(local_path(root, item['path'])) for item in context['locks']}
    return {'root': str(root), 'hostname': socket.gethostname(), 'git': git_state,
            'files': files, 'rule_paths': rules,
            'rule_targets': {n: fingerprint((root / n).resolve()) for n in rules}, 'config': cfg,
            'processes': process_state(context['processes']), 'locks': lock_state}, patches


def validate_context(value):
    if not isinstance(value, dict) or set(value) != set(FIELDS):
        raise ValueError(f'Context must contain exactly: {", ".join(FIELDS)}')
    for name in ('task', 'next_action'):
        if not isinstance(value[name], str) or not value[name].strip():
            raise ValueError(f'{name} must be a nonempty string')
    for name in set(FIELDS) - {'task', 'next_action', 'authorization'}:
        if not isinstance(value[name], list):
            raise ValueError(f'{name} must be an array (empty is valid)')
    auth = value['authorization']
    if not isinstance(auth, dict) or set(auth) != {'allowed', 'requires_confirmation', 'forbidden', 'source'}:
        raise ValueError('authorization requires allowed, requires_confirmation, forbidden, source')
    if any(not isinstance(auth[k], list) for k in ('allowed', 'requires_confirmation', 'forbidden')) or not isinstance(auth['source'], str):
        raise ValueError('Invalid authorization types')
    for item in value['locks']:
        if not isinstance(item, dict) or not isinstance(item.get('path'), str):
            raise ValueError('Each lock requires a project-relative path')
    for item in value['processes']:
        if not isinstance(item, dict):
            raise ValueError('Each process must be an object')
    return value


def storage(root, create=False):
    sync = root / '.ai-sync'
    if sync.is_symlink():
        raise ValueError('.ai-sync must not be a symlink')
    if create:
        sync.mkdir(mode=0o700, exist_ok=True)
    if not sync.is_dir():
        raise ValueError('No .ai-sync checkpoint storage exists')
    for name in ('snapshots', 'receipts', 'reports'):
        folder = sync / name
        if folder.is_symlink():
            raise ValueError(f'{folder} must not be a symlink')
        if create:
            folder.mkdir(mode=0o700, exist_ok=True)
    return sync


@contextlib.contextmanager
def locked(sync):
    lock = sync / 'write.lock'
    try:
        lock.mkdir(mode=0o700)
    except FileExistsError:
        raise ValueError(f'Writer lock exists: {lock}; inspect owner.json and verify owner is gone before manual cleanup')
    try:
        atomic_json(lock / 'owner.json', {'pid': os.getpid(), 'host': socket.gethostname(), 'time': now()})
        yield
    finally:
        (lock / 'owner.json').unlink(missing_ok=True)
        lock.rmdir()


def now():
    return dt.datetime.now(dt.timezone.utc).isoformat()


def refuse_tracked(root):
    if not git_root(root):
        return False
    if git(root, 'ls-files', '--', '.ai-sync').stdout:
        raise ValueError('.ai-sync contains tracked files; stop and resolve tracking explicitly')
    return True


def assert_local_storage(root):
    # A committed .ai-sync/ comes from someone else's clone; never present it as this user's handoff.
    if refuse_tracked(root) and git(root, 'check-ignore', '--quiet', '.ai-sync/', ok=True).returncode:
        raise ValueError('.ai-sync is not ignored; run project-sync-save or inspect ignore rules before loading')


def ensure_ignored(root):
    if not refuse_tracked(root):
        return
    probe = git(root, 'check-ignore', '--quiet', '.ai-sync/', ok=True)
    if probe.returncode == 0:
        return
    ignore = root / '.gitignore'
    if ignore.is_symlink():
        raise ValueError('Refusing to edit a symlinked .gitignore')
    old = ignore.read_bytes() if ignore.exists() else b''
    new = old + (b'\n' if old and not old.endswith(b'\n') else b'') + b'/.ai-sync/\n'
    fd, temp = tempfile.mkstemp(dir=root, prefix='.ignore-')
    try:
        with os.fdopen(fd, 'wb') as stream:
            stream.write(new)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(temp, stat.S_IMODE(ignore.stat().st_mode) if ignore.exists() else 0o644)
        os.replace(temp, ignore)
        flush_dir(root)
    finally:
        if os.path.exists(temp):
            os.unlink(temp)
    if git(root, 'check-ignore', '--quiet', '.ai-sync/', ok=True).returncode:
        raise ValueError('.ai-sync is still not ignored; inspect nested ignore rules')


def save(args, root):
    context = validate_context(read_json(args.context))
    cfg = config(root)
    sync = storage(root, create=True)
    with locked(sync):
        ensure_ignored(root)
        identifier = dt.datetime.now(dt.timezone.utc).strftime('%Y%m%dT%H%M%S%fZ') + '-' + uuid.uuid4().hex[:8]
        stage = Path(tempfile.mkdtemp(prefix='.pending-', dir=sync / 'snapshots'))
        try:
            artifacts = []
            (stage / 'artifacts').mkdir()
            for index, source in enumerate(args.artifact):
                source = Path(source).resolve(strict=True)
                if not source.is_file():
                    raise ValueError(f'Artifact must be a regular file: {source}')
                name = f'artifacts/{index:03d}-{source.name}'
                write_file(stage / name, source.read_bytes())
                artifacts.append({'path': name, 'source': str(source), 'fingerprint': fingerprint(stage / name)})
            state, patches = capture(root, cfg, context)
            for name, content in zip(('unstaged.patch', 'staged.patch'), patches):
                write_file(stage / name, content)
                artifacts.append({'path': name, 'fingerprint': fingerprint(stage / name)})
            checkpoint = {'format_version': VERSION, 'id': identifier, 'saved_at': now(),
                          'assistant': args.assistant, 'context': context, 'state': state, 'artifacts': artifacts}
            atomic_json(stage / 'checkpoint.json', checkpoint)
            again, _ = capture(root, cfg, context)
            if state != again:
                raise ValueError('Project changed during save; stabilize writers and retry')
            flush_dir(stage / 'artifacts')
            flush_dir(stage)
            os.rename(stage, sync / 'snapshots' / identifier)
            flush_dir(sync / 'snapshots')
            atomic_json(sync / 'latest.json', {'format_version': VERSION, 'id': identifier})
        except BaseException:
            if stage.exists():
                shutil.rmtree(stage)
            raise
    return {'saved': identifier, 'checkpoint': str(sync / 'snapshots' / identifier / 'checkpoint.json')}


def read_regular_json(path):
    if path.is_symlink():
        raise ValueError(f'{path.name} must not be a symlink')
    return read_json(path)


def checkpoint(sync):
    latest = read_regular_json(sync / 'latest.json')
    identifier = latest['id']
    if not isinstance(identifier, str) or Path(identifier).name != identifier or identifier in {'.', '..'}:
        raise ValueError('Invalid snapshot id')
    folder = sync / 'snapshots' / identifier
    if folder.is_symlink():
        raise ValueError('Snapshot must not be a symlink')
    value = read_regular_json(folder / 'checkpoint.json')
    if value.get('format_version') != VERSION or value.get('id') != identifier:
        raise ValueError('Unsupported or inconsistent checkpoint')
    validate_context(value['context'])
    return value, folder


def differences(saved, actual):
    changes = {}
    for key in set(saved) | set(actual):
        if saved.get(key) != actual.get(key):
            if key == 'files':
                before, after = saved[key], actual[key]
                changes[key] = {name: {'saved': before.get(name), 'actual': after.get(name)}
                                for name in sorted(set(before) | set(after)) if before.get(name) != after.get(name)}
            else:
                changes[key] = {'saved': saved.get(key), 'actual': actual.get(key)}
    return changes


def load_report(root, sync):
    value, folder = checkpoint(sync)
    actual, _ = capture(root, config(root), value['context'])
    changes = differences(value['state'], actual)
    damaged = []
    for item in value['artifacts']:
        path = local_path(folder, item['path'])
        if fingerprint(path) != item['fingerprint']:
            damaged.append(item['path'])
    receipt_path = sync / 'receipts' / (value['id'] + '.json')
    receipt = read_regular_json(receipt_path) if receipt_path.exists() or receipt_path.is_symlink() else None
    receipt_valid = bool(receipt and receipt.get('checkpoint_digest') == digest(value)
                         and receipt.get('actual_digest') == digest(actual))
    return {'format_version': VERSION, 'checkpoint_id': value['id'], 'checkpoint_digest': digest(value),
            'checkpoint_path': str(folder / 'checkpoint.json'), 'context': value['context'],
            'rule_paths': actual['rule_paths'], 'actual_digest': digest(actual),
            'differences': changes, 'damaged_artifacts': damaged,
            'reconciliation': receipt if receipt_valid else None,
            'resume_ready': receipt_valid and not damaged}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--project', required=True, help='Explicit project root (Git worktree root if Git)')
    commands = parser.add_subparsers(dest='command', required=True)
    save_parser = commands.add_parser('save')
    save_parser.add_argument('--context', required=True)
    save_parser.add_argument('--assistant', required=True, choices=['claude-code', 'codex'])
    save_parser.add_argument('--artifact', action='append', default=[])
    load_parser = commands.add_parser('load')
    load_parser.add_argument('--output', help='Optional report file inside .ai-sync/reports')
    reconcile = commands.add_parser('reconcile')
    reconcile.add_argument('--report', required=True)
    reconcile.add_argument('--notes', required=True, help='JSON with rules_read, resolutions, authorization, next_action')
    args = parser.parse_args()
    root = Path(args.project).resolve(strict=True)
    if not root.is_dir():
        raise ValueError('Project must be a directory')
    if args.command == 'save':
        result = save(args, root)
    else:
        assert_local_storage(root)
        sync = storage(root)
        result = load_report(root, sync)
        if args.command == 'reconcile':
            with locked(sync):
                previous = read_json(args.report)
                result = load_report(root, sync)
                for key in ('checkpoint_digest', 'actual_digest'):
                    if previous.get(key) != result[key]:
                        raise ValueError('State changed since load; load and reconcile again')
                if result['damaged_artifacts']:
                    raise ValueError('Checkpoint artifacts damaged; resolve before resuming')
                notes = read_json(args.notes)
                if not isinstance(notes, dict) or set(notes) != {'rules_read', 'resolutions', 'authorization', 'next_action'}:
                    raise ValueError('Notes require rules_read, resolutions, authorization, next_action')
                if not isinstance(notes['rules_read'], list) or not set(result['rule_paths']).issubset(notes['rules_read']):
                    raise ValueError('Read and list all discovered rule paths before reconciliation')
                if any(not isinstance(notes[k], str) or not notes[k].strip() for k in ('resolutions', 'authorization', 'next_action')):
                    raise ValueError('Reconciliation notes must be nonempty strings')
                receipt = {'checkpoint_digest': result['checkpoint_digest'], 'actual_digest': result['actual_digest'],
                           'reconciled_at': now(), 'notes': notes}
                atomic_json(sync / 'receipts' / (result['checkpoint_id'] + '.json'), receipt)
                result = load_report(root, sync)
        elif args.output:
            output = Path(args.output).absolute()
            if output.parent.resolve() != (sync / 'reports').resolve() or output.is_symlink():
                raise ValueError('Report output must be directly inside .ai-sync/reports')
            atomic_json(output, result)
    print(json.dumps(result, indent=2, ensure_ascii=True))
    return 0 if args.command == 'save' or result['resume_ready'] else 2


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError, KeyError, TypeError, subprocess.TimeoutExpired) as error:
        print(f'project-sync: {error}', file=sys.stderr)
        sys.exit(1)
