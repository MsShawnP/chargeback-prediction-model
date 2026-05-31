# Code conventions for this project's `src/`

This file applies when Claude is working in `chargeback-prediction-model/src/`.

## Style

- Match the existing code style. If there's a linter config, follow it strictly.
- New files mirror the structure of nearby existing files.
- No mixing of paradigms inside a module without a reason worth stating in DECISIONS.md.

## Naming

- Functions: verbs (`parse_reason_codes`, `compute_chargeback_risk`)
- Variables: nouns (`shipment_features`, `risk_score`)
- Booleans: predicates (`is_valid_gtin`, `has_case_dimensions`)
- Avoid abbreviations unless they're standard in this codebase.

## Imports

- Sort imports: standard library first, then external packages, then internal.
- No unused imports left in code.

## Comments

- Comment why, not what. The code already says what.
- TODO comments include a date or issue reference.

## Tests

- Each new non-trivial function gets at least one test in `tests/`.
- Test names describe behavior in plain English.
- Avoid testing implementation details — test inputs and outputs.

## Error handling

- Don't swallow errors. If you catch one, log or rethrow with context.
- No bare `except:` blocks without a comment explaining why.

## Critical domain rules

- Never join chargebacks to current product master state. Always use
  point-in-time data quality state at shipment time. See DECISIONS.md.
- The reason-code harmonization layer is the model's differentiator —
  changes to the mapping require explicit review and a DECISIONS.md entry.
- Every model output must carry a plain-language attribution string,
  not just a probability score.

## Don't invent

- Before adding a new utility, check if a similar one already exists.
- Before adding a dependency, explain what it does, why it's needed,
  and log to DECISIONS.md.
- Before refactoring an existing pattern, surface it as a question.
