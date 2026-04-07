"""
executors.py
------------
Workflow Executor wrappers and typed message models for the harmonization pipeline.

Each Executor wraps an Agent from agents.py and handles one step of the pipeline:
  1. TheoryExecutor     — runs Theory Agent, produces harmonic analysis
  2. HarmonizerExecutor — runs Harmonizer Agent, generates ABC chord progression
  3. OrchestratorExecutor — runs Orchestrator Agent, validates/cleans final ABC

Message flow:
  MelodyInput → [TheoryExecutor] → TheoryAnalysis → [HarmonizerExecutor] → HarmonizationResult
                                                                           ↑
                                                          (yielded as workflow output)

The Orchestrator is used directly in pipeline.py as a post-processing step
(not in the workflow graph, since it's a simple cleanup that doesn't need
the full agent-framework Workflow machinery).
"""

from pydantic import BaseModel

from agent_framework import Executor, WorkflowContext, handler

from .agents import create_theory_agent, create_harmonizer_agent


# ──────────────────────────────────────────────────────────────────────────────
# Typed message models
# These are Pydantic models that flow between executors in the workflow graph.
# Using typed messages makes the pipeline explicit and debuggable.
# ──────────────────────────────────────────────────────────────────────────────

class MelodyInput(BaseModel):
    """Input to the harmonization workflow.

    Attributes:
        melody_abc: A 2-voice ABC string with V:1 (melody) and V:2 (rests).
                    Produced by build_harmonization_template() in bach_melodies.py.
    """
    melody_abc: str


class TheoryAnalysis(BaseModel):
    """Output of TheoryExecutor — passed as input to HarmonizerExecutor.

    Attributes:
        melody_abc: The original melody template (passed through unchanged).
        analysis:   Measure-by-measure Roman numeral analysis from the Theory Agent.
                    Example: "Measure 1: I (T) → V7 (D)\nMeasure 2: ii6 (S) → V (D) → I (T) [PAC]"
    """
    melody_abc: str
    analysis: str


class HarmonizationResult(BaseModel):
    """Final output of the harmonization workflow.

    Attributes:
        melody_abc: The original melody template (for reference/debugging).
        analysis:   The theory analysis (intermediate step, useful for inspection).
        final_abc:  Complete 2-voice ABC with V:1 (melody) + V:2 (chord progression).
                    This string can be saved to a .abc file and loaded with util.load_abc().
    """
    melody_abc: str
    analysis: str
    final_abc: str


# ──────────────────────────────────────────────────────────────────────────────
# Workflow Executors
# Each Executor wraps one Agent and handles one step of the pipeline.
# ──────────────────────────────────────────────────────────────────────────────

class TheoryExecutor(Executor):
    """Step 1: Analyze the melody and produce a harmonic analysis.

    Wraps the Theory Agent (Claude Sonnet 4.6). Receives a MelodyInput
    containing the ABC template, sends the melody to the Theory Agent,
    and forwards the resulting analysis to the next executor.
    """

    def __init__(self):
        # 'theory' is the unique executor ID used by the WorkflowBuilder
        super().__init__("theory")
        # Create the Theory Agent once; reuse across workflow runs
        self.agent = create_theory_agent()

    @handler
    async def analyze_melody(self, input: MelodyInput, ctx: WorkflowContext[TheoryAnalysis]) -> None:
        """Ask the Theory Agent to analyze the melody, then pass results forward."""

        prompt = (
            "Analyze the harmonic content of this Bach chorale melody. "
            "The ABC notation shows V:1 (melody) and V:2 (currently all rests — ignore V:2).\n\n"
            f"{input.melody_abc}"
        )

        response = await self.agent.run(prompt)

        # Forward both the original melody and the new analysis to the next executor
        await ctx.send_message(TheoryAnalysis(
            melody_abc=input.melody_abc,
            analysis=response.text,
        ))


class HarmonizerExecutor(Executor):
    """Step 2: Generate chord progression and produce the final 2-voice ABC.

    Wraps the Harmonizer Agent (GPT-4o). Receives the melody + theory analysis
    from TheoryExecutor, sends both to the Harmonizer Agent, and yields the
    final HarmonizationResult as the workflow output.
    """

    def __init__(self):
        # 'harmonizer' is the unique executor ID used by the WorkflowBuilder
        super().__init__("harmonizer")
        # Create the Harmonizer Agent once; reuse across workflow runs
        self.agent = create_harmonizer_agent()

    @handler(input=TheoryAnalysis, workflow_output=HarmonizationResult)
    async def generate_chords(self, input, ctx) -> None:
        """Ask the Harmonizer Agent to generate V:2 chords, then yield final result."""

        prompt = (
            "Here is the melody template (V:1) and a harmonic analysis. "
            "Generate the complete 2-voice ABC score by filling in V:2 with block chords.\n\n"
            f"## Melody (ABC notation)\n{input.melody_abc}\n\n"
            f"## Harmonic Analysis\n{input.analysis}"
        )

        response = await self.agent.run(prompt)

        # Yield as workflow output — this becomes the result of workflow.run()
        await ctx.yield_output(HarmonizationResult(
            melody_abc=input.melody_abc,
            analysis=input.analysis,
            final_abc=response.text,
        ))
