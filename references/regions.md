# Yandex Search Region Codes

Use these IDs with `--region`.

## Major Cities

- `213` — Moscow
- `2` — St. Petersburg
- `65` — Novosibirsk
- `54` — Yekaterinburg
- `43` — Kazan
- `47` — Nizhny Novgorod
- `56` — Chelyabinsk
- `51` — Samara
- `66` — Omsk
- `39` — Rostov-on-Don

## Countries and Broad Regions

- `225` — Russia
- `187` — Ukraine
- `149` — Belarus
- `162` — Kazakhstan
- `983` — Turkey
- `84` — USA
- `102` — United Kingdom
- `96` — Germany
- `124` — France

## Usage Examples

```bash
python3 scripts/search.py "query" --region 213
python3 scripts/search.py "query" --region 225
```

If unsure, omit `--region` first and only add one when geographic ranking matters.

