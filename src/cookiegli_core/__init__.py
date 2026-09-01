"""
CookieGli Core — High-density context genome compressor and Bayesian ROI Darwin memory.
Designed for AI agents with zero-overhead token economy and true cross-platform safety.
"""

from .ast_scanner import AstScanner, CodeEntity, FileStructure
from .genome_engine import GenomeEngine, ProjectGenome, estimate_tokens
from .darwin_memory import DarwinMemory, LearnedArtifact

__version__ = "2.0.0"
__all__ = [
    "AstScanner",
    "CodeEntity",
    "FileStructure",
    "GenomeEngine",
    "ProjectGenome",
    "DarwinMemory",
    "LearnedArtifact",
    "estimate_tokens",
]
