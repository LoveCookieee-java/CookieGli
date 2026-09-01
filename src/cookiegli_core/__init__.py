"""
CookieGli Core — High-density context genome compressor and Bayesian ROI Darwin memory.
Designed for AI agents with zero-overhead token economy, monorepo hierarchy, and true cross-platform safety.
"""

from .ast_scanner import AstScanner, CodeEntity, FileStructure
from .cache_db import AstCache
from .genome_engine import GenomeEngine, ProjectGenome, estimate_tokens
from .monorepo_engine import MonorepoEngine, MonorepoGenome, PackageNode
from .darwin_memory import DarwinMemory, LearnedArtifact

__version__ = "2.1.0"
__all__ = [
    "AstScanner",
    "AstCache",
    "CodeEntity",
    "FileStructure",
    "GenomeEngine",
    "ProjectGenome",
    "MonorepoEngine",
    "MonorepoGenome",
    "PackageNode",
    "DarwinMemory",
    "LearnedArtifact",
    "estimate_tokens",
]
