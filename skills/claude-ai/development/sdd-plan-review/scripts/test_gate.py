"""Behavioral tests for gate.py using isolated temporary projects; no network or credentials."""
import importlib.util
import json
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest
from unittest import mock

SCRIPT = Path(__file__).with_name('gate.py')
spec = importlib.util.spec_from_file_location('gate', SCRIPT)
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)
CANONICAL = json.loads(gate.TRIGGERS.read_text())
TRIGGER_IDS = sorted(list(CANONICAL['floor']) + list(CANONICAL['defaults']))
TICKET = '.claude/tickets/T-1'
POLICY = '.claude/specs/sdd-gate.json'


def git(root, *args):
    return subprocess.run(['git', '-c', 'user.name=Test', '-c', 'user.email=test@example.invalid', *args],
                          cwd=root, check=True, capture_output=True, text=True).stdout.strip()


class GateTestCase(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name).resolve() / 'project'
        (self.root / 'src').mkdir(parents=True)
        (self.root / 'src/a.py').write_text('a = 1\n')
        git(self.root, 'init', '-q', '-b', 'main')
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'initial')
        git(self.root, 'checkout', '-qb', 'feature/T-1')
        self.write_policy({'schema': 1, 'auto_implement': True})
        git(self.root, 'add', '.')
        git(self.root, 'commit', '-qm', 'policy')
        self.folder = self.root / TICKET
        self.folder.mkdir(parents=True)
        for name in ('spec.md', 'plan.md'):
            (self.folder / name).write_text(f'# {name}\n')
        (self.folder / 'tasks.md').write_text('# Tasks\n\n- [ ] Change src/a.py\n- [ ] Commit\n')
        self.write_declaration('planner-risk.json', planned_files=['src/a.py'])
        self.write_declaration('review.json', verdict='APPROVED')

    def write_policy(self, value, commit=False):
        path = self.root / POLICY
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(value))
        if commit:
            git(self.root, 'add', POLICY)
            git(self.root, 'commit', '-qm', 'policy update')

    def write_declaration(self, name, overrides=None, extra=None, omit=(), planned_files=None, verdict=None):
        triggers = {t: {'answer': 'no', 'evidence': f'checked {t}'} for t in TRIGGER_IDS if t not in omit}
        triggers.update({t: {'answer': a, 'evidence': f'evidence for {t}'} for t, a in (overrides or {}).items()})
        triggers.update(extra or {})
        value = {'schema': 1, 'triggers': triggers}
        if planned_files is not None:
            value['planned_files'] = planned_files
        if verdict is not None:
            blocking = ['Planned step contradicts verified findings'] if verdict == 'REQUEST_CHANGES' else []
            value.update({'verdict': verdict, 'blocking_findings': blocking, 'non_blocking_findings': [],
                          'unverified_claims': [], 'summary': 'Reviewed.'})
        (self.folder / name).write_text(json.dumps(value))

    def evaluate(self):
        return gate.evaluate(self.root, TICKET)

    def assertHuman(self, result, fragment):
        self.assertEqual(result['decision'], 'HUMAN_REVIEW')
        self.assertTrue(any(fragment in reason for reason in result['reasons']), result['reasons'])


class Evaluate(GateTestCase):
    def test_clean_approved_plan_auto_implements(self):
        result = self.evaluate()
        self.assertEqual(result['decision'], 'AUTO_IMPLEMENT', result['reasons'])
        self.assertEqual(result['review_verdict'], 'APPROVED')
        self.assertEqual(result['repository']['branch'], 'feature/T-1')
        self.assertEqual(json.loads((self.folder / 'gate.json').read_text())['decision'], 'AUTO_IMPLEMENT')

    def test_missing_policy_requires_human_review(self):
        (self.root / POLICY).unlink()
        self.assertHuman(self.evaluate(), 'no project gate policy')

    def test_auto_disabled_requires_human_review(self):
        self.write_policy({'schema': 1, 'auto_implement': False})
        self.assertHuman(self.evaluate(), 'does not enable auto_implement')

    def test_floor_trigger_yes(self):
        self.write_declaration('planner-risk.json', {'security_sensitive_runtime_change': 'yes'}, planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'security_sensitive_runtime_change: planner=yes')

    def test_floor_trigger_unknown(self):
        self.write_declaration('review.json', {'investigation_incomplete': 'unknown'}, verdict='APPROVED')
        self.assertHuman(self.evaluate(), 'investigation_incomplete: reviewer=unknown')

    def test_floor_trigger_cannot_be_relaxed(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'relax': {'authn_authz': 'we trust it'}})
        self.write_declaration('planner-risk.json', {'authn_authz': 'yes'}, planned_files=['src/a.py'])
        result = self.evaluate()
        self.assertHuman(result, 'floor trigger cannot be relaxed: authn_authz')
        self.assertHuman(result, 'authn_authz: planner=yes')

    def test_default_trigger_requires_human_review(self):
        self.write_declaration('planner-risk.json', {'dependency_change': 'yes'}, planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'dependency_change: planner=yes')

    def test_valid_default_relaxation_allows_auto(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'relax': {'dependency_change': 'Lockfile bumps are routine here'}})
        self.write_declaration('planner-risk.json', {'dependency_change': 'yes'}, planned_files=['src/a.py'])
        self.write_declaration('review.json', {'dependency_change': 'yes'}, verdict='APPROVED')
        self.assertEqual(self.evaluate()['decision'], 'AUTO_IMPLEMENT')

    def test_empty_relaxation_reason_fails_closed(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'relax': {'dependency_change': '  '}})
        self.assertHuman(self.evaluate(), 'needs a non-empty reason')

    def test_relaxing_unknown_trigger_fails_closed(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'relax': {'made_up': 'reason'}})
        self.assertHuman(self.evaluate(), 'only default triggers can be relaxed')

    def test_planner_reviewer_union(self):
        self.write_declaration('review.json', {'schema_change': 'yes'}, verdict='APPROVED')
        self.assertHuman(self.evaluate(), 'schema_change: reviewer=yes')
        self.write_declaration('review.json', verdict='APPROVED')
        self.write_declaration('planner-risk.json', {'public_contract': 'yes'}, planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'public_contract: planner=yes')

    def test_reviewer_not_approved(self):
        for verdict in ('REQUEST_CHANGES', 'HUMAN_REVIEW_REQUIRED'):
            self.write_declaration('review.json', verdict=verdict)
            result = self.evaluate()
            self.assertHuman(result, f'reviewer verdict is {verdict}')
            self.assertEqual(result['review_verdict'], verdict)

    def test_review_contract_violation(self):
        value = json.loads((self.folder / 'review.json').read_text())
        del value['summary']
        (self.folder / 'review.json').write_text(json.dumps(value))
        self.assertHuman(self.evaluate(), 'does not follow the reviewer output contract')

    def test_contradictory_verdict_and_findings_fail_closed(self):
        value = json.loads((self.folder / 'review.json').read_text())
        value['blocking_findings'] = ['plan pushes to origin']
        (self.folder / 'review.json').write_text(json.dumps(value))
        self.assertHuman(self.evaluate(), 'does not follow the reviewer output contract')
        value.update(verdict='REQUEST_CHANGES', blocking_findings=[])
        (self.folder / 'review.json').write_text(json.dumps(value))
        self.assertHuman(self.evaluate(), 'does not follow the reviewer output contract')

    def test_non_string_answer_and_verdict_fail_closed(self):
        self.write_declaration('planner-risk.json', extra={'authn_authz': {'answer': ['no'], 'evidence': 'x'}},
                               planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'authn_authz: planner=unknown')
        self.write_declaration('planner-risk.json', planned_files=['src/a.py'])
        value = json.loads((self.folder / 'review.json').read_text())
        value['verdict'] = ['APPROVED']
        (self.folder / 'review.json').write_text(json.dumps(value))
        self.assertHuman(self.evaluate(), 'does not follow the reviewer output contract')

    def test_project_added_trigger(self):
        self.write_policy({'schema': 1, 'auto_implement': True,
                           'additional_triggers': {'cache_layout': 'Changes to full-page cache keys'}})
        self.assertHuman(self.evaluate(), 'planner: cache_layout is not declared')
        extra = {'cache_layout': {'answer': 'no', 'evidence': 'no cache keys touched'}}
        self.write_declaration('planner-risk.json', extra=extra, planned_files=['src/a.py'])
        self.write_declaration('review.json', extra=extra, verdict='APPROVED')
        self.assertEqual(self.evaluate()['decision'], 'AUTO_IMPLEMENT')
        self.write_declaration('review.json', extra={'cache_layout': {'answer': 'yes', 'evidence': 'key format changes'}},
                               verdict='APPROVED')
        self.assertHuman(self.evaluate(), 'cache_layout: reviewer=yes')

    def test_added_trigger_cannot_shadow_canonical(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'additional_triggers': {'authn_authz': 'x'}})
        self.assertHuman(self.evaluate(), 'collides with a canonical id')

    def test_planned_path_rule_match(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'path_rules': ['m2-hotfixes/**']})
        self.write_declaration('planner-risk.json', planned_files=['m2-hotfixes/04-oct.patch'])
        self.assertHuman(self.evaluate(), 'path rule m2-hotfixes/** matches planned file m2-hotfixes/04-oct.patch')

    def test_malformed_declarations(self):
        (self.folder / 'planner-risk.json').write_text('{not json')
        self.assertHuman(self.evaluate(), 'planner-risk.json is not valid JSON')
        self.write_declaration('planner-risk.json', extra={'authn_authz': {'answer': 'maybe', 'evidence': 'x'}},
                               planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'authn_authz has no valid answer')
        self.write_declaration('planner-risk.json', extra={'authn_authz': {'answer': 'no', 'evidence': ' '}},
                               planned_files=['src/a.py'])
        self.assertHuman(self.evaluate(), 'authn_authz: planner=unknown')

    def test_missing_trigger_is_unknown(self):
        self.write_declaration('planner-risk.json', omit=('secrets_crypto',), planned_files=['src/a.py'])
        result = self.evaluate()
        self.assertHuman(result, 'secrets_crypto is not declared')
        self.assertHuman(result, 'secrets_crypto: planner=unknown')

    def test_unexpected_trigger_rejected(self):
        self.write_declaration('review.json', extra={'vibes': {'answer': 'no', 'evidence': 'fine'}}, verdict='APPROVED')
        self.assertHuman(self.evaluate(), 'reviewer declares an unknown trigger: vibes')

    def test_planned_files_must_be_exact_project_paths(self):
        for bad in (['src/*.py'], ['/etc/passwd'], ['../outside.py'], ['./src/a.py'], []):
            self.write_declaration('planner-risk.json', planned_files=bad)
            self.assertEqual(self.evaluate()['decision'], 'HUMAN_REVIEW', bad)

    def test_missing_planning_document(self):
        (self.folder / 'tasks.md').unlink()
        self.assertHuman(self.evaluate(), 'tasks.md is missing')

    def test_symlinked_input_rejected(self):
        target = Path(self.temp.name) / 'outside.md'
        target.write_text('# spec\n')
        (self.folder / 'spec.md').unlink()
        (self.folder / 'spec.md').symlink_to(target)
        self.assertHuman(self.evaluate(), 'spec.md must not be a symlink')

    def test_invalid_policy_json_fails_closed(self):
        (self.root / POLICY).write_text('{"schema": 1, "auto_implement": "yes"}')
        self.assertHuman(self.evaluate(), 'auto_implement must be true or false')

    def test_non_git_project(self):
        shutil.rmtree(self.root / '.git')
        result = self.evaluate()
        self.assertHuman(result, 'not a Git project')
        self.assertIsNone(result['repository'])

    def test_reevaluation_replaces_gate(self):
        self.evaluate()
        self.write_declaration('review.json', verdict='REQUEST_CHANGES')
        self.assertEqual(self.evaluate()['decision'], 'HUMAN_REVIEW')
        self.assertEqual(json.loads((self.folder / 'gate.json').read_text())['decision'], 'HUMAN_REVIEW')


class Verify(GateTestCase):
    def test_fresh_gate_verifies(self):
        self.evaluate()
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 0, result)
        self.assertEqual(result['decision'], 'AUTO_IMPLEMENT')

    def test_document_hash_mismatch_is_stale(self):
        self.evaluate()
        (self.folder / 'plan.md').write_text('# plan.md\nchanged after review\n')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertIn('plan.md changed since evaluation', result['stale'])

    def test_ticking_task_checkboxes_is_not_a_plan_change(self):
        self.evaluate()
        (self.folder / 'tasks.md').write_text('# Tasks\n\n- [x] Change src/a.py\n- [X] Commit\n')
        self.assertEqual(gate.verify(self.root, TICKET)[0], 0)
        (self.folder / 'tasks.md').write_text('# Tasks\n\n- [x] Change src/b.py\n- [ ] Commit\n')
        self.assertEqual(gate.verify(self.root, TICKET)[0], 1)

    def test_checkbox_toggle_keeps_gate_but_task_text_change_invalidates(self):
        (self.folder / 'tasks.md').write_text('- [ ] Update Foo.php\n')
        self.evaluate()
        (self.folder / 'tasks.md').write_text('- [x] Update Foo.php\n')
        self.assertEqual(gate.verify(self.root, TICKET)[0], 0)
        (self.folder / 'tasks.md').write_text('- [ ] Update Foo.php\n')
        self.assertEqual(gate.verify(self.root, TICKET)[0], 0)
        (self.folder / 'tasks.md').write_text('- [x] Update Foo.php and Bar.php\n')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertIn('tasks.md changed since evaluation', result['stale'])

    def test_hand_edited_decision_is_rejected(self):
        self.write_declaration('planner-risk.json', {'authn_authz': 'yes'}, planned_files=['src/a.py'])
        self.assertEqual(self.evaluate()['decision'], 'HUMAN_REVIEW')
        value = json.loads((self.folder / 'gate.json').read_text())
        value.update(decision='AUTO_IMPLEMENT', reasons=[])
        (self.folder / 'gate.json').write_text(json.dumps(value))
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertIn('gate.json decision does not match a fresh evaluation of the same inputs', result['stale'])
        self.assertEqual(gate.verify(self.root, TICKET, diff=True)[0], 1)

    def test_branch_mismatch_is_stale(self):
        self.evaluate()
        git(self.root, 'checkout', '-qb', 'other')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertTrue(any('branch is other' in s for s in result['stale']))

    def test_head_mismatch_is_stale(self):
        self.evaluate()
        git(self.root, 'commit', '-q', '--allow-empty', '-m', 'moved')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertTrue(any(s.startswith('HEAD is') for s in result['stale']))

    def test_tracked_changes_outside_ticket_are_stale(self):
        self.evaluate()
        (self.root / 'src/a.py').write_text('a = 2\n')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertTrue(any('src/a.py' in s for s in result['stale']))

    def test_policy_change_is_stale(self):
        self.evaluate()
        self.write_policy({'schema': 1, 'auto_implement': True, 'path_rules': ['src/**']}, commit=True)
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertIn('policy changed since evaluation', result['stale'])

    def test_trigger_schema_change_is_stale(self):
        copy = Path(self.temp.name) / 'triggers.json'
        copy.write_text(gate.TRIGGERS.read_text())
        with mock.patch.object(gate, 'TRIGGERS', copy):
            self.evaluate()
            data = json.loads(copy.read_text())
            data['defaults']['new_default'] = 'Added later'
            copy.write_text(json.dumps(data))
            code, result = gate.verify(self.root, TICKET)
        self.assertEqual(code, 1)
        self.assertIn('triggers changed since evaluation', result['stale'])

    def test_missing_or_foreign_gate_fails(self):
        with self.assertRaises(gate.GateError):
            gate.verify(self.root, TICKET)
        self.evaluate()
        value = json.loads((self.folder / 'gate.json').read_text())
        value['ticket_dir'] = '.claude/tickets/OTHER'
        (self.folder / 'gate.json').write_text(json.dumps(value))
        with self.assertRaises(gate.GateError):
            gate.verify(self.root, TICKET)

    def test_non_git_verify_and_diff(self):
        shutil.rmtree(self.root / '.git')
        self.evaluate()
        self.assertEqual(gate.verify(self.root, TICKET)[0], 0)
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 2)
        self.assertIn('unavailable', result['diff'])


class VerifyDiff(GateTestCase):
    def setUp(self):
        super().setUp()
        self.write_policy({'schema': 1, 'auto_implement': True, 'path_rules': ['m2-hotfixes/**', '**/etc/acl.xml']},
                          commit=True)
        self.evaluate()

    def test_only_planned_files_pass(self):
        (self.root / 'src/a.py').write_text('a = 2\n')
        git(self.root, 'commit', '-qam', 'T-1 change')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 0, result)
        self.assertEqual(result['changed'], ['src/a.py'])
        self.assertEqual(result['unplanned'], [])

    def test_unplanned_unprotected_file_is_reported_not_blocking(self):
        (self.root / 'src/b.py').write_text('b = 1\n')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['unplanned'], ['src/b.py'])
        self.assertEqual(result['planned_unchanged'], ['src/a.py'])

    def test_unplanned_protected_file_requires_human(self):
        (self.root / 'm2-hotfixes').mkdir()
        (self.root / 'm2-hotfixes/05.patch').write_text('patch\n')
        (self.root / 'app/code/Vendor/Module/etc').mkdir(parents=True)
        (self.root / 'app/code/Vendor/Module/etc/acl.xml').write_text('<acl/>\n')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 2)
        self.assertEqual(len(result['unplanned_protected']), 2)

    def test_untracked_staged_and_deleted_paths_are_seen(self):
        (self.root / 'src/new.py').write_text('n = 1\n')
        (self.root / 'src/staged.py').write_text('s = 1\n')
        git(self.root, 'add', 'src/staged.py')
        (self.root / 'src/a.py').unlink()
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(result['changed'], ['src/a.py', 'src/new.py', 'src/staged.py'])

    def test_staged_change_with_reverted_worktree_is_seen(self):
        (self.root / 'm2-hotfixes').mkdir()
        (self.root / 'm2-hotfixes/06.patch').write_text('patch\n')
        git(self.root, 'add', 'm2-hotfixes/06.patch')
        (self.root / 'm2-hotfixes/06.patch').unlink()
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 2, result)
        self.assertIn('m2-hotfixes/06.patch', result['changed'])

    def test_ticket_folder_is_excluded(self):
        (self.folder / 'notes.md').write_text('working notes\n')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 0)
        self.assertEqual(result['changed'], [])

    def test_evaluated_head_no_longer_ancestor(self):
        git(self.root, 'commit', '-q', '--amend', '-m', 'rewritten history')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 1)
        self.assertTrue(any('not an ancestor' in s for s in result['stale']))

    def test_unusable_inputs_route_to_human_not_dead_end(self):
        (self.folder / 'planner-risk.json').unlink()
        self.assertEqual(self.evaluate()['decision'], 'HUMAN_REVIEW')
        (self.root / 'src/a.py').write_text('a = 3\n')
        code, result = gate.verify(self.root, TICKET, diff=True)
        self.assertEqual(code, 2, result)
        self.assertEqual(result['unplanned'], ['src/a.py'])
        self.assertTrue(result['unusable_inputs'])

    def test_plan_edit_during_implementation_is_stale(self):
        (self.folder / 'plan.md').write_text('# plan.md\nrevised mid-implementation\n')
        self.assertEqual(gate.verify(self.root, TICKET, diff=True)[0], 1)


class FixedLocations(GateTestCase):
    def test_policy_location_cannot_be_chosen_by_caller(self):
        self.write_policy({'schema': 1, 'auto_implement': False})
        (self.root / 'notes').mkdir()
        (self.root / 'notes/my-policy.json').write_text(json.dumps({'schema': 1, 'auto_implement': True}))
        cli = subprocess.run(['python3', str(SCRIPT), '--project', str(self.root), '--ticket', TICKET, 'evaluate',
                              '--policy', 'notes/my-policy.json'], capture_output=True, text=True)
        self.assertNotEqual(cli.returncode, 0)
        self.assertFalse((self.folder / 'gate.json').exists())
        self.assertHuman(self.evaluate(), 'does not enable auto_implement')

    def test_gate_recorded_against_another_policy_is_rejected(self):
        self.evaluate()
        value = json.loads((self.folder / 'gate.json').read_text())
        value['policy_path'] = 'notes/my-policy.json'
        (self.folder / 'gate.json').write_text(json.dumps(value))
        with self.assertRaisesRegex(gate.GateError, 'evaluated against notes/my-policy.json'):
            gate.verify(self.root, TICKET)

    def test_symlinked_policy_directory_fails_closed(self):
        outside = Path(self.temp.name) / 'outside-specs'
        outside.mkdir()
        (outside / 'sdd-gate.json').write_text(json.dumps({'schema': 1, 'auto_implement': True}))
        shutil.rmtree(self.root / '.claude/specs')
        (self.root / '.claude/specs').symlink_to(outside, target_is_directory=True)
        self.assertHuman(self.evaluate(), 'symlinked directory')

    def test_ticket_folder_must_be_under_claude_tickets(self):
        self.write_policy({'schema': 1, 'auto_implement': True, 'path_rules': ['m2-hotfixes/**']})
        (self.root / 'm2-hotfixes').mkdir()
        for bad in ('m2-hotfixes', 'src', '.claude/tickets', '.claude/tickets/T-1/nested', '.claude/specs'):
            with self.assertRaisesRegex(gate.GateError, 'ticket folder'):
                gate.evaluate(self.root, bad)

    def test_symlinked_tickets_directory_rejected(self):
        outside = Path(self.temp.name) / 'outside-tickets'
        shutil.move(str(self.root / '.claude/tickets'), str(outside))
        (self.root / '.claude/tickets').symlink_to(outside, target_is_directory=True)
        with self.assertRaisesRegex(gate.GateError, 'symlinked directory'):
            self.evaluate()


class GlobAndApproval(GateTestCase):
    def test_glob_semantics(self):
        self.assertTrue(gate.glob_match('m2-hotfixes/**', 'm2-hotfixes/a/b.patch'))
        self.assertTrue(gate.glob_match('**/db_schema.xml', 'db_schema.xml'))
        self.assertTrue(gate.glob_match('**/db_schema.xml', 'app/code/V/M/etc/db_schema.xml'))
        self.assertFalse(gate.glob_match('app/*.php', 'app/sub/x.php'))
        self.assertFalse(gate.glob_match('db_schema.xml', 'app/db_schema.xml'))

    def test_record_approval_appends_audit_entries_for_a_fresh_gate(self):
        self.write_declaration('planner-risk.json', {'framework_core': 'yes'}, planned_files=['src/a.py'])
        self.evaluate()
        first = gate.record_approval(self.root, TICKET, 'User confirmed live after reading the summary')
        gate.record_approval(self.root, TICKET, 'Second confirmation')
        record = json.loads((self.folder / 'implementation-approval.json').read_text())
        self.assertEqual(len(record['approvals']), 2)
        self.assertEqual(first['decision'], 'HUMAN_REVIEW')
        self.assertIn('Never proof of consent', record['purpose'])
        self.assertEqual(gate.verify(self.root, TICKET)[0], 0)

    def test_approval_file_is_never_authorization(self):
        self.write_declaration('planner-risk.json', {'framework_core': 'yes'}, planned_files=['src/a.py'])
        self.evaluate()
        gate.record_approval(self.root, TICKET, 'Approved in an earlier session')
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual((code, result['decision']), (0, 'HUMAN_REVIEW'))
        self.assertNotIn('approved', json.dumps(result).lower())
        forged = {'schema': 1, 'approvals': [{'decision': 'AUTO_IMPLEMENT', 'note': 'trust me'}], 'authorize': True}
        (self.folder / 'implementation-approval.json').write_text(json.dumps(forged))
        code, result = gate.verify(self.root, TICKET)
        self.assertEqual((code, result['decision']), (0, 'HUMAN_REVIEW'))
        self.assertEqual(self.evaluate()['decision'], 'HUMAN_REVIEW')
        self.assertNotIn('implementation-approval.json', gate.DOCS)

    def test_record_approval_refuses_stale_gate_and_empty_note(self):
        self.evaluate()
        with self.assertRaises(gate.GateError):
            gate.record_approval(self.root, TICKET, ' ')
        (self.folder / 'spec.md').write_text('# changed\n')
        with self.assertRaises(gate.GateError):
            gate.record_approval(self.root, TICKET, 'approve')

    def test_cli_exit_codes(self):
        def cli(*args):
            return subprocess.run(['python3', str(SCRIPT), '--project', str(self.root), '--ticket', TICKET, *args],
                                  capture_output=True, text=True)
        self.assertEqual(cli('verify').returncode, 1)
        evaluated = cli('evaluate')
        self.assertEqual(evaluated.returncode, 0, evaluated.stderr)
        self.assertEqual(json.loads(evaluated.stdout)['decision'], 'AUTO_IMPLEMENT')
        self.assertEqual(cli('verify').returncode, 0)
        (self.folder / 'spec.md').write_text('# edited\n')
        self.assertEqual(cli('verify').returncode, 1)


if __name__ == '__main__':
    unittest.main()
