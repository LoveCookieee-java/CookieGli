"""
Darwin Evolution Memory — ROI-based natural selection for learned patterns and artifacts.
Hardened with Laplace/Bayesian smoothed ROI, atomic file persistence, and semantic tag querying.
"""

import datetime
import hashlib
import json
import os
import tempfile
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Dict, List, Optional, Any


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
            raw = f"{self.name}:{self.artifact_type}:{self.created_at}"
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

    def to_summary_line(self) -> str:
        tag_str = f" `[{', '.join(self.tags)}]`" if self.tags else ""
        return f"- [{self.artifact_type.upper()}] **{self.name}**{tag_str} (ROI: {self.roi:.2f}, SR: {self.smoothed_success_rate:.0%}): {self.content}"


class DarwinMemory:
    """Enterprise Darwinian memory pool with atomic storage and Bayesian ROI dynamics."""

    def __init__(self, state_file: Optional[str] = None):
        self.state_file = Path(state_file).resolve() if state_file else None
        self.artifacts: Dict[str, LearnedArtifact] = {}
        self.current_generation = 0
        self.prune_log: List[Dict[str, Any]] = []

        if self.state_file and self.state_file.exists():
            self.load()

    def register(self, name: str, artifact_type: str, content: str, tags: Optional[List[str]] = None) -> LearnedArtifact:
        artifact = LearnedArtifact(
            id="",
            name=name,
            artifact_type=artifact_type,
            content=content,
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

    def search(self, query: str = "", tags: Optional[List[str]] = None) -> List[LearnedArtifact]:
        """Search active artifacts by keyword or tags."""
        active = self.get_active()
        q = query.lower()
        results = []

        for a in active:
            match = True
            if q and q not in a.name.lower() and q not in a.content.lower():
                match = False
            if tags and not any(t.lower() in [at.lower() for at in a.tags] for t in tags):
                match = False
            if match:
                results.append(a)

        return results

    def evolve(self, roi_threshold: float = 0.3, max_artifacts: int = 50,
               decay_rate: float = 0.95, protect_recent: int = 3,
               min_uses_to_evaluate: int = 2) -> Dict[str, Any]:
        """Execute one generation cycle: apply decay, prune low-ROI and enforce capacity."""
        self.current_generation += 1
        pruned_items: List[LearnedArtifact] = []

        active = [a for a in self.artifacts.values() if not a.pruned]
        for a in active:
            a.apply_decay(decay_rate)

        sorted_by_recency = sorted(active, key=lambda a: a.last_used, reverse=True)
        protected_ids = {a.id for a in sorted_by_recency[:protect_recent]}

        # Prune items below threshold with sufficient evaluation
        for a in active:
            if a.use_count >= min_uses_to_evaluate and a.roi < roi_threshold:
                if a.id not in protected_ids:
                    a.pruned = True
                    a.prune_reason = f"low_roi({a.roi:.2f} < {roi_threshold})"
                    pruned_items.append(a)

        # Enforce strict capacity limit
        active_survivors = [a for a in self.artifacts.values() if not a.pruned]
        if len(active_survivors) > max_artifacts:
            non_protected = [a for a in active_survivors if a.id not in protected_ids]
            protected = [a for a in active_survivors if a.id in protected_ids]

            non_protected.sort(key=lambda a: a.roi)
            protected.sort(key=lambda a: a.roi)

            excess = len(active_survivors) - max_artifacts
            to_prune = []

            if non_protected:
                take_np = min(len(non_protected), excess)
                to_prune.extend(non_protected[:take_np])
                excess -= take_np

            if excess > 0 and protected:
                to_prune.extend(protected[:excess])

            for a in to_prune:
                a.pruned = True
                a.prune_reason = f"capacity_overflow (roi={a.roi:.2f})"
                pruned_items.append(a)

        for p in pruned_items:
            self.prune_log.append({
                'id': p.id,
                'name': p.name,
                'roi': round(p.roi, 3),
                'generation': self.current_generation,
                'reason': p.prune_reason
            })

        self.save()
        active_count = len([a for a in self.artifacts.values() if not a.pruned])
        return {
            'generation': self.current_generation,
            'pruned_count': len(pruned_items),
            'active_count': active_count,
            'total_artifacts': len(self.artifacts),
        }

    def get_active(self, artifact_type: Optional[str] = None) -> List[LearnedArtifact]:
        active = [a for a in self.artifacts.values() if not a.pruned]
        if artifact_type:
            active = [a for a in active if a.artifact_type == artifact_type]
        return sorted(active, key=lambda a: a.roi, reverse=True)

    def to_markdown_summary(self, max_tokens: int = 500) -> str:
        """Produce compact markdown suitable for .agents/AGENTS.md inclusion."""
        active = self.get_active()
        if not active:
            return "<!-- darwin:empty -->\n*No learned patterns registered yet.*"

        lines = ["<!-- darwin:learnings:start -->", "### 🧬 Darwin Learned Patterns & Best Practices"]
        total_tokens = estimate_tokens("\n".join(lines))

        for a in active:
            line = a.to_summary_line()
            t = estimate_tokens(line)
            if total_tokens + t > max_tokens:
                break
            lines.append(line)
            total_tokens += t

        lines.append("<!-- darwin:learnings:end -->")
        return "\n".join(lines)

    def save(self):
        """Atomic file save to prevent corruption on sudden termination."""
        if not self.state_file:
            return
        self.state_file.parent.mkdir(parents=True, exist_ok=True)
        data = {
            'generation': self.current_generation,
            'artifacts': {k: asdict(v) for k, v in self.artifacts.items()},
            'prune_log': self.prune_log[-50:],
        }
        # Write to temporary file in the same directory, then atomic replace
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
                    os.unlink(temp_file)
                except Exception:
                    pass

    def load(self):
        if not self.state_file or not self.state_file.exists():
            return
        try:
            with open(self.state_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            self.current_generation = data.get('generation', 0)
            self.artifacts = {
                k: LearnedArtifact(**v) for k, v in data.get('artifacts', {}).items()
            }
            self.prune_log = data.get('prune_log', [])
        except Exception:
            pass
