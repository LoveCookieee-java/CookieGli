import tempfile
import unittest
from pathlib import Path

from cookiegli_core.monorepo_engine import MonorepoEngine
from cookiegli_core.genome_engine import estimate_tokens


class TestMonorepoEngine(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.temp_dir.name)

        # Setup synthetic multi-package monorepo
        # Package 1: auth-service (Python)
        pkg1 = self.root / "packages" / "auth-service"
        pkg1.mkdir(parents=True)
        (pkg1 / "pyproject.toml").write_text("[project]\nname='auth-service'", encoding='utf-8')
        (pkg1 / "auth.py").write_text("""
class AuthService:
    def verify_token(self, token: str) -> bool:
        return True
""", encoding='utf-8')

        # Package 2: web-dashboard (TypeScript)
        pkg2 = self.root / "packages" / "web-dashboard"
        pkg2.mkdir(parents=True)
        (pkg2 / "package.json").write_text('{"name": "@app/dashboard", "dependencies": {"@app/auth-service": "*"}}', encoding='utf-8')
        (pkg2 / "App.tsx").write_text("""
import { verify_token } from '@app/auth-service';
export const Dashboard = () => {
    return <div>Dashboard</div>;
};
""", encoding='utf-8')

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_discover_packages(self):
        engine = MonorepoEngine(str(self.root), use_cache=False)
        pkgs = engine.discover_packages()

        self.assertIn("auth-service", pkgs)
        self.assertIn("web-dashboard", pkgs)
        self.assertEqual(pkgs["auth-service"].pkg_type, "Python")
        self.assertEqual(pkgs["web-dashboard"].pkg_type, "Node/JS/TS")

    def test_monorepo_build_and_token_budget(self):
        engine = MonorepoEngine(str(self.root), use_cache=False)
        genome = engine.build()

        self.assertEqual(genome.total_files, 2)
        root_map = genome.to_root_compact(400)
        tokens = estimate_tokens(root_map)

        self.assertLess(tokens, 300)
        self.assertIn("auth-service", root_map)
        self.assertIn("web-dashboard", root_map)

    def test_monorepo_synthesize_task_context(self):
        engine = MonorepoEngine(str(self.root), use_cache=False)
        slice_ctx = engine.synthesize_task_context("Fix verify_token in auth-service", max_tokens=1000)

        self.assertIn("[ACTIVE_PACKAGE_SLICE: auth-service]", slice_ctx)
        self.assertIn("AuthService", slice_ctx)


if __name__ == '__main__':
    unittest.main()
