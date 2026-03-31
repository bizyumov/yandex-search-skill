---
name: yandex-search
description: Search the web with Yandex Cloud Search API v2. Use when Russian-language search results, Yandex regional targeting, or a Yandex-backed search fallback is preferred. Supports CLI and Python usage via the bundled script.
license: MIT
metadata: {"openclaw":{"emoji":"🟡","primaryEnv":"YANDEX_SEARCH_API_KEY","requires":{"env":["YANDEX_SEARCH_API_KEY","YANDEX_CLOUD_FOLDER_ID"]}}}
---

# Yandex Search

Use this skill when the task benefits from Yandex web search, especially for Russian-language sources or Yandex geo-targeting.

## Runtime Contract

- Required environment variables:
  - `YANDEX_SEARCH_API_KEY`
  - `YANDEX_CLOUD_FOLDER_ID`
- Optional environment variables:
  - `YANDEX_SEARCH_API_BASE`
  - `YANDEX_OPERATIONS_API_BASE`

If required credentials are missing, stop and tell the user exactly which variables are needed.

## Primary Entry Point

Run the bundled script from `{baseDir}`:

```bash
python3 {baseDir}/scripts/search.py "query text"
```

Common options:

- `--count N` results per page
- `--pages N` number of API pages
- `--type SEARCH_TYPE_RU|SEARCH_TYPE_COM|...`
- `--family FAMILY_MODE_STRICT|FAMILY_MODE_MODERATE|FAMILY_MODE_NONE`
- `--region ID`
- `--format json|text`
- `--verbose`

## Python API

Import the bundled module when a Python workflow needs search results:

```python
from search import search, search_async
```

Preserved public functions:

- `search(...)`
- `search_async(...)`

They return a list of result dictionaries with `title`, `url`, `domain`, `content`, `lang`, and `modtime`.

## Working Style

Prefer `--format json` if another tool or script will consume the results.
Prefer `--format text` for quick human-readable summaries.
If the user asks for a region-specific search, use the `--region` flag instead of baking the region into the query text.

## References

- API behavior and examples: `references/api.md`
- Common region IDs: `references/regions.md`

Read those files only when you need implementation detail or region lookup help.

