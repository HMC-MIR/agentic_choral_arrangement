# MIR Agentic Arrangement — Project Guide

This project is a Music Information Retrieval (MIR) toolkit built around two main goals:

1. **Sonification** — Loading, inspecting, selecting, and synthesizing ABC / MIDI music.
2. **Generation** — Multi-agent LLM-driven melody harmonization and text-to-music composition.

---

## Table of Contents

- [Repository Structure](#repository-structure)
- [Installation](#installation)
- [Core Module: `util/`](#core-module-util)
  - [util/midi\_sonify.py](#utilmidi_sonifypy)
  - [util/abc\_sonify.py](#utilabc_sonifypy)
  - [util/conversion.py](#utilconversionpy)
  - [util/extraction.py](#utilextractionpy)
  - [util/\_\_init\_\_.py](#util__init__py)
- [Notebooks](#notebooks)
- [Basic Agent Framework](#basic-agent-framework)
  - [Hub-and-Spoke Architecture](#hub-and-spoke-architecture)
  - [Agent Roles and Models](#agent-roles-and-models)
  - [The Orchestration Loop](#the-orchestration-loop)
  - [In-Context Learning with Open Music Theory](#in-context-learning-with-open-music-theory)
- [ComposerX (Legacy)](#composerx-legacy)
  - [Music Generation Pipeline](#music-generation-pipeline)
  - [Evaluation Metrics](#evaluation-metrics)
- [Legacy Code (`old/`)](#legacy-code-old)
- [Data Layout](#data-layout)
- [End-to-End Workflows](#end-to-end-workflows)

---

## Repository Structure

```
mir_agentic_arrangement/
│
├── util/                        # Shared utilities — all core logic lives here
│   ├── __init__.py              # Public API re-exports
│   ├── midi_sonify.py           # Raw MIDI manipulation and synthesis (pretty_midi-based)
│   ├── abc_sonify.py            # ABC notation → audio pipeline (abc2midi-based)
│   ├── conversion.py            # ABC ↔ MusicXML format conversion (EasyABC wrappers)
│   ├── extraction.py            # Hymn dataset lookup + SATB part extraction
│   ├── abc2xml.py               # EasyABC converter (vendored, ABC → MusicXML)
│   └── xml2abc.py               # EasyABC converter (vendored, MusicXML → ABC)
│
├── basic_agent_framework/       # 3-agent melody harmonization (hub-and-spoke)
│   ├── __init__.py              # Public API exports
│   ├── agents.py                # Agent factory functions (Orchestrator, Theory, Harmonizer)
│   ├── pipeline.py              # Hub-and-spoke orchestration loop
│   ├── executors.py             # Pydantic message types (Iteration, HarmonizationResult)
│   ├── music_theory_context.py  # Open Music Theory textbook chapters as string constants
│   ├── bach_melodies.py         # music21 corpus → ABC template pipeline
│   ├── demo.ipynb               # Interactive notebook with audio playback
│   └── GUIDE.md                 # Detailed guide for this module
│
├── ComposerX/                   # Legacy multi-agent music generation (AutoGen-based)
│   ├── music_generation/
│   │   ├── multi_agent_pipe.py      # Top-level orchestration script
│   │   ├── multi_agent_groupchat.py # AutoGen agent group chat
│   │   ├── Single_agent.py          # Single-agent generation (OpenAI)
│   │   ├── convert_abc_to_wav.py    # ABC → MIDI → WAV (abc2midi + MuseScore)
│   │   ├── converter.py             # Basic ABC → MIDI via music21
│   │   └── requirements.txt         # ComposerX-specific dependencies
│   ├── eval/
│   │   ├── metrics/metrics.py       # Music quality metrics (muspy)
│   │   └── prompt_set/              # Evaluation prompt sets
│   └── results/                     # Generated ABC / WAV outputs
│
├── notebooks/                   # Jupyter notebooks
│   ├── abc2midi_sonify_demo.ipynb   # Main ABC sonification demo
│   ├── abc_sonify_demo.ipynb        # Legacy ABC sonification demo (music21-based)
│   ├── midi_sonify_demo.ipynb       # MIDI manipulation demo
│   └── music21_exploratory.ipynb   # Exploratory music21 analysis
│
├── old/                         # Legacy implementations (kept for reference)
│   ├── midi_sonify.py               # Original midi_sonify (identical to util/)
│   └── abc_sonify.py                # music21-based ABC sonification (superseded)
│
├── data/
│   ├── hymns/                   # Source MusicXML / ABC / MIDI files
│   └── soundfonts/              # SoundFont (.sf2) files for synthesis
│
├── output/                      # Generated audio output
├── requirements.txt             # Project dependencies
├── README.md                    # Quick-start reference
└── abc2midi_sonify_overview.md  # Design notes for abc_sonify module
```

---

## Installation

```bash
conda create -n mir python=3.13
conda activate mir

# Core dependencies
pip install pretty_midi soundfile numpy music21

# Optional: SoundFont-based synthesis (much better audio quality)
brew install fluidsynth
pip install pyfluidsynth

# Required for ABC → MIDI conversion
brew install abcmidi         # macOS
# sudo apt install abcmidi   # Debian/Ubuntu
```

**Verify abc2midi is available:**

```bash
abc2midi --version
```

---

## Core Module: `util/`

All shared utilities live here. Import from the package directly:

```python
from util import load_abc, sonify_parts, extract_hymn, abc_to_musicxml
```

Or import submodules:

```python
from util import midi_sonify as ms
from util import abc_sonify as abc
```

---

### `util/midi_sonify.py`

The lowest-level module. Works directly with `pretty_midi.PrettyMIDI` objects. All other
sonification modules delegate to this for MIDI manipulation and synthesis.

#### Private helpers

| Function | Purpose |
|---|---|
| `_normalize(audio, eps)` | Scales a numpy audio array to `[-1, 1]`. |
| `_get_instrument_label(index, inst)` | Returns instrument name or GM program name; returns `"Drums"` for percussion. |
| `_copy_pm_skeleton(pm, initial_tempo)` | Creates a new `PrettyMIDI` that shares the tempo map, time signatures, and key signatures of `pm` but has no instruments. Used to preserve metadata across trimming operations. |

#### `load_midi(path) → PrettyMIDI`

Loads a MIDI file. Provides helpful error messages if the file is missing (lists nearby
`.mid` files) or has a non-standard extension.

```python
pm = ms.load_midi("data/hymns/Amazing_Grace.mid")
```

#### `list_instruments(pm) → list[dict]`

Returns a list of info dicts — one per instrument. Each dict contains:

| Key | Description |
|---|---|
| `instrument_index` | Index in `pm.instruments`. |
| `program` | GM program number. |
| `is_drum` | Whether it is a drum track. |
| `name` | Instrument name string. |
| `note_count` | Total notes. |
| `pitch_min` / `pitch_max` | MIDI pitch range. |
| `start_time` / `end_time` | Seconds. |
| `unique_pitches_count` | Number of distinct pitches. |
| `approximate_polyphony` | Estimated max simultaneous notes (sampled at ~200 time points). |

```python
for part in ms.list_instruments(pm):
    print(part["instrument_index"], part["name"], part["note_count"])
```

#### `select_instruments(pm, selector) → PrettyMIDI`

Returns a new `PrettyMIDI` containing only the matched instruments. The `selector` can be:

| Type | Behaviour |
|---|---|
| `int` | Single index (e.g. `0`). |
| `list[int]` | Multiple indices (e.g. `[0, 2]`). |
| `str` | Case-insensitive substring match on instrument name. |
| `Callable[[int, Instrument], bool]` | Custom predicate. |

```python
soprano = ms.select_instruments(pm, 0)
upper_voices = ms.select_instruments(pm, [0, 1])
strings = ms.select_instruments(pm, "violin")
```

Raises `IndexError` if index is out of range; `ValueError` if no instruments match.

#### `trim_time(pm, start_s, end_s) → PrettyMIDI`

Returns a new `PrettyMIDI` clipped to `[start_s, end_s]` seconds. The timeline is
shifted so that `start_s` becomes `t=0`. Notes, control changes, and pitch bends are
all clipped. Tempo/time-signature/key-signature maps are preserved.

```python
first_ten = ms.trim_time(pm, 0.0, 10.0)
middle = ms.trim_time(pm, 30.0, 60.0)
```

#### `estimate_measure_times(pm) → list[float]`

Returns a list of measure-start times in seconds. Derived from the tempo map and time
signatures embedded in the MIDI. Defaults to 4/4 if no time signatures are present.

#### `trim_measures(pm, start_measure, end_measure) → PrettyMIDI`

Convenience wrapper around `trim_time` that accepts 1-indexed, inclusive measure numbers.

```python
chorus = ms.trim_measures(pm, 9, 16)  # measures 9–16
```

#### `synthesize(pm, sample_rate, sf2_path) → np.ndarray`

Synthesizes a `PrettyMIDI` to a mono `float64` numpy array normalized to `[-1, 1]`.

- If `sf2_path` is given (path to a `.sf2` SoundFont), uses FluidSynth for high-quality
  sample-based synthesis.
- Otherwise falls back to pretty_midi's built-in sine-wave synthesis (robotic but dependency-free).

```python
audio = ms.synthesize(pm)                             # sine-wave
audio = ms.synthesize(pm, sf2_path="data/soundfonts/GeneralUser_GS.sf2")  # SoundFont
```

#### `mix_audio(*audios) → np.ndarray`

Sums any number of audio arrays (zero-padding shorter ones) and normalizes the result.

#### `merge_midi(*pms) → PrettyMIDI`

Combines multiple `PrettyMIDI` objects into one by collecting all their instruments.
Tempo and time-signature information is taken from the first argument.

#### `play_audio(audio, sample_rate)`

Returns an `IPython.display.Audio` widget for inline playback in Jupyter.

#### `write_wav(path, audio, sample_rate)`

Writes audio to a WAV file. Tries `soundfile` (float32) first; falls back to
`scipy.io.wavfile` (int16) if soundfile is not installed.

---

### `util/abc_sonify.py`

Higher-level module built on top of `midi_sonify`. Works with ABC notation files
rather than raw MIDI, using the native `abc2midi` CLI for conversion.

**Why `abc2midi` instead of `music21`?** The native converter handles ABC-specific
features (fermatas, ornaments, custom tempo markings) more faithfully than music21's
ABC parser.

#### `ABCScore` dataclass

The central data container for this module:

```python
@dataclasses.dataclass
class ABCScore:
    midi: pretty_midi.PrettyMIDI   # Converted MIDI object
    voice_map: dict[str, int]      # Maps voice ID (e.g. "S1V1") → instrument index
    metadata: dict                 # Parsed from ABC header (title, key, tempo, etc.)
    abc_path: pathlib.Path         # Path to the source .abc file
```

#### Private helpers

| Function | Purpose |
|---|---|
| `_check_abc2midi()` | Raises `RuntimeError` with install instructions if `abc2midi` is not on PATH. |
| `_parse_abc_header(text)` | Parses `T:`, `C:`, `M:`, `K:`, `Q:`, and `V:` fields. Returns `(metadata_dict, ordered_voice_ids)`. |
| `_parse_tempo(raw)` | Handles both `"1/4=100"` and `"120"` tempo formats. Returns BPM as `float`. |
| `_mean_pitch(instrument)` | Mean MIDI pitch across all notes in an instrument. Returns `0.0` for empty instruments. |
| `_classify_voice(mean_pitch)` | Maps mean MIDI pitch → `"Soprano"` / `"Alto"` / `"Tenor"` / `"Bass"` using pitch thresholds. |

#### `load_abc(path) → ABCScore`

The main entry point for ABC files.

1. Reads the ABC text and calls `_parse_abc_header` to extract metadata and voice IDs.
2. Runs `abc2midi` as a subprocess to produce a temporary MIDI file.
3. Loads the MIDI with `pretty_midi`.
4. Builds `voice_map` by aligning parsed voice IDs with instrument order.
5. Cleans up the temp file.

```python
score = abc.load_abc("data/hymns/Amazing_Grace.abc")
```

#### `list_parts(score) → list[dict]`

Extends `midi_sonify.list_instruments()` output with ABC-specific fields:

| Extra key | Description |
|---|---|
| `voice_id` | The voice ID from the ABC header (e.g. `"S1V1"`). |
| `mean_pitch` | Mean MIDI pitch (rounded to 1 decimal). |
| `voice` | Classified voice label (`Soprano` / `Alto` / `Tenor` / `Bass`). |

#### `select_parts(score, selector) → ABCScore`

Returns a new `ABCScore` containing only the matched parts. The `selector` is tried
in this order:

1. **Voice ID substring match** — e.g. `"S1"` matches `"S1V1"`.
2. **Voice label match** — e.g. `"Soprano"`, `"Bass"`.
3. **Instrument name substring match**.
4. **Integer index** or **list of indices**.

Raises `ValueError` listing all available parts if nothing matches.

```python
soprano = abc.select_parts(score, "Soprano")
upper   = abc.select_parts(score, [0, 1])
```

#### `sonify_part(score, selector, sample_rate, sf2_path) → (np.ndarray, int)`

Sonifies a single part. Internally calls `select_parts` then `midi_sonify.synthesize`.

#### `sonify_parts(score, selectors, sample_rate, sf2_path) → (np.ndarray, int)`

Sonifies multiple parts and combines them. Each selector is resolved independently,
then all matched instruments are merged into one `PrettyMIDI` before synthesis (preserving relative timing perfectly).

```python
audio, sr = abc.sonify_parts(score, ["Soprano", "Alto"])
```

#### `trim_time / trim_measures`

Thin wrappers around the `midi_sonify` equivalents that return `ABCScore` objects
(preserving `voice_map`, `metadata`, and `abc_path`).

#### `synthesize(score, sample_rate, sf2_path) → np.ndarray`

Synthesizes the entire score to a mono audio array.

#### `get_metadata(score) → dict`

Returns all ABC header metadata plus two computed fields:

| Key | Source |
|---|---|
| `title` | `T:` field |
| `composer` | `C:` field |
| `key` | `K:` field |
| `time_signature` | `M:` field |
| `tempo_bpm` | `Q:` field or `[Q:...]` inline |
| `num_parts` | `len(score.midi.instruments)` |
| `duration_seconds` | `score.midi.get_end_time()` |

#### `get_lyrics(source) → list[dict]`

Extracts lyrics from the raw ABC text. Accepts either an `ABCScore` or a file path.

**Parsing logic:**

- Tracks `[V:...]` inline markers to assign lyrics to the correct voice.
- `w:` lines are inline per-voice lyrics; verse numbers are inferred from `1.`, `2.`, etc. prefixes.
- `W:` lines are footer lyrics, returned with `voice="all"`.
- Lyric cleaning strips verse number prefixes, tildes (`~`), asterisks (`*`), hyphens, and extra whitespace.

Returns a list of `{"verse": int, "voice": str, "text": str}` dicts.

---

### `util/conversion.py`

Wraps the two EasyABC converters (`abc2xml.py`, `xml2abc.py`) that are bundled in the
same `util/` directory. Both converters are invoked as subprocesses using
`sys.executable` so they run in isolation.

#### `abc_to_musicxml(abc_path, output_xml) → Path`

Converts an ABC file to MusicXML by running `abc2xml.py`.

- If `output_xml` is omitted, mirrors `abc_path` with a `.musicxml` extension.
- Creates parent directories automatically.
- The converter writes to stdout; this function captures it and writes to file.

```python
xml_path = abc_to_musicxml(Path("data/hymns/Amazing_Grace.abc"))
```

#### `part_musicxml_to_abc(part_xml, output_abc) → Path`

Converts a single-part MusicXML file to ABC notation by running `xml2abc.py`.

- If `output_abc` is omitted, mirrors `part_xml` with a `.abc` extension.

```python
abc_path = part_musicxml_to_abc(Path("data/hymns/Amazing_Grace_Soprano.musicxml"))
```

**CLI usage:**

```bash
# ABC → MusicXML
python -m util.conversion Amazing_Grace.abc --output-xml Amazing_Grace.musicxml

# MusicXML → ABC
python -m util.conversion xml2abc Amazing_Grace_Soprano.musicxml
```

---

### `util/extraction.py`

Utilities for working with the hymn dataset: locating files by name or randomly,
and extracting individual SATB parts from full hymn scores.

**Dependencies:** `music21`

#### `extract_hymn(dataset_dir, hymn_stem, output_path) → Path`

Finds a hymn in `dataset_dir` by matching the filename stem (without extension).

- `output_path` is optional; if given, copies the file there.
- Raises `FileNotFoundError` if no match; `RuntimeError` if multiple matches.

```python
hymn_path = extract_hymn(Path("data/hymns"), "Amazing_Grace_(nc)pope")
```

#### `random_hymn(dataset_dir, output_path) → Path`

Picks a random `.xml` or `.musicxml` file from `dataset_dir`.

```python
hymn_path = random_hymn(Path("data/hymns"), output_path=Path("working/hymn.xml"))
```

#### `extract_part(hymn_xml, part_label, output_xml) → music21.stream.Score`

Extracts a single SATB part from a multi-part MusicXML file.

- `part_label` accepts: `S`, `A`, `T`, `B`, `Soprano`, `Alto`, `Tenor`, `Bass`.
- First tries to match `part.partName` or `part.id` against the label.
- Falls back to positional index via `PART_LABEL_MAP` (`S=0`, `A=1`, `T=2`, `B=3`).
- If `output_xml` is given, writes the result as MusicXML.

```python
soprano_score = extract_part(Path("data/hymns/Amazing_Grace.xml"), "S",
                              output_xml=Path("working/Amazing_Grace_S.musicxml"))
```

**CLI usage:**

```bash
# Extract soprano part
python -m util.extraction part Amazing_Grace.xml S --output-xml Amazing_Grace_S.musicxml

# Find a specific hymn
python -m util.extraction Amazing_Grace_(nc)pope data/hymns/ --output-path working/hymn.xml

# Pick a random hymn
python -m util.extraction data/hymns/ --random --output-path working/hymn.xml
```

---

### `util/__init__.py`

Re-exports the full public API so callers never need to know which submodule a function
lives in:

```python
from util import (
    # ABC sonification
    ABCScore, load_abc, list_parts, select_parts, abc_to_midi,
    sonify_part, sonify_parts, trim_time, trim_measures,
    estimate_measure_times, synthesize, play_audio, write_wav,
    get_metadata, get_lyrics,
    # Format conversion
    abc_to_musicxml, part_musicxml_to_abc,
    # Dataset extraction
    extract_hymn, random_hymn, extract_part,
)
```

`midi_sonify` is not re-exported by name because its API is accessed through the
ABC-level wrappers, but it can be imported directly:

```python
from util import midi_sonify as ms
```

---

## Notebooks

All notebooks live in `notebooks/` and assume they are run with the repo root as the
working directory (the first cell does `sys.path.insert(0, str(Path.cwd().parent))`
so that `import util` resolves correctly).

| Notebook | What it demonstrates |
|---|---|
| `abc2midi_sonify_demo.ipynb` | Main demo: load an ABC hymn, inspect parts, trim, sonify per-voice, play inline audio. Uses `util.abc_sonify`. |
| `abc_sonify_demo.ipynb` | Same demo using the legacy music21-based pipeline (`util.abc_sonify` + `util.midi_sonify`). Useful for comparing old vs new results. |
| `midi_sonify_demo.ipynb` | Low-level MIDI demo: load a MIDI hymn, list instruments, select/trim, synthesize with sine-wave and SoundFont. Uses `util.midi_sonify`. |
| `music21_exploratory.ipynb` | Exploratory analysis of MIDI hymns using music21 directly: parse parts, inspect notes, pitch distributions. |

**Import pattern used in all notebooks:**

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path.cwd().parent))  # repo root

from util import abc_sonify as abc
from util import midi_sonify as ms
```

---

## Basic Agent Framework

A 3-agent melody harmonization system built on
[Microsoft Agent Framework](https://learn.microsoft.com/en-us/agent-framework/),
using a **hub-and-spoke** architecture with iterative refinement. Given a Bach
chorale soprano melody in ABC notation, the pipeline produces a two-voice score
with a chord progression.

> For the full walkthrough see [`basic_agent_framework/GUIDE.md`](basic_agent_framework/GUIDE.md).

### Hub-and-Spoke Architecture

An Orchestrator agent coordinates an iterative loop between a Harmonizer (who
generates chords) and a Theory critic (who evaluates them against Open Music
Theory textbook knowledge). The Harmonizer and Theory Agent **never talk to
each other directly** — every message passes through the Orchestrator.

```
                 ┌──────────────────────┐
                 │    Orchestrator      │
                 │    (GPT-4o)          │
                 │    decides: APPROVE  │
                 │    or REVISE         │
                 └───┬──────────────┬───┘
                     │              │
            generate/│              │critique
             revise  │              │
                     ▼              ▼
           ┌──────────────┐  ┌──────────────┐
           │  Harmonizer  │  │  Theory      │
           │  (GPT-4o)    │  │  (Claude)    │
           │              │  │              │
           │  Generates   │  │  Critiques   │
           │  ABC chords  │  │  w/ OMT ctx  │
           │  No textbook │  │  No music gen│
           └──────────────┘  └──────────────┘
```

### Agent Roles and Models

| Agent | Default Model | Provider | Role |
|-------|---------------|----------|------|
| Orchestrator | GPT-4o | OpenAI | Coordinator — routes messages, decides approve/revise |
| Theory Agent | Claude Sonnet 4.6 | Anthropic | Critic — has all 6 OMT chapters, never generates music |
| Harmonizer | GPT-4o | OpenAI | Generator — writes ABC chords, no textbook context |

Each agent is created by a factory function in `agents.py` that accepts a `model`
parameter, making it easy to swap models per role.

### The Orchestration Loop

The pipeline runs up to `max_iterations` rounds (default 3):

1. **Harmonizer** generates (or revises) V:2 chords
2. **Theory Agent** critiques the result against textbook rules
3. **Orchestrator** reads the critique and decides APPROVED or REVISE
4. If REVISE, distilled feedback goes back to the Harmonizer

Each iteration is recorded as an `Iteration` Pydantic model. The full history
is returned in `HarmonizationResult.iterations`.

### In-Context Learning with Open Music Theory

The Theory Agent receives ~4,000 words of curated excerpts from
[Open Music Theory](https://openmusictheory.github.io/) covering harmonic
functions, phrase syntax, prolongation, cadence types, altered subdominants,
and applied chords. The Harmonizer gets **none** of this — it operates on
musicianship alone, improving through the feedback loop.

### Quick Start

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

### Dependencies

```bash
pip install agent-framework agent-framework-openai agent-framework-anthropic --pre
```

Both `OPENAI_API_KEY` and `ANTHROPIC_API_KEY` must be set (via `.env` at project root).

---

## ComposerX (Legacy)

A legacy multi-agent text-to-music generation system built on AutoGen. Given a natural-language prompt, a
group of LLM agents collaborates to compose an original piece in ABC notation, which
is then converted to audio.

### Music Generation Pipeline

#### Entry point: `multi_agent_pipe.py`

```bash
cd ComposerX/music_generation
python multi_agent_pipe.py --prompt "A peaceful Celtic lullaby in G major" \
                           --output_dir ../results/lullaby/
```

**What happens internally:**

1. Writes the prompt to `prompt.txt`.
2. Launches `multi_agent_groupchat.py` as a subprocess (the AutoGen group chat).
3. Captures stdout and extracts the ABC notation block (delimited by triple-backtick markers).
4. Saves the chat log to `output_dir/chat_log.txt`.
5. Saves the ABC to `output_dir/{title}.abc` (title extracted from the `T:` field).
6. Calls `convert_abc_to_wav()` to produce audio.

#### `extract_title(abc_notation) → str`

Finds the `T:` field in ABC text and returns it as a filename (`"Title.abc"`).
Returns `"Untitled.abc"` if no title is found.

#### `multi_agent_groupchat.py`

Orchestrates a group of AutoGen agents:

- **Information Extractor** — pulls musical attributes from the prompt (key, mode, time signature, tempo, style).
- **Chord Composer** — generates a chord progression in ABC notation.
- **Melody Composer** — composes a melody over the chords.
- **Group Chat Manager** — coordinates turn order and termination.

The full transcript is streamed to stdout and captured by `multi_agent_pipe.py`.

#### `Single_agent.py`

An alternative single-agent approach using the OpenAI API directly.
Supports batch generation from a JSON prompt set, with rate limiting and
multi-processing for large-scale runs.

Key prompt modes exposed:
- `CoT_instruction` — chain-of-thought 16-bar composition.
- `chord_instruction` — chord progression generation.
- `instructionICL` — in-context learning with examples.

#### `convert_abc_to_wav.py`

```python
convert_abc_to_wav(abc_file_path, results_dir="results") → Path | None
```

1. Runs `abc2midi <abc_file> -o <tmp.mid>` to convert ABC to MIDI.
2. Checks if MuseScore 4 is installed at `/Applications/MuseScore 4.app/Contents/MacOS/mscore`.
3. If found, runs MuseScore to render MIDI to WAV.
4. Returns the WAV path, or `None` if MuseScore is unavailable.

**Note:** MuseScore is optional. If absent, only the MIDI file is produced.

#### `converter.py`

A simpler, exploratory ABC-to-MIDI converter using `music21`:

```python
abc2midi(abcfile, turn) → int   # Returns 1 on success, 0 on failure
```

Used for quick batch conversion during experiments. Does not have the same
error handling as `convert_abc_to_wav.py`.

---

### Evaluation Metrics

#### `ComposerX/eval/metrics/metrics.py`

Computes a suite of objective music quality metrics from MIDI files using the `muspy`
library.

**Usage:**

```bash
python metrics.py --data_path path/to/midi_folder/ --output_path results/
```

Outputs `results/metrics.json` with the following structure:

```json
{
  "pitch_range": {"hymn1.mid": 42, "hymn2.mid": 38, ...},
  "n_pitches_used": {...},
  ...
}
```

**Metrics computed:**

| Metric | What it measures |
|---|---|
| `pitch_range` | Span of pitches used (max − min). |
| `n_pitches_used` | Count of distinct MIDI pitches. |
| `n_pitch_classes_used` | Distinct pitch classes (0–11). |
| `pitch_entropy` | Shannon entropy of pitch distribution. |
| `pitch_class_entropy` | Entropy of pitch-class distribution. |
| `pitch_in_scale_rate` | Fraction of notes that fall in the key's scale. |
| `scale_consistency` | How consistently the piece stays in one scale. |
| `polyphony` | Maximum simultaneous note count. |
| `polyphony_rate` | Fraction of beats exceeding polyphony threshold. |
| `empty_beat_rate` | Fraction of beats with no notes. |
| `empty_measure_rate` | Fraction of measures with no notes. |
| `groove_consistency` | Rhythmic consistency across measures. |
| `drum_in_pattern_rate` | Drum hits aligning with a duple-time grid. |
| `drum_pattern_consistency` | Consistency of the drum pattern. |

`pitch_in_scale_rate` uses the key and mode from the first key signature in the MIDI.

---

## Legacy Code (`old/`)

Kept for reference. Not used by any current code path.

### `old/midi_sonify.py`

Identical to `util/midi_sonify.py`. The canonical version is in `util/`.

### `old/abc_sonify.py`

The original ABC sonification module. Uses `music21` instead of `abc2midi` for
conversion. Notable differences from the current `util/abc_sonify.py`:

| Aspect | `old/abc_sonify.py` | `util/abc_sonify.py` |
|---|---|---|
| ABC parser | `music21.converter` | `abc2midi` CLI |
| Score type | `music21.stream.Score` | `ABCScore` dataclass |
| Multi-voice | Custom regex splitter (`_split_abc_voices`) | abc2midi handles natively |
| Tempo/fermata | Less reliable | Correct via abc2midi |
| Dependencies | music21, pretty_midi | abc2midi, pretty_midi |

`_split_abc_voices(text)` is the most significant unique piece of logic in the old module.
It manually splits a multi-voice ABC Plus file by scanning `[V:...]` inline markers
and reassembles per-voice ABC strings with the shared header, so each can be parsed
independently by music21.

---

## Data Layout

```
data/
├── hymns/          # Source hymn files (.xml, .musicxml, .abc, .mid)
└── soundfonts/     # SoundFont files (.sf2) for FluidSynth synthesis
```

The hymn dataset is attributed to reedperkins (MIT License). Filenames follow the
pattern `Hymn_Title_(variant)author.ext`.

**Recommended SoundFont:** `GeneralUser_GS.sf2` (General MIDI coverage).

```python
SF2 = "data/soundfonts/GeneralUser_GS.sf2"
audio = abc.synthesize(score, sf2_path=SF2)
```

---

## End-to-End Workflows

### 1. Sonify an ABC hymn (all voices)

```python
from util import load_abc, synthesize, write_wav

score = load_abc("data/hymns/Amazing_Grace.abc")
audio = synthesize(score, sf2_path="data/soundfonts/GeneralUser_GS.sf2")
write_wav("output/Amazing_Grace.wav", audio)
```

### 2. Isolate and compare SATB voices

```python
from util import load_abc, sonify_part, play_audio
from IPython.display import display

score = load_abc("data/hymns/Amazing_Grace.abc")
for voice in ["Soprano", "Alto", "Tenor", "Bass"]:
    audio, sr = sonify_part(score, voice)
    display(play_audio(audio, sr))
```

### 3. Extract a clip by measure range

```python
from util import load_abc, trim_measures, synthesize

score = load_abc("data/hymns/Amazing_Grace.abc")
chorus = trim_measures(score, 9, 16)
audio = synthesize(chorus)
```

### 4. Full pipeline: MusicXML → ABC → audio

```python
from pathlib import Path
from util import extract_hymn, extract_part, abc_to_musicxml, part_musicxml_to_abc, load_abc, synthesize

# Step 1: get a hymn from the dataset
hymn_xml = extract_hymn(Path("data/hymns"), "Amazing_Grace_(nc)pope")

# Step 2: isolate the soprano part as MusicXML
soprano_xml = extract_part(hymn_xml, "S", output_xml=Path("working/soprano.musicxml"))

# Step 3: convert to ABC
soprano_abc = part_musicxml_to_abc(soprano_xml.parts[0])
# (or use abc_to_musicxml for the reverse direction)

# Step 4: sonify
score = load_abc(soprano_abc)
audio = synthesize(score)
```

### 5. Harmonize a Bach melody with the agent pipeline

```python
import asyncio
from basic_agent_framework import (
    harmonize_melody, load_bach_melody,
    build_harmonization_template, clean_abc_for_llm,
)
from util import abc_sonify as abc
import tempfile, pathlib

# Load and prepare a Bach soprano melody
melody   = load_bach_melody("bwv253", measures=(1, 8))
template = build_harmonization_template(melody, title_override="BWV 253")
clean    = clean_abc_for_llm(template)

# Run the 3-agent pipeline
result   = asyncio.run(harmonize_melody(clean, max_iterations=3))

# Sonify the result
with tempfile.NamedTemporaryFile(mode="w", suffix=".abc", delete=False) as f:
    f.write(result.final_abc)
    tmp = pathlib.Path(f.name)

score = abc.load_abc(tmp)
audio, sr = abc.sonify_parts(score, [0, 1], sf2_path="data/soundfonts/GeneralUser_GS.sf2")
abc.write_wav("output/bwv253_harmonized.wav", audio, sr)
tmp.unlink()
```

### 6. Generate music with ComposerX (legacy)

```bash
cd ComposerX/music_generation
python multi_agent_pipe.py \
    --prompt "A Bach chorale-style SATB hymn in D major, moderato" \
    --output_dir ../results/my_chorale/
```

Output directory will contain:
- `chat_log.txt` — full agent conversation
- `{title}.abc` — generated ABC notation
- `{title}.wav` — synthesized audio (if MuseScore is installed)

### 7. Evaluate generated MIDI files

```bash
python ComposerX/eval/metrics/metrics.py \
    --data_path ComposerX/results/ \
    --output_path ComposerX/eval/output/
```
