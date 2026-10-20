# Fall back to synchronous search when searchAsync returns HTTP 429

Accepted specification: https://github.com/bizyumov/yandex-search-skill/issues/5

Scheduling: implementation authorized by the operator; no calendar deadline assigned.
The implementation is proposed through a pull request; this file preserves the
approved issue text rather than describing the current client as unmodified.

## Problem

The client always submits searches to `POST /v2/web/searchAsync`. The service can reject an asynchronous search with HTTP 429 while the synchronous endpoint, `POST /v2/web/search`, still accepts the same search.

This was observed with the same credentials and query: asynchronous submission returned HTTP 429 with `search rate limit exceeded, retry later`; a subsequent synchronous request returned HTTP 200 and search results. This does not establish that every HTTP 429 has the same cause.

At revision `77a72c5e55a4a053c542452136ee3cd210ba17fa`, `_search_api()` logs unsuccessful submissions and continues. A failed search can consequently be presented as a successful empty result.

## Reproduction

1. Configure valid `YANDEX_SEARCH_API_KEY` and `YANDEX_CLOUD_FOLDER_ID` credentials.
2. Run the existing CLI while the asynchronous endpoint rejects submission with HTTP 429:

```bash
python3 scripts/search.py "example query" --count 3 --format json
```

3. Observe the current submission branch in `scripts/search.py`:

```python
async with session.post(f"{search_api_base}/v2/web/searchAsync", json=body) as resp:
    if resp.status != 200:
        error = await resp.text()
        logger.error("Request error: %s - %s", resp.status, error)
        continue
```

4. For deterministic reproduction, use a local HTTP fixture that returns HTTP 429 from `/v2/web/searchAsync` and a valid successful search response from `/v2/web/search`.

## Expected behavior

- Keep asynchronous submission as the primary path.
- If `POST /v2/web/searchAsync` returns HTTP 429, attempt `POST /v2/web/search` once for that page with the same search parameters and configured credentials.
- If synchronous fallback succeeds, decode and parse its response through the existing result pipeline and return the search results normally. A valid successful response with no matches remains a successful empty result.
- If fallback also fails, report both attempts and the actual failure of each. Do not replace failure with an empty result or claim both endpoints returned HTTP 429 when the synchronous endpoint returned a different error.
- Return an error to Python callers and a non-zero CLI exit code with a concise stderr message.

Example diagnostic when both endpoints return HTTP 429:

```text
Yandex Search failed: asynchronous submission returned HTTP 429; synchronous fallback also returned HTTP 429.
```

If synchronous fallback fails differently, replace its failure description with the actual HTTP status or sanitized transport/response error. The CLI error must describe the outcomes of both attempts, without status/billing links or an unverified diagnosis.

## Troubleshooting documentation

Put troubleshooting guidance in `SKILL.md` or the accompanying API documentation, not in the CLI error:

- Service status: https://center.yandex.cloud/statusboard
- Billing and balance: https://center.yandex.cloud/billing/

Explain that repeated failures may warrant checking for a service incident or account/balance problems. These are possible troubleshooting paths, not a diagnosis inferred from HTTP 429.

## Proposed implementation

Handle HTTP 429 at asynchronous submission, before entering the failed-request branch. Submit the same page to `/v2/web/search`, decode its direct `rawData` payload, and reuse XML parsing and result formatting. The synchronous fallback does not create an operation or poll `/operations/{id}`. Preserve requested page order in mixed asynchronous/fallback responses.

No new CLI flag is required. Both existing Python entry points, `search()` and `search_async()`, should receive the behavior through the shared request layer.

## Acceptance criteria

- [ ] Async HTTP 429 followed by sync HTTP 200 returns the parsed synchronous results; the CLI exits 0.
- [ ] Fallback preserves query, page, search type, family mode, sorting, grouping, region, localization, response format and credentials.
- [ ] Successful asynchronous search still polls and returns results without invoking fallback.
- [ ] Fallback is triggered by asynchronous submission HTTP 429, not by unrelated HTTP statuses.
- [ ] Async HTTP 429 followed by sync HTTP 429 produces the explicit two-attempt CLI diagnostic without troubleshooting links.
- [ ] Async HTTP 429 followed by another synchronous error reports the actual second failure while retaining the original HTTP 429 context.
- [ ] Failed or malformed fallback responses propagate as errors, never as successful empty results; no credentials or raw error bodies are exposed.
- [ ] A valid empty synchronous response remains successful.
- [ ] Each affected page receives at most one synchronous fallback attempt, and multi-page results retain their requested order.
- [ ] Deterministic regression tests cover these branches without live credentials; existing tests remain green.
- [ ] `SKILL.md` or accompanying documentation explains the fallback and includes both exact status/billing links; the CLI error describes both attempt outcomes only.

## Environment and scope

- Yandex Cloud Search API v2; Python client using `aiohttp`.
- Preserve configured HTTPS endpoints, credential handling, result schema and ranking.
- Do not hard-code an operating-hours restriction or assume that HTTP 429 proves an outage or insufficient balance.
- Do not add another provider, indefinite retries, scheduled waiting, or automatic billing changes.

## Relationship to existing work

Related to #3, "Propagate API failures instead of reporting empty results". This request refines its submission-error contract for HTTP 429: attempt recovery first; propagate an error if recovery fails. Other error-propagation requirements from #3 remain applicable. This is a fallback within the same Yandex service, not a different search provider.
