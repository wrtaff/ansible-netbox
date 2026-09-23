#!/usr/bin/env python3
"""
Unit tests for graylog_query.py HTTP Basic authentication, retry, and cache handling.
Context: http://trac.gafla.us.com/ticket/4656
"""
import unittest
from unittest.mock import patch, MagicMock
import os
import sys

# Ensure ansible-netbox root is on sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from scripts import graylog_query as gq


class TestGraylogAuth(unittest.TestCase):

    def setUp(self):
        gq.GRAYLOG_API_TOKEN = None

    @patch("scripts.graylog_query.get_token")
    @patch("scripts.graylog_query.requests.get")
    def test_graylog_get_basic_auth_success(self, mock_get, mock_get_token):
        mock_get_token.return_value = "dummy-token-123"
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        res = gq._graylog_get("http://graylog.home.arpa:9000/api/system", timeout=10)

        self.assertEqual(res.status_code, 200)
        mock_get.assert_called_once()
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs.get("auth"), ("dummy-token-123", "token"))
        self.assertEqual(kwargs.get("headers"), {"Accept": "application/json", "X-Requested-By": "pops-agent"})

    @patch("scripts.graylog_query._clear_token_cache")
    @patch("scripts.graylog_query.get_token")
    @patch("scripts.graylog_query.requests.get")
    def test_graylog_get_401_retry_behavior(self, mock_get, mock_get_token, mock_clear_cache):
        # First call returns 401, second call returns 200
        mock_get_token.side_effect = ["old-token", "new-token"]
        
        resp_401 = MagicMock()
        resp_401.status_code = 401
        resp_200 = MagicMock()
        resp_200.status_code = 200
        mock_get.side_effect = [resp_401, resp_200]

        res = gq._graylog_get("http://graylog.home.arpa:9000/api/system", timeout=10)

        self.assertEqual(res.status_code, 200)
        self.assertEqual(mock_get.call_count, 2)
        mock_clear_cache.assert_called_once()
        
        # Verify first call auth
        first_call_kwargs = mock_get.call_args_list[0][1]
        self.assertEqual(first_call_kwargs.get("auth"), ("old-token", "token"))

        # Verify second call auth
        second_call_kwargs = mock_get.call_args_list[1][1]
        self.assertEqual(second_call_kwargs.get("auth"), ("new-token", "token"))

    @patch("scripts.graylog_query._graylog_get")
    def test_test_connection_success(self, mock_graylog_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 200
        mock_resp.json.return_value = {"version": "6.3.0-RC1"}
        mock_graylog_get.return_value = mock_resp

        self.assertTrue(gq.test_connection())

    @patch("scripts.graylog_query._graylog_get")
    def test_test_connection_auth_failure(self, mock_graylog_get):
        mock_resp = MagicMock()
        mock_resp.status_code = 401
        mock_graylog_get.return_value = mock_resp

        self.assertFalse(gq.test_connection())


if __name__ == "__main__":
    unittest.main()
