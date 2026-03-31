# yandex-search-skill

Standalone OpenClaw skill for web search via Yandex Cloud Search API v2.

This repo contains a single self-contained skill named `yandex-search`. It was split out of the broader `yandex-skills` pack so search can be versioned, installed, and tested independently.

## Contents

```text
yandex-search-skill/
├── SKILL.md
├── README.md
├── LICENSE
├── requirements.txt
├── references/
│   ├── api.md
│   └── regions.md
└── scripts/
    ├── search.py
    └── test_search.py
```

## Requirements

- Python 3.10+
- `aiohttp`
- Yandex Cloud Search API credentials

Install dependencies:

```bash
python3 -m pip install -r requirements.txt
```

## Configuration

Required environment variables:

```bash
export YANDEX_SEARCH_API_KEY="<api_key>"
export YANDEX_CLOUD_FOLDER_ID="<folder_id>"
```

Optional overrides:

```bash
export YANDEX_SEARCH_API_BASE="https://searchapi.api.cloud.yandex.net"
export YANDEX_OPERATIONS_API_BASE="https://operation.api.cloud.yandex.net"
```

## Usage

Basic CLI:

```bash
python3 scripts/search.py "yandex cloud tutorial"
```

Text output:

```bash
python3 scripts/search.py "python async" --count 5 --format text
```

Regional search:

```bash
python3 scripts/search.py "новости ИИ" --region 213 --type SEARCH_TYPE_RU
```

## Python API

```python
from search import search, search_async

results = search("machine learning", count=10, pages=1)
for item in results:
    print(item["title"], item["url"])
```

## OpenClaw Deployment

On this host, the expected deployment path is:

```bash
/opt/openclaw/shared/skills/yandex-search
```

`/opt/openclaw/gateway/openclaw.json` already loads `/opt/openclaw/shared/skills` through `skills.load.extraDirs`, so no gateway config change is needed once this directory exists.

## Testing

Run the local regression script:

```bash
python3 scripts/test_search.py
```

The live API test is automatically skipped unless `YANDEX_SEARCH_API_KEY` and `YANDEX_CLOUD_FOLDER_ID` are set.

## Validation

The repo CI checks:

- SKILL frontmatter shape
- CLI `--help`
- unit tests and smoke tests

## Source Split

The original monorepo-style Yandex pack now treats search as external. Human-facing migration notes in the old repo point here.

