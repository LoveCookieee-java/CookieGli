"""
CookieGli Boost Engine — High-precision Layer 2 Dynamic Task Tail synthesizer for 2026 Frontier Models.
Integrates SQLite FTS5 BM25+ symbol ranking, Git blast radius analysis, surgical code skeletonization,
and blast-depth reasoning calibration.
Zero external dependencies. 100% pure Python stdlib.
"""

import os
from pathlib import Path
import re
from typing import Any, Dict, List, Optional, Union

from .ast_scanner import AstScanner
from .cache_db import AstCache
from .blast_radius import BlastRadiusEngine, BlastRadiusReport
from .skeletonizer import CodeSkeletonizer, SkeletonResult
from .genome_engine import GenomeEngine, estimate_tokens
from .adapters import TargetManager
from .darwin_memory import DarwinMemory
from .distiller import resolve_darwin_state_path


def compute_reasoning_calibration(blast_depth: int, impact_level: str) -> str:
    """
    Synthesize reasoning calibration guidance for July-September 2026 Frontier Models.
    Calibrates thinking budget based on blast radius depth to prevent token waste and cost traps.
    """
    if blast_depth <= 1:
        effort = "LOW"
        guidance = "Targeted localized change. Minimize reasoning tokens to prevent output billing surcharge."
        gpt_spec = "effort=low"
        claude_spec = "thinking: low (budget ~ 1024-2048 tokens)"
        gemini_spec = "thinking: low / off"
        deepseek_spec = "thinking: low"
    elif blast_depth == 2:
        effort = "MEDIUM"
        guidance = "Direct callers impacted. Verify function contracts and direct consumer interface stability."
        gpt_spec = "effort=medium"
        claude_spec = "thinking: medium (budget ~ 4096 tokens)"
        gemini_spec = "thinking: medium"
        deepseek_spec = "thinking: medium"
    else:
        effort = "HIGH"
        guidance = "Transitive architectural impact. Deep verification of ripple blast and invariant safety required."
        gpt_spec = "effort=high"
        claude_spec = "thinking: high (budget ~ 8192-16384 tokens)"
        gemini_spec = "thinking: high"
        deepseek_spec = "thinking: high"

    lines = [
        "[REASONING_CALIBRATION_2026]",
        f"blast_depth: {blast_depth} | impact: {impact_level} | effort: {effort}",
        f"guidance: {guidance}",
        f"models: GPT-6 Astra ({gpt_spec}), GPT-5.6 Sol ({gpt_spec}), Claude Opus 5 / Fable 5.1 ({claude_spec}), Gemini 3.7 Flash ({gemini_spec}), Kimi K3 / DeepSeek-V4 ({deepseek_spec})"
    ]
    return "\n".join(lines)


class BoostEngine:
    """
    CookieGli Boost Engine for 2026 Frontier AI Models.
    Manages Layer 1 static anchor initialization and Layer 2 on-demand dynamic task synthesis.
    """

    def __init__(
        self,
        workspace_root: Optional[Union[str, Path]] = None,
        use_cache: bool = True,
        cache_dir: Optional[str] = None
    ):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        self.use_cache = use_cache
        self.cache_dir = Path(cache_dir) if cache_dir else (self.workspace_root / '.cookiegli')
        self.cache: Optional[AstCache] = None
        if self.use_cache:
            try:
                self.cache = AstCache(str(self.cache_dir))
            except Exception:
                self.cache = None

        self.blast_engine = BlastRadiusEngine(str(self.workspace_root), use_cache=use_cache, cache_dir=str(self.cache_dir))
        self.skeletonizer = CodeSkeletonizer(str(self.workspace_root), use_cache=use_cache, cache_dir=str(self.cache_dir))

    def close(self) -> None:
        """Release SQLite and engine resources cleanly."""
        if self.cache:
            try:
                self.cache.close()
            except Exception:
                pass
            self.cache = None

        if self.blast_engine:
            try:
                self.blast_engine.close()
            except Exception:
                pass

        if self.skeletonizer:
            try:
                self.skeletonizer.close()
            except Exception:
                pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    def __del__(self):
        self.close()

    def init_project(self, target: str = "all", max_tokens: int = 600) -> Dict[str, Any]:
        """
        One-command initialization:
        1. Full AST scan to populate SQLite B-Tree and FTS5 symbol index.
        2. Build Layer 1 ProjectGenome (Token 0 byte-stable anchor).
        3. Synchronize static anchor to target configurations (CLAUDE.md, AGENTS.md, etc.).
        """
        # Step 1: Scan codebase to populate cache and FTS5
        with AstScanner(str(self.workspace_root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
            files = scanner.scan()

        total_files = len(files)

        # Step 2: Build ProjectGenome
        with GenomeEngine(str(self.workspace_root), use_cache=True, cache_dir=str(self.cache_dir)) as genome_engine:
            genome = genome_engine.build()
            genome_text = genome.to_compact(max_tokens)

        # Step 3: Load Darwin memory summary
        state_file = resolve_darwin_state_path(self.workspace_root)
        darwin_text = None
        if state_file.exists():
            memory = DarwinMemory(state_file=str(state_file))
            darwin_text = memory.to_markdown_summary(max_tokens=400, include_telemetry=False)

        # Step 4: Sync to targets
        synced = TargetManager.sync(
            target=target,
            workspace_root=self.workspace_root,
            genome_text=genome_text,
            darwin_text=darwin_text
        )

        return {
            "total_files": total_files,
            "genome_hash": genome.genome_hash,
            "synced_targets": synced,
            "status": "success"
        }

    def synthesize_task_context(self, task: str, max_tokens: int = 600) -> str:
        """
        Synthesize Layer 2 Dynamic Task Tail context slice strictly <= max_tokens.
        Extracts BM25 symbols, blast radius impact, focus skeleton, and 2026 reasoning calibration.
        """
        task_clean = task.strip() if task else "General Task"

        # 1. Match symbols via BM25 (auto-populate cache if empty)
        matched_symbols: List[Dict[str, Any]] = []
        if self.cache:
            if self.cache.count() == 0:
                try:
                    with AstScanner(str(self.workspace_root), use_cache=True, cache_dir=str(self.cache_dir)) as scanner:
                        scanner.scan()
                except Exception:
                    pass
            try:
                matched_symbols = self.cache.search_bm25(task_clean, limit=5)
            except Exception:
                matched_symbols = []

        top_symbol: Optional[Dict[str, Any]] = matched_symbols[0] if matched_symbols else None
        target_file: Optional[str] = None
        focus_name: Optional[str] = None

        if top_symbol:
            target_file = top_symbol.get("relative_path") or top_symbol.get("file_path")
            focus_name = top_symbol.get("simple_name") or top_symbol.get("name")

        # 2. Blast Radius Analysis
        report: Optional[BlastRadiusReport] = None
        try:
            if target_file:
                report = self.blast_engine.analyze(target_files=[target_file], symbol=focus_name)
            else:
                report = self.blast_engine.analyze()
        except Exception:
            report = None

        # 3. Determine Blast Depth & Impact
        if report:
            impact_level = report.impact_level
            if report.transitive_consumers or impact_level in ("HIGH", "CRITICAL"):
                blast_depth = 3
            elif report.direct_consumers or impact_level == "MEDIUM":
                blast_depth = 2
            elif report.target_files:
                blast_depth = 1
            else:
                blast_depth = 0
            test_cmd = report.recommended_test_command
            targeted_tests = report.targeted_tests
        else:
            impact_level = "LOW"
            blast_depth = 0
            test_cmd = "python -m unittest discover -s tests -v"
            targeted_tests = []

        # 4. Calibration block
        calib_block = compute_reasoning_calibration(blast_depth, impact_level)

        # 5. BM25 Symbols block
        sym_lines = ["[TARGET_SYMBOLS_BM25]"]
        if matched_symbols:
            for s in matched_symbols[:4]:
                score_str = f" [score:{s['score']}]" if 'score' in s else ""
                sym_lines.append(f"• {s['entity_type']} `{s['name']}` -> {s['relative_path']}:{s['line_number']}{score_str}")
        else:
            sym_lines.append("(no direct symbol matches found)")
        sym_block = "\n".join(sym_lines)

        # 6. Test command & blast impact block
        test_lines = ["[BLAST_RADIUS_TARGETED_TESTS]"]
        test_lines.append(f"test_command: {test_cmd}")
        if targeted_tests:
            test_lines.append(f"targeted_tests: {', '.join(targeted_tests[:3])}")
        if report and report.direct_consumers:
            test_lines.append(f"direct_consumers: {', '.join(report.direct_consumers[:3])}")
        test_block = "\n".join(test_lines)

        # 7. Skeletonize focus code
        skel_block = ""
        resolved_file = None
        if target_file:
            cand = self.workspace_root / target_file
            if cand.is_file():
                resolved_file = cand
        elif report and report.target_files:
            for tf in report.target_files:
                cand = self.workspace_root / tf
                if cand.is_file():
                    resolved_file = cand
                    break

        # Calculate budget available for skeleton
        fixed_text = f"[LAYER 2: DYNAMIC TASK TAIL | Task: {task_clean[:80]}]\n\n{calib_block}\n\n{sym_block}\n\n{test_block}"
        fixed_tokens = estimate_tokens(fixed_text)
        skel_token_budget = max(50, max_tokens - fixed_tokens - 40)

        if resolved_file:
            try:
                skel_res = self.skeletonizer.skeletonize_file(
                    resolved_file,
                    focus_symbol=focus_name,
                    max_tokens=skel_token_budget
                )
                try:
                    rel_disp = resolved_file.relative_to(self.workspace_root).as_posix()
                except Exception:
                    rel_disp = resolved_file.name
                skel_block = f"[SURGICAL_CODE_SKELETON | {rel_disp}]\n```{skel_res.language}\n{skel_res.skeleton.strip()}\n```"
            except Exception:
                skel_block = ""

        # Assemble slices
        slices = [
            f"[LAYER 2: DYNAMIC TASK TAIL | Task: {task_clean[:80]}]",
            calib_block,
            sym_block,
        ]
        if skel_block:
            slices.append(skel_block)
        slices.append(test_block)

        result = "\n\n".join(slices)

        # Strict token constraint enforcement: <= max_tokens
        if estimate_tokens(result) > max_tokens:
            if skel_block and len(slices) >= 4:
                overhead = estimate_tokens("\n\n".join([slices[0], slices[1], slices[2], slices[-1]]))
                allowed_chars = max(100, (max_tokens - overhead - 20) * 4)
                if len(skel_block) > allowed_chars:
                    trimmed_skel = skel_block[:allowed_chars]
                    last_nl = trimmed_skel.rfind('\n')
                    if last_nl > 0:
                        trimmed_skel = trimmed_skel[:last_nl]
                    if not trimmed_skel.endswith("```"):
                        trimmed_skel += "\n// ... [compacted for token budget]\n```"
                    slices[-2] = trimmed_skel
                    result = "\n\n".join(slices)

            while estimate_tokens(result) > max_tokens and len(result) > 100:
                result = result[:max_tokens * 4]
                last_nl = result.rfind('\n')
                if last_nl > 0:
                    result = result[:last_nl]

            # Ensure markdown code fences are properly balanced
            if result.count("```") % 2 != 0:
                result += "\n```"
                while estimate_tokens(result) > max_tokens and len(result) > 100:
                    body = result[:-4]
                    last_nl = body.rfind('\n')
                    if last_nl > 0:
                        result = body[:last_nl] + "\n```"
                    else:
                        break

        return result
