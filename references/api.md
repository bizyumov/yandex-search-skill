# Yandex Cloud Search API Notes

This skill uses **Yandex Cloud Search API v2**, not the legacy Yandex XML search endpoint.

Original documentation:
- https://aistudio.yandex.ru/docs/ru/search-api/concepts/index.html
- https://aistudio.yandex.ru/docs/ru/search-api/api-ref/
- https://aistudio.yandex.ru/docs/ru/search-api/reference/regions.html

## Required Credentials

- `YANDEX_SEARCH_API_KEY`
- `YANDEX_CLOUD_FOLDER_ID`

Optional endpoint overrides:

- `YANDEX_SEARCH_API_BASE`
- `YANDEX_OPERATIONS_API_BASE`

Defaults:

- `https://searchapi.api.cloud.yandex.net`
- `https://operation.api.cloud.yandex.net`

## Request Model

The script submits async search operations to:

```text
POST /v2/web/searchAsync
```

Then polls operation status at:

```text
GET /operations/{id}
```

The completed payload contains base64-encoded XML, which the script decodes and parses.

Only when asynchronous **submission** returns HTTP 429, the client tries the same
page once using the same request body, credentials, and search API base:

```text
POST /v2/web/search
```

This synchronous endpoint returns `rawData` directly; it does not create an
operation or use the operations API. The client validates JSON, base64, UTF-8, and
the search XML before parsing it through the existing result pipeline. Mixed
asynchronous/fallback pages retain their requested order. An unrelated submission
HTTP status does not trigger fallback. There are no additional fallback retries.

Official synchronous response contract:
https://aistudio.yandex.ru/docs/ru/search-api/api-ref/WebSearch/search

If fallback fails, both Python entry points raise `SearchError`, a `RuntimeError`.
The CLI exits 1, writes no success payload, and describes both attempts on stderr,
including the actual second HTTP status or a sanitized transport/response error.
For example:

```text
Yandex Search failed: asynchronous submission returned HTTP 429; synchronous fallback returned HTTP 503.
```

This diagnostic does not include raw error bodies, credentials, links, or an
inferred cause. A valid empty fallback response remains successful.

## Operation Polling Errors

The polling budget remains ten attempts with the existing retry timing. Transient
HTTP errors may still recover within that budget. Exhaustion raises `SearchError`,
including the last HTTP status if the final attempt failed at HTTP level; a final
successful-but-pending reply is reported as incomplete, not as a stale HTTP error.

Completed-operation errors, missing payloads, malformed operation JSON, and invalid
base64/UTF-8/search XML also raise `SearchError`. Completed payloads reuse the
fallback's existing validation and result parser. Error diagnostics omit service
bodies, credentials, folder/operation identifiers, and tracebacks. The CLI exits 1
without printing partial successful results if any requested page fails. A valid
completed response with zero matches remains successful.

The submission HTTP 429 fallback policy above is unchanged. A polling HTTP 429
is retried as a polling failure, not submitted again through the synchronous API.

## Supported Search Parameters

- `search_type`
  - `SEARCH_TYPE_RU`
  - `SEARCH_TYPE_COM`
  - `SEARCH_TYPE_TR`
  - `SEARCH_TYPE_KK`
  - `SEARCH_TYPE_BE`
  - `SEARCH_TYPE_UZ`
- `family_mode`
  - `FAMILY_MODE_STRICT`
  - `FAMILY_MODE_MODERATE`
  - `FAMILY_MODE_NONE`
- `region`
- `groups_on_page`
- `pages_to_fetch`

## Output Contract

Each parsed result contains:

- `url`
- `domain`
- `title`
- `headline`
- `content`
- `modtime`
- `lang`

CLI JSON output maps `content` to `snippet`.

## Implementation Notes

- `content` resolution priority is:
  1. `extended-text`
  2. `passage` entries
  3. `headline`
- Results shorter than the minimum content threshold are filtered out by `optimize_results()`.
- The client preserves both synchronous and async Python entry points for callers.

## Troubleshooting

- Missing credentials:
  - verify `YANDEX_SEARCH_API_KEY`
  - verify `YANDEX_CLOUD_FOLDER_ID`
- Empty results:
  - broaden the query
  - switch `SEARCH_TYPE_RU` vs `SEARCH_TYPE_COM`
  - remove or widen the region filter
- API errors:
  - inspect the outcomes of both attempts reported by the CLI
  - check service status: https://center.yandex.cloud/statusboard
  - check billing and balance: https://center.yandex.cloud/billing/
  - verify the service account role in Yandex Cloud
  - a service incident or account/balance problem is a possible explanation to
    investigate, not a cause established by HTTP 429 alone
