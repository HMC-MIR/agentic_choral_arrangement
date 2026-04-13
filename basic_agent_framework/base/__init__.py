"""
base
----
Self-contained hub-and-spoke melody harmonization system.

Copy this entire folder to create a new experiment variant. The test.ipynb
notebook auto-detects the folder name and routes audio output accordingly.

Quick start:
    import asyncio
    from basic_agent_framework.base import (
        harmonize_melody, load_bach_melody,
        build_harmonization_template, clean_abc_for_llm,
    )

    melody   = load_bach_melody("bwv253")
    template = build_harmonization_template(melody)
    clean    = clean_abc_for_llm(template)

    result = asyncio.run(harmonize_melody(clean))
    print(result.final_abc)
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
