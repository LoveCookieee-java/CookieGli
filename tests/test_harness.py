"""
Comprehensive Unit Tests for CookieGli Continuous Evolution Harness.
Verifies UserPreferences, AntiPatterns, CorrectionDistiller, ProjectMaturityTracker,
HarnessEngine, BoostEngine integration, TargetManager sync, and MCP/CLI execution.
"""

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))
sys.path.insert(0, str(REPO_ROOT))

from cookiegli_core.harness import (
    AntiPattern,
    CorrectionDistiller,
    HarnessEngine,
    HarnessEpisode,
    ProjectMaturity,
    ProjectMaturityTracker,
    UserPreference,
    estimate_tokens,
)
from cookiegli_core.boost_engine import BoostEngine
from cookiegli_core.adapters import TargetManager
from cookiegli_core.mcp_server import CookieGliMcpServer
import cli.cookiegli as cli_module


class TestHarness(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.workspace_root = Path(self.temp_dir.name).resolve()
        self.state_file = self.workspace_root / ".cookiegli" / "harness_state.json"
        self.harness = HarnessEngine(workspace_root=self.workspace_root, state_file=self.state_file)

    def tearDown(self):
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    # 1. UserPreference model and Bayesian confidence update
    def test_user_preference_bayesian_confidence(self):
        pref = UserPreference(
            id="",
            category="style",
            key="strict_typing",
            value=True,
            description="Always use type annotations on all function signatures",
            confidence=0.85,
            adherence_count=1,
            violation_count=0
        )
        self.assertTrue(len(pref.id) > 0)
        self.assertAlmostEqual(pref.confidence, 0.85)

        # Record positive adherence
        pref.record_feedback(adhered=True)
        # Total: adherence=2, violation=0 -> (2 + 2) / (2 + 3) = 4/5 = 0.80
        self.assertAlmostEqual(pref.confidence, 0.80)

        # Record violation
        pref.record_feedback(adhered=False)
        # Total: adherence=2, violation=1 -> (2 + 2) / (3 + 3) = 4/6 = 0.67
        self.assertAlmostEqual(pref.confidence, 0.667, places=2)

    # 2. AntiPattern model
    def test_anti_pattern_model(self):
        anti = AntiPattern(
            id="",
            name="no_eval",
            forbidden_action="use eval() or exec() dynamically",
            preferred_alternative="use ast.literal_eval() or safe parser",
            severity=0.95
        )
        self.assertTrue(len(anti.id) > 0)
        self.assertEqual(anti.violation_count, 0)
        anti.record_trigger()
        self.assertEqual(anti.violation_count, 1)
        summary = anti.to_summary_line()
        self.assertIn("[GUARD]", summary)
        self.assertIn("Do NOT use eval()", summary)

    # 3. CorrectionDistiller: Vietnamese natural language
    def test_correction_distiller_vietnamese(self):
        text1 = "Đừng dùng requests, hãy dùng urllib.request của stdlib"
        anti, pref = CorrectionDistiller.distill(text1, scope="network")
        self.assertIsNotNone(anti)
        self.assertIn("requests", anti.forbidden_action)
        self.assertIn("urllib.request", anti.preferred_alternative)
        self.assertEqual(anti.scope, "network")

        text2 = "Luôn luôn sử dụng dataclasses thay vì dict cho dữ liệu có cấu trúc"
        anti2, pref2 = CorrectionDistiller.distill(text2, scope="core")
        self.assertIsNotNone(pref2)
        self.assertIn("dataclasses", pref2.description)

    # 4. CorrectionDistiller: English natural language
    def test_correction_distiller_english(self):
        text = "Never use subprocess shell=True, prefer passing list of arguments"
        anti, pref = CorrectionDistiller.distill(text, scope="os")
        self.assertIsNotNone(anti)
        self.assertIn("shell=True", anti.forbidden_action)
        self.assertIn("passing list", anti.preferred_alternative)

    # 5. ProjectMaturityTracker calculation
    def test_project_maturity_tracker(self):
        # Create mock source and test files
        src_dir = self.workspace_root / "src"
        test_dir = self.workspace_root / "tests"
        src_dir.mkdir(parents=True, exist_ok=True)
        test_dir.mkdir(parents=True, exist_ok=True)

        (src_dir / "module_a.py").write_text("def a(): pass\n", encoding="utf-8")
        (src_dir / "module_b.py").write_text("def b(): pass\n", encoding="utf-8")
        (test_dir / "test_a.py").write_text("def test_a(): pass\n", encoding="utf-8")

        tracker = ProjectMaturityTracker(self.workspace_root)
        maturity = tracker.assess_maturity(total_episodes=5, alignment_score=90.0, hotspot_count=2)

        self.assertIsInstance(maturity, ProjectMaturity)
        self.assertGreaterEqual(maturity.maturity_score, 5.0)
        self.assertLessEqual(maturity.maturity_score, 100.0)
        self.assertTrue(maturity.phase.startswith("Phase"))
        self.assertGreater(len(maturity.guidance), 10)

    # 6. Initial seed invariants in HarnessEngine
    def test_harness_engine_initial_seed(self):
        # Fresh engine should have initial preferences
        self.assertGreaterEqual(len(self.harness.preferences), 2)
        self.assertGreaterEqual(len(self.harness.anti_patterns), 1)

        # Invariant for stdlib_first should be present
        prefs_desc = [p.description for p in self.harness.preferences.values()]
        self.assertTrue(any("pure Python standard library" in d for d in prefs_desc))

        # Invariant for unauthorized_file_deletion should be present
        antis_act = [a.forbidden_action for a in self.harness.anti_patterns.values()]
        self.assertTrue(any("delete files" in act for act in antis_act))

    # 7. Record feedback and praise
    def test_harness_engine_feedback_praise_and_correction(self):
        # Record praise
        praise_res = self.harness.record_feedback(
            feedback_type="praise",
            content="Great job adhering to stdlib rules!",
            scope="core"
        )
        self.assertIn("Reinforced", praise_res.get("message", ""))

        # Record correction
        corr_res = self.harness.record_feedback(
            feedback_type="correction",
            content="Do not use raw print(), instead use logging or return result",
            scope="core"
        )
        self.assertEqual(len(corr_res["learned_anti_patterns"]), 1)
        self.assertIn("raw print()", corr_res["learned_anti_patterns"][0]["forbidden_action"])

    # 8. Alignment Score and Episodes
    def test_harness_alignment_score_and_episodes(self):
        self.harness.record_episode(
            task="Task 1",
            touched_files=["src/module.py"],
            test_passed=True,
            feedback_type="implicit_success"
        )
        self.harness.record_episode(
            task="Task 2",
            touched_files=["src/module.py"],
            test_passed=True,
            feedback_type="praise"
        )
        score = self.harness.get_alignment_score()
        self.assertGreaterEqual(score, 70.0)
        self.assertLessEqual(score, 100.0)

    # 9. Relevant context synthesis and token limit
    def test_harness_get_relevant_context(self):
        ctx = self.harness.get_relevant_context(
            task="Fix bug in cache",
            target_files=["src/cookiegli_core/cache_db.py"],
            max_tokens=100,
            hotspot_count=6
        )
        self.assertIn("[HARNESS_PREFERENCES & STAGE_GUARDS]", ctx)
        self.assertIn("STAGE:", ctx)
        self.assertLessEqual(estimate_tokens(ctx), 100)

    # 10. Fitness evaluation benchmark
    def test_harness_evaluate_fitness(self):
        eval_res = self.harness.evaluate_fitness()
        self.assertIn(eval_res["fitness_status"], ("OPTIMAL", "ADAPTING"))
        self.assertIn("alignment_score", eval_res)
        self.assertIn("zero_defect_success_rate", eval_res)
        self.assertGreaterEqual(eval_res["active_preferences_count"], 1)

    # 11. Markdown summary generation
    def test_harness_to_markdown_summary(self):
        summary = self.harness.to_markdown_summary(max_tokens=300)
        self.assertIn("<!-- cookiegli:preferences:start -->", summary)
        self.assertIn("<!-- cookiegli:preferences:end -->", summary)
        self.assertIn("Developer Preferences", summary)
        self.assertLessEqual(estimate_tokens(summary), 300)

    # 12. Atomic persistence and re-loading
    def test_harness_atomic_file_persistence(self):
        self.harness.record_preference(
            key="custom_pref",
            value=42,
            description="Custom user preference for testing",
            category="style"
        )
        self.harness.save()
        self.assertTrue(self.state_file.exists())

        # Load fresh instance
        fresh_harness = HarnessEngine(workspace_root=self.workspace_root, state_file=self.state_file)
        pref_keys = [p.key for p in fresh_harness.preferences.values()]
        self.assertIn("custom_pref", pref_keys)

    # 13. BoostEngine integration with Harness
    def test_boost_engine_integration_with_harness(self):
        # Create minimal source file so BoostEngine can analyze
        src_file = self.workspace_root / "src" / "sample.py"
        src_file.parent.mkdir(parents=True, exist_ok=True)
        src_file.write_text("def compute(x: int) -> int:\n    return x * 2\n", encoding="utf-8")

        with BoostEngine(workspace_root=self.workspace_root) as boost_engine:
            context = boost_engine.synthesize_task_context("Refactor compute function", max_tokens=600)
            self.assertIn("[HARNESS_PREFERENCES & STAGE_GUARDS]", context)
            self.assertIn("STAGE:", context)
            self.assertLessEqual(estimate_tokens(context), 600)

    # 14. TargetManager preferences sync
    def test_target_manager_preferences_sync(self):
        pref_summary = self.harness.to_markdown_summary(max_tokens=300)
        results = TargetManager.sync(
            target="all",
            workspace_root=self.workspace_root,
            genome_text="sample genome text",
            darwin_text="- [PATTERN] Sample pattern",
            preferences_text=pref_summary
        )
        self.assertIn("claude", results)
        self.assertIn("codex", results)
        self.assertIn("antigravity", results)

        claude_md = self.workspace_root / "CLAUDE.md"
        self.assertTrue(claude_md.exists())
        claude_text = claude_md.read_text(encoding="utf-8")
        self.assertIn("<!-- cookiegli:preferences:start -->", claude_text)
        self.assertIn("Developer Preferences", claude_text)

        agents_md = self.workspace_root / "AGENTS.md"
        self.assertTrue(agents_md.exists())
        agents_text = agents_md.read_text(encoding="utf-8")
        self.assertIn("<!-- cookiegli:preferences:start -->", agents_text)

    # 15. MCP tool: cookiegli_harness_status
    def test_mcp_harness_status_tool(self):
        with CookieGliMcpServer(workspace_root=self.workspace_root, profile="full") as server:
            res_str = server.handle_tool_call("cookiegli_harness_status", {})
            data = json.loads(res_str)
            self.assertIn("maturity", data)
            self.assertIn("alignment_score", data)
            self.assertIn("active_preferences", data)

    # 16. MCP tool: cookiegli_harness_feedback
    def test_mcp_harness_feedback_tool(self):
        with CookieGliMcpServer(workspace_root=self.workspace_root, profile="full") as server:
            res_str = server.handle_tool_call("cookiegli_harness_feedback", {
                "feedback_type": "correction",
                "content": "Do not write complex loops, instead use list comprehensions",
                "scope": "core"
            })
            data = json.loads(res_str)
            self.assertEqual(data["feedback_type"], "correction")
            self.assertGreaterEqual(len(data["learned_anti_patterns"]), 1)

    # 17. MCP tool: cookiegli_harness_eval
    def test_mcp_harness_eval_tool(self):
        with CookieGliMcpServer(workspace_root=self.workspace_root, profile="full") as server:
            res_str = server.handle_tool_call("cookiegli_harness_eval", {})
            data = json.loads(res_str)
            self.assertIn("fitness_status", data)
            self.assertIn("alignment_score", data)

    # 18. MCP full dispatch for harness actions
    def test_mcp_full_harness_actions(self):
        with CookieGliMcpServer(workspace_root=self.workspace_root, profile="full") as server:
            res_status = server.handle_tool_call("cookiegli_full", {"action": "harness"})
            self.assertIn("alignment_score", res_status)

            res_eval = server.handle_tool_call("cookiegli_full", {"action": "harness_eval"})
            self.assertIn("fitness_status", res_eval)

    # 19. CLI harness commands execution
    def test_cli_harness_commands(self):
        class MockArgs:
            pass

        # Test CLI status
        args_status = MockArgs()
        args_status.root = str(self.workspace_root)
        args_status.state = str(self.state_file)
        args_status.harness_cmd = 'status'
        args_status.json = True
        rc = cli_module.cmd_harness(args_status)
        self.assertEqual(rc, 0)

        # Test CLI feedback
        args_feed = MockArgs()
        args_feed.root = str(self.workspace_root)
        args_feed.state = str(self.state_file)
        args_feed.harness_cmd = 'feedback'
        args_feed.type = 'preference'
        args_feed.content = 'Always use dataclasses for configs'
        args_feed.scope = 'config'
        args_feed.task = 'Setup configs'
        args_feed.json = True
        rc_feed = cli_module.cmd_harness(args_feed)
        self.assertEqual(rc_feed, 0)

        # Test CLI eval
        args_eval = MockArgs()
        args_eval.root = str(self.workspace_root)
        args_eval.state = str(self.state_file)
        args_eval.harness_cmd = 'eval'
        args_eval.json = True
        rc_eval = cli_module.cmd_harness(args_eval)
        self.assertEqual(rc_eval, 0)

        # Test CLI history
        args_hist = MockArgs()
        args_hist.root = str(self.workspace_root)
        args_hist.state = str(self.state_file)
        args_hist.harness_cmd = 'history'
        args_hist.limit = 5
        args_hist.json = True
        rc_hist = cli_module.cmd_harness(args_hist)
        self.assertEqual(rc_hist, 0)


if __name__ == '__main__':
    unittest.main()
