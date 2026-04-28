# General Scoring Principles

Shared by spotcat-sprint-dev and spotcat-quant-dev.

## Rules

- Scores are objective and evidence-based
- Every deduction must cite specific file:line
- Pass thresholds are non-negotiable
- Safety issues override all scores (total = 0)
- Reviewers must provide specific, actionable feedback on FAIL

## Evidence Requirements

- Score justifications must reference concrete code, not vague impressions
- "Poor quality" is not valid — "Function `calculate_signal()` at line 42 uses bare `except` without logging the error" is valid
- Each dimension score must have at least one sentence of justification
