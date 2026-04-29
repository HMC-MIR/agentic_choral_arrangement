# Prompt: Implement Harmonization Evaluation Metrics

Use this prompt with Claude in the project context. It instructs Claude to create a reusable metrics utility and update each experiment notebook to display metrics per iteration.

---

## Prompt

I need you to implement a harmonization evaluation metrics utility for my multi-agent Bach chorale harmonization project. Here is the full context before you write any code.

### Project structure

```
mir_agentic_arrangement/
├── basic_agent_framework/
│   ├── base/
│   │   ├── test.ipynb          ← experiment notebook
│   │   ├── pipeline.py
│   │   ├── agents.py
│   │   └── ...
│   ├── improved_prompt/
│   │   └── test.ipynb
│   ├── chain_of_thought/
│   │   └── test.ipynb
│   ├── contextless_prompt/
│   │   └── test.ipynb
│   └── experiments/            ← audio + log outputs per experiment
├── util/
│   ├── abc_sonify.py
│   ├── extraction.py
│   └── ...                     ← PUT THE NEW FILE HERE: util/harmonization_metrics.py
├── data/
│   └── soundfonts/
└── requirements.txt
```

### What my system outputs

Each experiment runs a 3-agent pipeline (Orchestrator, Theory Agent, Harmonizer) for up to 3 iterations on the soprano line of bwv253 (measures 1-10, A major, 4/4). The output is a `HarmonizationResult` with a `.iterations` list. Each iteration has:
- `it.attempt` — integer round number (1, 2, 3)
- `it.harmonization` — full 2-voice ABC notation string
- `it.approved` — bool (True if Orchestrator said APPROVE)
- `it.critique` — Theory Agent prose critique
- `it.decision` — Orchestrator decision text

The ABC notation has two voices:
- `V:1` — soprano melody (verbatim from Bach, never changes)
- `V:2` — block chord stacks the LLM generates, like `[A,EAc] [C#EAc] [F#,EAc]`

This is a chord progression (one voice playing stacked chords), NOT true four-part SATB with independent alto/tenor/bass lines. Keep this in mind when implementing voice-leading checks.

### Metrics to implement

**1. Rule violations** (count per harmonization, lower is better):

- `doubled_leading_tone` — count of chords in V:2 where the leading tone (G# in A major) appears more than once in the chord stack. Lower is better.

- `unresolved_leading_tone` — count of consecutive chord pairs where G# appears in chord N AND chord N+1 does NOT contain A (pitch class 9). This is the violation: G# present but fails to resolve up to A. Lower is better. Do NOT count pairs where G# resolves correctly to A — those are correct voice leading, not violations.

- `parallel_fifth_octave` — implement using a pseudo-voice heuristic since we have block chords not independent melodic lines. Sort the pitches in each chord stack from lowest to highest. Pair the lowest pitch of chord N with the lowest of chord N+1, second-lowest with second-lowest, and so on (align by position from bottom). For each such pair, compute the harmonic interval within each chord (i.e. the interval between voice position i and voice position i+1 within the same chord). If the same perfect fifth (7 semitones) or perfect octave (12 semitones) interval appears between the same two positional voices in both chord N and chord N+1, count it as a parallel motion violation. This approximates traditional parallel fifths/octaves detection without requiring true independent voice tracking. Lower is better.

**2. Melody-chord fit metrics** (from Yeh 2021 — higher is better for CTnCTR and PCS, lower is better for MCTD):

- `ctnctr` — Chord Tone to Non-Chord Tone Ratio: for each soprano note in V:1, check if its pitch class is present in the chord stack playing at that beat. Return ratio of matches to total soprano notes.
- `pcs` — Pitch Consonance Score: for each soprano note, compute consonance against each pitch in the chord stack. Use interval consonance weights: unison/octave=1.0, M3/m3/M6/m6=0.8, P5=0.7, P4=0.4, M2/m7=−0.2, m2/M7/tritone=−1.0. Return average score across all soprano notes.
- `mctd` — Melody-Chord Tonal Distance: compute as the average minimum chromatic distance from the soprano note's pitch class to the nearest pitch class in the chord stack at that beat. Do NOT use `music21.analysis.tonalyzer` — that module does not exist in music21 and will raise an ImportError. Implement manually: for each soprano note, compute `min(abs(soprano_pc - chord_pc) % 12 for chord_pc in chord.pitchClasses)`, average across all soprano notes. Lower is better. This is a simplified proxy for tonal pitch space distance that avoids a non-existent dependency.

**3. Harmonic/structural metrics:**

- `cadence_score` — fraction of phrase endings that have correct cadential harmony. Load the source chorale from music21's corpus (`corpus.parse(f'bach/{bwv}')`), find all fermata positions by scanning for `expressions.Fermata` on notes — these mark phrase endings in Bach chorales. For each fermata position, extract the last two chords from V:2 immediately before and on that beat. Convert both to Roman numerals using `roman.romanNumeralFromChord(chord, key)`. Classify the two-chord cadence pattern and score as follows: V→I = 1.0 (authentic cadence), IV→I = 0.8 (plagal cadence), any chord→V = 0.6 (half cadence), I→V→I where only the final I is at fermata = 1.0, anything else = 0.0. Return mean score across all phrase endings. Do NOT score based on a single chord alone — a lone V or I without context misses what makes it a cadence.
- `diatonic_coverage` — fraction of V:2 chords whose Roman numeral is diatonic in A major (i.e. I, ii, iii, IV, V, vi, vii°). Chords outside the key score 0.
- `bigram_typicality` — do NOT build the bigram table from only four chorales (bwv253, bwv255, bwv269, bwv274). A table built from ~40–60 chord transitions is too sparse — almost any standard tonal progression will appear "unattested" simply because the reference is too small. Instead use a hand-built diatonic transition score based on common-practice tonal harmony rules for A major. Score each consecutive chord pair (expressed as Roman numerals) using this rubric: I→IV=1.0, I→V=1.0, I→ii=1.0, I→vi=1.0, ii→V=1.0, ii→vii°=0.9, IV→V=1.0, IV→I=0.9, V→I=1.0, V→vi=0.8 (deceptive), vi→ii=0.9, vi→IV=0.9, vi→V=0.8, iii→vi=0.8, iii→IV=0.7, any diatonic→any diatonic not listed=0.5, any transition involving a chromatic chord=0.1. Return the mean score across all consecutive chord pairs in V:2. Higher is better. Use `@functools.lru_cache` on the rubric dict construction since it is constant.

**4. Pipeline behavior metrics** (computed across iterations of one run, not per harmonization):

- `approve_rate` — fraction of iterations that were APPROVED
- `avg_rounds_to_approve` — if approved, which round. If never approved, return `max_iterations`.
- `metric_delta` — for each numeric metric above, compute the change from iteration N to iteration N+1. Return a dict of lists.

### Implementation instructions

**Step 1 — Create `util/harmonization_metrics.py`**

Write a single self-contained Python module at `util/harmonization_metrics.py`. It must:

- Import music21 at the top. All music21 parsing should be done inside functions, not at import time, so the module imports quickly even if music21 is slow to start.
- Expose one main entry point: `compute_metrics(abc_text: str, bwv: str = "bwv253") -> dict` that returns a flat dict of all per-harmonization metrics listed above.
- Expose a second function: `compute_pipeline_metrics(iterations: list) -> dict` that takes the `result.iterations` list and returns pipeline behavior metrics plus a per-iteration breakdown.
- Expose a third function: `format_metrics_html(metrics: dict) -> str` that returns a compact HTML string suitable for `display(HTML(...))` in a Jupyter notebook — a small table with metric name, value, and a colored indicator (green = good, red = bad) based on reasonable thresholds.
- Parse the ABC text using music21's `converter.parse(abc_text, format='abc')` to get a Score object. Then use `score.chordify()` to extract chord objects per beat for V:2 analysis. Extract V:1 soprano notes separately by part index.
- For the JSB bigram table, build it once using `@functools.lru_cache` so it is only computed on first call per session.
- Handle parse failures gracefully — if music21 cannot parse the ABC, return a dict with all metrics set to `None` and include an `'error'` key with the exception message.
- Add a brief docstring to each function explaining what it computes and what the return dict keys are.

**Step 2 — Update all four experiment notebooks**

Modify `basic_agent_framework/base/test.ipynb`, `improved_prompt/test.ipynb`, `chain_of_thought/test.ipynb`, and `contextless_prompt/test.ipynb`.

In each notebook, after the existing imports cell, add a new cell that imports the metrics module:

```python
import sys
sys.path.insert(0, str(project_root))
from util.harmonization_metrics import compute_metrics, compute_pipeline_metrics, format_metrics_html
```

Then in the per-iteration display loop (the cell that already loops over `result.iterations` and shows the ABC diff, critique, and decision), add a metrics display block inside the loop immediately after the ABC display and before the audio playback:

```python
# inside the existing for it in result.iterations loop, after displaying ABC:
metrics = compute_metrics(it.harmonization, bwv=BWV)
display(HTML(f"<b>Metrics — Round {it.attempt}</b>"))
display(HTML(format_metrics_html(metrics)))
```

After the full iteration loop, add a final cell that shows pipeline-level metrics and a cross-iteration comparison table:

```python
pipeline_metrics = compute_pipeline_metrics(result.iterations)
display(HTML("<h3>Pipeline Behavior Metrics</h3>"))
display(HTML(format_metrics_html(pipeline_metrics['summary'])))

display(HTML("<h3>Metric Progression Across Iterations</h3>"))
# Show a table: rows = metrics, columns = iterations
# Highlight cells green where metric improved vs previous round, red where it worsened
```

### Constraints and notes

- Do NOT modify `pipeline.py`, `agents.py`, or any other source files outside `util/harmonization_metrics.py` and the four `test.ipynb` notebooks.
- The ABC parser in music21 may struggle with some chord stack notation. If `converter.parse` fails, fall back to manual regex parsing of the V:2 line to extract pitch sets — write a `_parse_chord_stacks_fallback(abc_text)` helper that uses regex to find `[...]` groups and extracts pitch names from them.
- bwv253 is in A major. The leading tone is G#. Hard-code this for now since all experiments use bwv253, but accept the `bwv` parameter so it is easy to generalize later.
- The fermata positions for bwv253 should be detected dynamically from `corpus.parse('bach/bwv253')` not hard-coded, so the function generalizes when we extend to bwv255, bwv269, bwv274.
- Keep the `format_metrics_html` output compact — single HTML table, no external CSS dependencies, inline styles only. It will render inside a Jupyter notebook cell.
- Print a short summary to stdout as well as returning HTML, so metrics are visible in the iterations.txt log if the notebook is run non-interactively.

Please implement Step 1 first and show me the complete `util/harmonization_metrics.py` file. Then implement Step 2 by showing the new and modified cells for each notebook. Show me the full content of each changed notebook cell, not just a diff.
