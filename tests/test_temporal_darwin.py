import tempfile
import time
import unittest
from pathlib import Path

from cookiegli_core.darwin_memory import DarwinMemory, LearnedArtifact


class TestTemporalDarwin(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.state_file = Path(self.temp_dir.name) / "state.json"
        self.multi_dir = Path(self.temp_dir.name) / "artifacts"
        self.memory = DarwinMemory(state_file=str(self.state_file))

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_namespaced_domain_filtering(self):
        self.memory.register("jwt_rule", "pattern", "Check exp", scope="backend.auth")
        self.memory.register("ui_rule", "pattern", "Use memo", scope="frontend.ui")
        self.memory.register("global_rule", "lesson", "Always write tests", scope="global")

        backend_arts = self.memory.get_active(scope="backend.auth")
        names = [a.name for a in backend_arts]

        self.assertIn("jwt_rule", names)
        self.assertIn("global_rule", names)
        self.assertNotIn("ui_rule", names)

    def test_temporal_half_life_decay(self):
        art = self.memory.register("old_rule", "pattern", "Legacy pattern")
        for _ in range(5):
            self.memory.record_usage(art.id, True)

        initial_roi = art.roi
        self.assertGreater(initial_roi, 0.8)

        # Simulate 30 days passing (half life = 30 days)
        now_30d_later = time.time() + (30.0 * 86400.0)
        self.memory.evolve(half_life_days=30.0, roi_threshold=0.1, now_timestamp=now_30d_later)

        # After 1 half-life, ROI should be approximately half of initial
        decayed_art = self.memory.artifacts[art.id]
        self.assertAlmostEqual(decayed_art.roi, initial_roi * 0.5, delta=0.08)

    def test_multi_file_persistence_mode(self):
        multi_mem = DarwinMemory(multi_file_dir=str(self.multi_dir))
        a1 = multi_mem.register("rule1", "pattern", "Multi file 1", scope="core")
        a2 = multi_mem.register("rule2", "lesson", "Multi file 2", scope="db")

        # Verify individual JSON files exist on disk
        self.assertTrue((self.multi_dir / f"{a1.id}.json").exists())
        self.assertTrue((self.multi_dir / f"{a2.id}.json").exists())

        # Verify reloading from disk
        reloaded = DarwinMemory(multi_file_dir=str(self.multi_dir))
        self.assertEqual(len(reloaded.artifacts), 2)
        self.assertIn(a1.id, reloaded.artifacts)


if __name__ == '__main__':
    unittest.main()
