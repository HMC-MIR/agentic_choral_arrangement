"""
pipeline.py
-----------
Main entry point for the 3-agent melody harmonization pipeline.

The pipeline uses Microsoft Agent Framework's Workflow API to orchestrate
two executors in sequence:

  MelodyInput
      ↓
  TheoryExecutor (Theory Agent — Claude Sonnet 4.6)
      Analyzes melody → produces Roman numeral harmonic analysis
      ↓
  HarmonizerExecutor (Harmonizer Agent — GPT-4o)
      Takes melody + analysis → generates complete 2-voice ABC
      ↓
  HarmonizationResult (final_abc ready for util.load_abc())

After the workflow completes, an optional Orchestrator Agent (GPT-4o-mini)
cleans up the final ABC (strips markdown fences, validates structure).

Usage:
    import asyncio
    from basic_agent_framework import harmonize_melody, load_bach_melody
    from basic_agent_framework.bach_melodies import build_harmonization_template

    melody_abc = load_bach_melody("bwv253")
    template   = build_harmonization_template(melody_abc)
    result     = asyncio.run(harmonize_melody(template))

    print(result.analysis)   # Roman numeral analysis from Theory Agent
    print(result.final_abc)  # Complete 2-voice ABC with chords
"""

import re

from agent_framework import WorkflowBuilder

from .executors import TheoryExecutor, HarmonizerExecutor, MelodyInput, HarmonizationResult
from .agents import create_orchestrator_agent


def _strip_markdown_fences(text: str) -> str:
    """Remove ```abc ... ``` or ``` ... ``` fences that LLMs sometimes add.

    Even with explicit instructions not to use fences, LLMs occasionally
    wrap their output in markdown code blocks. This removes those wrappers.
    """
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"^```\s*$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


async def harmonize_melody(
    melody_abc: str,
    *,
    clean_with_orchestrator: bool = True,
) -> HarmonizationResult:
    """Run the full 3-agent harmonization pipeline on a 2-voice ABC template.

    Pipeline steps:
      1. TheoryExecutor   → harmonic analysis (Roman numerals, cadence labels)
      2. HarmonizerExecutor → final 2-voice ABC with chord progression in V:2
      3. (Optional) OrchestratorAgent → final cleanup of ABC formatting

    Args:
        melody_abc:               A 2-voice ABC template string (V:1 = melody,
                                  V:2 = rests). Use build_harmonization_template()
                                  from bach_melodies.py to generate this.
        clean_with_orchestrator:  If True (default), run a final cleanup pass
                                  using the Orchestrator Agent to strip any
                                  stray markdown and validate the ABC.

    Returns:
        A HarmonizationResult with:
          - melody_abc:  The original template (unchanged)
          - analysis:    The Theory Agent's Roman numeral analysis
          - final_abc:   Complete, clean 2-voice ABC ready for util.load_abc()
    """
    # ── Step 1 & 2: Build and run the workflow ────────────────────────────────
    # Create fresh executor instances for each run (stateless — no shared state)
    theory_executor = TheoryExecutor()
    harmonizer_executor = HarmonizerExecutor()

    # Connect them sequentially: theory → harmonizer
    workflow = (
        WorkflowBuilder(start_executor=theory_executor)
        .add_edge(theory_executor, harmonizer_executor)
        .build()
    )

    # Run the workflow with the melody template as input
    run_result = await workflow.run(MelodyInput(melody_abc=melody_abc))

    # Extract the HarmonizationResult yielded by HarmonizerExecutor
    outputs = run_result.get_outputs()
    result: HarmonizationResult = outputs[0]

    # ── Step 3 (optional): Orchestrator cleanup pass ──────────────────────────
    if clean_with_orchestrator:
        # First do a quick local strip of markdown fences
        cleaned_abc = _strip_markdown_fences(result.final_abc)

        # Then ask the Orchestrator Agent to validate and clean up
        orchestrator = create_orchestrator_agent()
        cleanup_response = await orchestrator.run(
            f"Clean and validate this ABC notation:\n\n{cleaned_abc}"
        )
        final_abc = _strip_markdown_fences(cleanup_response.text)
    else:
        # Just do the local strip without an extra LLM call
        final_abc = _strip_markdown_fences(result.final_abc)

    # Return the complete result with the cleaned ABC
    return HarmonizationResult(
        melody_abc=result.melody_abc,
        analysis=result.analysis,
        final_abc=final_abc,
    )
