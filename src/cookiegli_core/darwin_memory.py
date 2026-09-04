"""
Darwin Memory Pool — Long-term evolutionary knowledge persistence with Bayesian smoothed ROI,
namespaced domain scopes, temporal half-life decay, and Git-resilient multi-file persistence.
"""

import hashlib
import json
import math
import os
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, len(text) // 4)


@dataclass
class LearnedArtifact:
    id: str
    name: str
    artifact_type: str  # 'pattern', 'lesson', 'skill', 'tool'
    content: str
    scope: str = "global"  # Domain namespace e.g. 'backend.auth', 'frontend.ui'
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)
    use_count: int = 0
    success_count: int = 0
    failure_count: int = 0
    roi: float = 0.35  # Initial Bayesian smoothed prior with 0 observations
    generation: int = 0
    tags: List[str] = field(default_factory=list)
    pruned: bool = False
    prune_reason: str = ""

    def __post_init__(self):
        if not self.id:
            raw = f"{self.scope}:{self.name}:{self.artifact_type}:{self.created_at}"
            self.id = hashlib.sha256(raw.encode('utf-8')).hexdigest()[:10]
        if self.use_count > 0 and self.roi == 0.35:
            self._recalculate_roi()

    @property
    def smoothed_success_rate(self) -> float:
        """Laplace smoothed success rate: (successes + 1) / (total + 2)."""
        return (self.success_count + 1.0) / (self.use_count + 2.0)

    def record_use(self, success: bool):
        self.use_count += 1
        self.last_used = time.time()
        if success:
            self.success_count += 1
        else:
            self.failure_count += 1
        self._recalculate_roi()

    def _recalculate_roi(self):
        sr = self.smoothed_success_rate
        freq = min(self.use_count / 5.0, 1.0)
        self.roi = max(0.0, min(1.0, 0.7 * sr + 0.3 * freq))

    def apply_decay(self, decay_rate: float = 0.95):
        self.roi *= decay_rate
        self.generation += 1

    def apply_temporal_decay(self, now_timestamp: Optional[float] = None, half_life_days: float = 30.0):
        """Temporal half-life decay: ROI(t) = ROI * 2^(-dt / half_life)."""
        now = now_timestamp or time.time()
        age_seconds = max(0.0, now - self.last_used)
        half_life_seconds = half_life_days * 86400.0
        if half_life_seconds > 0:
            decay_factor = math.pow(2.0, - (age_seconds / half_life_seconds))
            self.roi *= decay_factor

    def to_summary_line(self, include_telemetry: bool = False) -> str:
        scope_str = f" `[{self.scope}]`" if self.scope and self.scope != "global" else ""
        tag_str = f" `[{', '.join(self.tags)}]`" if self.tags else ""
        telemetry = f" (ROI: {self.roi:.2f}, SR: {self.smoothed_success_rate:.0%})" if include_telemetry else ""
        return f"- [{self.artifact_type.upper()}] **{self.name}**{scope_str}{tag_str}{telemetry}: {self.content}"


class DarwinMemory:
    """Enterprise Darwinian memory pool with atomic storage, namespaces, and temporal decay."""

    def __init__(self, state_file: Optional[str] = None, multi_file_dir: Optional[str] = None):
        self.state_file = Path(state_file).resolve() if state_file else None
        self.multi_file_dir = Path(multi_file_dir).resolve() if multi_file_dir else None
        self.artifacts: Dict[str, LearnedArtifact] = {}
        self.current_generation = 0
        self.prune_log: List[Dict[str, Any]] = []

        if self.multi_file_dir:
            self.multi_file_dir.mkdir(parents=True, exist_ok=True)
            self.load_multi_file()
        elif self.state_file and self.state_file.exists():
            self.load()

    def register(self, name: str, artifact_type: str, content: str, scope: str = "global", tags: Optional[List[str]] = None) -> LearnedArtifact:
        artifact = LearnedArtifact(
            id="",
            name=name,
            artifact_type=artifact_type,
            content=content,
            scope=scope or "global",
            tags=tags or [],
            generation=self.current_generation,
        )
        self.artifacts[artifact.id] = artifact
        self.save()
        return artifact

    def record_usage(self, artifact_id: str, success: bool) -> Optional[LearnedArtifact]:
        artifact = self.artifacts.get(artifact_id)
        if not artifact or artifact.pruned:
            return None
        artifact.record_use(success)
        self.save()
        return artifact

    def get_active(self, artifact_type: Optional[str] = None, scope: Optional[str] = None) -> List[LearnedArtifact]:
        """Return active unpruned artifacts, sorted by ROI descending."""
        active = [a for a in self.artifacts.values() if not a.pruned]
        if artifact_type:
            active = [a for a in active if a.artifact_type == artifact_type]
        if scope and scope != "all":
            active = [a for a in active if a.scope == "global" or a.scope == scope or a.scope.startswith(scope + '.')]
        return sorted(active, key=lambda a: a.roi, reverse=True)

    def get_preferences(self, scope: Optional[str] = None) -> List[LearnedArtifact]:
        """Return active unpruned preferences and invariants."""
        return [a for a in self.get_active(scope=scope) if a.artifact_type in ('preference', 'invariant')]

    def get_anti_patterns(self, scope: Optional[str] = None) -> List[LearnedArtifact]:
        """Return active unpruned anti-patterns and guards."""
        return [a for a in self.get_active(scope=scope) if a.artifact_type in ('anti_pattern', 'guard')]

    def search(self, query: str = "", scope: Optional[str] = None, tags: Optional[List[str]] = None, top_k: int = 10) -> List[LearnedArtifact]:
        """Search active artifacts matching query, scope, or tags."""
        active = self.get_active(scope=scope)
        if not query and not tags:
            return active[:top_k]

        scored: List[Tuple[float, LearnedArtifact]] = []
        q_words = set(query.lower().split()) if query else set()
        tag_set = set(t.lower() for t in tags) if tags else set()

        for a in active:
            score = 0.0
            match_found = False

            if q_words:
                content_words = set(a.content.lower().split()) | set(a.name.lower().split())
                overlap = len(q_words & content_words)
                if overlap > 0:
                    score += overlap * 2.0
                    match_found = True

            if tag_set:
                a_tags = set(t.lower() for t in a.tags)
                tag_overlap = len(tag_set & a_tags)
                if tag_overlap > 0:
                    score += tag_overlap * 3.0
                    match_found = True

            # If user queried or tagged, must match at least one filter criterion
            if match_found:
                score += a.roi * 1.5
                scored.append((score, a))

        scored.sort(key=lambda x: x[0], reverse=True)
        return [a for _, a in scored[:top_k]]

    def evolve(self, roi_threshold: float = 0.3, max_artifacts: int = 50, decay_rate: float = 0.95,
               half_life_days: Optional[float] = None, now_timestamp: Optional[float] = None, protect_recent: int = 5) -> Dict[str, Any]:
        """
        Run evolutionary generational decay and strict capacity pruning.
        """
        self.current_generation += 1
        now = now_timestamp or time.time()

        for a in self.artifacts.values():
            if not a.pruned:
                if half_life_days:
                    a.apply_temporal_decay(now, half_life_days)
                else:
                    a.apply_decay(decay_rate)

        active = [a for a in self.artifacts.values() if not a.pruned]
        pruned_count = 0

        # Phase 1: Prune artifacts falling below ROI threshold
        for a in active:
            if a.roi < roi_threshold:
                a.pruned = True
                a.prune_reason = f"ROI {a.roi:.3f} below threshold {roi_threshold}"
                self.prune_log.append({
                    'id': a.id,
                    'name': a.name,
                    'roi': a.roi,
                    'generation': self.current_generation,
                    'reason': a.prune_reason,
                    'timestamp': now
                })
                pruned_count += 1

        # Phase 2: Capacity constraint pruning
        active = [a for a in self.artifacts.values() if not a.pruned]
        if len(active) > max_artifacts:
            excess = len(active) - max_artifacts
            sorted_by_recency = sorted(active, key=lambda x: x.last_used, reverse=True)
            protected_ids = {x.id for x in sorted_by_recency[:protect_recent]}

            non_protected = [x for x in active if x.id not in protected_ids]
            non_protected_sorted = sorted(non_protected, key=lambda x: x.roi)

            prune_from_non_protected = non_protected_sorted[:excess]
            for a in prune_from_non_protected:
                a.pruned = True
                a.prune_reason = f"Capacity constraint (limit {max_artifacts})"
                pruned_count += 1

            # If still over capacity
            active = [a for a in self.artifacts.values() if not a.pruned]
            if len(active) > max_artifacts:
                remaining_excess = len(active) - max_artifacts
                all_sorted = sorted(active, key=lambda x: x.roi)
                for a in all_sorted[:remaining_excess]:
                    a.pruned = True
                    a.prune_reason = f"Strict capacity constraint (limit {max_artifacts})"
                    pruned_count += 1

        self.save()
        remaining_active = len([a for a in self.artifacts.values() if not a.pruned])
        return {
            'generation': self.current_generation,
            'pruned_count': pruned_count,
            'active_count': remaining_active,
            'total_artifacts': len(self.artifacts)
        }

    def to_markdown_summary(self, max_tokens: int = 500, scope: Optional[str] = None, include_telemetry: bool = False) -> str:
        """Generate markdown summary for .agents/AGENTS.md integration."""
        active = self.get_active(scope=scope)
        lines = [
            "<!-- darwin:learnings:start -->",
            "### 🧬 Darwin Learned Patterns & Best Practices"
        ]

        if not active:
            lines.append("- *No verified patterns evolved yet. Run tasks to build evolutionary memory.*")
        else:
            for a in active:
                line = a.to_summary_line(include_telemetry=include_telemetry)
                test_str = "\n".join(lines + [line, "<!-- darwin:learnings:end -->"])
                if estimate_tokens(test_str) > max_tokens:
                    break
                lines.append(line)

        lines.append("<!-- darwin:learnings:end -->")
        return "\n".join(lines)

    def save(self):
        """Atomic persistence."""
        if self.multi_file_dir:
            self._save_multi_file()
        elif self.state_file:
            self._save_single_file()

    def _save_single_file(self):
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'version': '2.1.0',
            'generation': self.current_generation,
            'artifacts': {k: v.__dict__ for k, v in self.artifacts.items()},
            'prune_log': self.prune_log
        }
        temp_file = None
        try:
            with tempfile.NamedTemporaryFile('w', dir=str(self.state_file.parent),
                                             delete=False, encoding='utf-8') as f:
                temp_file = f.name
                json.dump(data, f, indent=2, ensure_ascii=False)
            os.replace(temp_file, str(self.state_file))
        except Exception:
            if temp_file and os.path.exists(temp_file):
                try:
                    os.remove(temp_file)
                except Exception:
                    pass

    def _save_multi_file(self):
        """Save each artifact as a separate JSON file in multi_file_dir."""
        if not self.multi_file_dir:
            return
        for art in self.artifacts.values():
            art_file = self.multi_file_dir / f"{art.id}.json"
            temp_file = None
            try:
                with tempfile.NamedTemporaryFile('w', dir=str(self.multi_file_dir),
                                                 delete=False, encoding='utf-8') as f:
                    temp_file = f.name
                    json.dump(art.__dict__, f, indent=2, ensure_ascii=False)
                os.replace(temp_file, str(art_file))
            except Exception:
                if temp_file and os.path.exists(temp_file):
                    try:
                        os.remove(temp_file)
                    except Exception:
                        pass

    def load(self):
        if not self.state_file or not self.state_file.exists():
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_generation = data.get('generation', 0)
            self.prune_log = data.get('prune_log', [])
            self.artifacts = {}
            for k, v in data.get('artifacts', {}).items():
                self.artifacts[k] = LearnedArtifact(**v)
        except Exception:
            pass

    def load_multi_file(self):
        """Load artifacts from individual JSON files."""
        if not self.multi_file_dir or not self.multi_file_dir.exists():
            return
        self.artifacts = {}
        for p in self.multi_file_dir.glob("*.json"):
            try:
                with open(p, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                art = LearnedArtifact(**data)
                self.artifacts[art.id] = art
            except Exception:
                pass
