"""
Unit Tests for CookieGli GenomeEngine.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.genome_engine import GenomeEngine, ProjectGenome, estimate_tokens


class TestGenomeEngine(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

        (self.root / 'main.py').write_text(
            '"""Main entry point."""\nimport fastapi\nfrom src.auth_service import AuthService\napp = fastapi.FastAPI()\n',
            encoding='utf-8'
        )
        src_dir = self.root / 'src'
        src_dir.mkdir()
        (src_dir / 'auth_service.py').write_text(
            '"""Auth service core."""\nimport pydantic\nclass AuthService:\n    def authenticate_jwt(self, token: str) -> bool:\n        return True\n',
            encoding='utf-8'
        )
        (self.root / 'requirements.txt').write_text('fastapi\npydantic\n', encoding='utf-8')

    def tearDown(self):
        self.test_dir.cleanup()

    def test_build_genome_compact(self):
        engine = GenomeEngine(str(self.root))
        genome = engine.build()

        self.assertIsNotNone(genome)
        self.assertEqual(genome.dna.total_files, 2)
        self.assertIn('Python', genome.dna.languages)
        self.assertIn('main.py', genome.dna.entry_points)

        compact = genome.to_compact(max_tokens=1500)
        tokens = estimate_tokens(compact)
        self.assertLessEqual(tokens, 1500)
        self.assertIn('[ARCHITECTURE_DNA]', compact)
        self.assertIn('[API_REGISTRY]', compact)

    def test_synthesize_task_context_entity_targeting(self):
        engine = GenomeEngine(str(self.root))
        genome = engine.build()

        ctx = genome.synthesize_task_context("Refactor AuthService and fix authenticate_jwt error", max_tokens=1200)

        tokens = estimate_tokens(ctx)
        self.assertLessEqual(tokens, 1200)
        self.assertIn('AuthService', ctx)
        self.assertIn('authenticate_jwt', ctx)
        self.assertIn('target_classes:', ctx)


if __name__ == '__main__':
    unittest.main()
