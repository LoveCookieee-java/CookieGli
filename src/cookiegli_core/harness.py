"""
CookieGli Continuous Evolution Harness — Adaptive Agent Learning & Project Trajectory Engine.
Enables closed-loop continuous adaptation: the more you use the Agent, the better it understands
your intent, coding conventions, architectural invariants, and safety boundaries.

Zero external dependencies. 100% pure Python standard library.
Cross-platform safe (Windows / Linux / macOS).
"""

import hashlib
import json
import math
import os
import re
import tempfile
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union


def estimate_tokens(text: str) -> int:
    """Fast token estimation: ~4 chars per token."""
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class UserPreference:
    """Represents a developer preference or coding convention."""
    id: str
    category: str  # 'style', 'architecture', 'safety', 'testing', 'interaction'
    key: str
    value: Any
    description: str
    scope: str = "global"  # e.g. 'core', 'adapters', 'backend.auth'
    confidence: float = 0.85
    adherence_count: int = 1
    violation_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            raw = f"{self.category}:{self.key}:{self.scope}"
            self.id = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:10]

    def record_feedback(self, adhered: bool):
        """Update confidence using Laplace smoothing: (adherence + 2) / (total + 3)."""
        if adhered:
            self.adherence_count += 1
        else:
            self.violation_count += 1
        self.last_updated = time.time()
        total = self.adherence_count + self.violation_count
        self.confidence = (self.adherence_count + 2.0) / (total + 3.0)

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_summary_line(self) -> str:
        scope_str = f" `[{self.scope}]`" if self.scope and self.scope != "global" else ""
        return f"- [PREF:{self.category.upper()}]{scope_str} **{self.key}**: {self.description} (conf: {self.confidence:.0%})"


@dataclass
class AntiPattern:
    """Represents a learned anti-pattern or forbidden action distilled from corrections."""
    id: str
    name: str
    forbidden_action: str
    preferred_alternative: str
    scope: str = "global"
    severity: float = 0.90  # High initial guard priority
    violation_count: int = 0
    created_at: float = field(default_factory=time.time)
    last_triggered: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.id:
            raw = f"{self.name}:{self.scope}:{self.forbidden_action}"
            self.id = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:10]

    def record_trigger(self):
        self.violation_count += 1
        self.last_triggered = time.time()

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_summary_line(self) -> str:
        scope_str = f" `[{self.scope}]`" if self.scope and self.scope != "global" else ""
        return f"- [GUARD]{scope_str} **{self.name}**: Do NOT {self.forbidden_action}. Instead: {self.preferred_alternative}."


@dataclass
class HarnessEpisode:
    """Records an interaction episode between the developer and Agent."""
    episode_id: str
    timestamp: float
    task_prompt: str
    touched_files: List[str] = field(default_factory=list)
    tests_executed: List[str] = field(default_factory=list)
    test_passed: bool = True
    feedback_type: str = "neutral"  # 'praise', 'correction', 'preference', 'neutral', 'implicit_success'
    user_feedback: str = ""
    applied_preferences: List[str] = field(default_factory=list)
    applied_anti_patterns: List[str] = field(default_factory=list)
    tokens_used: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)


@dataclass
class ProjectMaturity:
    """Evaluates project trajectory and maturity across 4 evolution stages."""
    phase: str  # 'Phase 1: Inception', 'Phase 2: Expansion', 'Phase 3: Hardening', 'Phase 4: Enterprise'
    phase_number: int  # 1, 2, 3, 4
    maturity_score: float  # 0.0 to 100.0
    code_stability: float  # 0.0 to 1.0 (mtime stability across files)
    test_density: float  # ratio of test LOC or test files to source files
    hotspot_count: int  # count of high fan-in modules (fan-in >= 5)
    total_episodes: int
    alignment_score: float  # 0.0 to 100.0
    guidance: str

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    def to_summary(self) -> str:
        lines = [
            f"Project Maturity: {self.phase} (Score: {self.maturity_score:.1f}/100)",
            f"Agent Alignment Score: {self.alignment_score:.1f}% | Episodes: {self.total_episodes}",
            f"Stability: {self.code_stability:.0%} | Test Density: {self.test_density:.2f} | Hotspots: {self.hotspot_count}",
            f"Guidance: {self.guidance}"
        ]
        return "\n".join(lines)


class CorrectionDistiller:
    """
    Analyzes natural language developer feedback (Vietnamese & English) and code diffs
    to extract actionable UserPreferences and AntiPatterns.
    """

    # Multi-lingual patterns for negative feedback / corrections
    CORRECTION_PATTERNS = [
        # Vietnamese: "đừng/không ... hãy/nên/dùng ..."
        re.compile(r'(?:đừng|không|tuyệt đối không|hạn chế)\s+(?:dùng|làm|thực hiện|gọi|viết)?\s*([^\,\;\n]+?)(?:[\,\;]|\s+mà|\s+thay vào đó|\s+hãy|\s+nên|\s+cần|\s+dùng)\s+(?:hãy|nên|cần|dùng|thay bằng|ưu tiên)\s*(.+?)(?:\.\s*$|\n|$)', re.IGNORECASE),
        # English: "do not / never / avoid ... instead / use / prefer ..."
        re.compile(r'(?:do not|don\'t|never|avoid|stop)\s+(?:use|using|calling|doing|writing)?\s*([^\,\;\n]+?)(?:[\,\;]|\s+instead|\s+rather than|\s+use|\s+prefer)\s+(?:use|prefer|instead use|always use|rely on)\s*(.+?)(?:\.\s*$|\n|$)', re.IGNORECASE),
        # Positive preference: "luôn luôn / always ...", "ưu tiên / prefer ..."
        re.compile(r'(?:luôn luôn|luôn|cần phải|bắt buộc|always|ensure|prefer)\s+(?:dùng|sử dụng|tuân thủ|áp dụng|use|follow)?\s*(.+?)(?:\.\s*$|\n|$)', re.IGNORECASE),
    ]

    @classmethod
    def distill(cls, feedback_text: str, scope: str = "global") -> Tuple[Optional[AntiPattern], Optional[UserPreference]]:
        """Extract an AntiPattern or UserPreference from developer feedback."""
        if not feedback_text or not feedback_text.strip():
            return None, None

        cleaned = feedback_text.strip()

        # Check negative pattern: Do not X, instead Y
        for i, pat in enumerate(cls.CORRECTION_PATTERNS[:2]):
            m = pat.search(cleaned)
            if m:
                forbidden = m.group(1).strip().strip('"\'')
                preferred = m.group(2).strip().strip('"\'')
                preferred = re.sub(r'^(?:dùng|sử dụng|use)\s+', '', preferred, flags=re.IGNORECASE).strip()
                name_words = [w for w in forbidden.split() if len(w) > 2][:3]
                rule_name = "_".join(name_words) or "guard_rule"
                rule_name = re.sub(r'[^a-zA-Z0-9_]', '', rule_name).lower()
                if not rule_name:
                    rule_name = "learned_guard"

                anti = AntiPattern(
                    id="",
                    name=rule_name,
                    forbidden_action=forbidden,
                    preferred_alternative=preferred,
                    scope=scope,
                    severity=0.90
                )
                pref = UserPreference(
                    id="",
                    category="safety" if any(w in forbidden.lower() for w in ["xóa", "delete", "rm", "unlink", "drop"]) else "style",
                    key=f"prefer_{rule_name}",
                    value=preferred,
                    description=f"Prefer {preferred} over {forbidden}",
                    scope=scope,
                    confidence=0.90
                )
                return anti, pref

        # Check positive preference pattern
        pos_match = cls.CORRECTION_PATTERNS[2].search(cleaned)
        if pos_match:
            rule_content = pos_match.group(1).strip().strip('"\'')
            key_words = [w for w in rule_content.split() if len(w) > 2][:3]
            pref_key = "_".join(key_words) or "convention"
            pref_key = re.sub(r'[^a-zA-Z0-9_]', '', pref_key).lower()
            if not pref_key:
                pref_key = "user_preference"

            pref = UserPreference(
                id="",
                category="style",
                key=pref_key,
                value=rule_content,
                description=f"Enforce: {rule_content}",
                scope=scope,
                confidence=0.85
            )
            return None, pref

        # Fallback: create general preference if non-empty
        clean_key = re.sub(r'[^a-zA-Z0-9_]', '_', cleaned[:20]).lower().strip('_') or "general_pref"
        pref = UserPreference(
            id="",
            category="interaction",
            key=clean_key,
            value=cleaned,
            description=cleaned[:100],
            scope=scope,
            confidence=0.75
        )
        return None, pref


class ProjectMaturityTracker:
    """Computes project trajectory, churn, test density, and 4-phase maturity."""

    def __init__(self, workspace_root: Union[str, Path]):
        self.workspace_root = Path(workspace_root).resolve()

    def assess_maturity(
        self,
        total_episodes: int = 0,
        alignment_score: float = 85.0,
        hotspot_count: int = 0
    ) -> ProjectMaturity:
        """Calculates project maturity across 4 phases."""
        src_files = []
        test_files = []
        now = time.time()
        stable_file_count = 0
        total_checked = 0

        # Scan repository files safely
        for root, dirs, files in os.walk(self.workspace_root):
            # Skip hidden, git, cache dirs
            dirs[:] = [d for d in dirs if not d.startswith('.') and d not in ('node_modules', 'dist', 'build', '__pycache__', 'vendor')]
            for f in files:
                if f.endswith(('.py', '.ts', '.js', '.go', '.rs', '.java', '.cpp', '.c', '.h')):
                    fp = Path(root) / f
                    total_checked += 1
                    try:
                        mtime = fp.stat().st_mtime
                        # Files untouched in the last 24 hours are considered stable
                        if (now - mtime) > 86400:
                            stable_file_count += 1
                    except Exception:
                        pass

                    if 'test' in f.lower() or 'tests' in fp.parts:
                        test_files.append(fp)
                    else:
                        src_files.append(fp)

        stability = (stable_file_count / max(1, total_checked))
        test_density = len(test_files) / max(1, len(src_files))

        # Composite Maturity Score Calculation (0.0 to 100.0)
        # S_code (0-35) + D_test (0-25) + H_invariants (0-20) + V_episodes (0-20)
        s_score = min(35.0, stability * 35.0)
        d_score = min(25.0, (test_density / 0.5) * 25.0)  # max score if test ratio >= 0.5
        h_score = min(20.0, (min(hotspot_count, 5) / 5.0) * 20.0)
        v_score = min(20.0, (math.log(1 + total_episodes) / math.log(50)) * 20.0) if total_episodes > 0 else 5.0

        maturity_score = max(5.0, min(100.0, s_score + d_score + h_score + v_score))

        if maturity_score < 25.0:
            phase = "Phase 1: Inception"
            phase_num = 1
            guidance = "Rapid scaffolding & prototyping. Flexible patterns allowed; focus on modular boundaries."
        elif maturity_score < 55.0:
            phase = "Phase 2: Expansion"
            phase_num = 2
            guidance = "Active feature addition. Enforce interface contracts and keep symbol cache updated."
        elif maturity_score < 80.0:
            phase = "Phase 3: Hardening"
            phase_num = 3
            guidance = "Strict zero-regression gate. Enforce surgical Blast Radius test targeting and reasoning depth."
        else:
            phase = "Phase 4: Enterprise"
            phase_num = 4
            guidance = "Invariant lockdown. Critical fan-in hotspots must not be modified without explicit verification."

        return ProjectMaturity(
            phase=phase,
            phase_number=phase_num,
            maturity_score=round(maturity_score, 1),
            code_stability=round(stability, 2),
            test_density=round(test_density, 2),
            hotspot_count=hotspot_count,
            total_episodes=total_episodes,
            alignment_score=round(alignment_score, 1),
            guidance=guidance
        )


class HarnessEngine:
    """
    Central Controller for CookieGli Continuous Evolution Harness.
    Coordinates UserPreference persistence, AntiPattern guards, ProjectMaturity tracking,
    and adaptive context synthesis strictly budgeted <= 600 tokens.
    """

    def __init__(self, workspace_root: Optional[Union[str, Path]] = None, state_file: Optional[Union[str, Path]] = None):
        self.workspace_root = Path(workspace_root or Path.cwd()).resolve()
        if state_file:
            self.state_file = Path(state_file).resolve()
        else:
            self.state_file = self.workspace_root / ".cookiegli" / "harness_state.json"

        self.preferences: Dict[str, UserPreference] = {}
        self.anti_patterns: Dict[str, AntiPattern] = {}
        self.episodes: List[HarnessEpisode] = []
        self.maturity_tracker = ProjectMaturityTracker(self.workspace_root)
        self.load()

        # Seed initial fundamental invariants if empty
        if not self.preferences:
            self._seed_default_invariants()

    def _seed_default_invariants(self):
        """Seed initial project invariants (Ponytail & Safety rules)."""
        self.record_preference(
            key="stdlib_first",
            value=True,
            description="Prioritize pure Python standard library; zero unnecessary external dependencies.",
            category="style",
            scope="global"
        )
        self.record_preference(
            key="token_budget_strict",
            value=600,
            description="Strict token budget: Layer 1 (<600t) and Layer 2 (<600t) for 100% prefix cache hits.",
            category="architecture",
            scope="global"
        )
        self.record_anti_pattern(
            name="unauthorized_file_deletion",
            forbidden_action="delete files or directories without explicit user confirmation",
            preferred_alternative="ask user permission explicitly before deleting or modifying files",
            scope="global"
        )

    def record_preference(
        self,
        key: str,
        value: Any,
        description: str,
        category: str = "style",
        scope: str = "global"
    ) -> UserPreference:
        """Register or update a user preference."""
        pref = UserPreference(
            id="",
            category=category,
            key=key,
            value=value,
            description=description,
            scope=scope,
            confidence=0.90
        )
        # If already exists, boost confidence
        if pref.id in self.preferences:
            self.preferences[pref.id].record_feedback(adhered=True)
            if description:
                self.preferences[pref.id].description = description
        else:
            self.preferences[pref.id] = pref
        self.save()
        return self.preferences[pref.id]

    def record_anti_pattern(
        self,
        name: str,
        forbidden_action: str,
        preferred_alternative: str,
        scope: str = "global"
    ) -> AntiPattern:
        """Register a learned anti-pattern guard."""
        anti = AntiPattern(
            id="",
            name=name,
            forbidden_action=forbidden_action,
            preferred_alternative=preferred_alternative,
            scope=scope,
            severity=0.95
        )
        self.anti_patterns[anti.id] = anti
        self.save()
        return anti

    def record_feedback(
        self,
        feedback_type: str,
        content: str,
        scope: str = "global",
        task: str = ""
    ) -> Dict[str, Any]:
        """
        Record developer feedback.
        - 'praise' / 'approval': increases confidence in active preferences.
        - 'correction': extracts anti-pattern or preference and penalizes violated rules.
        - 'preference': directly adds user preference.
        """
        result: Dict[str, Any] = {
            "feedback_type": feedback_type,
            "learned_preferences": [],
            "learned_anti_patterns": []
        }

        if feedback_type in ("correction", "preference"):
            anti, pref = CorrectionDistiller.distill(content, scope=scope)
            if anti:
                self.anti_patterns[anti.id] = anti
                result["learned_anti_patterns"].append(anti.to_dict())
            if pref:
                self.preferences[pref.id] = pref
                result["learned_preferences"].append(pref.to_dict())
        elif feedback_type in ("praise", "approval"):
            for p in self.preferences.values():
                if p.scope == "global" or p.scope == scope:
                    p.record_feedback(adhered=True)
            result["message"] = "Reinforced active preferences."

        # Log episode
        self.record_episode(
            task=task or f"Feedback: {content[:60]}",
            touched_files=[],
            test_passed=True,
            feedback_type=feedback_type,
            user_feedback=content
        )
        self.save()
        return result

    def record_episode(
        self,
        task: str,
        touched_files: Optional[List[str]] = None,
        tests_executed: Optional[List[str]] = None,
        test_passed: bool = True,
        feedback_type: str = "neutral",
        user_feedback: str = "",
        tokens_used: int = 0
    ) -> HarnessEpisode:
        """Log task completion episode and calculate alignment."""
        ep_id = hashlib.sha256(f"{task}:{time.time()}".encode('utf-8')).hexdigest()[:10]
        ep = HarnessEpisode(
            episode_id=ep_id,
            timestamp=time.time(),
            task_prompt=task,
            touched_files=touched_files or [],
            tests_executed=tests_executed or [],
            test_passed=test_passed,
            feedback_type=feedback_type,
            user_feedback=user_feedback,
            tokens_used=tokens_used
        )
        self.episodes.append(ep)
        # Keep last 100 episodes
        if len(self.episodes) > 100:
            self.episodes = self.episodes[-100:]
        self.save()
        return ep

    def get_alignment_score(self) -> float:
        """
        Calculate Bayesian Agent Alignment Score (0.0% to 100.0%):
        Formula: 0.40 * ZeroDefectRate + 0.35 * (1 - CorrectionRate) + 0.25 * PreferenceAdherence
        """
        if not self.episodes:
            return 88.0  # Favorable initial prior

        total = len(self.episodes)
        passed_tests = sum(1 for e in self.episodes if e.test_passed)
        zero_defect_rate = passed_tests / total

        corrections = sum(1 for e in self.episodes if e.feedback_type == "correction")
        correction_rate = corrections / total

        # Preference adherence across all active preferences
        pref_adherence = 1.0
        if self.preferences:
            total_adhere = sum(p.adherence_count for p in self.preferences.values())
            total_viol = sum(p.violation_count for p in self.preferences.values())
            pref_adherence = (total_adhere + 1.0) / (total_adhere + total_viol + 2.0)

        score = (0.40 * zero_defect_rate + 0.35 * (1.0 - correction_rate) + 0.25 * pref_adherence) * 100.0
        return max(10.0, min(100.0, round(score, 1)))

    def get_maturity(self, hotspot_count: int = 0) -> ProjectMaturity:
        """Assess and return current ProjectMaturity status."""
        alignment = self.get_alignment_score()
        return self.maturity_tracker.assess_maturity(
            total_episodes=len(self.episodes),
            alignment_score=alignment,
            hotspot_count=hotspot_count
        )

    def get_relevant_context(
        self,
        task: str,
        target_files: Optional[List[str]] = None,
        max_tokens: int = 150,
        hotspot_count: int = 0
    ) -> str:
        """
        Synthesize surgical Layer 2 Harness block strictly <= max_tokens.
        Contains active preferences, relevant anti-patterns, and project maturity stage.
        """
        maturity = self.get_maturity(hotspot_count=hotspot_count)
        lines = ["[HARNESS_PREFERENCES & STAGE_GUARDS]"]
        lines.append(f"• STAGE: {maturity.phase} (Alignment IQ: {maturity.alignment_score:.1f}%) | {maturity.guidance}")

        # Add top relevant preferences
        matched_prefs: List[UserPreference] = []
        for p in self.preferences.values():
            if p.scope == "global":
                matched_prefs.append(p)
            elif target_files and any(p.scope in tf for tf in target_files):
                matched_prefs.append(p)

        matched_prefs.sort(key=lambda x: x.confidence, reverse=True)
        for p in matched_prefs[:3]:
            lines.append(f"• PREF [{p.category}]: {p.description}")

        # Add top relevant anti-pattern guards
        matched_antis: List[AntiPattern] = []
        for a in self.anti_patterns.values():
            if a.scope == "global":
                matched_antis.append(a)
            elif target_files and any(a.scope in tf for tf in target_files):
                matched_antis.append(a)

        matched_antis.sort(key=lambda x: x.severity, reverse=True)
        for a in matched_antis[:2]:
            lines.append(f"• GUARD: Do NOT {a.forbidden_action}. Instead: {a.preferred_alternative}.")

        block = "\n".join(lines)
        # Token limit guard
        if estimate_tokens(block) > max_tokens:
            while len(lines) > 2 and estimate_tokens("\n".join(lines)) > max_tokens:
                lines.pop()
            block = "\n".join(lines)

        return block

    def get_status(self, hotspot_count: int = 0) -> Dict[str, Any]:
        """Return comprehensive status dashboard for CLI / MCP."""
        maturity = self.get_maturity(hotspot_count=hotspot_count)
        return {
            "maturity": maturity.to_dict(),
            "alignment_score": maturity.alignment_score,
            "total_episodes": len(self.episodes),
            "preferences_count": len(self.preferences),
            "anti_patterns_count": len(self.anti_patterns),
            "active_preferences": [p.to_dict() for p in self.preferences.values()],
            "active_anti_patterns": [a.to_dict() for a in self.anti_patterns.values()],
            "recent_episodes": [e.to_dict() for e in self.episodes[-5:]]
        }

    def evaluate_fitness(self) -> Dict[str, Any]:
        """
        Run self-evaluating benchmark on Agent alignment, zero-defect capability,
        and rule retention rate.
        """
        alignment = self.get_alignment_score()
        maturity = self.get_maturity()
        zero_defect_tasks = sum(1 for e in self.episodes if e.test_passed)
        adherence_rate = 1.0
        if self.preferences:
            tot_adh = sum(p.adherence_count for p in self.preferences.values())
            tot_v = sum(p.violation_count for p in self.preferences.values())
            adherence_rate = (tot_adh + 1.0) / (tot_adh + tot_v + 2.0)

        fitness_status = "OPTIMAL" if alignment >= 80.0 else "ADAPTING"

        return {
            "fitness_status": fitness_status,
            "alignment_score": alignment,
            "project_phase": maturity.phase,
            "maturity_score": maturity.maturity_score,
            "total_episodes_analyzed": len(self.episodes),
            "zero_defect_success_rate": f"{(zero_defect_tasks / max(1, len(self.episodes))):.0%}",
            "preference_adherence_rate": f"{adherence_rate:.0%}",
            "active_guards_count": len(self.anti_patterns),
            "active_preferences_count": len(self.preferences)
        }

    def to_markdown_summary(self, max_tokens: int = 400) -> str:
        """Generate markdown summary for multi-target configuration files."""
        lines = [
            "<!-- cookiegli:preferences:start -->",
            "### 🧬 Developer Preferences & Invariant Guards"
        ]
        maturity = self.get_maturity()
        lines.append(f"- **Project Trajectory**: {maturity.phase} (Alignment Score: {maturity.alignment_score:.1f}%)")

        # Top preferences
        active_prefs = sorted(self.preferences.values(), key=lambda p: p.confidence, reverse=True)
        for p in active_prefs:
            lines.append(p.to_summary_line())

        # Top guards
        active_guards = sorted(self.anti_patterns.values(), key=lambda g: g.severity, reverse=True)
        for g in active_guards:
            lines.append(g.to_summary_line())

        lines.append("<!-- cookiegli:preferences:end -->")
        result = "\n".join(lines)
        if estimate_tokens(result) > max_tokens:
            while len(lines) > 4 and estimate_tokens("\n".join(lines + ["<!-- cookiegli:preferences:end -->"])) > max_tokens:
                lines.pop(-2)
            result = "\n".join(lines)

        return result

    def save(self):
        """Atomic persistence of harness state file."""
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "version": "1.0.0",
            "last_updated": time.time(),
            "preferences": {k: v.to_dict() for k, v in self.preferences.items()},
            "anti_patterns": {k: v.to_dict() for k, v in self.anti_patterns.items()},
            "episodes": [e.to_dict() for e in self.episodes]
        }
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=str(self.state_file.parent), delete=False, encoding='utf-8') as f:
                temp_file = f.name
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, str(self.state_file))
        except Exception:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def load(self):
        """Load state from state_file safely."""
        if not self.state_file or not self.state_file.exists():
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.preferences = {}
            for k, v in data.get("preferences", {}).items():
                self.preferences[k] = UserPreference(**v)
            self.anti_patterns = {}
            for k, v in data.get("anti_patterns", {}).items():
                self.anti_patterns[k] = AntiPattern(**v)
            self.episodes = []
            for ep in data.get("episodes", []):
                self.episodes.append(HarnessEpisode(**ep))
        except Exception:
            pass
