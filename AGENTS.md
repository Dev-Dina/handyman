# AGENTS.md

## Communication budget

Use minimal communication. No narration. No thinking aloud.

## While working

Allowed only if blocked:

BLOCKED: <one short reason>

Otherwise stay silent until final response.

## Final response format

DONE:
- <1-3 bullets>

FILES:
- <changed files only>

COMMANDS:
- <commands run or "not run">

RESULT:
- <pass/fail/partial>

RISKS:
- <real risks or "none">

NEXT:
- <one next action>

## Project rules

Caveman mode = short communication only. Code stays production-grade.

Architecture:
- app/api = HTTP only
- app/services = business logic
- app/repositories = SQL only
- app/domain = domain models/errors
- app/infra = external adapters

Do not touch unrelated files.
Do not redesign the repo.
Do not invent metrics.
Do not print secrets.
Do not run broad refactors unless explicitly asked.
Use Vault for GitHub token (secret/github, key: token).
If Vault token missing, continue unauthenticated with warning.

## State tracking rule

PROJECT_STATE.md is the source of truth.

For every task:
- read PROJECT_STATE.md before editing
- update PROJECT_STATE.md before final response
- only check off items when the relevant command actually passed
- never mark synthetic data as real dataset completion
- if blocked, update Current blockers and Next 3 tasks

Final response must include PROJECT_STATE.md in FILES if it was changed.
