# Test conventions for this project's `tests/`

This file applies when Claude is working in `chargeback-prediction-model/tests/`.

## What gets tested

- Public-facing functions and behaviors.
- The reason-code harmonization mapping (critical — get this wrong and all
  predictions are noise).
- The point-in-time join logic (critical — getting this wrong breaks the
  model's causal logic).
- Edge cases surfaced during /clarify.
- Anything in FAILURES.md that has a corresponding fix in code.

## What doesn't need a test

- Glue code (one-line wrappers, trivial mappings).
- Configuration constants.
- Pure type definitions.

## Structure

- Mirror the source tree: `src/foo/bar.py` → `tests/foo/test_bar.py`.
- One file per source module unless tests are huge.
- Group related tests by behavior, not by function name.
- Fixtures (sample data, synthetic chargebacks) live in `tests/fixtures/`.

## Test names

- Describe what the test verifies, in plain English.
- Pattern: `test_<behavior>_when_<condition>`
- Bad: `test_function_1`, `test_parse`
- Good: `test_harmonize_returns_data_error_for_walmart_code_22`,
        `test_point_in_time_join_uses_historical_not_current_state`

## Setup and teardown

- Prefer fresh state per test over shared mutable state.
- Use synthetic (Cinderhaven-style) data — never real brand data in tests.

## Assertions

- One concept per test. If a test asserts five unrelated things, split it.
- Assertions should print useful failure messages.

## Mocks and fakes

- Mock at the boundary (filesystem, database connections), not internal
  pure functions.
- The harmonization mapping and point-in-time join should be testable
  without mocking — they're pure logic.

## Running

- Tests must be runnable with a single command. Document it in README.md.
- A failing test is more useful than an unrun test.

## When a test fails

- Read the actual output, not what you expected to see.
- Bisect: which change broke it?
- Don't suppress with `skip` or `xfail` without a PLAN item to come back.
