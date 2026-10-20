# Verification problems

## Problem 1: trailing whitespace in raw evidence

- Status: fixed
- Detected by: `git diff --cached --check`
- Affected files: `raw/red-test.txt` and `raw/search-fix.patch`
- Cause: captured test output contained empty failure suffixes, and the unified diff used space-prefixed blank context lines.
- Fix: remove trailing spaces from the stored evidence without changing production code or test behavior.
