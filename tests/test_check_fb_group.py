#!/usr/bin/env python3
"""
Filename:       test_check_fb_group.py
Version:        1.0
Last Modified:  2026-08-10
Context:        Facebook Group Updates (EPSC)

Secrets:
    None - tests use temporary fixtures and stub the browser module.
"""
import importlib.util
import json
import sys
import tempfile
import types
import unittest
from pathlib import Path


SCRIPT_PATH = Path(__file__).parents[1] / "scripts" / "check_fb_group.py"
FIXTURE_PATH = Path(__file__).parent / "fixtures" / "facebook_feed_candidates.json"


def load_scraper_module():
    """Load pure scraper helpers without requiring the deployed Playwright venv."""
    playwright = types.ModuleType("playwright")
    sync_api = types.ModuleType("playwright.sync_api")
    sync_api.sync_playwright = None
    sys.modules["playwright"] = playwright
    sys.modules["playwright.sync_api"] = sync_api
    spec = importlib.util.spec_from_file_location("check_fb_group", SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


scraper = load_scraper_module()


class CheckFbGroupTests(unittest.TestCase):
    def test_fixture_candidates_validate_by_item_type(self):
        candidates = json.loads(FIXTURE_PATH.read_text())
        failures = [
            scraper.get_validation_failures({
                "display_url": candidate["url"],
                "is_comment": candidate["type"] == "comment",
                "author": candidate["author"],
                "author_status": candidate["author_status"],
                "content": candidate["content"],
            })
            for candidate in candidates
        ]
        self.assertEqual(failures[0], [])
        self.assertEqual(failures[1], [])
        self.assertEqual(set(failures[2]), {"missing_url", "missing_author"})

    def test_comment_cannot_use_parent_post_permalink(self):
        parent_url = "https://www.facebook.com/groups/473971729877417/posts/123/"
        self.assertFalse(scraper.is_facebook_permalink(parent_url, True))

    def test_canonical_url_preserves_identity_parameters(self):
        url = "https://www.facebook.com/groups/g/posts/123/?story_fbid=123&utm_source=test"
        canonical = scraper.get_canonical_url(url)
        self.assertIn("story_fbid=123", canonical)
        self.assertNotIn("utm_source", canonical)

    def test_legacy_state_migration_preserves_suppression(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            path.write_text(json.dumps({"notified_hashes": ["already-sent"]}))
            state, migrated = scraper.load_state(str(path))
            self.assertTrue(migrated)
            self.assertIn("already-sent", state["notification_ids"])

    def test_atomic_state_write_is_versioned(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            state = scraper.empty_state()
            scraper.save_state(str(path), state)
            saved = json.loads(path.read_text())
            self.assertEqual(saved["version"], scraper.STATE_VERSION)
            self.assertIn("runs", saved)
            self.assertIn("items", saved)

    def test_oldest_first_order_is_reversal_of_feed_order(self):
        newest_first = ["newest", "middle", "oldest"]
        self.assertEqual(list(reversed(newest_first)), ["oldest", "middle", "newest"])


if __name__ == "__main__":
    unittest.main()
