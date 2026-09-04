"""
CookieGli Core — High-density context genome compressor and Bayesian ROI Darwin memory.
Designed for AI agents with zero-overhead token economy, monorepo hierarchy, and true cross-platform safety.
"""

from .ast_scanner import AstScanner, CodeEntity, FileStructure
from .cache_db import AstCache
from .genome_engine import GenomeEngine, ProjectGenome, estimate_tokens
from .monorepo_engine import MonorepoEngine, MonorepoGenome, PackageNode
from .darwin_memory import DarwinMemory, LearnedArtifact
from .adapters import TargetManager
from .mcp_server import CookieGliMcpServer
from .skeletonizer import CodeSkeletonizer, SkeletonResult
from .blast_radius import BlastRadiusEngine, BlastRadiusReport
from .distiller import (
    ErrorDistiller,
    DistilledError,
    DistilledLesson,
    StackFrame,
    clean_darwin_summary,
)

__version__ = "2.2.0"
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
    "TargetManager",
    "CookieGliMcpServer",
    "CodeSkeletonizer",
    "SkeletonResult",
    "BlastRadiusEngine",
    "BlastRadiusReport",
    "ErrorDistiller",
    "DistilledError",
    "DistilledLesson",
    "StackFrame",
    "clean_darwin_summary",
    "estimate_tokens",
]

