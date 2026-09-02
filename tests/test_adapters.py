import sys
import unittest
import tempfile
import shutil
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.adapters import TargetManager


class TestTargetManager(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path(tempfile.mkdtemp())

    def tearDown(self):
        shutil.rmtree(self.test_dir, ignore_errors=True)

    def test_sync_claude_non_destructive(self):
        claude_file = self.test_dir / "CLAUDE.md"
        claude_file.write_text("# My Custom Claude Rules\nDo not touch this.\n", encoding="utf-8")

        TargetManager.sync_claude(
            workspace_root=self.test_dir,
            genome_text="[GENOME_CONTENT]",
            darwin_text="- [PATTERN] Always test before commit"
        )

        content = claude_file.read_text(encoding="utf-8")
        self.assertIn("# My Custom Claude Rules\nDo not touch this.", content)
        self.assertIn("<!-- cookiegli:genome:start -->", content)
        self.assertIn("[GENOME_CONTENT]", content)
        self.assertIn("<!-- cookiegli:darwin:start -->", content)
        self.assertIn("Always test before commit", content)

        # Re-run sync with updated content (idempotency & replacement)
        TargetManager.sync_claude(
            workspace_root=self.test_dir,
            genome_text="[GENOME_UPDATED]",
            darwin_text="- [PATTERN] Updated pattern"
        )
        updated = claude_file.read_text(encoding="utf-8")
        self.assertIn("# My Custom Claude Rules\nDo not touch this.", updated)
        self.assertIn("[GENOME_UPDATED]", updated)
        self.assertNotIn("[GENOME_CONTENT]", updated)
        self.assertEqual(updated.count("<!-- cookiegli:genome:start -->"), 1)

    def test_sync_codex(self):
        agents_file = self.test_dir / "AGENTS.md"
        agents_file.write_text("# Existing OpenAI Codex Instructions\n", encoding="utf-8")

        TargetManager.sync_codex(
            workspace_root=self.test_dir,
            genome_text="[CODEX_GENOME]",
            darwin_text="- [LESSON] Avoid unhandled exceptions"
        )

        content = agents_file.read_text(encoding="utf-8")
        self.assertIn("# Existing OpenAI Codex Instructions", content)
        self.assertIn("<!-- cookiegli:genome:start -->", content)
        self.assertIn("[CODEX_GENOME]", content)
        self.assertIn("Avoid unhandled exceptions", content)

    def test_sync_antigravity(self):
        g_path, d_path = TargetManager.sync_antigravity(
            workspace_root=self.test_dir,
            genome_text="[ANTIGRAVITY_GENOME]",
            darwin_text="- [PATTERN] Zero-Defect delivery"
        )
        self.assertTrue(g_path.exists())
        self.assertTrue(d_path.exists())
        self.assertIn("[ANTIGRAVITY_GENOME]", g_path.read_text(encoding="utf-8"))
        self.assertIn("Zero-Defect delivery", d_path.read_text(encoding="utf-8"))

    def test_sync_cursor(self):
        paths = TargetManager.sync_cursor(
            workspace_root=self.test_dir,
            genome_text="[CURSOR_GENOME]",
            darwin_text="- [PATTERN] Cursor rule"
        )
        self.assertTrue(len(paths) >= 2)
        mdc_path = self.test_dir / ".cursor" / "rules" / "cookiegli_context.mdc"
        cursorrules_path = self.test_dir / ".cursorrules"
        self.assertTrue(mdc_path.exists())
        self.assertTrue(cursorrules_path.exists())
        self.assertIn("[CURSOR_GENOME]", mdc_path.read_text(encoding="utf-8"))
        self.assertIn("[CURSOR_GENOME]", cursorrules_path.read_text(encoding="utf-8"))

    def test_sync_windsurf(self):
        w_path = TargetManager.sync_windsurf(
            workspace_root=self.test_dir,
            genome_text="[WINDSURF_GENOME]",
            darwin_text="- [PATTERN] Cascade flow"
        )
        self.assertTrue(w_path.exists())
        content = w_path.read_text(encoding="utf-8")
        self.assertIn("[WINDSURF_GENOME]", content)
        self.assertIn("Cascade flow", content)

    def test_sync_all_broadcast(self):
        results = TargetManager.sync(
            target="all",
            workspace_root=self.test_dir,
            genome_text="[ALL_GENOME]",
            darwin_text="- [PATTERN] Universal pattern"
        )
        self.assertIn("claude", results)
        self.assertIn("codex", results)
        self.assertIn("antigravity", results)
        self.assertIn("cursor", results)
        self.assertIn("windsurf", results)

        self.assertTrue((self.test_dir / "CLAUDE.md").exists())
        self.assertTrue((self.test_dir / "AGENTS.md").exists())
        self.assertTrue((self.test_dir / ".agents" / "GENOME.md").exists())
        self.assertTrue((self.test_dir / ".cursorrules").exists())
        self.assertTrue((self.test_dir / ".windsurfrules").exists())

    def test_invalid_target_raises(self):
        with self.assertRaises(ValueError):
            TargetManager.sync("unsupported_target", self.test_dir)


if __name__ == "__main__":
    unittest.main()
