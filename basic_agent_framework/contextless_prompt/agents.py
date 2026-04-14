"""
prompt_only_framework.py
------------------------
Variant of the hub-and-spoke harmonization loop with **no injected reference
context**: no Open Music Theory textbook in the Theory agent's instructions,
and **minimal** system prompts for all three agents. User turns are short:
a single-line task prefix plus the payload (ABC, critique, etc.), without the
long markdown-section framing used in ``pipeline.py``.

Same orchestration graph as ``pipeline.harmonize_melody``; only prompts differ.

All three roles use **Anthropic** (``ANTHROPIC_API_KEY`` in ``.env``) — no OpenAI client.

Usage::

    import asyncio
    from basic_agent_framework.experiment_less_prompt.prompt_only_framework import (
        harmonize_melody_prompt_only,
    )
    from basic_agent_framework import load_bach_melody, build_harmonization_template, clean_abc_for_llm

    melody = clean_abc_for_llm(build_harmonization_template(load_bach_melody("bwv253")))
    result = asyncio.run(harmonize_melody_prompt_only(melody))
"""

import re

from agent_framework import Agent
from agent_framework.anthropic import AnthropicClient

_DEFAULT_CLAUDE = "claude-sonnet-4-6"

from ..executors import Iteration, HarmonizationResult


def _strip_markdown_fences(text: str) -> str:
    text = re.sub(r"^```[a-zA-Z]*\n?", "", text.strip(), flags=re.MULTILINE)
    text = re.sub(r"^```\s*$", "", text.strip(), flags=re.MULTILINE)
    return text.strip()


def create_orchestrator_agent_prompt_only(model: str = _DEFAULT_CLAUDE) -> Agent:
    instructions = """\
You decide if a harmonization is good enough or needs revision.
After reading the critique (and the ABC), output either:

DECISION: APPROVED
Summary: <one sentence>

or:

DECISION: REVISE
Priority issues:
1. <specific fix>
2. <specific fix>

Do not write ABC. Be stricter on wrong chords or broken notation; lenient on minor voice-leading on later attempts."""

    return AnthropicClient(model=model).as_agent(
        name="OrchestratorAgent",
        instructions=instructions,
    )


def create_theory_agent_prompt_only(model: str = _DEFAULT_CLAUDE) -> Agent:
    instructions = """\
You critique Bach-style chorale harmonizations given as ABC (V:1 melody, V:2 chords).
You never write or rewrite ABC — feedback only.

Reply with: KEY, OVERALL, MEASURE-BY-MEASURE notes, ISSUES (severity), VERDICT: ACCEPTABLE or NEEDS REVISION."""

    return AnthropicClient(model=model).as_agent(
        name="TheoryAgent",
        instructions=instructions,
    )


def create_harmonizer_agent_prompt_only(model: str = _DEFAULT_CLAUDE) -> Agent:
    instructions = """\
You complete ABC templates: fill V:2 with block chords; never change V:1.
Return only the full ABC text — no markdown fences, no commentary."""

    return AnthropicClient(model=model).as_agent(
        name="HarmonizerAgent",
        instructions=instructions,
    )


async def harmonize_melody_prompt_only(
    melody_abc: str,
    *,
    max_iterations: int = 3,
    verbose: bool = True,
) -> HarmonizationResult:
    """Like ``harmonize_melody`` but with minimal system prompts and terse user messages."""
    orchestrator = create_orchestrator_agent_prompt_only()
    theory = create_theory_agent_prompt_only()
    harmonizer = create_harmonizer_agent_prompt_only()

    iterations: list[Iteration] = []
    current_abc = ""
    previous_feedback = ""

    for i in range(1, max_iterations + 1):

        if i == 1:
            if verbose:
                print(f"  [{i}/{max_iterations}] Harmonizer: generating initial chords...")
            harmonizer_prompt = f"Harmonize (replace V:2 rests).\n\n{melody_abc}"
        else:
            if verbose:
                print(f"  [{i}/{max_iterations}] Harmonizer: revising based on feedback...")
            harmonizer_prompt = (
                f"Revise per feedback.\n{previous_feedback}\n\n"
                f"Template:\n{melody_abc}\n\nPrevious ABC:\n{current_abc}"
            )

        harmonizer_response = await harmonizer.run(harmonizer_prompt)
        current_abc = _strip_markdown_fences(harmonizer_response.text)

        if verbose:
            print(f"  [{i}/{max_iterations}] Theory Agent: critiquing harmonization...")
        theory_prompt = f"Critique.\n\n{current_abc}"
        theory_response = await theory.run(theory_prompt)
        critique = theory_response.text

        if verbose:
            print(f"  [{i}/{max_iterations}] Orchestrator: evaluating critique...")
        orchestrator_prompt = (
            f"Iteration {i}/{max_iterations}.\n\n"
            f"Critique:\n{critique}\n\nABC:\n{current_abc}"
        )
        orchestrator_response = await orchestrator.run(orchestrator_prompt)
        decision = orchestrator_response.text
        approved = "APPROVED" in decision.upper()

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
        previous_feedback = decision

    if verbose and iterations and not iterations[-1].approved:
        print(f"  Max iterations ({max_iterations}) reached — using last attempt")

    return HarmonizationResult(
        melody_abc=melody_abc,
        iterations=iterations,
        final_abc=current_abc,
    )


__all__ = [
    "create_orchestrator_agent_prompt_only",
    "create_theory_agent_prompt_only",
    "create_harmonizer_agent_prompt_only",
    "harmonize_melody_prompt_only",
]
