# Yandex Cloud Search API Notes

This skill uses **Yandex Cloud Search API v2**, not the legacy Yandex XML search endpoint.

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
  - rerun with `--verbose`
  - verify the service account role and billing state in Yandex Cloud

