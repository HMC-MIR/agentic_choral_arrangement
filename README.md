# MIR Agentic Arrangement

A Music Information Retrieval toolkit for **sonifying** and **generating**
chorale-style music. Two halves:

1. **Sonification utilities** (`util/`) — load, inspect, trim, and synthesize
   MIDI / ABC scores, including per-voice (SATB) extraction.
2. **Multi-agent harmonization** (`basic_agent_framework/`) — a 3-agent
   hub-and-spoke pipeline (Orchestrator + Theory critic + Harmonizer) that
   takes a Bach soprano melody and generates a chord accompaniment,
   iteratively refining it against music-theory feedback.

## Documentation

Start here based on what you want to do:

| Goal | Read |
|---|---|
| End-to-end project tour (utilities, notebooks, agent framework, ComposerX) | [docs/GUIDE.md](docs/GUIDE.md) |
| Architecture & design of the agent framework | [basic_agent_framework/documentation/ARCHITECTURE.md](basic_agent_framework/documentation/ARCHITECTURE.md) |
| What every harmonization metric measures (reference) | [basic_agent_framework/documentation/METRICS.md](basic_agent_framework/documentation/METRICS.md) |
| Why those metrics were chosen (design spec) | [docs/METRICS_DESIGN.md](docs/METRICS_DESIGN.md) |
| Just run the agent framework | [basic_agent_framework/documentation/README.md](basic_agent_framework/documentation/README.md) |

## Repository at a glance

```
mir_agentic_arrangement/
├── util/                     # Sonification + conversion + metrics
│   ├── midi_sonify.py        # Load / inspect / trim / synthesize MIDI
│   ├── abc_sonify.py         # ABC notation → audio (via abc2midi)
│   ├── conversion.py         # ABC ↔ MusicXML
│   ├── extraction.py         # Hymn dataset lookup + SATB part extraction
│   └── harmonization_metrics.py  # Evaluation metrics for the agent pipeline
├── basic_agent_framework/    # 3-agent harmonization system
│   ├── base/                 # Reference variant
│   ├── improved_prompt/      # Structured-rubric variant
│   ├── chain_of_thought/     # Reasoning-before-ABC variant
│   ├── contextless_prompt/   # Ablation (no theory context)
│   ├── experiments/          # Generated audio + iteration logs
│   └── documentation/        # Architecture & metrics docs for this module
├── notebooks/                # Sonification demos + scratchpads
├── docs/                     # Project-wide docs (GUIDE, METRICS_DESIGN)
├── data/                     # Hymn dataset + soundfonts
├── ComposerX/                # Legacy AutoGen-based generation pipeline
├── old/                      # Superseded earlier implementations
└── output/                   # Generated audio (gitignored)
```

## Setup

```bash
# 1. Create environment
conda create -n mir python=3.13
conda activate mir

# 2. Core dependencies
pip install pretty_midi soundfile numpy music21

# 3. Agent framework (optional — only if running basic_agent_framework)
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre
pip install python-dotenv

# 4. SoundFont synthesis (optional but recommended)
brew install fluidsynth          # macOS
pip install pyfluidsynth
# Download GeneralUser_GS.sf2 from https://schristiancollins.com/generaluser.php

# 5. ABC ↔ MIDI conversion (required for util/abc_sonify)
brew install abcmidi             # macOS
# sudo apt install abcmidi       # Debian/Ubuntu
```

For the agent framework, also create a `.env` at the project root:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
```

## Quick start

### Sonify an ABC hymn

```python
from util import load_abc, synthesize, write_wav

score = load_abc("data/hymns/Amazing_Grace.abc")
audio = synthesize(score, sf2_path="data/soundfonts/GeneralUser_GS.sf2")
write_wav("output/Amazing_Grace.wav", audio)
```

### Harmonize a Bach melody with the agent pipeline

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
```

For more, open any of:
- `notebooks/abc2midi_sonify_demo.ipynb` — sonification walkthrough
- `basic_agent_framework/<variant>/test.ipynb` — agent pipeline with audio + metrics
