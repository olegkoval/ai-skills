"""Behavioral tests using isolated local projects; no services or credentials."""
import copy
import importlib.util
import json
import os
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name('project_sync.py')
LOADER = SCRIPT.parents[2] / 'project-sync-load/scripts/project_sync.py'
spec = importlib.util.spec_from_file_location('project_sync', SCRIPT)
engine = importlib.util.module_from_spec(spec)
spec.loader.exec_module(engine)
CONTEXT = {'task': 'Make the requested change', 'user_decisions': [], 'completed_work': [],
           'remaining_work': ['Run meaningful verification'], 'next_action': 'Inspect source.txt',
           'verification': [], 'authorization': {'allowed': ['Local edits'], 'requires_confirmation': ['Push'],
                                                'forbidden': ['Automatic commits'], 'source': 'Test user'},
           'operations': [], 'processes': [], 'locks': [], 'cleanup': []}


class RoundTrip(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'project'
        self.root.mkdir()
        self.context = Path(self.temp.name) / 'context.json'
        self.context.write_text(json.dumps(CONTEXT))
        (self.root / 'source.txt').write_text('original\n')
        (self.root / 'CLAUDE.md').write_text('Use local rules.\n')

    def cli(self, *args, code=0, loader=False):
        result = subprocess.run(['python3', str(LOADER if loader else SCRIPT), '--project', str(self.root), *args],
                                capture_output=True, text=True)
        self.assertEqual(result.returncode, code, result.stderr + result.stdout)
        return json.loads(result.stdout) if result.stdout else result.stderr

    def save(self, *args):
        return self.cli('save', '--assistant', 'codex', '--context', str(self.context), *args)

    def load(self):
        return self.cli('load', '--output', str(self.root / '.ai-sync/reports/load.json'), code=2, loader=True)

    def reconcile(self, report):
        notes = self.root / '.ai-sync/notes.json'
        notes.write_text(json.dumps({'rules_read': report['rule_paths'], 'resolutions': 'Inspected every difference and verification; preserve current work.',
                                     'authorization': 'Local edits only; push needs consent.', 'next_action': 'Inspect source.txt'}))
        return self.cli('reconcile', '--report', str(self.root / '.ai-sync/reports/load.json'), '--notes', str(notes), loader=True)

    def init_git(self):
        for args in (('init', '-q'), ('add', '.'), ('-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', 'commit', '-qm', 'initial')):
            subprocess.run(['git', *args], cwd=self.root, check=True, capture_output=True)

    def test_non_git_roundtrip_and_receipt_invalidation(self):
        self.save()
        report = self.load()
        self.assertEqual(report['differences'], {})
        self.assertTrue(self.reconcile(report)['resume_ready'])
        self.cli('load', loader=True)
        (self.root / 'source.txt').write_text('new')
        report = self.load()
        self.assertIn('source.txt', report['differences']['files'])
        self.assertIsNone(report['reconciliation'])

    def test_git_index_worktree_untracked_and_head(self):
        self.init_git()
        original = subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root).strip()
        (self.root / 'source.txt').write_text('staged')
        subprocess.run(['git', 'add', 'source.txt'], cwd=self.root, check=True)
        (self.root / 'source.txt').write_text('unstaged')
        (self.root / 'odd\nname.txt').write_text('untracked')
        saved = self.save()
        checkpoint = json.loads(Path(saved['checkpoint']).read_text())
        self.assertIn('odd\nname.txt', checkpoint['state']['git']['untracked'])
        self.assertTrue((Path(saved['checkpoint']).parent / 'staged.patch').read_bytes())
        self.assertEqual(subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=self.root).strip(), original)
        self.assertEqual(subprocess.run(['git', 'check-ignore', '-q', '.ai-sync/probe'], cwd=self.root).returncode, 0)
        (self.root / 'odd\nname.txt').write_text('altered')
        self.assertIn('odd\nname.txt', self.load()['differences']['files'])

    def test_artifacts_survive_source_removal_and_detect_tampering(self):
        log = Path(self.temp.name) / 'verification.log'
        log.write_text('checks passed')
        saved = self.save('--artifact', str(log))
        log.unlink()
        report = self.load()
        self.assertEqual(report['damaged_artifacts'], [])
        artifact = Path(saved['checkpoint']).parent / 'artifacts/000-verification.log'
        self.assertEqual(artifact.read_text(), 'checks passed')
        artifact.write_text('tampered')
        self.assertEqual(self.load()['damaged_artifacts'], ['artifacts/000-verification.log'])

    def test_snapshots_retained_and_failed_publish_preserves_pointer(self):
        first = self.save()['saved']
        second = self.save()['saved']
        self.assertNotEqual(first, second)
        self.assertTrue((self.root / '.ai-sync/snapshots' / first).is_dir())
        self.cli('save', '--assistant', 'codex', '--context', str(self.context), '--artifact', str(self.root / 'absent'), code=1)
        self.assertEqual(engine.read_json(self.root / '.ai-sync/latest.json')['id'], second)

    def test_concurrent_writer_refused(self):
        self.save()
        (self.root / '.ai-sync/write.lock').mkdir()
        error = self.cli('save', '--assistant', 'codex', '--context', str(self.context), code=1)
        self.assertIn('Writer lock exists', error)
        self.assertTrue((self.root / '.ai-sync/write.lock').exists())

    def test_stale_report_cannot_be_reconciled(self):
        self.save()
        report = self.load()
        notes = self.root / '.ai-sync/notes.json'
        notes.write_text(json.dumps({'rules_read': report['rule_paths'], 'resolutions': 'All inspected', 'authorization': 'Local only', 'next_action': 'Inspect'}))
        (self.root / 'source.txt').write_text('changed after load')
        self.cli('reconcile', '--report', str(self.root / '.ai-sync/reports/load.json'), '--notes', str(notes), code=1)

    def test_changed_rules_ignored_extra_files_locks_and_processes(self):
        self.init_git()
        (self.root / '.gitignore').write_text('ignored.txt\n')
        (self.root / 'ignored.txt').write_text('important')
        (self.root / '.ai-sync.json').write_text(json.dumps({'extra_paths': ['ignored.txt']}))
        ctx = copy.deepcopy(CONTEXT)
        ctx['locks'] = [{'path': 'job.lock', 'owner': 'test'}]
        ctx['processes'] = [{'pid': os.getpid(), 'purpose': 'test'}]
        self.context.write_text(json.dumps(ctx))
        self.save()
        (self.root / 'job.lock').write_text('owner')
        (self.root / 'ignored.txt').write_text('changed')
        (self.root / 'CLAUDE.md').write_text('Revised rules')
        report = self.load()
        self.assertIn('locks', report['differences'])
        self.assertIn('ignored.txt', report['differences']['files'])
        self.assertIn('CLAUDE.md', report['differences']['files'])

    def test_unborn_detached_and_linked_worktree(self):
        subprocess.run(['git', 'init', '-q'], cwd=self.root, check=True)
        saved = self.save()
        self.assertIsNone(engine.read_json(saved['checkpoint'])['state']['git']['head'])
        subprocess.run(['git', 'add', '.'], cwd=self.root, check=True)
        subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=t@example.invalid', 'commit', '-qm', 'initial'], cwd=self.root, check=True, capture_output=True)
        linked = Path(self.temp.name) / 'linked'
        subprocess.run(['git', 'worktree', 'add', '--detach', str(linked)], cwd=self.root, check=True, capture_output=True)
        self.root = linked
        saved = self.save()
        self.assertIsNone(engine.read_json(saved['checkpoint'])['state']['git']['branch'])
        self.assertEqual(self.load()['differences'], {})

    def test_symlink_inventory_does_not_read_external_target(self):
        outside = Path(self.temp.name) / 'outside'
        outside.write_text('private')
        (self.root / 'link').symlink_to(outside)
        saved = self.save()
        self.assertEqual(engine.read_json(saved['checkpoint'])['state']['files']['link']['kind'], 'symlink')
        outside.write_text('other')
        self.assertEqual(self.load()['differences'], {})

    def test_narrow_ignore_does_not_expose_handoff(self):
        self.init_git()
        (self.root / '.gitignore').write_text('/.ai-sync/probe\n')
        self.save()
        paths = subprocess.check_output(['git', 'ls-files', '--others', '--exclude-standard'], cwd=self.root).decode()
        self.assertNotIn('.ai-sync/', paths)
        self.assertEqual(self.load()['differences'], {})

    def test_override_rules_and_extra_directory_symlinks(self):
        (self.root / 'AGENTS.override.md').write_text('Override instructions')
        (self.root / 'cache').mkdir()
        (self.root / 'destination').mkdir()
        (self.root / 'cache/link').symlink_to(self.root / 'destination', target_is_directory=True)
        (self.root / '.ai-sync.json').write_text(json.dumps({'exclude_dirs': ['cache'], 'extra_paths': ['cache']}))
        saved = self.save()
        state = engine.read_json(saved['checkpoint'])['state']
        self.assertIn('AGENTS.override.md', state['rule_paths'])
        self.assertEqual(state['files']['cache/link']['kind'], 'symlink')

    def test_external_instruction_symlink_and_target_drift(self):
        external = Path(self.temp.name) / 'shared-rules.md'
        external.write_text('Existing authority')
        (self.root / 'CLAUDE.md').unlink()
        (self.root / 'CLAUDE.md').symlink_to(external)
        self.save()
        report = self.load()
        self.assertEqual(report['differences'], {})
        self.assertTrue(self.reconcile(report)['resume_ready'])
        external.write_text('Changed authority')
        changed = self.load()
        self.assertIn('rule_targets', changed['differences'])
        self.assertIsNone(changed['reconciliation'])

    def test_state_mutation_aborts_publication(self):
        self.save()
        before = engine.read_json(self.root / '.ai-sync/latest.json')
        real_capture = engine.capture
        count = 0
        def mutating(*args):
            nonlocal count
            count += 1
            if count == 2:
                (self.root / 'source.txt').write_text('concurrent writer')
            return real_capture(*args)
        args = type('Args', (), {'context': str(self.context), 'assistant': 'codex', 'artifact': []})()
        with mock.patch.object(engine, 'capture', side_effect=mutating):
            with self.assertRaisesRegex(ValueError, 'changed during save'):
                engine.save(args, self.root)
        self.assertEqual(engine.read_json(self.root / '.ai-sync/latest.json'), before)


if __name__ == '__main__':
    unittest.main()
