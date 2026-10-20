# Integrate operation errors without regressing current main

## Sources and scheduling

- Owning issue: https://github.com/bizyumov/yandex-search-skill/issues/3
- Existing pull request: https://github.com/bizyumov/yandex-search-skill/pull/4
- Original PR head: `3bbd18d946db154e9f4de2276d0a3ec280be2a8a`.
- Preserved main baseline: `105e96b79746fccaeb51f1a98af794583c35a9af`.
- Integration constraint and scheduling: https://github.com/bizyumov/yandex-search-skill/issues/3#issuecomment-6291341412
- Scheduling state: implementation authorized and in progress; no calendar deadline assigned.

The original `spec.md`, `evidence.json`, `evidence.md`, and raw test artifacts in
this task directory describe the historical implementation. They are preserved,
not rewritten or presented as verification of this integration.

## Selected behavior

Port the useful operation-error behavior from PR #4 onto the current main code:

- Report exhausted polling HTTP errors and operations that never complete.
- Report completed-operation errors and missing response payloads.
- Reject malformed operation JSON and base64/UTF-8/search XML as errors, not empty
  or partial successful searches.
- Reuse main's `SearchError` and safe CLI handling; do not introduce a second
  public exception contract from the unmerged old branch.
- Retain main's submission HTTP 429 synchronous fallback, request parameters,
  requested page ordering, result formatting, and successful empty responses.
- Retain the existing polling budget and retry timing. Polling HTTP 429 is not
  grounds for another synchronous search.

The existing fallback decoder was extracted verbatim into
`_decode_search_response()` so completed operations can use the same validation.
No result parser, authentication, endpoint, ranking, or CLI flag changes are made.

## Verification performed before publication

- `python -m unittest discover -s scripts -p test_operations.py -v` before the
  implementation: exit 1, reproducing swallowed errors, raw lookup/decoding
  exceptions, and successful partial output on failed polling.
- Same command after implementation: 12 tests passed.
- `python scripts/test_search.py`: 10 existing tests and 26 HTTP integration
  tests passed, exit 0. The 26 integration tests comprise the unchanged 14
  fallback tests and 12 new operation tests.
- `git diff --check`: passed.
- AST comparison against the main baseline: submission/request-building and 429
  recovery loop unchanged; fallback HTTP/error handling unchanged; the decoder
  body is an exact extraction of existing fallback validation.
- AST comparison: existing `SearchError`, endpoint loading, parsing/formatting,
  public `search()` / `search_async()`, and CLI `main()` definitions unchanged.
- `scripts/test_fallback.py` is byte-identical to the main baseline.
- In-memory mutation checks: removing the incomplete-operation failure and
  ignoring completed-operation errors were both detected by regression tests.

The full existing CI entry point now discovers `test_*.py`, keeping both HTTP
suites active without replacing or weakening main's fallback regressions.
