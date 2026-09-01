"""
Unit Tests for CookieGli AstScanner.
"""

import os
import sys
import tempfile
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / 'src'))

from cookiegli_core.ast_scanner import AstScanner, CodeEntity, FileStructure


class TestAstScanner(unittest.TestCase):
    def setUp(self):
        self.test_dir = tempfile.TemporaryDirectory()
        self.root = Path(self.test_dir.name)

        py_code = '''"""Sample module docstring."""
import os
import sys
from typing import List, Optional
import requests
from .local_mod import helper

class Calculator:
    """A sample calculator class."""
    def __init__(self, val: int = 0):
        self.val = val

    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

async def fetch_data(url: str) -> Optional[dict]:
    """Async fetch function."""
    return None
'''
        (self.root / 'sample.py').write_text(py_code, encoding='utf-8')

        ts_code = '''
import { useState, useEffect } from "react";
import axios from "axios";
import { format } from "./utils";

export interface UserSession {
    token: string;
    expiresIn: number;
}

export class DataManager extends BaseManager {
    constructor() {}
}

export const handleLogin = async (username: string, pass: string): Promise<UserSession> => {
    return { token: "abc", expiresIn: 3600 };
};

export function processItems(items) {
    return items.map(x => x * 2);
}
'''
        (self.root / 'auth.tsx').write_text(ts_code, encoding='utf-8')

        min_code = 'var a=1;' + 'console.log(a);'*500
        (self.root / 'bundle.min.js').write_text(min_code, encoding='utf-8')
        (self.root / 'vendor.js').write_text(min_code, encoding='utf-8')

    def tearDown(self):
        self.test_dir.cleanup()

    def test_scan_python_file(self):
        scanner = AstScanner(str(self.root))
        results = scanner.scan()
        py_res = next((r for r in results if r.relative_path == 'sample.py'), None)

        self.assertIsNotNone(py_res)
        self.assertEqual(py_res.language, 'Python')
        self.assertEqual(len(py_res.classes), 1)
        self.assertEqual(py_res.classes[0].name, 'Calculator')
        self.assertIn('add', py_res.classes[0].signature)

        func_names = [f.name for f in py_res.functions]
        self.assertIn('fetch_data', func_names)

        self.assertIn('requests', py_res.imports_external)
        self.assertNotIn('os', py_res.imports_external)

    def test_scan_typescript_and_arrow_functions(self):
        scanner = AstScanner(str(self.root))
        results = scanner.scan()
        ts_res = next((r for r in results if r.relative_path == 'auth.tsx'), None)

        self.assertIsNotNone(ts_res)
        self.assertEqual(ts_res.language, 'React TSX')

        class_names = [c.name for c in ts_res.classes]
        self.assertIn('UserSession', class_names)
        self.assertIn('DataManager', class_names)

        func_names = [f.name for f in ts_res.functions]
        self.assertIn('handleLogin', func_names)
        self.assertIn('processItems', func_names)

    def test_minified_file_guard(self):
        scanner = AstScanner(str(self.root))
        results = scanner.scan()
        scanned_paths = [r.relative_path for r in results]

        self.assertNotIn('bundle.min.js', scanned_paths)
        self.assertNotIn('vendor.js', scanned_paths)


if __name__ == '__main__':
    unittest.main()
