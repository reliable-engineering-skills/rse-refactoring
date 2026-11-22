import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
import unittest

SCRIPT = Path(__file__).resolve().parents[1] / 'scripts' / 'check_baseline.py'


class RecorderTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.scope = self.root / 'project'
        self.scope.mkdir()
        self.session = self.root / 'record'
        self.program = self.scope / 'check.py'
        self.program.write_text('print("ok")\n', encoding='utf-8')
        self.config = self.root / 'checks.json'
        self.settings = {'checks': [{'name': 'contract', 'kind': 'behavior',
                                    'argv': [sys.executable, str(self.program)], 'timeout_seconds': 5}]}
        self.write_config()

    def write_config(self):
        self.config.write_text(json.dumps(self.settings), encoding='utf-8')

    def run_phase(self, phase, expected, scope=None, env=None):
        result = subprocess.run([sys.executable, str(SCRIPT), '--scope', str(scope or self.scope),
                                 '--config', str(self.config), '--session', str(self.session),
                                 '--phase', phase], capture_output=True, text=True, timeout=30, env=env)
        self.assertEqual(result.returncode, expected, result.stdout + result.stderr)
        return result

    def comparison(self):
        return json.loads((self.session / 'comparison.json').read_text(encoding='utf-8'))['checks'][0]['comparison']

    def test_passing_snapshot_and_comparison(self):
        self.run_phase('before', 0)
        self.run_phase('after', 0)
        self.assertEqual(self.comparison(), 'passing_in_both')

    def test_regression_is_reported(self):
        self.run_phase('before', 0)
        self.program.write_text('raise SystemExit(7)\n', encoding='utf-8')
        self.run_phase('after', 1)
        self.assertEqual(self.comparison(), 'new_failure')

    def test_preexisting_failure_is_not_reported_as_new(self):
        self.program.write_text('raise SystemExit(1)\n', encoding='utf-8')
        self.run_phase('before', 1)
        self.run_phase('after', 1)
        self.assertEqual(self.comparison(), 'still_failing')

    def test_failure_to_success(self):
        self.program.write_text('raise SystemExit(1)\n', encoding='utf-8')
        self.run_phase('before', 1)
        self.program.write_text('print("fixed")\n', encoding='utf-8')
        self.run_phase('after', 0)
        self.assertEqual(self.comparison(), 'now_passing')

    def test_baseline_cannot_be_overwritten(self):
        self.run_phase('before', 0)
        original = (self.session / 'before.json').read_bytes()
        self.run_phase('before', 3)
        self.assertEqual((self.session / 'before.json').read_bytes(), original)

    def test_changed_config_rejected_before_execution(self):
        self.run_phase('before', 0)
        self.settings['checks'][0]['argv'] = [sys.executable, '-c', 'open("should-not-exist", "w").close()']
        self.write_config()
        self.run_phase('after', 3)
        self.assertFalse((self.scope / 'should-not-exist').exists())

    def test_changed_scope_rejected(self):
        self.run_phase('before', 0)
        other = self.root / 'other'
        other.mkdir()
        self.run_phase('after', 3, other)
        self.assertFalse((self.session / 'after.json').exists())

    def test_missing_tool_is_incomplete(self):
        self.settings['checks'][0]['argv'] = ['rse-test-nonexistent-executable-71489']
        self.write_config()
        self.run_phase('before', 2)
        self.run_phase('after', 2)
        self.assertEqual(self.comparison(), 'incomplete')

    def test_timeout_is_incomplete(self):
        self.program.write_text('import time\ntime.sleep(2)\n', encoding='utf-8')
        self.settings['checks'][0]['timeout_seconds'] = 0.1
        self.write_config()
        self.run_phase('before', 2)
        report = json.loads((self.session/'before.json').read_text(encoding='utf-8'))
        self.assertEqual(report['results'][0]['status'], 'timeout')

    def test_timed_out_baseline_keeps_completed_after_incomplete(self):
        for after_code in (0, 7):
            with self.subTest(after_code=after_code):
                self.session = self.root / ('record-' + str(after_code))
                self.program.write_text('import time\ntime.sleep(30)\n', encoding='utf-8')
                self.settings['checks'][0]['timeout_seconds'] = 1
                self.write_config()
                self.run_phase('before', 2)
                self.program.write_text('raise SystemExit(' + str(after_code) + ')\n', encoding='utf-8')
                self.run_phase('after', 2)
                self.assertEqual(self.comparison(), 'baseline_incomplete')
                report = json.loads((self.session / 'after.json').read_text(encoding='utf-8'))
                self.assertEqual(report['results'][0]['exit_code'], after_code)

    def test_after_timeout_keeps_comparison_incomplete(self):
        self.settings['checks'][0]['timeout_seconds'] = 1
        self.write_config()
        self.run_phase('before', 0)
        self.program.write_text('import time\ntime.sleep(30)\n', encoding='utf-8')
        self.run_phase('after', 2)
        self.assertEqual(self.comparison(), 'incomplete')

    def test_shell_string_is_rejected(self):
        self.settings['checks'][0]['argv'] = 'echo unsafe'
        self.write_config()
        self.run_phase('before', 3)
        self.assertFalse(self.session.exists())

    def test_large_output_is_flagged(self):
        self.program.write_text('print("x" * 20000)\n', encoding='utf-8')
        self.run_phase('before', 0)
        report = json.loads((self.session/'before.json').read_text(encoding='utf-8'))
        self.assertTrue(report['results'][0]['stdout_truncated'])
        self.assertLessEqual(len(report['results'][0]['stdout']), 16384 + 64)


    def test_long_output_keeps_head_and_tail(self):
        self.program.write_text('print("FIRST-LINE")\nprint("x" * 50000)\nprint("FINAL-SUMMARY")\n', encoding='utf-8')
        self.run_phase('before', 0)
        result = json.loads((self.session / 'before.json').read_text(encoding='utf-8'))['results'][0]
        self.assertIn('FIRST-LINE', result['stdout'])
        self.assertIn('FINAL-SUMMARY', result['stdout'])
        self.assertIn('bytes omitted', result['stdout'])
        self.assertGreater(result['stdout_bytes'], 50000)

    def test_timeout_may_be_raised_explicitly_but_stays_bounded(self):
        self.settings['checks'][0]['timeout_seconds'] = 1800
        self.write_config()
        self.run_phase('before', 0)
        self.session = self.root / 'record-too-long'
        self.settings['checks'][0]['timeout_seconds'] = 3601
        self.write_config()
        self.run_phase('before', 3)
        self.assertFalse(self.session.exists())

    def test_timeout_kills_processes_started_by_the_check(self):
        marker = self.root / 'child-survived'
        child = 'import time, pathlib; time.sleep(3); pathlib.Path(%r).write_text("alive")' % str(marker)
        self.program.write_text('import subprocess, sys, time\n'
                                'subprocess.Popen([sys.executable, "-c", %r])\n'
                                'time.sleep(30)\n' % child, encoding='utf-8')
        self.settings['checks'][0]['timeout_seconds'] = 1
        self.write_config()
        self.run_phase('before', 2)
        time.sleep(4)
        self.assertFalse(marker.exists(), 'a child process outlived the timeout')

    @unittest.skipUnless(os.name == 'nt', 'Windows batch shims only')
    def test_windows_cmd_shim_runs_by_bare_name(self):
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'rse-shim-tool.cmd').write_text('@echo shim-ok %1\r\n', encoding='utf-8')
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get('PATH', ''))
        self.settings['checks'][0]['argv'] = ['rse-shim-tool', 'arg']
        self.write_config()
        self.run_phase('before', 0, env=env)
        result = json.loads((self.session / 'before.json').read_text(encoding='utf-8'))['results'][0]
        self.assertIn('shim-ok arg', result['stdout'])

    @unittest.skipUnless(os.name == 'nt', 'Windows batch shims only')
    def test_windows_cmd_shim_rejects_cmd_metacharacters(self):
        bin_dir = self.root / 'bin'
        bin_dir.mkdir()
        (bin_dir / 'rse-shim-tool.cmd').write_text('@echo %1\r\n', encoding='utf-8')
        env = dict(os.environ, PATH=str(bin_dir) + os.pathsep + os.environ.get('PATH', ''))
        self.settings['checks'][0]['argv'] = ['rse-shim-tool', 'safe&echo injected']
        self.write_config()
        self.run_phase('before', 3, env=env)
        self.assertFalse(self.session.exists())


if __name__ == '__main__':
    unittest.main()
