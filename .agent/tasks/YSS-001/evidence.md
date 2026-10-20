# Verification evidence

## Verdict

PASS

## Acceptance criteria

| Criterion | Result | Evidence |
|---|---|---|
| AC1: submit HTTP failures raise a sanitized exception | PASS | `test_submit_http_error_is_raised_and_sanitized` |
| AC2: polling HTTP failures raise after retry exhaustion | PASS | `test_poll_http_error_is_raised_after_retries` |
| AC3: completed operation errors raise a sanitized exception | PASS | `test_completed_operation_error_is_raised_and_sanitized` |
| AC4: operations that never complete raise a timeout-style exception | PASS | `test_pending_operation_times_out` |
| AC5: CLI writes the error to stderr and exits non-zero | PASS | `test_cli_api_error_exits_nonzero_without_empty_result_message` |
| AC6: genuine empty results remain successful | PASS | `test_successful_empty_result_remains_successful` |
| AC7: regression test fails before the fix and passes after it | PASS | `raw/red-test.txt` and `raw/green-test.txt` |
| AC8: existing tests remain green | PASS | 16 passed, 0 failed in `raw/green-test.txt` |
| AC9: artifacts contain no personal data or credentials | PASS | Synthetic local test data only; staged secret scan required before commit |

## Commands

- `python -m py_compile scripts/search.py scripts/test_search.py`
- `python scripts/test_search.py`
- Sabotage run: restore the pre-fix `scripts/search.py`, run the complete suite, restore the fix, and rerun the complete suite.

## Results

- Pre-fix sabotage run: exit status 1; 11 passed, 5 failed.
- Post-fix run: exit status 0; 16 passed, 0 failed.
- Python compilation: exit status 0.
- `git diff --check`: exit status 0.

## Raw evidence

- `raw/red-test.txt`
- `raw/green-test.txt`
- `raw/search-fix.patch`
