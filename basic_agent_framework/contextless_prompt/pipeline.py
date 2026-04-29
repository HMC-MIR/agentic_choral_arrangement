"""
pipeline.py
-----------
Hub-and-spoke orchestration loop for the 3-agent harmonization pipeline.

The Orchestrator Agent sits at the center and mediates every exchange:

  ┌─────────────────────────────────────────────────────────┐
  │                                                         │
  │   1. Orchestrator → Harmonizer: "generate chords"       │
  │   2. Orchestrator → Theory:     "critique these chords" │
  │   3. Orchestrator evaluates critique → APPROVED/REVISE  │
  │   4. If REVISE → back to step 1 with feedback           │
  │                                                         │
  │   Repeat up to max_iterations times                     │
  └─────────────────────────────────────────────────────────┘

Each agent is called via agent.run() — the Orchestrator is an LLM that makes
the approve/revise decision, not hardcoded logic.

Usage:
    import asyncio
    from basic_agent_framework import harmonize_melody, load_bach_melody
    from basic_agent_framework.bach_melodies import build_harmonization_template

    melody  = load_bach_melody("bwv253")
    template = build_harmonization_template(melody)
    result   = asyncio.run(harmonize_melody(template))

    print(result.final_abc)          # 2-voice ABC with chords
    for it in result.iterations:     # inspect each round
        print(f"Round {it.attempt}: {'APPROVED' if it.approved else 'REVISE'}")
"""

import re

from .agents import (
    create_orchestrator_agent_prompt_only as create_orchestrator_agent,
    create_theory_agent_prompt_only as create_theory_agent,
    create_harmonizer_agent_prompt_only as create_harmonizer_agent,
)
from .executors import Iteration, HarmonizationResult


def _strip_markdown_fences(text: str) -> str:
    """Remove ```abc ... ``` or ``` ... ``` fences that LLMs sometimes add."""
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"^```\s*$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


async def harmonize_melody(
    melody_abc: str,
    *,
    max_iterations: int = 3,
    verbose: bool = True,
    orchestrator_model: str = "gpt-4o",
    theory_model: str = "claude-sonnet-4-6",
    harmonizer_model: str = "claude-sonnet-4-6",
) -> HarmonizationResult:
    """Run the hub-and-spoke harmonization pipeline.

    The Orchestrator coordinates a loop between the Harmonizer and Theory agents:
      1. Harmonizer generates (or revises) V:2 chords
      2. Theory Agent critiques the result
      3. Orchestrator reads the critique and decides APPROVED or REVISE
      4. If REVISE, the Orchestrator distills actionable feedback and sends
         it back to the Harmonizer for the next iteration

    Args:
        melody_abc:          A 2-voice ABC template (V:1 = melody, V:2 = rests).
                             Use build_harmonization_template() to generate this.
        max_iterations:      Maximum number of generate→critique→decide rounds.
                             The pipeline stops early if the Orchestrator approves.
        verbose:             If True, print status messages during execution.
        orchestrator_model:  Model for the Orchestrator agent (OpenAI).
        theory_model:        Model for the Theory agent (Anthropic).
        harmonizer_model:    Model for the Harmonizer agent (OpenAI).

    Returns:
        HarmonizationResult with the full iteration history and final ABC.
    """
    # Create the three agents
    orchestrator = create_orchestrator_agent(model=orchestrator_model)
    theory = create_theory_agent(model=theory_model)
    harmonizer = create_harmonizer_agent(model=harmonizer_model)

    iterations: list[Iteration] = []
    current_abc = ""
    previous_feedback = ""

    for i in range(1, max_iterations + 1):

        # ── Step 1: Harmonizer generates or revises ───────────────────────────
        if i == 1:
            if verbose:
                print(f"  [{i}/{max_iterations}] Harmonizer: generating initial chords...")
            harmonizer_prompt = (
                "Generate a chord progression for this melody. Replace the rests "
                "in V:2 with block chords.\n\n"
                f"{melody_abc}"
            )
        else:
            if verbose:
                print(f"  [{i}/{max_iterations}] Harmonizer: revising based on feedback...")
            harmonizer_prompt = (
                "Revise your harmonization based on this feedback.\n\n"
                f"## Original melody template\n{melody_abc}\n\n"
                f"## Your previous harmonization\n{current_abc}\n\n"
                f"## Feedback to address\n{previous_feedback}"
            )

        harmonizer_response = await harmonizer.run(harmonizer_prompt)
        current_abc = _strip_markdown_fences(harmonizer_response.text)

        # ── Step 2: Theory Agent critiques ────────────────────────────────────
        if verbose:
            print(f"  [{i}/{max_iterations}] Theory Agent: critiquing harmonization...")

        theory_prompt = (
            "Critique this harmonization of a Bach chorale melody. "
            "The key is given in the K: field. Analyze the V:2 chords against "
            "the V:1 melody.\n\n"
            f"{current_abc}"
        )

        theory_response = await theory.run(theory_prompt)
        critique = theory_response.text

        # ── Step 3: Orchestrator evaluates ────────────────────────────────────
        if verbose:
            print(f"  [{i}/{max_iterations}] Orchestrator: evaluating critique...")

        orchestrator_prompt = (
            f"This is iteration {i} of {max_iterations}.\n\n"
            f"## Current harmonization (from Harmonizer)\n{current_abc}\n\n"
            f"## Critique (from Theory Expert)\n{critique}\n\n"
            "Read the critique and decide: is this harmonization good enough, "
            "or should the Harmonizer revise it?"
        )

        orchestrator_response = await orchestrator.run(orchestrator_prompt)
        decision = orchestrator_response.text
        approved = "APPROVED" in decision.upper()

        # Record this iteration
        iterations.append(Iteration(
            attempt=i,
            harmonization=current_abc,
            critique=critique,
            decision=decision,
            approved=approved,
        ))

        if approved:
            if verbose:
                print(f"  [{i}/{max_iterations}] APPROVED")
            break

        if verbose:
            print(f"  [{i}/{max_iterations}] REVISE — sending feedback to Harmonizer")

        # Extract the Orchestrator's distilled feedback for the Harmonizer
        previous_feedback = decision

    # ── Return final result ───────────────────────────────────────────────────
    if verbose and not iterations[-1].approved:
        print(f"  Max iterations ({max_iterations}) reached — using last attempt")

    return HarmonizationResult(
        melody_abc=melody_abc,
        iterations=iterations,
        final_abc=current_abc,
    )
