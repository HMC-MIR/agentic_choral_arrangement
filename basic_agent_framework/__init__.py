"""
basic_agent_framework
---------------------
A 3-agent melody harmonization framework built on Microsoft Agent Framework.

The pipeline takes a Bach chorale melody in ABC notation and uses three
specialized LLM agents to generate a chord progression:

  1. Theory Agent    (Claude Sonnet 4.6)  — Roman numeral harmonic analysis
  2. Harmonizer Agent (GPT-4o)            — generates ABC V:2 chord progression
  3. Orchestrator Agent (GPT-4o-mini)     — validates and cleans final ABC output

Quick start:
    import asyncio
    from basic_agent_framework import harmonize_melody
    from basic_agent_framework.bach_melodies import (
        load_bach_melody, build_harmonization_template, clean_abc_for_llm
    )

    melody_abc = load_bach_melody("bwv253")
    template   = build_harmonization_template(melody_abc)
    clean      = clean_abc_for_llm(template)

    result = asyncio.run(harmonize_melody(clean))
    print(result.analysis)    # Roman numeral analysis
    print(result.final_abc)   # 2-voice ABC with chord progression
"""

from .pipeline import harmonize_melody
from .executors import MelodyInput, TheoryAnalysis, HarmonizationResult
from .bach_melodies import (
    load_bach_melody,
    build_harmonization_template,
    clean_abc_for_llm,
    AVAILABLE_BWV,
)

__all__ = [
    # Main pipeline entry point
    "harmonize_melody",
    # Message types (useful for type hints and inspection)
    "MelodyInput",
    "TheoryAnalysis",
    "HarmonizationResult",
    # Bach melody utilities
    "load_bach_melody",
    "build_harmonization_template",
    "clean_abc_for_llm",
    "AVAILABLE_BWV",
]
