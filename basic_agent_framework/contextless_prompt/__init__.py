"""
contextless_prompt
------------------
Minimal-prompt variant of the hub-and-spoke melody harmonization system.

Same interface as `base`: copy this folder to create a new variant. The
test.ipynb notebook auto-detects the folder name and routes audio output
accordingly.
"""

from .pipeline import harmonize_melody
from .executors import Iteration, HarmonizationResult
from .bach_melodies import (
    load_bach_melody,
    build_harmonization_template,
    clean_abc_for_llm,
    AVAILABLE_BWV,
)

__all__ = [
    "harmonize_melody",
    "Iteration",
    "HarmonizationResult",
    "load_bach_melody",
    "build_harmonization_template",
    "clean_abc_for_llm",
    "AVAILABLE_BWV",
]
