import sys
import tempfile
import time
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.ast_scanner import CodeEntity, FileStructure
from cookiegli_core.cache_db import AstCache


class TestAstCache(unittest.TestCase):

    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.cache = AstCache(self.temp_dir.name)

    def tearDown(self):
        self.cache.close()
        try:
            self.temp_dir.cleanup()
        except Exception:
            pass

    def test_put_and_get_matching_mtime(self):
        struct = FileStructure(
            path="src/service.py",
            relative_path="src/service.py",
            language="Python",
            total_lines=100,
            classes=[CodeEntity(name="ServiceA", entity_type="class", signature="class ServiceA:", line_number=10)],
            functions=[CodeEntity(name="run", entity_type="function", signature="def run():", line_number=20)],
            imports_internal=["./utils"],
            imports_external=["requests"],
            is_minified=False
        )
        mtime = 1700000000.0
        sha = "fake_sha_256_hash"

        self.cache.put(struct, mtime, sha)
        cached = self.cache.get("src/service.py", mtime)

        self.assertIsNotNone(cached)
        self.assertEqual(cached.path, "src/service.py")
        self.assertEqual(len(cached.classes), 1)
        self.assertEqual(cached.classes[0].name, "ServiceA")
        self.assertEqual(cached.functions[0].name, "run")

    def test_cache_miss_on_mtime_change(self):
        struct = FileStructure(path="src/app.py", relative_path="src/app.py", language="Python", total_lines=50)
        self.cache.put(struct, 1000.0, "sha1")

        # Query with different mtime
        cached = self.cache.get("src/app.py", 2000.0)
        self.assertIsNone(cached)

    def test_prune_missing_files(self):
        s1 = FileStructure(path="src/file1.py", relative_path="src/file1.py", language="Python", total_lines=20)
        s2 = FileStructure(path="src/file2.py", relative_path="src/file2.py", language="Python", total_lines=30)
        self.cache.put(s1, 100.0, "sha1")
        self.cache.put(s2, 100.0, "sha2")

        self.assertEqual(self.cache.count(), 2)

        # File 2 was deleted in active paths
        pruned = self.cache.prune_missing(["src/file1.py"])
        self.assertEqual(pruned, 1)
        self.assertEqual(self.cache.count(), 1)


if __name__ == '__main__':
    unittest.main()
