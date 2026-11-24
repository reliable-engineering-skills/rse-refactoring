# rse-refactoring

Behavior-preserving refactoring and codebase rescue, one responsibility at a time, with a before/after check recorder.

> Requires [reliable-software-engineering](https://github.com/reliable-engineering-skills/reliable-software-engineering) installed alongside. Links such as `../reliable-software-engineering/references/...` resolve on disk after installation, not on the GitHub web view.

Part of the **RSE skill suite**: five complementary agent skills for Claude Code and Codex. One core skill
holds the shared rules; each companion adds one workflow and points back to the core, so every rule has
exactly one owner.

| Skill | Role | What it does |
| --- | --- | --- |
| [reliable-software-engineering](https://github.com/reliable-engineering-skills/reliable-software-engineering) | Core (required) | Proportionate, evidence-based engineering decisions: scope, smallest sufficient change, contracts, payments and data history, authorization, caching, operations and honest verification. |
| [rse-task-packs](https://github.com/reliable-engineering-skills/rse-task-packs) | Companion | Turns accepted work into portable, resumable task packs for another agent or a later session, with a structural validator. |
| **rse-refactoring** (this repo) | Companion | Behavior-preserving refactoring and codebase rescue, one responsibility at a time, with a before/after check recorder. |
| [rse-security-review](https://github.com/reliable-engineering-skills/rse-security-review) | Companion | Focused security review: trace untrusted input to sensitive sinks and report evidence-graded findings without touching production. |
| [rse-debugging](https://github.com/reliable-engineering-skills/rse-debugging) | Companion | Fixes reported bugs from evidence: reproduces with a failing check, fixes the cause, and leaves a regression test, even when the cause looks obvious. |

## Install the suite

The companions link into the core skill's files, so install all five side by side.

Claude Code (PowerShell):

```powershell
foreach ($r in "reliable-software-engineering", "rse-task-packs", "rse-refactoring", "rse-security-review", "rse-debugging") { git clone "https://github.com/reliable-engineering-skills/$r" "$env:USERPROFILE\.claude\skills\$r" }
```

Claude Code (bash/zsh):

```bash
for r in reliable-software-engineering rse-task-packs rse-refactoring rse-security-review rse-debugging; do git clone "https://github.com/reliable-engineering-skills/$r" ~/.claude/skills/$r; done
```

Codex: clone the same five repositories into `~/.codex/skills/`. Update later with `git pull` in each folder.

## Contents

- `SKILL.md`: evidence before structural work, incremental change, rescue/rewrite trade-offs.
- `references/check-recorder.md` and `scripts/check_baseline.py`: record trusted project checks before and
  after a change and compare them (Python 3.9+, standard library only).

```powershell
py -3 scripts/check_baseline.py --scope <project> --config <checks.json> --session <dir> --phase before
py -3 scripts/check_baseline.py --scope <project> --config <checks.json> --session <dir> --phase after
```

Timeouts and missing tools are recorded as incomplete evidence, never as success.

## License

MIT. Version 3.0.0; see the [core changelog](https://github.com/reliable-engineering-skills/reliable-software-engineering/blob/main/CHANGELOG.md).
