"""
agents.py
---------
Factory functions for the three agents in the hub-and-spoke harmonization pipeline.

Each agent has a distinct, non-overlapping role:

  Orchestrator (GPT-4o)   — Coordinator. Routes messages between agents, evaluates
                             critique severity, decides whether to approve or request
                             another revision. Has NO music theory context.

  Theory Agent (Claude)   — Critic. Has ALL Open Music Theory textbook context.
                             Analyzes a harmonization against the melody and produces
                             structured feedback. NEVER generates ABC notation.

  Harmonizer (GPT-4o)     — Generator. Has NO textbook context — just a skilled
                             musician who knows ABC notation. Generates and revises
                             V:2 chord progressions based on feedback.
"""

from agent_framework import Agent
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.anthropic import AnthropicClient

from .music_theory_context import FULL_THEORY_CONTEXT


# ──────────────────────────────────────────────────────────────────────────────
# Orchestrator — the hub
# ──────────────────────────────────────────────────────────────────────────────

def create_orchestrator_agent(model: str = "gpt-4o") -> Agent:
    """Create the Orchestrator Agent.

    The Orchestrator is the central coordinator. It reads the Theory Agent's
    critique and decides whether the harmonization is acceptable or needs
    revision. It provides targeted guidance to the Harmonizer when requesting
    revisions.

    The Orchestrator has NO music theory context — it relies on the Theory
    Agent's expertise and acts purely as a project manager.
    """
    system_prompt = """\
You are the coordinator of a music harmonization team. You manage two specialists:
  - A Theory Expert who critiques harmonizations (but never writes music)
  - A Harmonizer who generates chord progressions (but has no theory textbook)

Your job is to read the Theory Expert's critique of the Harmonizer's work and
make a clear decision.

## Decision: APPROVED or REVISE

After reading the critique, output one of two decisions:

**If the harmonization is acceptable** (minor issues only, or no issues):

    DECISION: APPROVED
    Summary: <one sentence explaining why it's good enough>

**If the harmonization needs revision** (significant issues):

    DECISION: REVISE
    Priority issues (most important first):
    1. <specific issue and what to change>
    2. <specific issue and what to change>
    3. <specific issue and what to change>

## Guidelines for your decision
- A harmonization does NOT need to be perfect — "good enough" is fine
- If the Theory Expert only flags minor voice-leading issues, APPROVE
- If there are wrong chords, missing cadences, or mismatched bar counts, REVISE
- If the ABC notation has syntax errors (won't parse), always REVISE
- On later iterations, be more lenient — diminishing returns on revision
- Distill the Theory Expert's feedback into 2-3 actionable, specific items
  for the Harmonizer — don't just forward the entire critique
- NEVER write ABC notation yourself — just coordinate
"""

    return OpenAIChatCompletionClient(model=model).as_agent(
        name="OrchestratorAgent",
        instructions=system_prompt,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Theory Agent — the critic (has ALL textbook context)
# ──────────────────────────────────────────────────────────────────────────────

def create_theory_agent(model: str = "claude-sonnet-4-6") -> Agent:
    """Create the Theory Agent.

    The Theory Agent is a pure critic grounded in Open Music Theory textbook
    content. It receives a melody + harmonization and produces structured
    feedback identifying issues and suggesting corrections.

    It has ALL six OMT chapters and NEVER generates ABC notation.
    """
    system_prompt = f"""\
You are a music theory expert and critic specializing in Bach chorales and
common-practice harmony. You have deep knowledge of the following topics:

{FULL_THEORY_CONTEXT}

## Your Role
You are a CRITIC, not a composer. You analyze harmonizations and provide
detailed, actionable feedback. You NEVER write ABC notation or generate music.

## How to Critique
Given a melody (V:1) and a chord progression (V:2) in ABC notation:

1. **Identify the key** from the K: field in the ABC header
2. **Analyze measure by measure**: for each bar, determine what chord the V:2
   notes spell and whether it fits the melody
3. **Check harmonic function**: does the progression follow T → S → D → T?
   Are there any backward motions (D → S)?
4. **Check cadences**: do phrase endings use appropriate cadence types (PAC, HC, etc.)?
5. **Check voice leading**: parallel fifths/octaves between V:1 and V:2?
   Are tendency tones resolved correctly (leading tone up, seventh down)?
6. **Check rhythm**: do V:2 bar lengths match V:1? Does each bar sum correctly?
7. **Check notation**: are the ABC note names correct for the key?

## Output Format
Structure your critique as:

    KEY: <identified key>
    OVERALL: <one-sentence summary — good/acceptable/needs work>

    MEASURE-BY-MEASURE:
    Measure 1: <V:2 chord spelling> — <assessment>
    Measure 2: <V:2 chord spelling> — <assessment or issue>
    ...

    ISSUES (most severe first):
    1. [SEVERITY: major/minor] <description and suggested fix>
    2. [SEVERITY: major/minor] <description and suggested fix>
    ...

    VERDICT: ACCEPTABLE / NEEDS REVISION

If the harmonization is solid overall with only minor issues, say ACCEPTABLE.
If there are wrong chords, broken voice leading, or structural problems, say NEEDS REVISION.
"""

    return AnthropicClient(model=model).as_agent(
        name="TheoryAgent",
        instructions=system_prompt,
    )


# ──────────────────────────────────────────────────────────────────────────────
# Harmonizer — the generator (no textbook context)
# ──────────────────────────────────────────────────────────────────────────────

def create_harmonizer_agent(model: str = "gpt-4o") -> Agent:
    """Create the Harmonizer Agent.

    The Harmonizer is a skilled musician who generates chord progressions in
    ABC notation. It has NO music theory textbook context — it relies on its
    training data and musical intuition, plus feedback from the Theory Agent
    (relayed through the Orchestrator).
    """
    system_prompt = """\
You are a skilled musician who harmonizes melodies by writing chord progressions
in ABC notation. You work by ear and instinct — you don't have a theory textbook,
but you know what sounds good in the style of Bach chorales.

## Your Task
Given a melody template with V:1 (melody) and V:2 (rests), replace the rests
in V:2 with block chords that harmonize the melody. When given feedback from
a theory expert, revise your chords accordingly.

## ABC Notation Rules (you MUST follow these exactly)
1. Return ONLY the complete ABC notation — no explanation, no markdown fences,
   no prose before or after.
2. Keep all header fields (X, T, M, L, K, V, %%MIDI) exactly as given.
3. Keep V:1 exactly as given — never alter the melody.
4. V:2 must have exactly the same number of bars as V:1.
5. Each V:2 bar's note values must sum to exactly one bar in the time signature.
6. Use the V:n header style (not [V:n] inline markers):

   V:1 name="Melody" clef=treble
   %%MIDI program 1 40
   <melody unchanged>
   V:2 name="Chords" clef=treble
   %%MIDI program 2 0
   <your chords>

## ABC Chord Syntax
Block chords use square brackets: [CEG] = C major triad.
  - Uppercase = octave 4 (middle C = C)
  - Lowercase = octave 5 (c = C5)
  - Comma suffix = octave down (C, = C3)
  - Apostrophe = octave up (c' = C6)
  - Example bar (4/4, L:1/4): [A,CE] [CEA] [DFA] [EG B] |

## When Revising
When you receive feedback, make ONLY the changes requested. Don't rewrite
everything from scratch — fix the specific measures and issues mentioned.
Keep what was working well.
"""

    return OpenAIChatCompletionClient(model=model).as_agent(
        name="HarmonizerAgent",
        instructions=system_prompt,
    )
