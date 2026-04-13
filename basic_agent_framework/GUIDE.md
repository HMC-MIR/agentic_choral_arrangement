# Basic Agent Framework -- Detailed Guide

A 3-agent melody harmonization system built on
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/),
using a **hub-and-spoke** architecture with iterative refinement.

Given a Bach chorale soprano melody in ABC notation, the pipeline produces a
two-voice score with a chord progression. An Orchestrator agent coordinates an
iterative loop between a Harmonizer (who generates chords) and a Theory critic
(who evaluates them against music theory textbook knowledge).

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Architecture Overview](#2-architecture-overview)
3. [The Three Agents](#3-the-three-agents)
4. [The Orchestration Loop](#4-the-orchestration-loop)
5. [File-by-File Walkthrough](#5-file-by-file-walkthrough)
6. [In-Context Learning with Open Music Theory](#6-in-context-learning-with-open-music-theory)
7. [Data Flow and Typed Messages](#7-data-flow-and-typed-messages)
8. [Microsoft Agent Framework Concepts](#8-microsoft-agent-framework-concepts)
9. [Bach Melody Loading Pipeline](#9-bach-melody-loading-pipeline)
10. [Customizing the Framework](#10-customizing-the-framework)
11. [Sonifying the Output](#11-sonifying-the-output)
12. [Troubleshooting](#12-troubleshooting)

---

## 1. Quick Start

### Prerequisites

```bash
# Install Microsoft Agent Framework and providers
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre

# Other dependencies (should already be installed in the mir conda env)
pip install python-dotenv music21
```

### API Keys

Create a `.env` file at the **project root** (`mir_agentic_arrangement/.env`):

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Run in 6 Lines

```python
import asyncio
from basic_agent_framework import (
    harmonize_melody, load_bach_melody,
    build_harmonization_template, clean_abc_for_llm,
)

melody   = load_bach_melody("bwv253", measures=(1, 8))
template = build_harmonization_template(melody, title_override="BWV 253")
clean    = clean_abc_for_llm(template)
result   = asyncio.run(harmonize_melody(clean, max_iterations=3))

for it in result.iterations:
    print(f"Round {it.attempt}: {'APPROVED' if it.approved else 'REVISE'}")
print(result.final_abc)
```

### Run the Notebook

Open `basic_agent_framework/experiment_less_prompt/experiment_less_prompt.ipynb` using the **Python (mir)** Jupyter
kernel for a step-by-step walkthrough with audio playback.

---

## 2. Architecture Overview

### Hub-and-Spoke Design

```
                     ┌───────────────────────┐
                     │     Orchestrator       │
                     │     (GPT-4o)           │
                     │                        │
                     │  - Sends melody to     │
                     │    Harmonizer          │
                     │  - Sends chords to     │
                     │    Theory for critique │
                     │  - Reads critique      │
                     │  - Decides: APPROVED   │
                     │    or REVISE           │
                     │  - Distills feedback   │
                     │    for Harmonizer      │
                     └───┬──────────────┬─────┘
                         │              │
              "generate" │              │ "critique"
              "revise"   │              │
                         ▼              ▼
              ┌──────────────┐  ┌──────────────┐
              │  Harmonizer  │  │  Theory      │
              │  (GPT-4o)    │  │  (Claude)    │
              │              │  │              │
              │  Generates   │  │  Critiques   │
              │  ABC chords  │  │  w/ OMT ctx  │
              │              │  │              │
              │  NO textbook │  │  NO music    │
              │  context     │  │  generation  │
              └──────────────┘  └──────────────┘
```

The Orchestrator sits at the center. The Harmonizer and Theory Agent **never
talk to each other directly** -- every message passes through the Orchestrator.
This gives you full visibility into every exchange and lets the Orchestrator
add its own judgment (e.g., "the ABC doesn't parse, skip theory and ask
harmonizer to fix syntax first").

### Why Three Agents Instead of One?

| Concern | Single-agent | Hub-and-spoke |
|---------|-------------|---------------|
| Prompt size | One massive prompt with theory + ABC rules + generation | Each agent gets a focused, shorter prompt |
| Model selection | One model must be good at everything | Pick the best model per task |
| Debuggability | Opaque -- hard to tell what went wrong | Every iteration's critique and decision is inspectable |
| Quality | Single pass, no self-correction | Iterative refinement via theory feedback |
| Separation of concerns | Analysis and generation are tangled | Critic never generates; generator never critiques |

---

## 3. The Three Agents

### Orchestrator (GPT-4o)

**Role**: Project manager. Routes messages between agents and makes the
stop/continue decision at each iteration.

**Has**: Coordination logic in its system prompt.
**Does NOT have**: Any music theory context or ABC notation knowledge.

The Orchestrator reads the Theory Agent's critique and outputs one of:
- `DECISION: APPROVED` -- harmonization is good enough, stop iterating
- `DECISION: REVISE` -- followed by 2-3 specific, actionable items for the Harmonizer

The Orchestrator is lenient on later iterations (diminishing returns on revision)
and strict on structural issues (wrong chords, syntax errors).

### Theory Agent (Claude Sonnet 4.6)

**Role**: Music theory critic grounded in textbook knowledge.

**Has**: All six Open Music Theory chapters (~4,000 words) covering harmonic
functions, phrase syntax, prolongation, cadence types, altered subdominants,
and applied chords.

**Does NOT**: Generate any ABC notation or music. Only critiques.

The Theory Agent's output is structured:
```
KEY: A major
OVERALL: The harmonization shows reasonable chord choices but has voice-leading issues.

MEASURE-BY-MEASURE:
Measure 1: [ACE] = A major (I) — correct tonic opening
Measure 2: [EGB] = E major (V) — good dominant, but parallel fifths with V:1
...

ISSUES (most severe first):
1. [SEVERITY: major] Parallel fifths between V:1 and V:2 in measures 2-3
2. [SEVERITY: minor] Measure 7 ends on V but sounds like it should be a PAC

VERDICT: NEEDS REVISION
```

### Harmonizer (GPT-4o)

**Role**: Musician who generates chord progressions in ABC notation.

**Has**: Detailed knowledge of ABC notation syntax (octave conventions, block
chord brackets, bar structure, voice format).

**Does NOT have**: Any music theory textbook content. Works from musical instinct
and training data, plus feedback from the Theory Agent.

On the first iteration, the Harmonizer generates chords from scratch.
On subsequent iterations, it receives its previous attempt plus the
Orchestrator's distilled feedback and makes targeted revisions.

---

## 4. The Orchestration Loop

The pipeline runs up to `max_iterations` rounds (default 3):

```
┌──────────────────────────────────────────────────────────────┐
│  Iteration i                                                 │
│                                                              │
│  1. Orchestrator → Harmonizer:                               │
│     First round:  "Generate chords for this melody"          │
│     Later rounds: "Revise based on this feedback: ..."       │
│                                                              │
│  2. Harmonizer → Orchestrator:                               │
│     Returns complete 2-voice ABC with V:2 chords             │
│                                                              │
│  3. Orchestrator → Theory Agent:                             │
│     "Critique this harmonization against the melody"         │
│                                                              │
│  4. Theory Agent → Orchestrator:                             │
│     Returns structured critique with ACCEPTABLE/NEEDS REVISION│
│                                                              │
│  5. Orchestrator evaluates critique:                         │
│     APPROVED → stop, return final ABC                        │
│     REVISE   → distill feedback, go to iteration i+1         │
└──────────────────────────────────────────────────────────────┘
```

Each iteration is recorded as an `Iteration` object with the Harmonizer's
ABC output, the Theory Agent's critique, and the Orchestrator's decision.
The full history is available in `result.iterations` for inspection.

### LLM Calls Per Iteration

| Step | Agent | LLM Provider | Purpose |
|------|-------|-------------|---------|
| 1 | Harmonizer | OpenAI GPT-4o | Generate or revise chords |
| 2 | Theory Agent | Anthropic Claude | Critique the result |
| 3 | Orchestrator | OpenAI GPT-4o | Evaluate and decide |

That's **3 LLM calls per iteration**. A typical run uses 1-3 iterations =
3-9 total LLM calls.

---

## 5. File-by-File Walkthrough

```
basic_agent_framework/
├── __init__.py                 # Public API exports
├── music_theory_context.py     # OMT textbook chapters as string constants
├── bach_melodies.py            # music21 corpus → ABC template pipeline
├── agents.py                   # Agent factory functions (one per role)
├── executors.py                # Pydantic message types (Iteration, HarmonizationResult)
├── pipeline.py                 # Hub-and-spoke orchestration loop
├── experiment_less_prompt/
│   ├── experiment_less_prompt.ipynb  # Interactive notebook (minimal-prompt pipeline)
│   └── prompt_only_framework.py
└── GUIDE.md                    # This file
```

### `music_theory_context.py`

Stores curated excerpts from [Open Music Theory](https://openmusictheory.github.io/)
as Python string constants. Six chapters are included:

| Constant | OMT Chapter |
|----------|-------------|
| `HARMONIC_FUNCTIONS` | Harmonic Functions (T/S/D, scale degrees) |
| `HARMONIC_SYNTAX_PHRASE` | The Idealized Phrase (T->S->D->T cycle) |
| `HARMONIC_SYNTAX_PROLONGATION` | Prolongation (passing chords, neighbors) |
| `CADENCE_TYPES` | Classical Cadence Types (PAC, IAC, HC, DC, PC) |
| `ALTERED_SUBDOMINANT_CHORDS` | Neapolitan and augmented-sixth chords |
| `APPLIED_CHORDS` | Secondary dominants (V/V, vii/V) |

These are assembled into `FULL_THEORY_CONTEXT` which is injected into the
Theory Agent's system prompt. The Harmonizer gets **none** of this context --
it operates on musicianship alone.

### `agents.py`

Three factory functions. Each returns a standard `agent_framework.Agent`:

| Factory Function | Default Model | Provider | Has OMT Context? |
|-----------------|---------------|----------|------------------|
| `create_orchestrator_agent()` | GPT-4o | `OpenAIChatCompletionClient` | No |
| `create_theory_agent()` | Claude Sonnet 4.6 | `AnthropicClient` | **Yes** (all 6 chapters) |
| `create_harmonizer_agent()` | GPT-4o | `OpenAIChatCompletionClient` | No |

### `executors.py`

Defines the Pydantic message types:

```python
class Iteration(BaseModel):
    attempt: int           # 1-indexed round number
    harmonization: str     # Harmonizer's ABC output this round
    critique: str          # Theory Agent's feedback
    decision: str          # Orchestrator's APPROVED/REVISE response
    approved: bool         # Whether the Orchestrator approved

class HarmonizationResult(BaseModel):
    melody_abc: str        # Original input template
    iterations: list[Iteration]  # Full history of every round
    final_abc: str         # Last (and best) ABC with V:2 chords
```

### `pipeline.py`

The hub-and-spoke loop. Exposes one async function:

```python
async def harmonize_melody(
    melody_abc: str,
    *,
    max_iterations: int = 3,
    verbose: bool = True,
) -> HarmonizationResult:
```

The function:
1. Creates all three agents
2. Runs the iteration loop (Harmonizer → Theory → Orchestrator decision)
3. Stops when the Orchestrator says APPROVED or `max_iterations` is reached
4. Returns `HarmonizationResult` with the full history

### `bach_melodies.py`

Three utilities for preparing Bach melodies (unchanged from before):
- `load_bach_melody(bwv, measures)` -- music21 corpus → single-voice ABC
- `build_harmonization_template(abc)` -- single-voice → 2-voice template
- `clean_abc_for_llm(abc)` -- strip lyrics, fermatas, linebreak markers

### `experiment_less_prompt/experiment_less_prompt.ipynb`

Interactive walkthrough (merged with the latest `aidan` demo): load melody, play audio, run
`harmonize_melody_prompt_only()`, inspect iterations, sonify, and compare rounds. Setup uses
`ANTHROPIC_API_KEY` only (all three agents are Claude in this variant).

---

## 6. In-Context Learning with Open Music Theory

### Why Only the Theory Agent Gets Context

In the hub-and-spoke design, the roles are strictly separated:

- **Theory Agent** = the one who *knows* the rules. It needs the textbook to
  identify parallel fifths, incorrect cadences, non-functional progressions, etc.
- **Harmonizer** = the one who *creates*. It works from musical instinct,
  like a musician who learned by ear. The feedback loop with the Theory Agent
  is how it improves -- not by reading a textbook, but by responding to critique.

This models a real-world collaboration: one person composes, another with formal
training reviews and provides feedback.

### What the Theory Agent Receives

The full `FULL_THEORY_CONTEXT` string (~4,000 words) covers:

1. **Harmonic Functions** -- T/S/D categories, which chords belong to which
2. **Idealized Phrase** -- the T→S→D→T cycle and how phrases are structured
3. **Prolongation** -- how a single function extends across multiple chords
4. **Cadence Types** -- PAC, IAC, HC, DC, PC with definitions and rules
5. **Altered Subdominants** -- Neapolitan, augmented sixths
6. **Applied Chords** -- secondary dominants (V/V), tonicization

This is injected directly into the Theory Agent's system prompt so it has
authoritative reference material when evaluating the Harmonizer's work.

---

## 7. Data Flow and Typed Messages

```
melody_abc (str)
     │
     ▼
┌────────────────────────────────────────────────────────────────┐
│  Iteration 1:                                                  │
│    Harmonizer.run("generate chords") → abc_v1                  │
│    TheoryAgent.run("critique this")  → critique_v1             │
│    Orchestrator.run("evaluate")      → "REVISE: fix measures…" │
│                                                                │
│    Iteration(attempt=1, harmonization=abc_v1,                  │
│              critique=critique_v1, decision=..., approved=False)│
│                                                                │
│  Iteration 2:                                                  │
│    Harmonizer.run("revise: ..." + abc_v1 + feedback) → abc_v2  │
│    TheoryAgent.run("critique this")  → critique_v2             │
│    Orchestrator.run("evaluate")      → "APPROVED"              │
│                                                                │
│    Iteration(attempt=2, harmonization=abc_v2,                  │
│              critique=critique_v2, decision=..., approved=True) │
└────────────────────────────────────────────────────────────────┘
     │
     ▼
HarmonizationResult(
    melody_abc = original template,
    iterations = [iter1, iter2],
    final_abc  = abc_v2
)
```

Every piece of intermediate data is preserved. You can:
- `result.iterations[0].critique` -- see what the Theory Agent said about the first attempt
- `result.iterations[0].harmonization` -- hear the first attempt (before feedback)
- `result.iterations[-1].decision` -- see the Orchestrator's final verdict

---

## 8. Microsoft Agent Framework Concepts

### Agent

The core building block. Wraps an LLM client + system prompt. Provider-agnostic:

```python
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.anthropic import AnthropicClient

# Same .run() interface regardless of provider
openai_agent = OpenAIChatCompletionClient(model="gpt-4o").as_agent(
    name="MyAgent", instructions="..."
)
claude_agent = AnthropicClient(model="claude-sonnet-4-6").as_agent(
    name="MyAgent", instructions="..."
)

result = await openai_agent.run("Hello")
print(result.text)
```

### Why Not WorkflowBuilder?

The Agent Framework's `WorkflowBuilder` creates static directed graphs --
great for fixed pipelines (A → B → C). But our hub-and-spoke loop has
**dynamic, conditional** flow: the Orchestrator decides at runtime whether
to loop back or stop.

Instead, we use agents directly in a Python async loop (`pipeline.py`).
This gives us:
- Natural conditional logic (`if approved: break`)
- Easy access to intermediate state for logging
- Simpler code that reads top-to-bottom

The Agent Framework's `Agent` abstraction still provides value:
provider-agnostic LLM calls, streaming support, and the ability to add
sessions, middleware, and tool use later.

---

## 9. Bach Melody Loading Pipeline

```
music21.corpus.parse("bach/bwv253")
    │
    ▼
bach.parts[0]  (soprano)
    │
    ▼
soprano.measures(1, 8)  (first 8 measures)
    │
    ▼
write("musicxml")  →  temp .musicxml file
    │
    ▼
util.conversion.part_musicxml_to_abc()  →  single-voice ABC
    │
    ▼
build_harmonization_template()  →  2-voice ABC (V:1 melody, V:2 rests)
    │
    ▼
clean_abc_for_llm()  →  cleaned (no lyrics, fermatas, linebreaks)
    │
    ▼
Ready for harmonize_melody()
```

**Available chorales** (tested):

| BWV | Title | Key |
|-----|-------|-----|
| bwv253 | Bleib bei uns, Herr Jesu Christ | A major |
| bwv255 | Durch Adams Fall ist ganz verderbt | D minor |
| bwv269 | Aus meines Herzens Grunde | G major |
| bwv274 | O Haupt voll Blut und Wunden | E major |

---

## 10. Customizing the Framework

### Swap Models

Each factory function accepts a `model` parameter:

```python
from basic_agent_framework.agents import (
    create_theory_agent, create_harmonizer_agent, create_orchestrator_agent,
)

theory      = create_theory_agent(model="claude-opus-4-6")       # deeper analysis
harmonizer  = create_harmonizer_agent(model="gpt-4o-mini")       # faster/cheaper
orchestrator = create_orchestrator_agent(model="gpt-4o-mini")    # lighter coordinator
```

To use a different provider entirely (e.g., Ollama):

```python
from agent_framework.ollama import OllamaChatClient

def create_harmonizer_agent(model="llama3"):
    return OllamaChatClient(model=model).as_agent(
        name="HarmonizerAgent",
        instructions=system_prompt,
    )
```

### Change Iteration Count

```python
# More iterations = more refinement, more API calls
result = await harmonize_melody(melody, max_iterations=5)

# Single pass, no refinement
result = await harmonize_melody(melody, max_iterations=1)
```

### Add a Fourth Agent

To add a Voice-Leading Checker that runs before the Theory Agent:

1. Add a factory to `agents.py`
2. Add the call in the iteration loop in `pipeline.py`
3. Add a message type in `executors.py` if needed

### Change the Music Theory Context

Edit `music_theory_context.py` to add, remove, or modify chapters. The
`FULL_THEORY_CONTEXT` string is assembled at the bottom of the file and
injected into the Theory Agent's system prompt via `agents.py`.

---

## 11. Sonifying the Output

The `final_abc` string is designed to work with the project's `util` module:

```python
import tempfile, pathlib
from util import abc_sonify as abc

# Write ABC to temp file (load_abc expects a file path)
with tempfile.NamedTemporaryFile(mode="w", suffix=".abc", delete=False) as f:
    f.write(result.final_abc)
    tmp_path = pathlib.Path(f.name)

# Load and parse with abc2midi
score = abc.load_abc(tmp_path)

# Synthesize both voices
sf2 = "data/soundfonts/GeneralUser_GS.sf2"
audio, sr = abc.sonify_parts(score, [0, 1], sf2_path=sf2)

# Play in Jupyter
abc.play_audio(audio, sr)

# Or save to WAV
abc.write_wav("output.wav", audio, sr)

tmp_path.unlink()
```

You can also sonify individual iterations to hear how the harmonization
improved:

```python
for it in result.iterations:
    # Write it.harmonization to temp file, load_abc, sonify...
```

---

## 12. Troubleshooting

### `abc2midi parse error`

The Harmonizer sometimes produces ABC with syntax errors. The iterative
refinement usually catches this (the Theory Agent flags it), but if the
final output still doesn't parse:

- **Re-run the pipeline** -- LLM outputs are stochastic
- **Use fewer measures** -- `load_bach_melody("bwv253", measures=(1, 4))`
- **Increase iterations** -- `max_iterations=5` gives more chances to fix issues
- **Check `result.iterations`** -- the critique often explains what's wrong

### Architecture mismatch errors (numpy / pydantic_core)

Use the **mir** conda environment:

```bash
conda activate mir
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre
```

### API key errors

Both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` must be set. Use `.env` at
the project root with `python-dotenv`.

### Timeout on large excerpts

With 3 agents and up to 3 iterations, the pipeline may take 30-60 seconds
for 8 measures. Use `verbose=True` (the default) to see progress. For faster
iteration during development, use `max_iterations=1` or fewer measures.

### Missing music21 corpus data

```python
from music21 import environment
environment.UserSettings()['autoDownload'] = 'allow'
```
