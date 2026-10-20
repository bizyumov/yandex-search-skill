## Summary

- propagate Yandex Search submission and polling failures through a dedicated sanitized exception
- return a non-zero CLI exit status instead of reporting API failures as empty results
- distinguish completed-operation errors, polling exhaustion, and genuine empty search results
- document the failure contract and add local regression coverage

## Test plan

- `python -m py_compile scripts/search.py scripts/test_search.py`
- `python scripts/test_search.py` (16 passed, 0 failed)
- sabotage run against the pre-fix implementation (11 passed, 5 failed)
- `git diff --cached --check`
- `gitleaks protect --staged --redact --no-banner`

## Privacy and security

- tests use a local HTTP server with synthetic credentials and payloads
- exception messages omit response bodies, authorization headers, resource identifiers, and operation error payloads
- no personal data or credentials are included

Closes #3
