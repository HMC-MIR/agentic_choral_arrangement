"""
agents.py
---------
Factory functions for creating the three agents in the harmonization pipeline.

Each agent is backed by a different LLM, making the model choice transparent
and easy to change. System prompts embed relevant Open Music Theory chapters
for in-context learning.

Agents:
  - Theory Agent    (Claude Sonnet 4.6)  — analyzes melody, produces Roman numeral analysis
  - Harmonizer Agent (GPT-4o)            — generates ABC chord progression from analysis
  - Orchestrator Agent (GPT-4o-mini)     — cleans up and validates the final ABC output

Dependencies:
  pip install agent-framework agent-framework-openai agent-framework-anthropic --pre
"""

from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.anthropic import AnthropicClient

from .music_theory_context import THEORY_AGENT_CONTEXT, HARMONIZER_AGENT_CONTEXT


def create_theory_agent(model: str = "claude-sonnet-4-6") -> Agent:
    """Create the Theory Agent backed by Claude.

    This agent receives a melody in ABC notation and produces a structured,
    measure-by-measure harmonic analysis using Roman numerals and functional labels.
    Its system prompt is grounded in Open Music Theory chapters on harmonic
    functions, the idealized phrase, and prolongation.

    Args:
        model: Anthropic model name. Defaults to claude-sonnet-4-6.

    Returns:
        An Agent ready to analyze melodies.
    """
    system_prompt = f"""\
You are an expert music theorist specializing in Bach chorales and common-practice harmony.

Your task: analyze a melody in ABC notation and produce a clear, measure-by-measure
harmonic analysis using Roman numerals.

## Output Format
For each measure, write one line:
  Measure N: <chord> (<function>) [→ <chord> (<function>)]  [CADENCE TYPE if applicable]

Where:
  - <chord> is a Roman numeral with figured bass (e.g., I, V7, ii6, vii°6)
  - <function> is T (tonic), S (subdominant/pre-dominant), or D (dominant)
  - [→] separates multiple chords within a measure (if harmonic rhythm allows)
  - Cadence types: PAC, IAC, HC, DC, PC (only at phrase endings)

## Example Output
  Measure 1: I (T) → V6 (D) → I6 (T)
  Measure 2: IV (S) → ii6 (S) → V7 (D)
  Measure 3: I (T) [PAC]
  Measure 4: I (T) → V/V (D) → V (D) [HC]

## Music Theory Reference
Use the following Open Music Theory chapters as your guide:

{THEORY_AGENT_CONTEXT}

## Rules
- Stick to the key signature given in the ABC header (K: field)
- Base your analysis on the melody's scale degrees to infer implied harmony
- Consider melodic contour: a leaping melody often outlines a chord
- Identify phrase endings and label cadences
- Keep your analysis concise — one line per measure
"""

    return AnthropicClient(model=model).as_agent(
        name="TheoryAgent",
        instructions=system_prompt,
    )


def create_harmonizer_agent(model: str = "gpt-4o") -> Agent:
    """Create the Harmonizer Agent backed by GPT-4o.

    This agent takes the original melody (ABC notation) plus the Theory Agent's
    Roman numeral analysis, then generates a complete 2-voice ABC score with a
    chord progression in V:2. The output must be immediately parseable by abc2midi.

    Args:
        model: OpenAI model name. Defaults to gpt-4o.

    Returns:
        An Agent ready to generate ABC chord progressions.
    """
    system_prompt = f"""\
You are an expert Bach chorale harmonizer. Your job is to generate a chord
progression as a second voice (V:2) in ABC notation, given:
  1. A melody in V:1 (ABC notation)
  2. A harmonic analysis from a music theory expert

## Critical Output Rules
1. Return ONLY the complete, valid ABC notation — no explanation, no markdown
   fences (no ```), no prose before or after.
2. Keep all header fields (X, T, M, L, Q, K, V declarations, %%MIDI lines)
   exactly as given. Do NOT change the tempo (Q:).
3. Keep Voice 1 (V:1) exactly as given — do not alter any note, rest, or rhythm.
4. Replace every rest in Voice 2 (V:2) with block chords that match the harmonic
   analysis. Use the chord inversion and rhythm that fits the time signature.
5. V:2 MUST have exactly the same number of bars as V:1.
6. The note values in each V:2 bar must sum to exactly one bar of the given
   time signature.
7. The output must parse correctly with abc2midi.
8. Do not add extra voices, lyrics, or new header fields.

## Voice Format (CRITICAL)
Use the V:n header style where each voice's notes appear directly below its
V: declaration. Do NOT use [V:n] inline markers. Structure:

  V:1 name="Melody" clef=treble
  %%MIDI program 1 40
  <melody notes unchanged>
  V:2 name="Chords" clef=treble
  %%MIDI program 2 0
  <your chords here>

## Chord Voicing in ABC Notation
In ABC, a block chord is written with brackets: [CEG] = C major triad.
  - Use uppercase for notes in the 4th octave (middle C = C)
  - Use lowercase for notes in the 5th octave (c = C5)
  - Example 4/4 bar: [A,CE] [CEG] [EGc] [CEG] |  (four quarter-note chords)
  - Example with dotted rhythms: [A,CE]3/2 [DF A] / |

## Music Theory Reference
Use the following chapters to select appropriate chord types and cadence formulas:

{HARMONIZER_AGENT_CONTEXT}
"""

    return OpenAIChatCompletionClient(model=model).as_agent(
        name="HarmonizerAgent",
        instructions=system_prompt,
    )


def create_orchestrator_agent(model: str = "gpt-4o-mini") -> Agent:
    """Create the Orchestrator Agent backed by GPT-4o-mini.

    This lightweight agent performs a final cleanup pass on the ABC output:
    strips any accidental markdown fences, validates basic structure, and
    returns clean ABC text.

    Args:
        model: OpenAI model name. Defaults to gpt-4o-mini.

    Returns:
        An Agent ready to clean up ABC notation strings.
    """
    system_prompt = """\
You are an ABC notation validator and cleaner.

Your task: given a piece of ABC notation, ensure it is clean and well-formed.

Rules:
  1. Remove any markdown code fences (``` or ```abc) if present.
  2. Ensure the ABC starts with X: and ends with |] on the last bar.
  3. Do not change any notes, rhythms, or musical content.
  4. Return ONLY the raw ABC text — no explanation, no extra lines.

If the input is already clean, return it unchanged.
"""

    return OpenAIChatCompletionClient(model=model).as_agent(
        name="OrchestratorAgent",
        instructions=system_prompt,
    )
