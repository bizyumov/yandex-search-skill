# Fix Yandex Search API error propagation

## Summary

The CLI currently logs HTTP failures from the Yandex Cloud Search API, skips the failed request, returns an empty result list, prints `No results`, and exits with status 0. This makes an authorization or service failure indistinguishable from a successful search with no matches.

## Current behavior

When `POST /v2/web/searchAsync` returns a non-200 response, `_search_api` logs the response and continues. If every page fails, the function returns an empty list. The CLI then formats that list as a successful empty search result and exits with status 0.

Polling failures from `GET /operations/{id}` are also retried without preserving the final failure. A completed operation error is not handled explicitly.

## Expected behavior

API failures must propagate to the caller as sanitized exceptions. The CLI must print a concise error to stderr and exit with a non-zero status. A genuine successful search with no matches must remain a successful empty result.

## Scope

1. Introduce a dedicated exception type for Yandex Search API failures.
2. Raise it for non-200 `searchAsync` responses.
3. Raise it when operation polling exhausts its attempts after HTTP failures or never completes.
4. Raise it when a completed operation contains an API error or lacks the expected response payload.
5. Keep secrets out of exception messages and logs.
6. Make the CLI return a non-zero exit status for these failures.
7. Add regression tests for the API and CLI behavior.
8. Update troubleshooting documentation to distinguish API failure from an empty result.

## Non-goals

- Changing authentication configuration, IAM roles, quotas, endpoints, or retry timing beyond what is required for correct failure reporting.
- Adding another search provider or fallback engine.
- Printing API keys, authorization headers, full request payloads, or environment values.
- Changing result parsing or ranking behavior.

## Acceptance criteria

- **AC1:** A non-200 response from `POST /v2/web/searchAsync` raises a sanitized API exception instead of returning an empty result list.
- **AC2:** A non-200 operation response after retry exhaustion raises a sanitized API exception.
- **AC3:** An operation that completes with an `error` object raises a sanitized API exception.
- **AC4:** An operation that never completes within the configured polling attempts raises a sanitized timeout-style API exception.
- **AC5:** The CLI writes the API failure to stderr and exits with a non-zero status.
- **AC6:** A successful API response containing zero search results still exits with status 0 and prints the normal empty-result output.
- **AC7:** Regression tests fail against the previous behavior and pass after the fix.
- **AC8:** Existing tests remain green.
- **AC9:** Issue, commits, pull request, tests, and documentation are written in English and contain no personal data or credentials.

## Test plan

- Unit-test `_search_api` with a local in-process HTTP test server that returns controlled responses; no external credentials or personal data are used.
- Cover search submission failure, operation polling failure, completed-operation error, polling timeout, and successful empty results.
- Run the complete existing test module.
- Perform a red-green sabotage check by restoring the old failure-swallowing behavior temporarily and confirming the new regression test fails.
- Run a secret scan on the staged diff before commit.

## Risk

Low. The change affects only error paths. The main compatibility change is intentional: callers that previously received `[]` after an API failure will now receive an exception and the CLI will exit non-zero.
