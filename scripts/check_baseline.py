#!/usr/bin/env python3
"""Record trusted project checks before/after a change; does not analyze code itself."""
import argparse
import hashlib
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from datetime import datetime, timezone

if sys.version_info < (3, 9):
    sys.exit('Recorder error: Python 3.9 or newer is required')

SCHEMA = 1
DEFAULT_TIMEOUT = 30
MAX_TIMEOUT = 3600
HEAD_BYTES = 8192
TAIL_BYTES = 8192
WINDOWS = os.name == 'nt'
# cmd.exe interprets these even when Python passes an argument list to a .bat/.cmd file.
BATCH_METACHARACTERS = set('%^&|<>"!\r\n')


def read_config(path):
    config = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(config, dict) or set(config) != {'checks'}:
        raise ValueError('Config must contain only a checks array')
    checks = config['checks']
    if not isinstance(checks, list) or not checks:
        raise ValueError('At least one real project check is required')
    names = set()
    for check in checks:
        if not isinstance(check, dict) or set(check) - {'name', 'kind', 'argv', 'timeout_seconds'}:
            raise ValueError('Unknown check fields')
        name = check.get('name')
        if not isinstance(name, str) or not name.strip() or name in names:
            raise ValueError('Each check needs a unique nonempty name')
        names.add(name)
        if check.get('kind') not in ('behavior', 'structure', 'other'):
            raise ValueError('kind must be behavior, structure, or other')
        argv = check.get('argv')
        if not isinstance(argv, list) or not argv or not all(isinstance(a, str) and '\0' not in a for a in argv) or not argv[0]:
            raise ValueError('argv must be a nonempty argument array, not a shell string')
        timeout = check.get('timeout_seconds', DEFAULT_TIMEOUT)
        if type(timeout) not in (int, float) or not 0 < timeout <= MAX_TIMEOUT:
            raise ValueError('timeout_seconds must be positive and at most ' + str(MAX_TIMEOUT))
    return config


def resolve(command, scope):
    """Return the executable path that will actually run, or None if it cannot be found."""
    path = Path(command)
    if path.is_absolute() or '/' in command or '\\' in command:
        candidate = path if path.is_absolute() else scope / path
        return candidate if candidate.is_file() else None
    # shutil.which honours PATHEXT on Windows, so `npm` resolves to npm.cmd as a terminal would.
    located = shutil.which(command)
    return Path(located) if located else None


def identity(argv, scope):
    candidate = resolve(argv[0], scope)
    result = {'executable': str(candidate.resolve()) if candidate else None, 'sha256': None}
    if candidate:
        try:
            digest = hashlib.sha256()
            with candidate.open('rb') as stream:
                for block in iter(lambda: stream.read(1 << 20), b''):
                    digest.update(block)
            result['sha256'] = digest.hexdigest()
        except OSError:
            pass
    return result


def batch_file(path):
    return WINDOWS and path is not None and path.suffix.lower() in ('.bat', '.cmd')


def check_batch_arguments(check, scope):
    """Batch files always run through cmd.exe; refuse arguments it would reinterpret."""
    executable = resolve(check['argv'][0], scope)
    if batch_file(executable) and any(BATCH_METACHARACTERS & set(arg) for arg in check['argv'][1:]):
        raise ValueError(check['name'] + ': arguments to a .bat/.cmd file must not contain cmd.exe metacharacters')


def capture(stream):
    size = stream.tell()
    stream.seek(0)
    if size <= HEAD_BYTES + TAIL_BYTES:
        text = stream.read().decode('utf-8', errors='replace')
    else:
        # Keep both ends: tool banners are at the start, failure summaries at the end.
        head = stream.read(HEAD_BYTES)
        stream.seek(size - TAIL_BYTES)
        tail = stream.read()
        omitted = size - HEAD_BYTES - TAIL_BYTES
        text = (head.decode('utf-8', errors='replace') + '\n[... ' + str(omitted) + ' bytes omitted ...]\n'
                + tail.decode('utf-8', errors='replace'))
    return text, size, size > HEAD_BYTES + TAIL_BYTES


def kill_tree(proc):
    """Terminate the check and every process it started, then reap it."""
    if WINDOWS:
        subprocess.run(['taskkill', '/T', '/F', '/PID', str(proc.pid)],
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, check=False)
    else:
        try:
            os.killpg(proc.pid, signal.SIGKILL)
        except (ProcessLookupError, PermissionError):
            pass
    try:
        proc.wait(timeout=10)
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()


def run_check(check, scope):
    start = time.monotonic()
    result = {'name': check['name'], 'kind': check['kind'], 'argv': check['argv']}
    executable = resolve(check['argv'][0], scope)
    argv = [str(executable)] + check['argv'][1:] if executable else check['argv']
    # Temporary files avoid keeping unbounded command output in RAM.
    with tempfile.TemporaryFile() as stdout, tempfile.TemporaryFile() as stderr:
        try:
            extra = {'creationflags': subprocess.CREATE_NEW_PROCESS_GROUP} if WINDOWS else {'start_new_session': True}
            proc = subprocess.Popen(argv, cwd=scope, stdin=subprocess.DEVNULL,
                                    stdout=stdout, stderr=stderr, shell=False, **extra)
        except OSError as exc:
            result.update(status='unavailable', exit_code=None, reason=str(exc))
        else:
            try:
                code = proc.wait(timeout=check.get('timeout_seconds', DEFAULT_TIMEOUT))
                result.update(status='passed' if code == 0 else 'failed', exit_code=code)
            except subprocess.TimeoutExpired:
                kill_tree(proc)
                result.update(status='timeout', exit_code=None)
        for name, stream in (('stdout', stdout), ('stderr', stderr)):
            text, size, truncated = capture(stream)
            result[name] = text
            result[name + '_bytes'] = size
            result[name + '_truncated'] = truncated
    result['seconds'] = round(time.monotonic() - start, 4)
    return result


def compare(before, after):
    rows = []
    for old, new in zip(before['results'], after['results']):
        if new['status'] in ('timeout', 'unavailable'):
            state = 'incomplete'
        elif old['status'] in ('timeout', 'unavailable'):
            state = 'baseline_incomplete'
        elif old['status'] == 'passed' and new['status'] != 'passed':
            state = 'new_failure'
        elif old['status'] != 'passed' and new['status'] == 'passed':
            state = 'now_passing'
        elif new['status'] != 'passed':
            state = 'still_failing'
        else:
            state = 'passing_in_both'
        rows.append({'name': new['name'], 'before': old['status'], 'after': new['status'], 'comparison': state})
    return {'schema': SCHEMA, 'checks': rows,
            'note': 'The same failing command may contain different failures; inspect its output. Passing checks do not prove unchanged behavior or architectural quality.'}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--scope', required=True, type=Path)
    parser.add_argument('--config', required=True, type=Path)
    parser.add_argument('--session', required=True, type=Path)
    parser.add_argument('--phase', required=True, choices=('before', 'after'))
    args = parser.parse_args(argv)
    scope = args.scope.resolve(strict=True)
    if not scope.is_dir():
        raise ValueError('scope must be a directory')
    config = read_config(args.config)
    for check in config['checks']:
        check_batch_arguments(check, scope)
    session = args.session.resolve()
    baseline = session / 'before.json'
    output = session / (args.phase + '.json')
    comparison = session / 'comparison.json'
    if output.exists() or (args.phase == 'after' and comparison.exists()):
        raise ValueError('Snapshot already exists; use a new session for a new comparison')
    tools = [identity(c['argv'], scope) for c in config['checks']]
    before = None
    if args.phase == 'after':
        before = json.loads(baseline.read_text(encoding='utf-8'))
        if not isinstance(before, dict) or before.get('schema') != SCHEMA or before.get('scope') != str(scope) or before.get('config') != config or before.get('tools') != tools:
            raise ValueError('Incompatible baseline: scope, checks, or executable identity changed')
        old = before.get('results')
        if not isinstance(old, list) or len(old) != len(config['checks']):
            raise ValueError('Invalid baseline results')
        for check, result in zip(config['checks'], old):
            if not isinstance(result, dict) or result.get('name') != check['name'] or result.get('status') not in ('passed', 'failed', 'timeout', 'unavailable'):
                raise ValueError('Invalid baseline check result')
    report = {'schema': SCHEMA, 'phase': args.phase, 'scope': str(scope), 'config': config,
              'tools': tools, 'python': sys.version, 'created_at': datetime.now(timezone.utc).isoformat(),
              'results': [run_check(c, scope) for c in config['checks']]}
    session.mkdir(parents=True, exist_ok=True)
    with output.open('x', encoding='utf-8', newline='\n') as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2)
    if before:
        with comparison.open('x', encoding='utf-8', newline='\n') as stream:
            json.dump(compare(before, report), stream, ensure_ascii=False, indent=2)
    print(output)
    statuses = [r['status'] for r in report['results']]
    baseline_incomplete = before is not None and any(
        r['status'] in ('timeout', 'unavailable') for r in before['results'])
    if baseline_incomplete or any(s in ('timeout', 'unavailable') for s in statuses):
        return 2
    return 1 if 'failed' in statuses else 0


if __name__ == '__main__':
    try:
        sys.exit(main())
    except (ValueError, OSError) as exc:
        print('Recorder error: ' + str(exc), file=sys.stderr)
        sys.exit(3)
