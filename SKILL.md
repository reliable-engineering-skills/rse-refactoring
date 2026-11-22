---
name: rse-refactoring
description: "Restructure existing code safely: extract or move responsibilities, untangle modules, rescue a messy or AI-generated codebase, plan a rewrite versus incremental repair, and record before/after check results. Use when the user asks to refactor, clean up, split, reorganize, modernize or rescue code while preserving behavior. Includes a before/after check recorder. Builds on the reliable-software-engineering skill."
metadata:
  version: "3.0.0"
---

# Refactoring and system rescue

> Companion of the `reliable-software-engineering` skill, which must be installed alongside. Its core rules apply here; links into `../reliable-software-engineering/` point at its references.

Use for structural changes to an existing system. For a review, stop at findings and recommendations; for a plan, stop at the plan. A combined bug-fix/refactor request may implement both, with distinct acceptance evidence. Do not introduce an extra approval gate when the user already authorized the behavior change.

## Evidence before structural work

Read the affected code, callers, runtime references, and focused tests. Record the behavior that must remain: returned/serialized values, failures, externally visible effects, contracts, and ordering requirements. Consult history only to resolve a concrete design question.

For a substantial or risky change, capture the current revision, dirty worktree state, check commands, existing failures, scope, and settings in the project's existing task record. A separate record is useful if none exists; no fixed directory layout is required. Use [the check recorder](references/check-recorder.md) when consistent command snapshots help.

Describe structural findings with a location, current owner, concrete maintenance/correctness consequence, and proposed owner. File size is a prompt for inspection, not proof of a defect. Prioritize demonstrated security, data-loss, financial, and operational failures over cosmetic cleanup.

Map responsibilities and dependency direction for the affected scope. Keep framework paths and public interfaces. Select only boundaries that own real work; do not retrofit every application into identical folders. A function or module can be an adequate boundary.

## Incremental change

- Fix one ownership problem at a time. When extracting, a temporary forwarding path may preserve compatibility while callers migrate; remove it when unused. Keep required compatibility aliases for external consumers.
- Derive a dependency contract from actual caller needs. Add an interface, injected function, or protocol only when it provides a real boundary or useful test seam.
- Use language-aware rename/move tools when available, then inspect reflection, routes, plugin registration, configuration strings, and other runtime references that a compiler may miss.
- Update coupled callers, fixtures, exports, and setup together. Avoid import cycles and avoid widening public access merely to make a move convenient.
- Run focused behavior checks after meaningful moves. If a move causes a regression, repair that move before layering another transformation on top.
- Remove superseded implementations and temporary adapters inside the authorized scope. Preserve unrelated user edits. Keep verified changes coherent; commits follow user/project authorization and conventions.

## Move-sensitive contracts

Before moving errors, retries, async work, transactions, models, module initialization or configuration, read [move-sensitive contracts](../reliable-software-engineering/references/move-sensitive-contracts.md).

SOLID is a diagnostic lens: look for unrelated reasons to change, unsupported replacement behavior, overly broad contracts, or policy coupled to details. Do not add a strategy for every conditional or an interface for every class. Measure whether the boundary clarifies ownership and protects a real contract.

## Behavior and structure evidence

Compare the same relevant checks, scope, tool versions, configuration, and workload before and after. Use available project analyzers for complexity, dependency cycles, layer rules, or other claimed properties. Record unsupported languages or missing tools as incomplete; no generic script proves SOLID or unchanged behavior.

A reduction in lines, function size, or complexity is useful only if the acceptance behavior remains and responsibility improves. Do not split functions solely to improve a metric. If a wider suite is required by the project, run it; otherwise expand beyond focused checks for a reason. Report pre-existing unrelated failures separately. A changing environment can invalidate a comparison.

## Rescue, debt, and parallel work

Contain demonstrated dangerous behavior first within authorization. Distinguish urgent defects from debt that can be accepted temporarily. A debt record identifies the actual shortcut, reason, consequence, owner, and revisit trigger; an unspecified future cleanup is not a plan.

Compare local repair, replacing a bounded component, and a rewrite using migration cost, hidden contracts, data history, and coexistence burden. A rewrite is not automatically a refactor.

Experiments may use an isolated branch/worktree or staging environment. Start with synthetic or sanitized data. Where access to a real copy is authorized, separate credentials and storage and neutralize workers, email, notifications, payments, and webhooks that could create live effects. Shadow/replayed requests must not duplicate external operations. Agreement with the old implementation is not enough when the old behavior is defective.


For affected clean-code/formatting questions, read [code quality](../reliable-software-engineering/references/code-quality.md). Use principles to clarify actual ownership/contracts; do not impose universal function-size or parameter-count ceilings.
