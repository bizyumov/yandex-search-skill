"""Deterministic HTTP integration tests for the async-429 fallback contract."""

from __future__ import annotations

import asyncio
import base64
from contextlib import contextmanager
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import os
from pathlib import Path
import socket
import subprocess
import sys
from threading import Thread
import unittest
from unittest.mock import patch

import search as client

ASYNC = "/v2/web/searchAsync"
SYNC = "/v2/web/search"


def xml_page(page: int) -> str:
    return (
        '<yandexsearch><response><results><grouping><group><doc>'
        f'<url>https://example.com/{page}</url><domain>example.com</domain>'
        f'<title>Page {page}</title><headline>A sufficiently detailed result</headline>'
        '</doc></group></grouping></results></response></yandexsearch>'
    )


def encoded(xml: str) -> dict:
    return {"rawData": base64.b64encode(xml.encode("utf-8")).decode("ascii")}


@contextmanager
def local_api(routes: dict):
    """Serve queued HTTP replies; record only synthetic test requests."""
    requests = []
    queues = {key: list(replies) for key, replies in routes.items()}

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def handle_request(self):
            body = self.rfile.read(int(self.headers.get("Content-Length", "0")))
            requests.append({
                "method": self.command,
                "path": self.path,
                "body": json.loads(body) if body else None,
                "authorization": self.headers.get("Authorization"),
            })
            queue = queues.get((self.command, self.path), [])
            status, payload = queue.pop(0) if queue else (500, {"unexpected": True})
            if status is None:
                self.connection.shutdown(socket.SHUT_RDWR)
                self.connection.close()
                return
            raw = payload if isinstance(payload, bytes) else json.dumps(payload).encode()
            self.send_response(status)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(raw)))
            self.end_headers()
            self.wfile.write(raw)

        do_POST = handle_request
        do_GET = handle_request

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    env = {
        "YANDEX_SEARCH_API_KEY": "synthetic-test-key",
        "YANDEX_CLOUD_FOLDER_ID": "synthetic-test-folder",
        "YANDEX_SEARCH_API_BASE": base,
        "YANDEX_OPERATIONS_API_BASE": base,
    }
    try:
        with patch.dict(os.environ, env):
            yield requests
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


class FallbackTests(unittest.TestCase):
    def call(self, **kwargs):
        return asyncio.run(client._search_api(
            "synthetic-test-key", "synthetic-test-folder", "test query", **kwargs
        ))

    def cli(self, *args):
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("search.py")),
             "test query", *args],
            capture_output=True, text=True, timeout=15, check=False,
        )

    def assert_attempt_error(self, message, second):
        self.assertIn("asynchronous submission returned HTTP 429", message)
        self.assertIn("synchronous fallback", message)
        self.assertIn(second, message)
        for forbidden in ("synthetic-test-key", "RAW-SECRET", "statusboard", "billing/", "Traceback"):
            self.assertNotIn(forbidden, message)

    def test_fallback_preserves_parameters_and_credentials(self):
        with local_api({
            ("POST", ASYNC): [(429, {"error": "RAW-SECRET"})],
            ("POST", SYNC): [(200, encoded(xml_page(4)))],
        }) as requests:
            results = self.call(
                pages_to_fetch=[4], groups_on_page=3, docs_in_group=2,
                max_passages=4, search_type="SEARCH_TYPE_COM",
                family_mode="FAMILY_MODE_STRICT", region=213,
            )
        self.assertEqual([r["title"] for r in results], ["Page 4"])
        self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC])
        self.assertEqual(requests[0]["body"], requests[1]["body"])
        self.assertEqual(requests[1]["body"], {
            "query": {"search_type": "SEARCH_TYPE_COM", "query_text": "test query",
                      "family_mode": "FAMILY_MODE_STRICT", "page": 4},
            "sort_spec": {"sort_mode": "SORT_MODE_BY_RELEVANCE", "sort_order": "SORT_ORDER_DESC"},
            "group_spec": {"group_mode": "GROUP_MODE_DEEP", "groups_on_page": 3, "docs_in_group": 2},
            "max_passages": 4, "l10n": "LOCALIZATION_RU",
            "folder_id": "synthetic-test-folder", "response_format": "FORMAT_XML", "region": "213",
        })
        self.assertTrue(all(r["authorization"] == "Api-Key synthetic-test-key" for r in requests))

    def test_both_python_entrypoints_use_fallback(self):
        for async_entry in (False, True):
            with self.subTest(async_entry=async_entry), local_api({
                ("POST", ASYNC): [(429, {})],
                ("POST", SYNC): [(200, encoded(xml_page(0)))],
            }):
                results = (asyncio.run(client.search_async("test query")) if async_entry
                           else client.search("test query"))
                self.assertEqual(results[0]["title"], "Page 0")

    def test_async_success_polls_without_fallback(self):
        with local_api({
            ("POST", ASYNC): [(200, {"id": "operation-0"})],
            ("GET", "/operations/operation-0"): [(200, {"done": True, "response": encoded(xml_page(0))})],
        }) as requests:
            results = self.call()
        self.assertEqual(results[0]["title"], "Page 0")
        self.assertEqual([r["path"] for r in requests], [ASYNC, "/operations/operation-0"])

    def test_non_429_submission_never_uses_fallback(self):
        for status in (400, 401, 403, 500, 503):
            with self.subTest(status=status), local_api({
                ("POST", ASYNC): [(status, {"error": "RAW-SECRET"})],
            }) as requests:
                with self.assertRaises(RuntimeError) as error:
                    self.call()
                self.assertIn(f"HTTP {status}", str(error.exception))
                self.assertNotIn("RAW-SECRET", str(error.exception))
            self.assertEqual([r["path"] for r in requests], [ASYNC])

    def test_both_http_failures_propagate_actual_status(self):
        for status in (429, 401, 403, 500):
            with self.subTest(status=status), local_api({
                ("POST", ASYNC): [(429, {"error": "RAW-SECRET"})],
                ("POST", SYNC): [(status, {"error": "RAW-SECRET"})],
            }) as requests:
                with self.assertRaises(RuntimeError) as error:
                    self.call()
                self.assert_attempt_error(str(error.exception), f"returned HTTP {status}")
            self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC])

    def test_fallback_transport_failure_is_sanitized(self):
        with local_api({
            ("POST", ASYNC): [(429, {})],
            ("POST", SYNC): [(None, None)],
        }) as requests:
            with self.assertRaises(RuntimeError) as error:
                self.call()
            self.assert_attempt_error(str(error.exception), "transport error")
        self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC])

    def test_malformed_fallback_never_becomes_empty_success(self):
        bad_responses = [
            b"invalid JSON RAW-SECRET", {}, [], {"rawData": None},
            {"rawData": ""}, {"rawData": "!!!RAW-SECRET!!!"},
            {"rawData": base64.b64encode(b"\xff").decode()},
            encoded("not XML RAW-SECRET"), encoded("<unrelated/>"),
            encoded('<yandexsearch><response><error code="42">RAW-SECRET</error></response></yandexsearch>'),
        ]
        for payload in bad_responses:
            with self.subTest(payload=payload), local_api({
                ("POST", ASYNC): [(429, {})],
                ("POST", SYNC): [(200, payload)],
            }):
                with self.assertRaises(RuntimeError) as error:
                    self.call()
                self.assert_attempt_error(str(error.exception), "invalid search response")

    def test_valid_empty_fallback_succeeds(self):
        with local_api({
            ("POST", ASYNC): [(429, {})],
            ("POST", SYNC): [(200, encoded("<yandexsearch><response/></yandexsearch>"))],
        }) as requests:
            self.assertEqual(self.call(), [])
        self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC])

    def test_cli_valid_empty_fallback_succeeds(self):
        with local_api({
            ("POST", ASYNC): [(429, {})],
            ("POST", SYNC): [(200, encoded("<yandexsearch><response/></yandexsearch>"))],
        }) as requests:
            result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["results"], [])
        self.assertEqual(result.stderr, "")
        self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC])

    def test_mixed_pages_preserve_requested_order(self):
        for pages in ([0, 1, 2], [2, 0, 1]):
            with self.subTest(pages=pages), local_api({
                ("POST", ASYNC): [(200, {"id": "first"}), (429, {}), (200, {"id": "last"})],
                ("POST", SYNC): [(200, encoded(xml_page(pages[1])))],
                ("GET", "/operations/first"): [(200, {"done": True, "response": encoded(xml_page(pages[0]))})],
                ("GET", "/operations/last"): [(200, {"done": True, "response": encoded(xml_page(pages[2]))})],
            }) as requests:
                results = self.call(pages_to_fetch=pages)
            self.assertEqual([r["title"] for r in results], [f"Page {p}" for p in pages])
            self.assertEqual(sum(r["path"] == SYNC for r in requests), 1)

    def test_each_429_page_gets_one_fallback(self):
        with local_api({
            ("POST", ASYNC): [(429, {}), (429, {})],
            ("POST", SYNC): [(200, encoded(xml_page(0))), (200, encoded(xml_page(1)))],
        }) as requests:
            results = self.call(pages_to_fetch=[0, 1])
        self.assertEqual([r["title"] for r in results], ["Page 0", "Page 1"])
        self.assertEqual([r["path"] for r in requests], [ASYNC, SYNC, ASYNC, SYNC])

    def test_later_page_failure_does_not_return_partial_success(self):
        with local_api({
            ("POST", ASYNC): [(429, {}), (429, {})],
            ("POST", SYNC): [(200, encoded(xml_page(0))), (503, {})],
        }):
            with self.assertRaises(RuntimeError) as error:
                self.call(pages_to_fetch=[0, 1])
            self.assert_attempt_error(str(error.exception), "returned HTTP 503")

    def test_cli_fallback_success(self):
        with local_api({
            ("POST", ASYNC): [(429, {})],
            ("POST", SYNC): [(200, encoded(xml_page(0)))],
        }):
            result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["results"][0]["title"], "Page 0")
        self.assertEqual(result.stderr, "")

    def test_cli_both_failures_have_no_results_or_links_even_verbose(self):
        for status in (429, 503):
            for verbose in (False, True):
                with self.subTest(status=status, verbose=verbose), local_api({
                    ("POST", ASYNC): [(429, {"error": "RAW-SECRET"})],
                    ("POST", SYNC): [(status, {"error": "RAW-SECRET"})],
                }):
                    result = self.cli(*(["--verbose"] if verbose else []))
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assert_attempt_error(result.stderr, f"returned HTTP {status}")


if __name__ == "__main__":
    unittest.main()
