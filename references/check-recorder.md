# Recording checks before and after a change

Read this for substantial refactoring or when repeatable project-check comparisons help. The tool is optional; a text/spacing edit or small review does not automatically need it.

## What the recorder does

[check_baseline.py](../scripts/check_baseline.py) records commands you select from trusted project tools. It stores scope, commands, available executable hashes, results, output, and duration. It rejects overwriting snapshots and comparisons with changed scope, commands, or executable identities.

It is not a complexity/security analyzer and does not auto-run checks merely because it detects a language. Choose a real project analyzer for structural measurements and meaningful tests for behavior. Report a missing analyzer; passing tests are not a structural metric.

## Usage

Requires Python 3.9+ with no additional packages. Invoke it with the interpreter that exists on the machine: `python3` on most Linux/macOS hosts, `py -3` or `python` on Windows (the bare `python` there may be a Microsoft Store stub). Configure actual project checks; adapt this illustrative example before use:

```json
{
  "checks": [
    {
      "name": "pricing-regressions",
      "kind": "behavior",
      "argv": ["python", "-m", "unittest", "tests.test_pricing"],
      "timeout_seconds": 30
    }
  ]
}
```

Allowed kinds: `behavior`, `structure`, `other`. The author assigns the label; it does not verify the check's content. Supply the correct interpreter path if `python` is unavailable. Another check may invoke an installed project analyzer for complexity or dependency-cycle measurements.

`timeout_seconds` defaults to 30 and may be raised per check up to 3600 for a genuinely long suite; set it from the suite's observed duration plus margin. A timeout is always recorded as incomplete evidence, never as success. On timeout the recorder terminates the whole process tree the check started (Windows `taskkill /T`, POSIX process group).

```text
<python> <skill>/scripts/check_baseline.py --scope <project> --config <checks.json> --session <record-directory> --phase before
<python> <skill>/scripts/check_baseline.py --scope <project> --config <checks.json> --session <record-directory> --phase after
```

Angle-bracket paths are placeholders. Commands run inside `scope` without a shell. A bare command name is resolved like a terminal would (`PATHEXT` on Windows, so `npm` finds `npm.cmd`). Windows always runs `.bat`/`.cmd` files through `cmd.exe`, so the recorder refuses their arguments when they contain cmd metacharacters (`% ^ & | < > " !`). Quote paths containing spaces for the calling terminal. Store recording files outside project inputs when they would contaminate checks/builds.

## Reading results

- `before.json` and `after.json`: one snapshot per phase; use a new session for another comparison.
- `comparison.json`: new failure, new success, continuing failure, passing in both, or incomplete evidence in either phase.
- A continuing command failure need not have the same cause. Inspect output; do not implicitly repair unrelated preexisting problems.
- Exit `0`: current commands passed and any requested comparison is complete. Exit `1`: a current command failed with complete checks. Exit `2`: timeout/unavailable check in the current phase or compared baseline. Exit `3`: invalid configuration/comparison. Incomplete evidence takes precedence over a later failure, whose details remain recorded. A complete failed baseline followed by complete success returns `0` with `now_passing`.
- Each stored output stream keeps its first and last 8 KiB, with an omitted-bytes marker between them and the full size in `stdout_bytes`/`stderr_bytes`; failure summaries usually sit at the end. If omitted detail matters, consult original tool logs while protecting sensitive data.

Raw CLI messages and JSON keys stay in English. Explain outcomes, failures, and incomplete evidence to the user in plain terms.

## Authorization and evidence limits

Inspect configuration before execution; do not run untrusted commands. Avoiding a shell does not prevent an authorized command from modifying files or using the network. The recorder grants no authorization for deployment, production tests, or dependency installation. Protect environmental secrets and sensitive output.

Check relevant versions, plugins, configuration, and environment manually. An executable hash does not capture every dependency change. Test duration is not a performance benchmark without comparable workload/conditions. Timeouts terminate the direct process; commands starting background processes/services need an appropriate lifecycle tool and should not be selected automatically.

Recorder tests are separate from testing the skill's effect on an agent. This evidence does not benchmark token savings or engineering judgment.

Run the recorder's own tests with `<python> -B -m unittest discover -s <skill>/tests -v`, where `<python>` is the available interpreter. They use temporary fixtures for success/failure, regression, incomplete evidence, and incompatible settings without running your project/services.
