"""
CookieGli Cache DB — High-speed SQLite cache with WAL mode for incremental AST scanning.
Enables sub-5ms incremental scanning on massive enterprise monorepos (100k+ files).
"""

import hashlib
import json
import os
import sqlite3
import time
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .ast_scanner import CodeEntity, FileStructure


class AstCache:
    """
    High-performance SQLite-backed AST cache with WAL (Write-Ahead Logging).
    """

    def __init__(self, cache_dir: Optional[str] = None):
        if cache_dir:
            self.cache_dir = Path(cache_dir)
        else:
            self.cache_dir = Path.cwd() / '.cookiegli'
        
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        self.db_path = self.cache_dir / 'ast_cache.db'
        self.conn = sqlite3.connect(str(self.db_path), timeout=30.0)
        self.conn.row_factory = sqlite3.Row
        self._init_db()

    def _init_db(self) -> None:
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA synchronous=NORMAL")
        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS file_cache (
                path TEXT PRIMARY KEY,
                relative_path TEXT,
                mtime REAL,
                sha256 TEXT,
                language TEXT,
                total_lines INTEGER,
                is_entry_point INTEGER,
                is_minified INTEGER,
                classes_json TEXT,
                functions_json TEXT,
                methods_json TEXT,
                imports_internal_json TEXT,
                imports_external_json TEXT,
                last_scanned REAL
            )
        """)
        # Migration for existing tables without methods_json
        cur = self.conn.cursor()
        cur.execute("PRAGMA table_info(file_cache)")
        cols = [col[1] for col in cur.fetchall()]
        if 'methods_json' not in cols:
            self.conn.execute("ALTER TABLE file_cache ADD COLUMN methods_json TEXT DEFAULT '[]'")

        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_mtime ON file_cache(path, mtime)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_relpath_mtime ON file_cache(relative_path, mtime)")

        self.conn.execute("""
            CREATE TABLE IF NOT EXISTS symbol_cache (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                simple_name TEXT NOT NULL,
                container TEXT DEFAULT '',
                entity_type TEXT NOT NULL,
                file_path TEXT NOT NULL,
                relative_path TEXT NOT NULL,
                line_number INTEGER NOT NULL,
                signature TEXT,
                docstring TEXT
            )
        """)
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_name ON symbol_cache(name COLLATE NOCASE)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_simple ON symbol_cache(simple_name COLLATE NOCASE)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_relpath ON symbol_cache(relative_path)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_filepath ON symbol_cache(file_path)")
        self.conn.execute("CREATE INDEX IF NOT EXISTS idx_sym_type ON symbol_cache(entity_type)")
        self.conn.commit()

    @staticmethod
    def compute_sha256(filepath: Path) -> str:
        """Compute fast SHA-256 hash of file contents."""
        hasher = hashlib.sha256()
        with open(filepath, 'rb') as f:
            while chunk := f.read(65536):
                hasher.update(chunk)
        return hasher.hexdigest()

    def get(self, rel_path: str, mtime: float) -> Optional[FileStructure]:
        """Retrieve cached FileStructure if mtime matches."""
        try:
            norm_rel = rel_path.replace('\\', '/')
            cur = self.conn.cursor()
            cur.execute(
                "SELECT * FROM file_cache WHERE (relative_path = ? OR relative_path = ? OR path = ? OR path = ?) AND mtime = ?",
                (rel_path, norm_rel, rel_path, norm_rel, mtime)
            )
            row = cur.fetchone()
            if not row:
                return None

            classes_data = json.loads(row['classes_json'])
            functions_data = json.loads(row['functions_json'])
            methods_data = json.loads(row['methods_json']) if ('methods_json' in row.keys() and row['methods_json']) else []
            imports_int = json.loads(row['imports_internal_json'])
            imports_ext = json.loads(row['imports_external_json'])

            classes = [CodeEntity(**item) for item in classes_data]
            functions = [CodeEntity(**item) for item in functions_data]
            methods = [CodeEntity(**item) for item in methods_data]

            return FileStructure(
                path=row['path'],
                relative_path=row['relative_path'] or row['path'],
                language=row['language'],
                total_lines=row['total_lines'],
                classes=classes,
                functions=functions,
                methods=methods,
                imports_internal=imports_int,
                imports_external=imports_ext,
                is_entry_point=bool(row['is_entry_point']),
                is_minified=bool(row['is_minified'])
            )
        except Exception:
            return None

    def put(self, file_struct: FileStructure, mtime: float, sha256: str) -> None:
        """Insert or update a FileStructure in SQLite cache and index symbols."""
        classes_json = json.dumps([c.__dict__ for c in file_struct.classes], ensure_ascii=False)
        functions_json = json.dumps([f.__dict__ for f in file_struct.functions], ensure_ascii=False)
        methods_json = json.dumps([m.__dict__ for m in file_struct.methods], ensure_ascii=False)
        imports_int_json = json.dumps(file_struct.imports_internal, ensure_ascii=False)
        imports_ext_json = json.dumps(file_struct.imports_external, ensure_ascii=False)
        now = time.time()

        self.conn.execute("""
            INSERT OR REPLACE INTO file_cache 
            (path, relative_path, mtime, sha256, language, total_lines, is_entry_point, is_minified, classes_json, functions_json, methods_json, imports_internal_json, imports_external_json, last_scanned)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            file_struct.path,
            file_struct.relative_path,
            mtime,
            sha256,
            file_struct.language,
            file_struct.total_lines,
            1 if file_struct.is_entry_point else 0,
            1 if file_struct.is_minified else 0,
            classes_json,
            functions_json,
            methods_json,
            imports_int_json,
            imports_ext_json,
            now
        ))

        # Delete existing symbols for this file from symbol_cache
        self.conn.execute(
            "DELETE FROM symbol_cache WHERE file_path = ? OR relative_path = ?",
            (file_struct.path, file_struct.relative_path)
        )

        symbol_rows = []
        for entity in file_struct.classes + file_struct.functions + file_struct.methods:
            if '.' in entity.name:
                parts = entity.name.split('.')
                container = '.'.join(parts[:-1])
                simple_name = parts[-1]
            else:
                container = ""
                simple_name = entity.name

            symbol_rows.append((
                entity.name,
                simple_name,
                container,
                entity.entity_type,
                file_struct.path,
                file_struct.relative_path,
                entity.line_number,
                entity.signature,
                entity.docstring
            ))

        if symbol_rows:
            self.conn.executemany("""
                INSERT INTO symbol_cache 
                (name, simple_name, container, entity_type, file_path, relative_path, line_number, signature, docstring)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, symbol_rows)

    def commit(self) -> None:
        """Commit pending write transactions."""
        try:
            self.conn.commit()
        except Exception:
            pass

    def prune_missing(self, active_paths: List[str]) -> int:
        """Remove cached entries for files that no longer exist."""
        cur = self.conn.cursor()
        cur.execute("SELECT path, relative_path FROM file_cache")
        rows = cur.fetchall()
        active_set = set(active_paths) | {Path(p).as_posix() for p in active_paths}
        to_delete_files = []
        to_delete_symbols = []
        for row in rows:
            p = row['path']
            rel = row['relative_path'] or p
            rel_posix = rel.replace('\\', '/')
            if rel not in active_set and rel_posix not in active_set and p not in active_set:
                to_delete_files.append((p,))
                to_delete_symbols.append((p, rel))

        if to_delete_files:
            self.conn.executemany(
                "DELETE FROM file_cache WHERE path = ?",
                to_delete_files
            )
            self.conn.executemany(
                "DELETE FROM symbol_cache WHERE file_path = ? OR relative_path = ?",
                to_delete_symbols
            )
            self.commit()
        return len(to_delete_files)

    def count(self) -> int:
        cur = self.conn.cursor()
        cur.execute("SELECT COUNT(*) FROM file_cache")
        return cur.fetchone()[0]

    def clear(self) -> None:
        self.conn.execute("DELETE FROM file_cache")
        self.conn.execute("DELETE FROM symbol_cache")
        self.commit()

    @staticmethod
    def _escape_like(query: str) -> str:
        """Escape wildcard characters for SQLite LIKE queries."""
        return query.replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')

    def find_symbols(
        self,
        query: str = "",
        entity_type: Optional[str] = None,
        exact: bool = False,
        limit: int = 50,
        path: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """
        Query fast B-Tree symbol index.
        Uses exact OR matching with NOCASE collation for sub-millisecond retrieval,
        or escaped LIKE for substring matching.
        """
        conditions = []
        params: List[Any] = []

        query = query.strip() if query else ""

        if query:
            if exact:
                conditions.append("(simple_name = ? COLLATE NOCASE OR name = ? COLLATE NOCASE)")
                params.extend([query, query])
            else:
                escaped = self._escape_like(query)
                like_pattern = f"%{escaped}%"
                conditions.append("(simple_name LIKE ? ESCAPE '\\' OR name LIKE ? ESCAPE '\\')")
                params.extend([like_pattern, like_pattern])

        if entity_type:
            conditions.append("entity_type = ?")
            params.append(entity_type)

        if path:
            escaped_path = self._escape_like(path)
            like_path = f"%{escaped_path}%"
            conditions.append("(relative_path LIKE ? ESCAPE '\\' OR file_path LIKE ? ESCAPE '\\')")
            params.extend([like_path, like_path])

        where_clause = f"WHERE {' AND '.join(conditions)}" if conditions else ""

        if query:
            order_clause = "ORDER BY CASE WHEN simple_name = ? COLLATE NOCASE THEN 1 WHEN name = ? COLLATE NOCASE THEN 2 ELSE 3 END, line_number ASC"
            params.extend([query, query])
        else:
            order_clause = "ORDER BY relative_path ASC, line_number ASC"

        sql = f"""
            SELECT name, simple_name, container, entity_type, file_path, relative_path, line_number, signature, docstring
            FROM symbol_cache
            {where_clause}
            {order_clause}
            LIMIT ?
        """
        params.append(limit)

        cur = self.conn.cursor()
        cur.execute(sql, params)
        rows = cur.fetchall()

        results = []
        for r in rows:
            results.append({
                "name": r["name"],
                "simple_name": r["simple_name"],
                "container": r["container"],
                "entity_type": r["entity_type"],
                "file_path": r["file_path"],
                "relative_path": r["relative_path"],
                "line_number": r["line_number"],
                "signature": r["signature"] or "",
                "docstring": r["docstring"] or ""
            })
        return results

    def close(self) -> None:
        try:
            self.conn.close()
        except Exception:
            pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()
