"""
Target Adapters for CookieGli Universal AI Engine.
Supports non-destructive, bounded synchronization into:
- Claude Code (CLAUDE.md)
- OpenAI Codex & Agents (AGENTS.md)
- Google Antigravity (.agents/GENOME.md, .agents/AGENTS.md)
- Cursor (.cursor/rules/genome.mdc, .cursorrules)
- Windsurf (.windsurfrules)
"""

import os
import re
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TargetManager:
    """Manages idempotent, bounded injection of Genome and Darwin memory into various AI agent configs."""

    GENOME_START_TAG = "<!-- cookiegli:genome:start -->"
    GENOME_END_TAG = "<!-- cookiegli:genome:end -->"
    DARWIN_START_TAG = "<!-- cookiegli:darwin:start -->"
    DARWIN_END_TAG = "<!-- cookiegli:darwin:end -->"
    PREFERENCES_START_TAG = "<!-- cookiegli:preferences:start -->"
    PREFERENCES_END_TAG = "<!-- cookiegli:preferences:end -->"

    SUPPORTED_TARGETS = ("claude", "codex", "antigravity", "cursor", "windsurf", "all")

    @classmethod
    def _clean_darwin_body(cls, darwin_text: Optional[str]) -> Optional[str]:
        if not darwin_text:
            return None
        from .distiller import clean_darwin_summary
        return clean_darwin_summary(darwin_text)

    @classmethod
    def _clean_preferences_body(cls, pref_text: Optional[str]) -> Optional[str]:
        if not pref_text:
            return None
        cleaned = re.sub(r'<!--\s*(?:cookie|darwin)[\w:\-]*\s*-->', '', pref_text, flags=re.IGNORECASE)
        lines = []
        for line in cleaned.splitlines():
            s = line.strip()
            if not s:
                continue
            if re.match(r'^#{1,4}\s*(?:🧬|Developer|Preferences|Invariant)', s, flags=re.IGNORECASE):
                continue
            lines.append(s)
        return "\n".join(lines)

    @staticmethod
    def _inject_bounded_block(
        content: str,
        start_tag: str,
        end_tag: str,
        new_block_body: str,
        header_hint: str = ""
    ) -> str:
        """Replaces or appends a bounded block cleanly."""
        block = f"{start_tag}\n{new_block_body.strip()}\n{end_tag}"
        # Target unindented block at column 0 first to protect indented code examples
        pattern_unindented = re.compile(rf'^[ \t]*{re.escape(start_tag)}[ \t]*\r?$.*?^[ \t]*{re.escape(end_tag)}[ \t]*\r?$', re.DOTALL | re.MULTILINE)
        matches = list(pattern_unindented.finditer(content))
        if not matches:
            pattern_any = re.compile(rf'{re.escape(start_tag)}.*?{re.escape(end_tag)}', re.DOTALL)
            matches = list(pattern_any.finditer(content))

        if matches:
            target_match = matches[-1]
            res = content[:target_match.start()] + block + content[target_match.end():]
            if not res.endswith('\n'):
                res += '\n'
            return res

        # If tag not present, append to end
        stripped = content.strip()
        if stripped:
            res = f"{stripped}\n\n{header_hint}\n{block}\n" if header_hint else f"{stripped}\n\n{block}\n"
        else:
            res = f"{header_hint}\n{block}\n" if header_hint else f"{block}\n"
        if not res.endswith('\n'):
            res += '\n'
        return res

    @staticmethod
    def _write_file_idempotent(path: Path, content: str, encoding: str = "utf-8") -> bool:
        """Write content to path only if content differs, preserving mtime if unchanged."""
        if path.exists():
            try:
                existing = path.read_text(encoding=encoding)
                if existing == content:
                    return False
            except Exception:
                pass
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding=encoding)
        return True

    @classmethod
    def sync_claude(
        cls,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> Path:
        """Syncs into CLAUDE.md at the workspace root."""
        claude_md = workspace_root / "CLAUDE.md"
        existing = claude_md.read_text(encoding="utf-8") if claude_md.exists() else "# Claude Code Project Instructions\n"

        updated = existing
        if genome_text:
            genome_body = f"### 🧬 Project AST Genome (<600 tokens)\n```\n{genome_text.strip()}\n```"
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, genome_body, "## Architecture & Codebase Map"
            )
        if darwin_text:
            cleaned = cls._clean_darwin_body(darwin_text)
            darwin_body = f"### 🧬 Darwin Learned Best Practices\n{cleaned.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Learned Engineering Patterns"
            )
        if preferences_text:
            cleaned_pref = cls._clean_preferences_body(preferences_text)
            pref_body = f"### 🧬 Developer Preferences & Invariant Guards\n{cleaned_pref.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.PREFERENCES_START_TAG, cls.PREFERENCES_END_TAG, pref_body, "## Developer Preferences & Invariants"
            )

        cls._write_file_idempotent(claude_md, updated)
        return claude_md

    @classmethod
    def sync_codex(
        cls,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> Path:
        """Syncs into AGENTS.md at workspace root for OpenAI Codex & Agents."""
        agents_md = workspace_root / "AGENTS.md"
        existing = agents_md.read_text(encoding="utf-8") if agents_md.exists() else "# OpenAI Codex & Agent Instructions\n"

        updated = existing
        if genome_text:
            genome_body = f"### 🧬 Repository AST Genome\n```\n{genome_text.strip()}\n```"
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, genome_body, "## Architecture Context"
            )
        if darwin_text:
            cleaned = cls._clean_darwin_body(darwin_text)
            darwin_body = f"### 🧬 System Priors & Darwin Learnings\n{cleaned.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Operational Priors"
            )
        if preferences_text:
            cleaned_pref = cls._clean_preferences_body(preferences_text)
            pref_body = f"### 🧬 Developer Preferences & Invariant Guards\n{cleaned_pref.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.PREFERENCES_START_TAG, cls.PREFERENCES_END_TAG, pref_body, "## Developer Preferences"
            )

        cls._write_file_idempotent(agents_md, updated)
        return agents_md

    @classmethod
    def sync_antigravity(
        cls,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> Tuple[Optional[Path], Optional[Path]]:
        """Syncs into .agents/GENOME.md and .agents/AGENTS.md for Google Antigravity."""
        agents_dir = workspace_root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        g_path = None
        d_path = None

        if genome_text:
            g_path = agents_dir / "GENOME.md"
            cls._write_file_idempotent(g_path, genome_text.strip() + "\n")

        if darwin_text or preferences_text:
            d_path = agents_dir / "AGENTS.md"
            existing = d_path.read_text(encoding="utf-8") if d_path.exists() else "# Antigravity Operating Ruleset\n"
            updated = existing

            if darwin_text:
                cleaned = cls._clean_darwin_body(darwin_text)
                darwin_body = f"### 🧬 Darwin Learned Patterns & Best Practices\n{cleaned.strip()}"
                legacy_start = "<!-- darwin:learnings:start -->"
                legacy_end = "<!-- darwin:learnings:end -->"
                if legacy_start in updated and legacy_end in updated:
                    updated = cls._inject_bounded_block(updated, legacy_start, legacy_end, darwin_body)
                else:
                    updated = cls._inject_bounded_block(updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Operational Rules")

            if preferences_text:
                cleaned_pref = cls._clean_preferences_body(preferences_text)
                pref_body = f"### 🧬 Developer Preferences & Invariant Guards\n{cleaned_pref.strip()}"
                updated = cls._inject_bounded_block(updated, cls.PREFERENCES_START_TAG, cls.PREFERENCES_END_TAG, pref_body, "## Developer Preferences")

            cls._write_file_idempotent(d_path, updated)

        return g_path, d_path

    @classmethod
    def sync_cursor(
        cls,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> List[Path]:
        """Syncs into .cursor/rules/genome.mdc and .cursorrules for Cursor IDE."""
        rules_dir = workspace_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        if genome_text or darwin_text or preferences_text:
            mdc_path = rules_dir / "cookiegli_context.mdc"
            content = "---\ndescription: High-Density AST Genome and Darwin Patterns\nglobs: *\n---\n\n"
            content += "# CookieGli Project Intelligence\n\n"
            if genome_text:
                content += f"## AST Codebase Genome\n```\n{genome_text.strip()}\n```\n\n"
            if darwin_text:
                cleaned = cls._clean_darwin_body(darwin_text)
                content += f"## Verified Operational Patterns\n{cleaned.strip()}\n\n"
            if preferences_text:
                cleaned_pref = cls._clean_preferences_body(preferences_text)
                content += f"## Developer Preferences\n{cleaned_pref.strip()}\n"
            cls._write_file_idempotent(mdc_path, content)
            paths.append(mdc_path)

        cursorrules = workspace_root / ".cursorrules"
        existing = cursorrules.read_text(encoding="utf-8") if cursorrules.exists() else "# Cursor Project Rules\n"
        updated = existing
        if genome_text:
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, f"```\n{genome_text.strip()}\n```", "## Genome"
            )
        if darwin_text:
            cleaned = cls._clean_darwin_body(darwin_text)
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, cleaned.strip(), "## Learned Best Practices"
            )
        if preferences_text:
            cleaned_pref = cls._clean_preferences_body(preferences_text)
            updated = cls._inject_bounded_block(
                updated, cls.PREFERENCES_START_TAG, cls.PREFERENCES_END_TAG, cleaned_pref.strip(), "## Developer Preferences"
            )
        cls._write_file_idempotent(cursorrules, updated)
        paths.append(cursorrules)

        return paths

    @classmethod
    def sync_windsurf(
        cls,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> Path:
        """Syncs into .windsurfrules for Windsurf / Cascade."""
        windsurf_file = workspace_root / ".windsurfrules"
        existing = windsurf_file.read_text(encoding="utf-8") if windsurf_file.exists() else "# Windsurf Cascade Rules\n"
        updated = existing
        if genome_text:
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, f"```\n{genome_text.strip()}\n```", "## Codebase Genome"
            )
        if darwin_text:
            cleaned = cls._clean_darwin_body(darwin_text)
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, cleaned.strip(), "## Verified Practices"
            )
        if preferences_text:
            cleaned_pref = cls._clean_preferences_body(preferences_text)
            updated = cls._inject_bounded_block(
                updated, cls.PREFERENCES_START_TAG, cls.PREFERENCES_END_TAG, cleaned_pref.strip(), "## Developer Preferences"
            )
        cls._write_file_idempotent(windsurf_file, updated)
        return windsurf_file

    @classmethod
    def sync(
        cls,
        target: str,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None,
        preferences_text: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """Syncs genome, darwin, and harness preferences data to one or all supported agent targets."""
        target = target.lower().strip()
        workspace_root = workspace_root.resolve()
        results: Dict[str, List[str]] = {}

        if target not in cls.SUPPORTED_TARGETS:
            raise ValueError(f"Unsupported target '{target}'. Choose from: {', '.join(cls.SUPPORTED_TARGETS)}")

        targets_to_run = ["claude", "codex", "antigravity", "cursor", "windsurf"] if target == "all" else [target]

        for t in targets_to_run:
            if t == "claude":
                p = cls.sync_claude(workspace_root, genome_text, darwin_text, preferences_text)
                results["claude"] = [str(p)]
            elif t == "codex":
                p = cls.sync_codex(workspace_root, genome_text, darwin_text, preferences_text)
                results["codex"] = [str(p)]
            elif t == "antigravity":
                gp, dp = cls.sync_antigravity(workspace_root, genome_text, darwin_text, preferences_text)
                results["antigravity"] = [str(x) for x in (gp, dp) if x]
            elif t == "cursor":
                ps = cls.sync_cursor(workspace_root, genome_text, darwin_text, preferences_text)
                results["cursor"] = [str(x) for x in ps]
            elif t == "windsurf":
                p = cls.sync_windsurf(workspace_root, genome_text, darwin_text, preferences_text)
                results["windsurf"] = [str(p)]

        return results
