# Basic Agent Framework — Documentation

A 3-agent system that takes a Bach chorale soprano melody (in ABC notation) and
generates a chord accompaniment, then iteratively refines it against music theory
feedback.

## Where to start

| If you want to... | Read |
|---|---|
| Understand what was built and why | [ARCHITECTURE.md](ARCHITECTURE.md) |
| Understand how generated harmonizations are scored | [METRICS.md](METRICS.md) |
| Just run it | [ARCHITECTURE.md §1 — Quick Start](ARCHITECTURE.md#1-quick-start) |
| See it in a notebook | Open `basic_agent_framework/<variant>/test.ipynb` |

## At a glance

```
basic_agent_framework/
├── base/                  # Reference 3-agent hub-and-spoke pipeline
├── improved_prompt/       # Same agents, more rigorous structured prompts
├── chain_of_thought/      # Harmonizer must write a plan before any ABC
├── contextless_prompt/    # No textbook context, terse prompts (ablation)
├── experiments/           # Generated audio + iteration logs from each variant
└── documentation/         # ← you are here
```

Each `<variant>/` is a self-contained Python package (`agents.py`,
`pipeline.py`, `executors.py`, `music_theory_context.py`, `bach_melodies.py`,
`test.ipynb`). They share the same architecture; only the prompts and a few
agent behaviors differ. This lets you run all four variants against the same
input and compare results.

## The core idea

An **Orchestrator** sits in the middle of a loop between a **Harmonizer** (who
writes chords) and a **Theory Agent** (who critiques them against textbook
rules). The Harmonizer and Theory Agent never talk directly — every exchange
passes through the Orchestrator, which decides each round whether the
harmonization is good enough (`APPROVED`) or needs another revision (`REVISE`).

See [ARCHITECTURE.md](ARCHITECTURE.md) for the design rationale, the file
layout, and how each variant differs.
