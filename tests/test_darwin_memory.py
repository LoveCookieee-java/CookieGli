"""
Unit Tests for CookieGli DarwinMemory.
"""

import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.darwin_memory import DarwinMemory, LearnedArtifact, estimate_tokens


class TestDarwinMemory(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.test_dir.name) / 'state.json'
        self.memory = DarwinMemory(str(self.state_file))

    def tearDown(self):
        self.test_dir.cleanup()

    def test_bayesian_smoothed_roi(self):
        art = self.memory.register("auth_pattern", "pattern", "Always validate JWT before database query", tags=["security", "auth"])
        self.assertAlmostEqual(art.roi, 0.35, places=2)

        self.memory.record_usage(art.id, True)
        self.assertGreater(art.roi, 0.5)

        self.memory.record_usage(art.id, False)
        self.assertAlmostEqual(art.roi, 0.47, places=2)

    def test_search_by_query_and_tags(self):
        self.memory.register("jwt_guard", "pattern", "Validate JWT tokens", tags=["security", "auth"])
        self.memory.register("sql_indexer", "pattern", "Add B-tree index on foreign keys", tags=["db", "performance"])

        sec_results = self.memory.search(tags=["security"])
        self.assertEqual(len(sec_results), 1)
        self.assertEqual(sec_results[0].name, "jwt_guard")

        db_results = self.memory.search(query="B-tree")
        self.assertEqual(len(db_results), 1)
        self.assertEqual(db_results[0].name, "sql_indexer")

    def test_atomic_file_persistence(self):
        self.memory.register("p1", "lesson", "Check for None", tags=["core"])
        self.memory.save()

        self.assertTrue(self.state_file.exists())

        new_mem = DarwinMemory(str(self.state_file))
        active = new_mem.get_active()
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].name, "p1")
        self.assertIn("core", active[0].tags)

    def test_capacity_constraint_strict(self):
        for i in range(12):
            a = self.memory.register(f"art_{i}", "pattern", f"Rule {i}")
            self.memory.record_usage(a.id, (i % 2 == 0))

        res = self.memory.evolve(max_artifacts=5, protect_recent=2)
        active = self.memory.get_active()
        self.assertLessEqual(len(active), 5, f"Active count {len(active)} exceeded max_capacity 5")

    def test_markdown_summary(self):
        self.memory.register("p1", "lesson", "Always check for None", tags=["safety"])
        summary = self.memory.to_markdown_summary(max_tokens=300)
        self.assertIn("Darwin Learned Patterns", summary)
        self.assertIn("`[safety]`", summary)


if __name__ == '__main__':
    unittest.main()
