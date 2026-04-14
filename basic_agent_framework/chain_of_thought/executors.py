"""
executors.py
------------
Typed message models for the hub-and-spoke harmonization pipeline.

These Pydantic models define the data that flows through the pipeline. Using
typed models (rather than raw strings) makes each step's input/output explicit
and easy to inspect in the demo notebook.

Message flow:

  melody_abc (str)
       │
       ▼
  ┌─────────────────────────────────────────────────────────────┐
  │  Iteration 1..N:                                            │
  │                                                             │
  │   Orchestrator → Harmonizer: "generate/revise chords"       │
  │   Orchestrator → Theory:     "critique this harmonization"  │
  │   Orchestrator reads critique → APPROVED or REVISE          │
  │                                                             │
  │   Each iteration is recorded as an Iteration object         │
  └─────────────────────────────────────────────────────────────┘
       │
       ▼
  HarmonizationResult(melody_abc, iterations, final_abc)
"""

from pydantic import BaseModel


class Iteration(BaseModel):
    """One round of the generate → critique → decide loop.

    Each iteration captures the full state so you can inspect what happened
    at every step — useful for debugging and understanding agent behavior.

    Attributes:
        attempt:              1-indexed iteration number.
        harmonizer_reasoning: The Harmonizer's chain-of-thought plan (key, phrase
                              structure, cadences, harmonic arc) written before
                              the ABC.  Empty string if the Harmonizer did not
                              produce a <reasoning> block.
        harmonization:        The ABC V:2 chord output from the Harmonizer this round.
        critique:             The Theory Agent's feedback on the harmonization.
        decision:             The Orchestrator's response (contains APPROVED or REVISE).
        approved:             Whether the Orchestrator approved this iteration.
    """
    attempt: int
    harmonizer_reasoning: str = ""
    harmonization: str
    critique: str
    decision: str
    approved: bool


class HarmonizationResult(BaseModel):
    """Final output of the harmonization pipeline.

    Attributes:
        melody_abc:  The original 2-voice ABC template that was input to the pipeline.
        iterations:  Full history of every generate→critique→decide round. The last
                     iteration's harmonization is the final (possibly approved) version.
        final_abc:   The cleaned, final 2-voice ABC string with V:1 (melody) and
                     V:2 (chord progression). Ready for util.load_abc().
    """
    melody_abc: str
    iterations: list[Iteration]
    final_abc: str
