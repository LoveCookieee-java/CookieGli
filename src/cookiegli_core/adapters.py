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
from pathlib import Path
from typing import Dict, List, Optional, Tuple


class TargetManager:
    """Manages idempotent, bounded injection of Genome and Darwin memory into various AI agent configs."""

    GENOME_START_TAG = "<!-- cookiegli:genome:start -->"
    GENOME_END_TAG = "<!-- cookiegli:genome:end -->"
    DARWIN_START_TAG = "<!-- cookiegli:darwin:start -->"
    DARWIN_END_TAG = "<!-- cookiegli:darwin:end -->"

    SUPPORTED_TARGETS = ("claude", "codex", "antigravity", "cursor", "windsurf", "all")

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
        if start_tag in content and end_tag in content:
            pre = content.split(start_tag)[0]
            post = content.split(end_tag)[1]
            return f"{pre}{block}{post}"
        
        # If tag not present, append to end
        stripped = content.strip()
        if stripped:
            return f"{stripped}\n\n{header_hint}\n{block}\n"
        return f"{header_hint}\n{block}\n" if header_hint else f"{block}\n"

    @classmethod
    def sync_claude(cls, workspace_root: Path, genome_text: Optional[str] = None, darwin_text: Optional[str] = None) -> Path:
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
            darwin_body = f"### 🧬 Darwin Learned Best Practices\n{darwin_text.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Learned Engineering Patterns"
            )

        claude_md.write_text(updated, encoding="utf-8")
        return claude_md

    @classmethod
    def sync_codex(cls, workspace_root: Path, genome_text: Optional[str] = None, darwin_text: Optional[str] = None) -> Path:
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
            darwin_body = f"### 🧬 System Priors & Darwin Learnings\n{darwin_text.strip()}"
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Operational Priors"
            )

        agents_md.write_text(updated, encoding="utf-8")
        return agents_md

    @classmethod
    def sync_antigravity(cls, workspace_root: Path, genome_text: Optional[str] = None, darwin_text: Optional[str] = None) -> Tuple[Optional[Path], Optional[Path]]:
        """Syncs into .agents/GENOME.md and .agents/AGENTS.md for Google Antigravity."""
        agents_dir = workspace_root / ".agents"
        agents_dir.mkdir(parents=True, exist_ok=True)

        g_path = None
        d_path = None

        if genome_text:
            g_path = agents_dir / "GENOME.md"
            g_path.write_text(genome_text.strip() + "\n", encoding="utf-8")

        if darwin_text:
            d_path = agents_dir / "AGENTS.md"
            existing = d_path.read_text(encoding="utf-8") if d_path.exists() else "# Antigravity Operating Ruleset\n"
            darwin_body = f"### 🧬 Darwin Learned Patterns & Best Practices\n{darwin_text.strip()}"
            legacy_start = "<!-- darwin:learnings:start -->"
            legacy_end = "<!-- darwin:learnings:end -->"
            if legacy_start in existing and legacy_end in existing:
                updated = cls._inject_bounded_block(existing, legacy_start, legacy_end, darwin_body)
            else:
                updated = cls._inject_bounded_block(existing, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_body, "## Operational Rules")
            d_path.write_text(updated, encoding="utf-8")

        return g_path, d_path

    @classmethod
    def sync_cursor(cls, workspace_root: Path, genome_text: Optional[str] = None, darwin_text: Optional[str] = None) -> List[Path]:
        """Syncs into .cursor/rules/genome.mdc and .cursorrules for Cursor IDE."""
        rules_dir = workspace_root / ".cursor" / "rules"
        rules_dir.mkdir(parents=True, exist_ok=True)
        paths = []

        if genome_text or darwin_text:
            mdc_path = rules_dir / "cookiegli_context.mdc"
            content = "---\ndescription: High-Density AST Genome and Darwin Patterns\nglobs: *\n---\n\n"
            content += "# CookieGli Project Intelligence\n\n"
            if genome_text:
                content += f"## AST Codebase Genome\n```\n{genome_text.strip()}\n```\n\n"
            if darwin_text:
                content += f"## Verified Operational Patterns\n{darwin_text.strip()}\n"
            mdc_path.write_text(content, encoding="utf-8")
            paths.append(mdc_path)

        cursorrules = workspace_root / ".cursorrules"
        existing = cursorrules.read_text(encoding="utf-8") if cursorrules.exists() else "# Cursor Project Rules\n"
        updated = existing
        if genome_text:
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, f"```\n{genome_text.strip()}\n```", "## Genome"
            )
        if darwin_text:
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_text.strip(), "## Learned Best Practices"
            )
        cursorrules.write_text(updated, encoding="utf-8")
        paths.append(cursorrules)

        return paths

    @classmethod
    def sync_windsurf(cls, workspace_root: Path, genome_text: Optional[str] = None, darwin_text: Optional[str] = None) -> Path:
        """Syncs into .windsurfrules for Windsurf / Cascade."""
        windsurf_file = workspace_root / ".windsurfrules"
        existing = windsurf_file.read_text(encoding="utf-8") if windsurf_file.exists() else "# Windsurf Cascade Rules\n"
        updated = existing
        if genome_text:
            updated = cls._inject_bounded_block(
                updated, cls.GENOME_START_TAG, cls.GENOME_END_TAG, f"```\n{genome_text.strip()}\n```", "## Codebase Genome"
            )
        if darwin_text:
            updated = cls._inject_bounded_block(
                updated, cls.DARWIN_START_TAG, cls.DARWIN_END_TAG, darwin_text.strip(), "## Verified Practices"
            )
        windsurf_file.write_text(updated, encoding="utf-8")
        return windsurf_file

    @classmethod
    def sync(
        cls,
        target: str,
        workspace_root: Path,
        genome_text: Optional[str] = None,
        darwin_text: Optional[str] = None
    ) -> Dict[str, List[str]]:
        """Syncs genome and darwin data to one or all supported agent targets."""
        target = target.lower().strip()
        workspace_root = workspace_root.resolve()
        results: Dict[str, List[str]] = {}

        if target not in cls.SUPPORTED_TARGETS:
            raise ValueError(f"Unsupported target '{target}'. Choose from: {', '.join(cls.SUPPORTED_TARGETS)}")

        targets_to_run = ["claude", "codex", "antigravity", "cursor", "windsurf"] if target == "all" else [target]

        for t in targets_to_run:
            if t == "claude":
                p = cls.sync_claude(workspace_root, genome_text, darwin_text)
                results["claude"] = [str(p)]
            elif t == "codex":
                p = cls.sync_codex(workspace_root, genome_text, darwin_text)
                results["codex"] = [str(p)]
            elif t == "antigravity":
                gp, dp = cls.sync_antigravity(workspace_root, genome_text, darwin_text)
                results["antigravity"] = [str(x) for x in (gp, dp) if x]
            elif t == "cursor":
                ps = cls.sync_cursor(workspace_root, genome_text, darwin_text)
                results["cursor"] = [str(x) for x in ps]
            elif t == "windsurf":
                p = cls.sync_windsurf(workspace_root, genome_text, darwin_text)
                results["windsurf"] = [str(p)]

        return results
