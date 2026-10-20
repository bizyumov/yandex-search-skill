"""Operation error regressions, integrated with the current fallback contract."""

from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import AsyncMock, patch

import search as client
from test_fallback import ASYNC, SYNC, encoded, local_api, xml_page

OP_PATH = "/operations/private-operation-id"
PRIVATE = "synthetic-private-service-body"


def operation_routes(replies):
    return {
        ("POST", ASYNC): [(200, {"id": "private-operation-id"})],
        ("GET", OP_PATH): replies,
    }


class OperationTests(unittest.TestCase):
    def setUp(self):
        sleep_patch = patch.object(client.asyncio, "sleep", AsyncMock())
        self.sleep = sleep_patch.start()
        self.addCleanup(sleep_patch.stop)

    def call(self, **kwargs):
        return asyncio.run(client._search_api(
            "synthetic-test-key", "synthetic-test-folder", "operation query", **kwargs
        ))

    def cli(self, verbose=False):
        return subprocess.run(
            [sys.executable, str(Path(__file__).with_name("search.py")),
             "operation query", *(["--verbose"] if verbose else [])],
            capture_output=True, text=True, timeout=20, check=False,
        )

    def assert_safe(self, message, expected):
        self.assertIn(expected, message)
        for forbidden in (PRIVATE, "synthetic-test-key", "synthetic-test-folder",
                          "private-operation-id", "Traceback", "statusboard", "billing/"):
            self.assertNotIn(forbidden, message)

    def test_poll_http_error_after_ten_attempts_is_not_empty_success(self):
        for status in (429, 503):
            with self.subTest(status=status), local_api(operation_routes(
                [(status, {"message": PRIVATE})] * 10
            )) as requests:
                with self.assertRaises(client.SearchError) as error:
                    self.call()
                self.assert_safe(str(error.exception), f"last HTTP {status}")
                self.assertIn("after 10 attempts", str(error.exception))
            self.assertEqual(sum(r["method"] == "GET" for r in requests), 10)
            self.assertEqual(sum(r["method"] == "POST" for r in requests), 1)
            self.assertNotIn(SYNC, [r["path"] for r in requests])

    def test_pending_operation_exhaustion_is_an_error(self):
        with local_api(operation_routes([(200, {"done": False})] * 10)) as requests:
            with self.assertRaises(client.SearchError) as error:
                self.call()
            self.assert_safe(str(error.exception), "did not complete after 10 attempts")
        self.assertEqual(sum(r["method"] == "GET" for r in requests), 10)

    def test_later_pending_response_does_not_report_stale_http_failure(self):
        with local_api(operation_routes(
            [(503, {"message": PRIVATE})] + [(200, {"done": False})] * 9
        )):
            with self.assertRaises(client.SearchError) as error:
                self.call()
            self.assert_safe(str(error.exception), "did not complete")
            self.assertNotIn("HTTP 503", str(error.exception))

    def test_transient_poll_errors_can_still_recover(self):
        with local_api(operation_routes([
            (503, {"message": PRIVATE}), (200, {"done": False}),
            (200, {"done": True, "response": encoded(xml_page(0))}),
        ])) as requests:
            results = self.call()
        self.assertEqual(results[0]["title"], "Page 0")
        self.assertEqual(sum(r["method"] == "GET" for r in requests), 3)
        self.assertEqual(self.sleep.await_count, 2)

    def test_completed_operation_errors_are_sanitized(self):
        for payload in ({"message": PRIVATE, "code": 13}, {}):
            with self.subTest(payload=payload), local_api(operation_routes([
                (200, {"done": True, "error": payload}),
            ])):
                with self.assertRaises(client.SearchError) as error:
                    self.call()
                self.assert_safe(str(error.exception), "operation failed")

    def test_completed_operation_without_payload_is_sanitized(self):
        for payload in ({}, {"response": None}, {"response": []}, {"response": {}},
                        {"response": {"rawData": ""}}):
            with self.subTest(payload=payload), local_api(operation_routes([
                (200, {"done": True, **payload}),
            ])):
                with self.assertRaises(client.SearchError) as error:
                    self.call()
                self.assert_safe(str(error.exception), "no response payload")

    def test_malformed_operation_json_is_sanitized(self):
        for payload in (b"not JSON " + PRIVATE.encode(), [], None):
            with self.subTest(payload=payload), local_api(operation_routes([(200, payload)])):
                with self.assertRaises(client.SearchError) as error:
                    self.call()
                self.assert_safe(str(error.exception), "invalid operation response")

    def test_invalid_payload_never_becomes_empty_success(self):
        payloads = [
            {"rawData": "!!!"}, {"rawData": 42}, {"rawData": "/w=="},
            encoded("<broken"), encoded("<unrelated/>"),
            encoded('<yandexsearch><response><error code="42">' + PRIVATE
                    + '</error></response></yandexsearch>'),
        ]
        for payload in payloads:
            with self.subTest(payload=payload), local_api(operation_routes([
                (200, {"done": True, "response": payload}),
            ])):
                with self.assertRaises(client.SearchError) as error:
                    self.call()
                self.assert_safe(str(error.exception), "invalid response payload")

    def test_valid_empty_operation_remains_successful(self):
        with local_api(operation_routes([
            (200, {"done": True, "response": encoded("<yandexsearch><response/></yandexsearch>")}),
        ])):
            self.assertEqual(self.call(), [])

    def test_failed_poll_page_does_not_return_successful_fallback_page(self):
        with local_api({
            ("POST", ASYNC): [(429, {}), (200, {"id": "private-operation-id"})],
            ("POST", SYNC): [(200, encoded(xml_page(0)))],
            ("GET", OP_PATH): [(503, {"message": PRIVATE})] * 10,
        }) as requests:
            with self.assertRaises(client.SearchError) as error:
                self.call(pages_to_fetch=[0, 1])
            self.assert_safe(str(error.exception), "last HTTP 503")
        self.assertEqual(sum(r["path"] == SYNC for r in requests), 1)

    def test_cli_operation_failures_are_nonzero_and_safe_even_verbose(self):
        responses = [
            ({"done": True, "error": {"message": PRIVATE}}, "operation failed"),
            ({"done": True, "response": encoded("<broken")}, "invalid response payload"),
        ]
        for response, expected in responses:
            for verbose in (False, True):
                with self.subTest(response=response, verbose=verbose), local_api(
                    operation_routes([(200, response)])
                ):
                    result = self.cli(verbose)
                self.assertNotEqual(result.returncode, 0)
                self.assertEqual(result.stdout, "")
                self.assert_safe(result.stderr, expected)

    def test_cli_valid_empty_operation_succeeds(self):
        with local_api(operation_routes([
            (200, {"done": True, "response": encoded("<yandexsearch><response/></yandexsearch>")}),
        ])):
            result = self.cli()
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)["results"], [])
        self.assertEqual(result.stderr, "")


if __name__ == "__main__":
    unittest.main()
