# Harmonization Metrics — Design Spec

The companion to [`basic_agent_framework/documentation/METRICS.md`](../basic_agent_framework/documentation/METRICS.md).

- **METRICS.md** → *reference.* What each metric measures, how it's
  computed, and how to read a number.
- **METRICS_DESIGN.md** (this file) → *spec.* Why each metric exists, the
  design constraints behind it, and the approximations we knowingly accept.

The implementation lives at `util/harmonization_metrics.py` and is consumed
by every `basic_agent_framework/<variant>/test.ipynb`. This document is what
to read before adding a new metric, changing a threshold, or porting the
metrics to a different chorale.

---

## What we're scoring

Each experiment runs the 3-agent pipeline (Orchestrator, Theory Agent,
Harmonizer) for up to 3 iterations on a Bach soprano line — by default
`bwv253`, measures 1–10, A major, 4/4. Every iteration yields a
`HarmonizationResult` whose `.iterations` list contains:

- `it.attempt` — round number (1, 2, 3)
- `it.harmonization` — full 2-voice ABC notation
- `it.approved` — `True` iff Orchestrator said APPROVE
- `it.critique` — Theory Agent prose
- `it.decision` — Orchestrator decision text

The ABC has two voices:

- **`V:1`** — soprano melody, verbatim Bach, never changes
- **`V:2`** — block chord stacks the LLM generates, e.g. `[A,EAc] [C#EAc] [F#,EAc]`

`V:2` is *one voice playing stacked chords*, not true four-part SATB with
independent alto/tenor/bass lines. Every voice-leading metric below
acknowledges this and uses positional pseudo-voices rather than tracked voice
identity.

---

## Metric families

The full set lives in `util/harmonization_metrics.py` and is exposed by:

- `compute_metrics(abc_text, bwv) -> dict` — per-harmonization scores
- `compute_pipeline_metrics(iterations) -> dict` — across-iteration scores
- `format_metrics_html(metrics) -> str` — compact inline table for Jupyter

### 1. Rule violations *(count; lower = better)*

| Metric | Why it's here |
|---|---|
| `doubled_leading_tone` | Cheap, unambiguous voice-leading check. Doubled LT is the classical "two people grabbing the same door handle" error and is trivial to detect in a block-chord representation. |
| `unresolved_leading_tone` | The other half of LT hygiene. Counts only *missed* resolutions — when LT is present in chord N and the tonic pitch class is absent from chord N+1. Correct resolutions are not counted as violations (avoids the common bug of penalising the right answer). |
| `parallel_fifth_octave` | Classical parallel-motion check, adapted to block chords via the positional pseudo-voice heuristic (sort each chord ascending; compare position-to-position intervals between adjacent chords). See caveat below. |

**Parallel-fifth caveat (carry forward when discussing results).** The
positional heuristic is not equivalent to traditional parallel-fifth
analysis, which requires stable voice identity across chords. With block
chords we don't have stable voices, so we approximate. This will *under*-count
when the LLM reorders pitches within a chord and *over*-count as chord
density grows. It's a sanity-check signal, not ground truth.

### 2. Melody–chord fit *(Yeh 2021 family, simplified)*

| Metric | Why it's here |
|---|---|
| `ctnctr` | Chord Tone to Non-Chord-Tone Ratio. The most direct "does the melody land on the chord" measure. A real Bach harmonization scores ~0.6–0.8 (passing tones and suspensions push it below 1.0); a score < 0.4 means the LLM isn't even agreeing with the soprano on strong beats. |
| `pcs` | Pitch Consonance Score with a lookup table over folded interval classes. Catches the case where every chord *contains* a chord tone but also packs in dissonances. |
| `mctd` | Melody-Chord Tonal Distance (simplified). The original Yeh paper uses Lerdahl & Jackendoff's 5-level Tonal Pitch Space; we use a chromatic-distance proxy. Faster, no extra deps, still correlates with melodic alignment — **but the numbers are not comparable to the paper.** This is an explicit knowing approximation. |

### 3. Harmonic / structural

| Metric | Why it's here |
|---|---|
| `cadence_score` | Cadences are the load-bearing event in a chorale phrase. Detected by reading fermata positions from the source chorale via `music21.corpus`. Scores V→I = 1.0, IV→I = 0.8, anything→V = 0.6, else 0.0. Only looks at the *immediately preceding* chord, so cadential-six-four passes as plain V→I — accepted simplification. |
| `diatonic_coverage` | What fraction of `V:2` chords stay in the home key. Bach chorales are mostly diatonic with brief tonicizations; a low number means the LLM is wandering. Unclassifiable chords are skipped from the denominator (rather than counted as 0) so the score isn't dragged down by music21 mis-parses. |
| `bigram_typicality` | Mean score over consecutive Roman-numeral pairs against a **hand-built rubric** (V→I, ii→V, IV→V at 1.0; deceptive V→vi at 0.8; etc.). **Why hand-built and not corpus-learned:** the music21 Bach subset gives only ~40–60 transitions — far too sparse for reliable bigrams. A hand-written rubric encoding one theorist's understanding of common practice beats a noisy empirical table at this scale. Acknowledge this when reporting results — it is not "Bach's distribution," it's a sanity-check proxy. |

### 4. Pipeline behavior *(across iterations of one run)*

| Metric | Why it's here |
|---|---|
| `approve_rate` | Did the Orchestrator ever sign off? A zero is a meaningful signal (pipeline failed to converge) and a 1.0 across all rounds is also suspicious (low standards). |
| `avg_rounds_to_approve` | First-approval round. Distinguishes "got it on attempt 1" from "scraped through on attempt 3." |
| `metric_delta` | Per-metric difference between consecutive rounds. The point isn't the absolute scores — it's *whether each revision actually moved each metric in the right direction.* Surfaces oscillations, flat-lining (Harmonizer not really revising), and metric trade-offs. |

---

## Design constraints encoded in the implementation

These are the design rules to preserve when extending the module:

- **All `music21.parse` calls happen inside functions**, never at import
  time. The metrics module must import quickly even when music21 is slow to
  start.
- **`bwv` is a parameter, not a constant**, so the same metrics work on
  bwv255, bwv269, bwv274 once those experiments come online. The leading
  tone pitch class for each is hard-coded in `BWV_KEY`.
- **Fermata positions are detected dynamically** from
  `corpus.parse(f'bach/{bwv}')` — never hard-coded — so cadence scoring
  generalises across chorales for free.
- **Bigram rubric is cached** via `@functools.lru_cache` — it's a constant.
- **Parse failures are recoverable.** If `converter.parse(abc_text, format='abc')`
  fails, fall through to a regex chord-stack extractor (`_parse_chord_stacks_fallback`)
  so we still get *some* metrics rather than `None` everywhere.
- **HTML output is self-contained.** `format_metrics_html` uses inline styles
  only — no external CSS — so it renders in any Jupyter UI.
- **Each metric block is also printed to stdout** so it survives in the
  `iterations.txt` log when notebooks are run non-interactively.
- **Per-iteration table is direction-aware.** Cells are green when the
  metric moved in the right direction (down for violations and MCTD, up for
  everything else) and red when it moved the wrong way. The direction map
  lives in `_METRIC_DIRECTION`.

---

## Why these specific metrics?

The set was chosen to triangulate three different failure modes that a
harmonizer can plausibly exhibit, and that are *not* obvious from listening:

1. **Voice-leading errors** (violations family). Easy for humans to miss
   when chords are correctly *chosen* but voiced badly.
2. **Melody/chord disagreement** (Yeh family). The soprano is fixed — does
   the LLM's chord choice actually support it?
3. **Tonal coherence** (cadence + diatonic + bigram). Did the LLM produce
   a phrase that *functions* as a phrase, or a bag of locally-plausible
   chord choices?

Plus the pipeline-behavior family, which asks the meta-question: *is the
iterative loop actually doing work, or burning tokens?* The flat-metrics
finding on the `base` experiment (Harmonizer barely revising across rounds)
is exactly the kind of thing pipeline metrics surface that per-harmonization
scores can't.

---

## Where to add a metric

1. Implement it in `util/harmonization_metrics.py` and add its key to
   `_METRIC_DIRECTION` so the cross-iteration table colors correctly.
2. Have `compute_metrics` (or `compute_pipeline_metrics`) return it under
   the new key — the notebooks read whatever keys are present.
3. Add a section to [METRICS.md](../basic_agent_framework/documentation/METRICS.md)
   with the technical definition, plain-language version, implementation
   note, and good/bad bands.
4. Add a row to the "Metric families" table above with a one-line rationale.
