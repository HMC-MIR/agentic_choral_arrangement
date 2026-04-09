"""
basic_agent_framework
---------------------
A 3-agent melody harmonization system built on Microsoft Agent Framework,
using a hub-and-spoke architecture:

  Orchestrator (GPT-4o)  — coordinates the loop, decides approve/revise
  Theory Agent (Claude)  — critiques with full OMT textbook context
  Harmonizer   (GPT-4o)  — generates/revises ABC chords, no textbook

Quick start:
    import asyncio
    from basic_agent_framework import (
        harmonize_melody, load_bach_melody,
        build_harmonization_template, clean_abc_for_llm,
    )

    melody   = load_bach_melody("bwv253")
    template = build_harmonization_template(melody)
    clean    = clean_abc_for_llm(template)

    result = asyncio.run(harmonize_melody(clean))

    # Inspect every iteration
    for it in result.iterations:
        print(f"Round {it.attempt}: {'APPROVED' if it.approved else 'REVISE'}")

    print(result.final_abc)   # 2-voice ABC with chord progression
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
    # Main pipeline entry point
    "harmonize_melody",
    # Message types
    "Iteration",
    "HarmonizationResult",
    # Bach melody utilities
    "load_bach_melody",
    "build_harmonization_template",
    "clean_abc_for_llm",
    "AVAILABLE_BWV",
]
