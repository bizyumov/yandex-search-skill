#!/usr/bin/env python3
"""Tests for yandex-search."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import threading
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from unittest.mock import AsyncMock, patch

SCRIPT_DIR = Path(__file__).resolve().parent
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import search as search_module  # noqa: E402
from search import (  # noqa: E402
    _search_api,
    _clean_text,
    _parse_xml_results,
    format_output,
    format_results,
    optimize_results,
    search,
)


SAMPLE_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0">
<response>
<results>
<grouping>
<group>
<doc>
    <url>https://example.com/page1</url>
    <domain>example.com</domain>
    <title>Example Page &lt;b&gt;One&lt;/b&gt;</title>
    <headline>A sample headline</headline>
    <modtime>20260210T120000</modtime>
    <properties>
        <lang>ru</lang>
        <extended-text>Extended content about the topic with enough detail.</extended-text>
    </properties>
</doc>
</group>
<group>
<doc>
    <url>https://test.org/article</url>
    <domain>test.org</domain>
    <title>Test Article</title>
    <headline>Short</headline>
    <modtime>20260211T080000</modtime>
    <properties>
        <lang>en</lang>
    </properties>
    <passages><passage>This is a passage with more detail about the search result.</passage></passages>
</doc>
</group>
</grouping>
</results>
</response>
</yandexsearch>
"""

EMPTY_XML = """<?xml version="1.0" encoding="utf-8"?>
<yandexsearch version="1.0"><response><results><grouping /></results></response></yandexsearch>
"""


class _ApiHandler(BaseHTTPRequestHandler):
    def log_message(self, format: str, *args: object) -> None:
        return

    def _json(self, status: int, payload: dict) -> None:
        data = json.dumps(payload).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_POST(self) -> None:
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        scenario = payload["query"]["query_text"]
        if scenario == "submit-error":
            self._json(403, {"message": "denied sensitive-resource-id"})
            return
        self._json(200, {"id": scenario})

    def do_GET(self) -> None:
        scenario = self.path.rsplit("/", 1)[-1]
        if scenario == "poll-http-error":
            self._json(503, {"message": "unavailable sensitive-resource-id"})
        elif scenario == "operation-error":
            self._json(200, {"done": True, "error": {"message": "failed sensitive-resource-id"}})
        elif scenario == "pending":
            self._json(200, {"done": False})
        elif scenario == "empty":
            import base64

            raw_data = base64.b64encode(EMPTY_XML.encode()).decode()
            self._json(200, {"done": True, "response": {"rawData": raw_data}})
        else:
            self._json(404, {"message": "unknown operation"})


@contextmanager
def _api_server():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _ApiHandler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with patch.dict(
            os.environ,
            {
                "YANDEX_SEARCH_API_BASE": base,
                "YANDEX_OPERATIONS_API_BASE": base,
            },
        ):
            yield base
    finally:
        server.shutdown()
        thread.join(timeout=2)


def _run_search_scenario(scenario: str):
    with _api_server(), patch.object(search_module.asyncio, "sleep", AsyncMock()):
        return search_module.asyncio.run(
            _search_api("fake-key", "fake-folder", scenario, groups_on_page=1)
        )


def test_clean_text() -> None:
    assert _clean_text("<b>bold</b> text") == "bold text"
    assert _clean_text("no tags") == "no tags"
    assert _clean_text("") == ""
    assert _clean_text(None) == ""


def test_parse_xml_results() -> None:
    results = _parse_xml_results(SAMPLE_XML)
    assert len(results) == 2

    first = results[0]
    assert first["url"] == "https://example.com/page1"
    assert first["domain"] == "example.com"
    assert "One" in first["title"]
    assert "<b>" not in first["title"]
    assert first["lang"] == "ru"
    assert "Extended content" in first["content"]

    second = results[1]
    assert second["url"] == "https://test.org/article"
    assert "passage" in second["content"].lower()


def test_parse_xml_invalid() -> None:
    assert _parse_xml_results("not xml at all {}") == []


def test_optimize_results() -> None:
    results = [
        {"content": "short"},
        {"content": "a long enough content string that passes the filter"},
        {"content": ""},
    ]
    filtered = optimize_results(results, min_length=10)
    assert len(filtered) == 1
    assert "long enough" in filtered[0]["content"]


def test_format_results_text() -> None:
    results = [
        {
            "domain": "ex.com",
            "title": "Page",
            "url": "https://ex.com",
            "content": "Content",
            "modtime": "20260210",
            "lang": "ru",
        }
    ]
    text = format_results(results, "test query")
    assert "test query" in text
    assert "ex.com" in text
    assert "Page" in text


def test_format_results_empty() -> None:
    assert "No results" in format_results([], "nothing")


def test_format_output_json() -> None:
    results = [
        {
            "title": "T",
            "url": "U",
            "domain": "D",
            "content": "C",
            "headline": "H",
            "lang": "ru",
            "modtime": "20260210",
        }
    ]
    output = format_output(results, "q", fmt="json")
    data = json.loads(output)
    assert data["query"] == "q"
    assert data["count"] == 1
    assert data["results"][0]["title"] == "T"
    assert data["results"][0]["snippet"] == "C"


def _assert_api_error(scenario: str, expected_text: str) -> None:
    error_type = getattr(search_module, "YandexSearchAPIError", ())
    try:
        _run_search_scenario(scenario)
    except Exception as exc:  # noqa: BLE001
        assert error_type and isinstance(exc, error_type)
        assert expected_text in str(exc)
        assert "sensitive-resource-id" not in str(exc)
        return
    raise AssertionError("Expected a Yandex Search API error")


def test_submit_http_error_is_raised_and_sanitized() -> None:
    _assert_api_error("submit-error", "HTTP 403")


def test_poll_http_error_is_raised_after_retries() -> None:
    _assert_api_error("poll-http-error", "HTTP 503")


def test_completed_operation_error_is_raised_and_sanitized() -> None:
    _assert_api_error("operation-error", "operation failed")


def test_pending_operation_times_out() -> None:
    _assert_api_error("pending", "did not complete")


def test_successful_empty_result_remains_successful() -> None:
    assert _run_search_scenario("empty") == []


def test_cli_api_error_exits_nonzero_without_empty_result_message() -> None:
    script = str(SCRIPT_DIR / "search.py")
    with _api_server() as base:
        env = {
            **os.environ,
            "YANDEX_SEARCH_API_KEY": "fake-key",
            "YANDEX_CLOUD_FOLDER_ID": "fake-folder",
            "YANDEX_SEARCH_API_BASE": base,
            "YANDEX_OPERATIONS_API_BASE": base,
        }
        result = subprocess.run(
            [sys.executable, script, "submit-error", "--format", "text"],
            capture_output=True,
            text=True,
            timeout=5,
            env=env,
            check=False,
        )
    assert result.returncode != 0
    assert "Search error" in result.stderr
    assert "HTTP 403" in result.stderr
    assert "sensitive-resource-id" not in result.stderr
    assert "No results" not in result.stdout


def test_live_search() -> None:
    try:
        results = search("Яндекс Телемост", count=3, pages=1)
    except ValueError:
        return

    assert isinstance(results, list)
    assert len(results) > 0
    first = results[0]
    assert "url" in first
    assert "title" in first
    assert "content" in first


def test_cli_help() -> None:
    script = str(SCRIPT_DIR / "search.py")
    result = subprocess.run(
        [sys.executable, script, "--help"],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    assert result.returncode == 0
    assert "--count" in result.stdout
    assert "--pages" in result.stdout
    assert "--type" in result.stdout
    assert "--format" in result.stdout


def test_cli_missing_env() -> None:
    script = str(SCRIPT_DIR / "search.py")
    env = {"PATH": "/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, script, "test"],
        capture_output=True,
        text=True,
        timeout=5,
        env=env,
        check=False,
    )
    assert result.returncode != 0
    assert "Configuration error" in result.stderr or "YANDEX_SEARCH_API_KEY" in result.stderr


def run_all() -> bool:
    tests = [
        test_clean_text,
        test_parse_xml_results,
        test_parse_xml_invalid,
        test_optimize_results,
        test_format_results_text,
        test_format_results_empty,
        test_format_output_json,
        test_submit_http_error_is_raised_and_sanitized,
        test_poll_http_error_is_raised_after_retries,
        test_completed_operation_error_is_raised_and_sanitized,
        test_pending_operation_times_out,
        test_successful_empty_result_remains_successful,
        test_cli_api_error_exits_nonzero_without_empty_result_message,
        test_live_search,
        test_cli_help,
        test_cli_missing_env,
    ]

    passed = 0
    failed = 0
    for test in tests:
        print(f"\n[test] {test.__name__}")
        try:
            test()
            print("  PASS")
            passed += 1
        except Exception as exc:  # noqa: BLE001
            print(f"  FAIL: {exc}")
            failed += 1

    print(f"\nResults: {passed} passed, {failed} failed, {passed + failed} total")
    return failed == 0


if __name__ == "__main__":
    sys.exit(0 if run_all() else 1)

