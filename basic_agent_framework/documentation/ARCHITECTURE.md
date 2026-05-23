# Basic Agent Framework — Architecture & Design

A 3-agent melody harmonization system built on
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/),
using a **hub-and-spoke** architecture with iterative refinement.

Given a Bach chorale soprano melody in ABC notation, the pipeline produces a
two-voice score (melody + chord accompaniment). An Orchestrator agent
coordinates an iterative loop between a Harmonizer (who generates chords) and
a Theory critic (who evaluates them against music theory textbook knowledge).

---

## Table of Contents

1. [Quick Start](#1-quick-start)
2. [Architecture Overview](#2-architecture-overview)
3. [The Three Agents](#3-the-three-agents)
4. [The Orchestration Loop](#4-the-orchestration-loop)
5. [Folder Layout & Experiment Variants](#5-folder-layout--experiment-variants)
6. [File-by-File Walkthrough](#6-file-by-file-walkthrough)
7. [In-Context Learning with Open Music Theory](#7-in-context-learning-with-open-music-theory)
8. [Data Flow and Typed Messages](#8-data-flow-and-typed-messages)
9. [Microsoft Agent Framework Concepts](#9-microsoft-agent-framework-concepts)
10. [Bach Melody Loading Pipeline](#10-bach-melody-loading-pipeline)
11. [Customizing the Framework](#11-customizing-the-framework)
12. [Sonifying the Output](#12-sonifying-the-output)
13. [Evaluating the Output](#13-evaluating-the-output)
14. [Troubleshooting](#14-troubleshooting)

---

## 1. Quick Start

### Prerequisites

```bash
# Microsoft Agent Framework + provider clients
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre

# Other dependencies (should already be in the mir conda env)
pip install python-dotenv music21
```

### API keys

Create a `.env` at the **project root** (`mir_agentic_arrangement/.env`):

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

### Run in 7 lines

Pick any variant (`base`, `improved_prompt`, `chain_of_thought`,
`contextless_prompt`) — they all expose the same public API.

```python
import asyncio
from basic_agent_framework.base import (
    harmonize_melody, load_bach_melody,
    build_harmonization_template, clean_abc_for_llm,
)

melody   = load_bach_melody("bwv253", measures=(1, 10))
template = build_harmonization_template(melody, num_bars=10)
clean    = clean_abc_for_llm(template)
result   = asyncio.run(harmonize_melody(clean, max_iterations=3))

print(result.final_abc)
for it in result.iterations:
    print(f"Round {it.attempt}: {'APPROVED' if it.approved else 'REVISE'}")
```

### Run a notebook

Each variant has a `test.ipynb` that loads a melody, runs the pipeline, plays
audio for each iteration, and renders the metrics table. Use the **Python (mir)**
Jupyter kernel:

```
basic_agent_framework/base/test.ipynb
basic_agent_framework/improved_prompt/test.ipynb
basic_agent_framework/chain_of_thought/test.ipynb
basic_agent_framework/contextless_prompt/test.ipynb
```

---

## 2. Architecture Overview

### Hub-and-spoke design

```
                     ┌────────────────────────┐
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
talk to each other directly** — every message passes through the Orchestrator.
This gives full visibility into every exchange and lets the Orchestrator add
its own judgment (e.g., "the ABC doesn't parse, skip theory and ask the
harmonizer to fix syntax first").

### Why three agents instead of one?

| Concern | Single-agent | Hub-and-spoke |
|---|---|---|
| Prompt size | One massive prompt with theory + ABC rules + generation | Each agent gets a focused, shorter prompt |
| Model selection | One model must be good at everything | Pick the best model per task |
| Debuggability | Opaque — hard to tell what went wrong | Every iteration's critique and decision is inspectable |
| Quality | Single pass, no self-correction | Iterative refinement via theory feedback |
| Separation of concerns | Analysis and generation are tangled | Critic never generates; generator never critiques |

### Why a hand-written async loop instead of a workflow graph?

Microsoft Agent Framework's `WorkflowBuilder` builds static directed graphs —
ideal for fixed pipelines (A → B → C). Our loop is **dynamic and conditional**:
the Orchestrator decides at runtime whether to loop again or stop. A plain
Python `async` loop in `pipeline.py` is easier to read, easier to debug, and
makes it trivial to log intermediate state.

---

## 3. The Three Agents

### Orchestrator (GPT-4o)

**Role.** Coordinator. Routes messages between agents and makes the
stop/continue decision each iteration.

**Has.** Coordination logic in its system prompt.
**Does not have.** Any music theory context or ABC knowledge.

Output is one of:
- `DECISION: APPROVED` — harmonization is good enough; stop iterating.
- `DECISION: REVISE` — followed by 2–3 specific, actionable fixes for the
  Harmonizer.

The `base` Orchestrator is intentionally lenient. The `improved_prompt`
variant replaces this with a **deterministic decision rule** keyed off the
Theory Agent's severity counts (any CRITICAL → REVISE; iteration 1 with ≥3
MAJOR → REVISE; otherwise APPROVED).

### Theory Agent (Claude Sonnet 4.6)

**Role.** Music-theory critic grounded in textbook knowledge.

**Has.** Curated excerpts from [Open Music Theory](https://openmusictheory.github.io/)
— ~4,000 words across six chapters (harmonic functions, phrase syntax,
prolongation, cadence types, altered subdominants, applied chords).

**Does not.** Generate any ABC notation. Critique only.

Output is structured (the exact schema varies slightly between variants):

```
KEY: A major
OVERALL: The harmonization shows reasonable chord choices but has voice-leading issues.

MEASURE-BY-MEASURE:
Measure 1: [ACE] = A major (I) — correct tonic opening
Measure 2: [EGB] = E major (V) — good dominant, but parallel fifths with V:1
...

ISSUES (most severe first):
1. [SEVERITY: major] Parallel fifths between V:1 and V:2 in measures 2–3
2. [SEVERITY: minor] Measure 7 ends on V but sounds like it should be a PAC

VERDICT: NEEDS REVISION
```

The Theory Agent in `contextless_prompt` receives **no** OMT context — that
variant is an ablation that asks: "How much does the textbook actually buy us?"

### Harmonizer (GPT-4o)

**Role.** Musician who writes chord progressions in ABC notation.

**Has.** ABC notation syntax knowledge (octave conventions, block-chord
brackets, bar structure, voice headers).

**Does not have.** Any music theory textbook content. It works from training
data plus feedback from the Theory Agent.

First iteration: generate chords from scratch.
Later iterations: previous attempt + Orchestrator's distilled feedback →
targeted revision.

In the `chain_of_thought` variant the Harmonizer is required to first emit a
`<reasoning>...</reasoning>` block (phrase structure, cadence targets,
harmonic rhythm, T→S→D→T arc) before the `<abc>...</abc>` block. This forces
a global plan instead of bar-by-bar drift.

---

## 4. The Orchestration Loop

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

Each iteration is recorded as an `Iteration` Pydantic object. The full history
is available in `result.iterations` for inspection or replay.

### LLM calls per iteration

| Step | Agent | Provider | Purpose |
|---|---|---|---|
| 1 | Harmonizer | OpenAI GPT-4o | Generate or revise chords |
| 2 | Theory Agent | Anthropic Claude | Critique the result |
| 3 | Orchestrator | OpenAI GPT-4o | Evaluate and decide |

= **3 LLM calls per iteration**. A typical run uses 1–3 iterations = 3–9 calls.

---

## 5. Folder Layout & Experiment Variants

The framework ships with four sibling packages, each a complete copy of the
pipeline with one targeted variation. This makes it trivial to A/B test
prompting strategies on the same input.

| Variant | What's different | Hypothesis being tested |
|---|---|---|
| `base/` | Reference design. Three agents, OMT context for Theory, conversational prompts. | Baseline. |
| `improved_prompt/` | Same agents; Theory uses a strict severity rubric (CRITICAL/MAJOR/MINOR with `[abc]` fix snippets), Orchestrator follows a deterministic decision rule. | Structured prompts + machine-actionable fixes → faster convergence. |
| `chain_of_thought/` | Harmonizer must produce `<reasoning>` (phrase plan) before `<abc>`. | Forcing a global plan beats bar-by-bar drift. |
| `contextless_prompt/` | No OMT textbook context, terse system prompts for all three agents. | Ablation: how much does the textbook actually contribute? |

Each variant writes its outputs into a parallel folder:

```
basic_agent_framework/experiments/<variant>/<model_tag>/
    bwv253_iter1_chords.wav    # V:2 only (chords alone)
    bwv253_iter1_mix.wav       # V:1 + V:2 (melody + chords)
    bwv253_iter2_chords.wav
    bwv253_iter2_mix.wav
    bwv253_iter3_chords.wav
    bwv253_iter3_mix.wav
    bwv253_iterations.txt      # text log per round + final metric summary
```

`<model_tag>` encodes the orchestrator / theory / harmonizer models used —
e.g. `gpt-4o_claude-sonnet-4-6_claude-sonnet-4-6`.

### Adding a new variant

Copy any existing variant folder, rename it, edit the prompts in `agents.py`
(and the parsing in `pipeline.py` if your variant changes the output format),
then open the new `test.ipynb`. The notebook auto-detects its folder name and
routes audio output accordingly.

---

## 6. File-by-File Walkthrough

```
basic_agent_framework/<variant>/
├── __init__.py              # Public API exports
├── music_theory_context.py  # OMT textbook chapters as string constants
├── bach_melodies.py         # music21 corpus → ABC template pipeline
├── agents.py                # Agent factory functions (one per role)
├── executors.py             # Pydantic message types
├── pipeline.py              # Hub-and-spoke orchestration loop
└── test.ipynb               # Interactive notebook with audio + metrics
```

### `music_theory_context.py`

Six curated chapters from Open Music Theory as Python string constants:

| Constant | OMT Chapter |
|---|---|
| `HARMONIC_FUNCTIONS` | Harmonic Functions (T/S/D, scale degrees) |
| `HARMONIC_SYNTAX_PHRASE` | The Idealized Phrase (T→S→D→T cycle) |
| `HARMONIC_SYNTAX_PROLONGATION` | Prolongation (passing chords, neighbors) |
| `CADENCE_TYPES` | Classical Cadence Types (PAC, IAC, HC, DC, PC) |
| `ALTERED_SUBDOMINANT_CHORDS` | Neapolitan and augmented-sixth chords |
| `APPLIED_CHORDS` | Secondary dominants (V/V, vii°/V) |

These are concatenated into `FULL_THEORY_CONTEXT` and injected into the
Theory Agent's system prompt by `agents.py`. The Harmonizer gets **none** of
it.

### `agents.py`

Three factory functions, each returning a standard `agent_framework.Agent`:

| Factory | Default Model | Provider | OMT Context? |
|---|---|---|---|
| `create_orchestrator_agent()` | `gpt-4o` | OpenAI | No |
| `create_theory_agent()` | `claude-sonnet-4-6` | Anthropic | **Yes** (all 6 chapters) |
| `create_harmonizer_agent()` | `gpt-4o` | OpenAI | No |

Each takes an optional `model=` parameter so you can swap models per role.

### `executors.py`

Pydantic message types — the typed contract between iterations:

```python
class Iteration(BaseModel):
    attempt: int           # 1-indexed round number
    harmonization: str     # Harmonizer's ABC output this round
    critique: str          # Theory Agent's feedback
    decision: str          # Orchestrator's APPROVED/REVISE response
    approved: bool         # Whether the Orchestrator approved

class HarmonizationResult(BaseModel):
    melody_abc: str               # Original input template
    iterations: list[Iteration]   # Full history of every round
    final_abc: str                # Last (and best) ABC with V:2 chords
```

### `pipeline.py`

The hub-and-spoke loop. One async entry point:

```python
async def harmonize_melody(
    melody_abc: str,
    *,
    max_iterations: int = 3,
    verbose: bool = True,
) -> HarmonizationResult:
```

1. Instantiates all three agents.
2. Runs the loop: Harmonizer → Theory → Orchestrator decision.
3. Stops when the Orchestrator says APPROVED or `max_iterations` is reached.
4. Returns `HarmonizationResult` with the full history.

### `bach_melodies.py`

Three utilities for preparing input melodies:

- `load_bach_melody(bwv, measures)` — music21 corpus → single-voice ABC.
- `build_harmonization_template(abc, num_bars=...)` — single-voice → two-voice
  template (V:1 = melody, V:2 = rests for the Harmonizer to fill).
- `clean_abc_for_llm(abc)` — strip lyrics, fermatas, linebreak markers.

### `test.ipynb`

Step-by-step walkthrough: load a melody, play the source, run the pipeline,
play each iteration's audio side-by-side, render the per-round metrics table,
write outputs to `experiments/<variant>/<model_tag>/`.

---

## 7. In-Context Learning with Open Music Theory

### Why only the Theory Agent gets context

The hub-and-spoke roles are strictly separated:

- **Theory Agent** = the one who *knows* the rules. It needs the textbook to
  identify parallel fifths, incorrect cadences, non-functional progressions,
  etc.
- **Harmonizer** = the one who *creates*. It works from musical instinct,
  like a musician who learned by ear. The feedback loop with the Theory Agent
  is how it improves — not by reading a textbook, but by responding to
  critique.

This models a real-world collaboration: one person composes, another with
formal training reviews and provides feedback.

### What the Theory Agent receives

`FULL_THEORY_CONTEXT` (~4,000 words) covers:

1. **Harmonic functions** — T/S/D categories, which chords belong to which.
2. **Idealized phrase** — the T→S→D→T cycle and how phrases are structured.
3. **Prolongation** — how a single function extends across multiple chords.
4. **Cadence types** — PAC, IAC, HC, DC, PC.
5. **Altered subdominants** — Neapolitan, augmented sixths.
6. **Applied chords** — secondary dominants (V/V), tonicization.

The `contextless_prompt` variant deletes this entirely. Comparing it against
`base` is the cleanest answer to "does the textbook earn its tokens?"

---

## 8. Data Flow and Typed Messages

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

Every piece of intermediate state is preserved:

- `result.iterations[0].critique` — what the Theory Agent said about attempt 1.
- `result.iterations[0].harmonization` — the actual ABC of attempt 1.
- `result.iterations[-1].decision` — the Orchestrator's final verdict.

---

## 9. Microsoft Agent Framework Concepts

### Agent

The core building block. Wraps an LLM client + system prompt. Provider-agnostic:

```python
from agent_framework.openai import OpenAIChatCompletionClient
from agent_framework.anthropic import AnthropicClient

openai_agent = OpenAIChatCompletionClient(model="gpt-4o").as_agent(
    name="MyAgent", instructions="..."
)
claude_agent = AnthropicClient(model="claude-sonnet-4-6").as_agent(
    name="MyAgent", instructions="..."
)

result = await openai_agent.run("Hello")
print(result.text)
```

Same `.run()` interface regardless of provider — which is what makes mixing
GPT-4o and Claude in a single pipeline natural.

### Why not WorkflowBuilder?

`WorkflowBuilder` is for static directed graphs. Our loop is dynamic: the
Orchestrator decides at runtime whether to loop again. A plain async loop in
`pipeline.py` gives us conditional logic (`if approved: break`), easy access
to intermediate state for logging, and code that reads top-to-bottom.

The Agent abstraction still earns its place: provider-agnostic LLM calls,
streaming support, and a clean path to add sessions, middleware, and tool
use later.

---

## 10. Bach Melody Loading Pipeline

```
music21.corpus.parse("bach/bwv253")
    │
    ▼
bach.parts[0]  (soprano)
    │
    ▼
soprano.measures(1, 10)  (chorale body, 10 bars; pickup at bar 0 excluded)
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

### Available chorales (tested)

| BWV | Title | Key |
|---|---|---|
| `bwv253` | Bleib bei uns, Herr Jesu Christ | A major |
| `bwv255` | Durch Adams Fall ist ganz verderbt | D minor |
| `bwv269` | Aus meines Herzens Grunde | G major |
| `bwv274` | O Haupt voll Blut und Wunden | E major |

---

## 11. Customizing the Framework

### Swap models

Every factory accepts a `model=` parameter:

```python
from basic_agent_framework.base.agents import (
    create_theory_agent, create_harmonizer_agent, create_orchestrator_agent,
)

theory       = create_theory_agent(model="claude-opus-4-6")    # deeper analysis
harmonizer   = create_harmonizer_agent(model="gpt-4o-mini")    # faster/cheaper
orchestrator = create_orchestrator_agent(model="gpt-4o-mini")  # lighter coordinator
```

To use a different provider entirely (e.g., Ollama), import its client and
write a new factory — the same `.as_agent(...)` pattern works.

### Change iteration count

```python
result = await harmonize_melody(melody, max_iterations=5)   # more refinement
result = await harmonize_melody(melody, max_iterations=1)   # single-pass baseline
```

### Add a fourth agent

E.g. a Voice-Leading Checker that runs before the Theory Agent:

1. Add a factory to `agents.py`.
2. Add the call in `pipeline.py`'s loop.
3. Add a field to `Iteration` in `executors.py` if you want to log its output.

### Change the music theory context

Edit `music_theory_context.py` to add, remove, or modify chapters.
`FULL_THEORY_CONTEXT` is assembled at the bottom of the file and injected by
`agents.py` into the Theory Agent's system prompt.

---

## 12. Sonifying the Output

The `final_abc` string is designed to work with the project's `util` module:

```python
import tempfile, pathlib
from util import abc_sonify as abc

# load_abc expects a file path, so write to temp
with tempfile.NamedTemporaryFile(mode="w", suffix=".abc", delete=False) as f:
    f.write(result.final_abc)
    tmp_path = pathlib.Path(f.name)

score = abc.load_abc(tmp_path)
sf2   = "data/soundfonts/GeneralUser_GS.sf2"
audio, sr = abc.sonify_parts(score, [0, 1], sf2_path=sf2)

abc.play_audio(audio, sr)             # inline Jupyter playback
abc.write_wav("output.wav", audio, sr)

tmp_path.unlink()
```

To hear how the harmonization improved across iterations, sonify each
`it.harmonization` in `result.iterations`. The `test.ipynb` notebooks do this
automatically and stack the players side by side.

---

## 13. Evaluating the Output

Each `test.ipynb` runs the harmonization through `util/harmonization_metrics.py`
and prints a per-iteration table plus a final pipeline summary. Logs are
auto-saved to `experiments/<variant>/<model_tag>/<bwv>_iterations.txt`.

See [METRICS.md](METRICS.md) for the full definition of every metric, how it
is implemented, and how to read the numbers.

---

## 14. Troubleshooting

### `abc2midi parse error`

The Harmonizer sometimes produces ABC with syntax errors. The iterative loop
usually catches this (the Theory Agent flags it), but if the final output
still won't parse:

- **Re-run the pipeline** — LLM outputs are stochastic.
- **Use fewer measures** — `load_bach_melody("bwv253", measures=(1, 4))`.
- **Increase iterations** — `max_iterations=5` gives more chances to fix issues.
- **Inspect `result.iterations`** — the critique often pinpoints the syntax error.

### Architecture mismatch errors (numpy / pydantic_core)

Use the **mir** conda environment:

```bash
conda activate mir
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre
```

### API key errors

Both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` must be set. Use a `.env` at
the project root with `python-dotenv`.

### Timeout on long excerpts

With 3 agents × up to 3 iterations, a 10-measure run takes 30–60 seconds.
`verbose=True` (the default) prints progress. For faster dev iteration, use
`max_iterations=1` or fewer measures.

### Missing music21 corpus data

```python
from music21 import environment
environment.UserSettings()['autoDownload'] = 'allow'
```
