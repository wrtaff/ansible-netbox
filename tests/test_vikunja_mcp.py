#!/usr/bin/env python3
"""
Unit tests for Vikunja MCP Server hardening (Trac #4768 WP-5).
Tests due_date normalization, HTTP 400 error hints, Inbox warning, and project resolution.
"""
import sys
import os
import unittest
from unittest.mock import patch, MagicMock

# Add mcp-servers/vikunja and repo root to sys.path
TEST_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_ROOT = os.path.abspath(os.path.join(TEST_DIR, "../"))
VIKUNJA_MCP_DIR = os.path.join(REPO_ROOT, "mcp-servers/vikunja")
if REPO_ROOT not in sys.path:
    sys.path.insert(0, REPO_ROOT)
if VIKUNJA_MCP_DIR not in sys.path:
    sys.path.insert(0, VIKUNJA_MCP_DIR)

import server as vikunja_server


class TestVikunjaMCPHardening(unittest.TestCase):

    def test_normalize_due_date_empty_or_none(self):
        norm, err = vikunja_server._normalize_due_date(None)
        self.assertIsNone(norm)
        self.assertIsNone(err)

        norm, err = vikunja_server._normalize_due_date("")
        self.assertIsNone(norm)
        self.assertIsNone(err)

        norm, err = vikunja_server._normalize_due_date("   ")
        self.assertIsNone(norm)
        self.assertIsNone(err)

    def test_normalize_due_date_date_only(self):
        # 2026-10-01 in America/New_York (EDT, UTC-4) -> 2026-10-01T04:00:00Z
        norm, err = vikunja_server._normalize_due_date("2026-10-01")
        self.assertIsNone(err)
        self.assertEqual(norm, "2026-10-01T04:00:00Z")

    def test_normalize_due_date_naive_datetime(self):
        # 2026-10-01T09:00:00 in America/New_York (EDT, UTC-4) -> 2026-10-01T13:00:00Z
        norm, err = vikunja_server._normalize_due_date("2026-10-01T09:00:00")
        self.assertIsNone(err)
        self.assertEqual(norm, "2026-10-01T13:00:00Z")

    def test_normalize_due_date_aware_utc(self):
        norm, err = vikunja_server._normalize_due_date("2026-10-01T13:00:00Z")
        self.assertIsNone(err)
        self.assertEqual(norm, "2026-10-01T13:00:00Z")

        norm, err = vikunja_server._normalize_due_date("2026-10-01T13:00:00z")
        self.assertIsNone(err)
        self.assertEqual(norm, "2026-10-01T13:00:00Z")

    def test_normalize_due_date_aware_offset(self):
        norm, err = vikunja_server._normalize_due_date("2026-10-01T09:00:00-04:00")
        self.assertIsNone(err)
        self.assertEqual(norm, "2026-10-01T13:00:00Z")

    def test_normalize_due_date_invalid(self):
        norm, err = vikunja_server._normalize_due_date("next friday")
        self.assertIsNone(norm)
        self.assertIsNotNone(err)
        self.assertIn("Invalid due_date format", err)
        self.assertIn("next friday", err)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    def test_create_task_invalid_due_date(self):
        res = vikunja_server.create_task(title="Test Task", due_date="not-a-date")
        self.assertIn("Error: Invalid due_date format", res)
        self.assertIn("due_date", res)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    @patch("server.cvt.create_task")
    def test_create_task_http_400_hint(self, mock_create):
        mock_create.side_effect = Exception("HTTP Error 400: Bad Request - {\"message\":\"Invalid model provided\"}")
        res = vikunja_server.create_task(title="Test Task", due_date="2026-10-01")
        self.assertIn("Error from Vikunja (HTTP 400 - Invalid model)", res)
        self.assertIn("due_date", res)
        self.assertIn("project ID", res)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    @patch("server.cvt.create_task")
    def test_create_task_inbox_warning_when_no_project(self, mock_create):
        mock_create.return_value = {"id": 1234, "title": "Test Task"}
        res = vikunja_server.create_task(title="Test Task")
        self.assertIn("Successfully created Vikunja task #1234: Test Task (project_id=1)", res)
        self.assertIn("WARNING: Task was filed in Inbox (project_id=1) because no project was specified.", res)
        self.assertIn("Valid domain projects: board, church, eldercare", res)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    @patch("server._resolve_project_id")
    @patch("server.cvt.create_task")
    def test_create_task_with_named_project_no_inbox_warning(self, mock_create, mock_resolve):
        mock_resolve.return_value = (9, None)
        mock_create.return_value = {"id": 1235, "title": "Replace furnace filter"}
        res = vikunja_server.create_task(title="Replace furnace filter", project="maintenance")
        self.assertIn("Successfully created Vikunja task #1235: Replace furnace filter (project_id=9)", res)
        self.assertNotIn("WARNING: Task was filed in Inbox", res)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    @patch("requests.get")
    def test_update_task_invalid_due_date(self, mock_get):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {"id": 100, "title": "Existing"}
        mock_resp.ok = True
        mock_get.return_value = mock_resp

        res = vikunja_server.update_task(task_id=100, due_date="invalid-iso")
        self.assertIn("Error: Invalid due_date format", res)
        self.assertIn("due_date", res)

    @patch.dict(os.environ, {"VIKUNJA_API_TOKEN": "test_token", "VIKUNJA_URL": "http://test.todo"})
    @patch("requests.post")
    @patch("requests.get")
    def test_update_task_http_400_hint(self, mock_get, mock_post):
        mock_get_resp = MagicMock()
        mock_get_resp.json.return_value = {"id": 100, "title": "Existing"}
        mock_get_resp.ok = True
        mock_get.return_value = mock_get_resp

        mock_post_resp = MagicMock()
        mock_post_resp.status_code = 400
        mock_post_resp.text = '{"message":"Invalid model provided"}'
        import requests
        http_error = requests.exceptions.HTTPError("400 Client Error: Bad Request", response=mock_post_resp)
        mock_post_resp.raise_for_status.side_effect = http_error
        mock_post.return_value = mock_post_resp

        res = vikunja_server.update_task(task_id=100, title="New Title")
        self.assertIn("Error from Vikunja (HTTP 400 - Invalid model)", res)
        self.assertIn("due_date", res)
        self.assertIn("project ID", res)


if __name__ == "__main__":
    unittest.main()
