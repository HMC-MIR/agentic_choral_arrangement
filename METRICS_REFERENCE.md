# Harmonization Metrics — Reference

A reading guide for the nine per-harmonization metrics and three pipeline-level metrics produced by `util/harmonization_metrics.py`.

For each metric you get:
- **What it is** (technical) — the definition a music-theory or MIR person reads.
- **Plain-language version** (intuitive) — the same idea explained without jargon.
- **How it's implemented** — what the code actually does, and any approximation or shortcut taken.
- **Direction & rough good/bad bands** — interpreting the number.

---

## 1. Rule violations  *(lower = better)*

### `doubled_leading_tone`

**Technical.** Number of V:2 chord stacks that contain two or more pitches whose pitch class equals the key's leading tone (e.g. G♯ in A major, pitch class 8). Common-practice voice-leading discourages doubling the leading tone because both copies want to resolve up to tonic, which produces parallel motion when both actually do resolve.

**Plain language.** "How many chords have two copies of the note that *really wants* to lean upward into the home note?" That note (the seventh scale degree) has a strong pull. Two of them in the same chord is like two people both reaching for the same door handle — awkward.

**How it's implemented.** For each chord, count how many of its MIDI pitches satisfy `pitch % 12 == leading_tone_pc`. If that count is `> 1`, increment the violation tally. The leading-tone pitch class for each chorale is hard-coded in `BWV_KEY` (A major → 8, D minor → 1, G major → 6, E major → 3).

**Bands.** 0 = clean. 1–2 = occasional violation. 3+ = the model is regularly doubling the LT.

---

### `unresolved_leading_tone`

**Technical.** Count of consecutive chord pairs `(N, N+1)` where chord N contains the leading-tone pitch class but chord N+1 contains no tonic pitch class. The LT "should" resolve up by semitone to the tonic; failing to do so is a voice-leading violation.

**Plain language.** When a chord includes the "ti" of the scale (the seventh note, a half-step below the home note), the very next chord should normally have the home note in it — that's the resolution your ear expects. This metric counts how often the next chord skips that resolution.

**How it's implemented.** Walk consecutive chord pairs. Build pitch-class sets `{p % 12 for p in chord}` for both. Increment the counter when LT is in the first set and tonic (`(LT + 1) % 12`) is missing from the second set. Cases where LT correctly resolves to tonic are *not* counted (those are correct voice leading, not violations).

**Bands.** 0 = textbook. 1–2 = a couple of phrases didn't resolve. 3+ = the model is comfortable leaving leading tones hanging.

---

### `parallel_fifth_octave`

**Technical.** Detect parallel perfect fifths and perfect octaves between consecutive chords using a positional pseudo-voice heuristic. Sort each chord's pitches ascending. For each adjacent pair of pseudo-voice positions (lowest-to-second-lowest, second-to-third-lowest, etc.), measure the harmonic interval. If the *same* P5 (7 semitones) or P8 (12 semitones) interval appears at the *same* positional pair in two consecutive chords, count one violation. This approximates traditional parallel-motion detection without requiring true independent voice tracking.

**Plain language.** Composers traditionally avoid having two voices march in lockstep five or eight notes apart — it makes them sound like one fat voice instead of two distinct voices. Since our LLM writes block chords (not separate vocal parts), this metric uses a "stack from the bottom" trick: pretend the lowest note is the bass, second-lowest is the alto, etc., and check if any pair of those pretend-voices stays exactly 5 or 8 notes apart from one chord into the next.

**How it's implemented.** For each chord pair `(cur, nxt)`, compute `sorted(cur)` and `sorted(nxt)`. For each positional index `j` in `range(min(len(cur), len(nxt)) - 1)`, compute `cur[j+1] - cur[j]` and `nxt[j+1] - nxt[j]`. If both equal 7 (P5) or 12 (P8), increment.

**Caveat (worth flagging to your prof).** This is *not* equivalent to traditional parallel-fifth analysis, which requires stable voice identity across chords. Bach used four independently moving voices; we have block chord stacks. The positional heuristic catches the strongest cases but will under-count when the LLM voices the same chord with different note orderings, and may over-count when chord size grows (denser chords = more positional pairs = more chances).

**Bands.** 0–1 = unusually clean. 2–4 = typical for block-chord harmonizations. 5+ = the model is producing chains of identical-shape chords.

---

## 2. Melody-chord fit  *(Yeh 2021 family, simplified)*

### `ctnctr` — Chord-Tone to Non-Chord-Tone Ratio  *(higher = better, ~0.85 ideal)*

**Technical.** For each soprano note in V:1, find the V:2 chord active at that beat. Check whether the soprano's pitch class is contained in the chord's pitch-class set. Return the fraction of soprano notes whose pitch class matches.

**Plain language.** "What fraction of the time does the melody note land on a note that's actually inside the chord underneath it?" If the soprano sings A and the chord is A-major (A-C♯-E), that's a chord tone — match. If she sings B over an A-major chord, B isn't in the chord — miss (B is a passing tone there).

**How it's implemented.** Iterate `soprano_notes`. For each `(start, dur, midi)`, call `_chord_at_beat(chords, start)` to get the active chord pitches. Compute `sop_pc = midi % 12` and `chord_pcs = {p % 12 for p in chord}`. If `sop_pc in chord_pcs`, increment match counter. Return `matches / len(soprano_notes)`.

**Caveat.** A pure chord-tone melody scores ~1.0, but real Bach has lots of passing tones, neighbor tones, and suspensions — those *should* register as non-chord tones. So a Bach harmonization typically scores 0.6–0.8, not 1.0. Very low (<0.4) means the chords don't even agree with the soprano on the strong beats.

**Bands.** ≥0.85 = excellent. 0.65–0.85 = good (Bach-like). <0.65 = chords aren't matching the melody on most notes.

---

### `pcs` — Pitch Consonance Score  *(higher = better)*

**Technical.** For each soprano note, compute consonance weights against every pitch in the chord active at that beat, then average per soprano note, then average across all soprano notes. Consonance lookup (folded interval class):
- Unison/octave (0) → 1.0
- m2 / M7 (1) → −1.0
- M2 / m7 (2) → −0.2
- m3 / M6 (3) → 0.8
- M3 / m6 (4) → 0.8
- P4 (5) → 0.4
- Tritone (6) → −1.0
- P5 (7) → 0.7

**Plain language.** Some intervals sound smooth together (octaves, thirds, fifths) and some sound crunchy (minor seconds, tritones). This metric scores each melody note by how smoothly it blends with every note in its underlying chord, then averages across the whole piece. Higher = smoother overall sound.

**How it's implemented.** `_consonance_weight(semitones)` folds an absolute semitone difference modulo 12, then maps via the lookup above. Special-cased so that 7 semitones (a P5) returns 0.7 *before* folding to interval class 5 (P4=0.4). For each soprano note, average the weight across all chord pitches; then average across all soprano notes.

**Bands.** Bach typically scores 0.4–0.6 because of dissonances and suspensions. Higher than 0.6 means very vanilla consonant chords. Negative or near-zero means heavy clashing.

---

### `mctd` — Melody-Chord Tonal Distance (simplified)  *(lower = better)*

**Technical.** For each soprano note, compute the minimum chromatic pitch-class distance (folded to 0–6 semitones) between the soprano's pitch class and the nearest pitch class in the chord stack. Average across all soprano notes.

**Plain language.** "On average, how many semitones away is the melody note from the closest note in the chord?" Zero means the melody is always *inside* the chord. Higher numbers mean the melody is wandering away from the chord rather than landing on it.

**How it's implemented.** For each `(start, dur, midi)` soprano note, find the active chord, then compute `min(folded_distance(midi % 12, p % 12) for p in chord)` where `folded_distance(a, b) = min(|a-b| % 12, 12 - |a-b| % 12)`. Average all the minimums.

**Caveat.** This is a simplified proxy, *not* Lerdahl & Jackendoff's tonal pitch space distance from the original Yeh 2021 paper. Real TPS uses a 5-level hierarchy (chromatic, diatonic, triadic, etc.). The simplified chromatic version is faster, has no dependencies, and still correlates with melodic-vs-harmonic alignment, but you can't directly compare numbers to the Yeh paper.

**Bands.** ≤1.5 = melody mostly aligned with chords. 1.5–3.0 = some wandering. ≥3.0 = melody is regularly far from any chord tone.

---

## 3. Harmonic / structural

### `cadence_score`  *(higher = better)*

**Technical.** Find every fermata in the soprano part of the source corpus chorale (using `music21.corpus.parse('bach/<bwv>')`). Subtract the pickup-measure duration so offsets line up with V:2's bar-1-relative timeline. For each fermata position, look up the V:2 chord *at* that position and the chord *immediately before*. Convert both to Roman numerals via `music21.roman.romanNumeralFromChord`. Score:
- V → I = 1.0  (authentic cadence)
- IV → I = 0.8  (plagal cadence)
- anything → V = 0.6  (half cadence)
- otherwise = 0.0

Return the mean across all fermata positions.

**Plain language.** A "cadence" is the musical equivalent of a period at the end of a sentence. Bach marks them with fermatas (those held-note birds-eye signs over the soprano). The metric checks: when the soprano arrives at a fermata, do the last two chords actually land like a real ending? V→I is the textbook authentic landing. IV→I is the gentler plagal "amen" cadence. Half cadences pause on the dominant. Anything else gets 0.

**How it's implemented.** `_fermata_beats(bwv)` returns a tuple of beat offsets (cached). For each offset, find the chord index whose interval `[start, start+dur)` contains that beat. Use `_roman_numeral` on the chord pitches and on the previous chord's pitches. `_classify_cadence(rn_pre, rn_at)` applies the score table.

**Caveat.** Looks only at the immediately preceding chord, not the full preparatory progression — a cadential-six-four (I⁶⁴ → V → I) gets the same authentic-cadence score as a plain V → I. Also relies on music21's Roman-numeral classifier, which can mislabel ambiguous chords.

**Bands.** ≥0.8 = most phrase endings cleanly cadence. 0.4–0.8 = mixed bag, half cadences common. <0.4 = phrase endings rarely land on a recognizable cadence.

---

### `diatonic_coverage`  *(higher = better)*

**Technical.** Fraction of V:2 chords whose Roman numeral falls in the diatonic set {I, ii, iii, IV, V, vi, vii°}. Chords that music21 classifies with chromatic alteration (e.g. V/V, ♭VI) count as 0. Chords that music21 cannot classify at all are skipped from the denominator.

**Plain language.** "What percent of the chords stay in the home key?" Bach chorales are mostly diatonic with occasional brief detours through related keys. A score near 1.0 means the LLM stayed home; lower means it kept borrowing chords from other keys.

**How it's implemented.** Iterate all V:2 chord pitch lists. For each, call `_strip_rn(_roman_numeral(pitches, tonic, mode))` to get the bare Roman-numeral string. Compare against `_DIATONIC_MAJOR = {"I","ii","iii","IV","V","vi","vii","vii°"}` (and a small minor-mode equivalent). Track classified count separately so unclassifiable chords don't artificially lower the score.

**Bands.** ≥0.9 = strict diatonic style. 0.7–0.9 = some chromatic color. <0.7 = the model is regularly leaving the key.

---

### `bigram_typicality`  *(higher = better)*

**Technical.** Mean score over consecutive Roman-numeral pairs in V:2, looked up in a hand-built common-practice rubric:
- Top-shelf transitions (V→I, ii→V, IV→V, I→V, I→IV, I→ii, I→vi, V→I, vi→ii, ...) = 1.0
- Strong but secondary (V→vi deceptive, IV→I plagal, ii→vii°) = 0.8–0.9
- "Any diatonic to any diatonic not in the rubric" = 0.5
- Anything involving an unclassifiable / chromatic chord = 0.1

**Plain language.** Some chord movements are super common in Bach (V→I, ii→V) and others are rare or wrong-sounding. This metric reads each pair of consecutive chords like reading word-pairs in English: "the cat" is normal (high score), "cat the" is gibberish (low score). The reference rubric is hand-written rather than learned from a corpus because the music21 Bach subset we have access to is too small for reliable bigram statistics.

**How it's implemented.** `_bigram_rubric()` returns a `dict[(rn_from, rn_to)] -> float`, cached via `lru_cache`. Walk consecutive chords, classify each via `_strip_rn(_roman_numeral(...))`, look up the pair. Default to 0.5 for unlisted diatonic pairs and 0.1 for chromatic involvements. Mean across all pairs.

**Caveat (important).** This is a rubric, not a learned distribution. It encodes one music theorist's understanding of common practice. Don't claim it as ground truth on Bach style — it's a sanity-check proxy.

**Bands.** ≥0.8 = mostly textbook progressions. 0.5–0.8 = mixed. <0.5 = the model is producing unusual chord movements.

---

## 4. Pipeline behavior  *(across iterations of one run)*

### `approve_rate`

**Technical.** Fraction of iterations where `it.approved == True`.

**Plain language.** Out of all the rounds the agents played, how many ended in "good enough" (Orchestrator said APPROVE)?

**How it's implemented.** `n_approved / n_iterations`.

**Bands.** 0.0 = never approved. 0.33 = approved on the last try only. 1.0 = approved every round (rare; usually means low standards).

---

### `avg_rounds_to_approve`

**Technical.** The 1-indexed round number of the *first* APPROVE. If never approved, equals `max_iterations` (default 3).

**Plain language.** "How many tries did it take to get an OK?" 1 = approved on first attempt; 3 (with max=3) = ran out of rounds without approval.

**How it's implemented.** `next((i + 1 for i, it in enumerate(iterations) if it.approved), None)`; falls back to `max_iterations` when None.

**Bands.** 1 = strong first attempt. 2 = one revision needed. 3 = ran out of tries (probably never approved).

---

### `metric_delta`

**Technical.** Per-metric list of deltas `metric[i+1] - metric[i]` across consecutive iterations. Captures whether revisions actually moved each metric in the right direction.

**Plain language.** "Did each round actually improve things, or did it make them worse?" The cross-iteration table colors cells **green** when the metric moved in the right direction (down for violations and MCTD; up for everything else) and **red** when it moved the wrong way.

**How it's implemented.** For each metric key, walk consecutive `per_iteration` dicts and compute the difference. Direction-aware coloring lives in `format_progression_html` using `_METRIC_DIRECTION` to know whether higher or lower is better.

---

## How to read the cross-iteration table

The HTML table renders one row per metric, one column per round. **Light-green cells** mean that round's value is better than the previous round's value (using the metric's natural direction). **Light-red cells** mean it got worse. **Off-white** means no change (or first round, which has no prior to compare against).

A healthy convergence pattern looks like: violations trending down, fit metrics (ctnctr, pcs) trending up, MCTD trending down, cadence_score creeping toward 1.0.

A pathological pattern: metrics oscillating round-to-round, or all flat (Harmonizer barely revising), or one metric improving while another regresses (model is making trade-offs the orchestrator may or may not be aware of).

---

## Reading the numbers in context

A few patterns from the existing `iterations.txt` logs that illustrate what the metrics surface:

- **base** showed nearly identical values across all three rounds → Harmonizer was barely revising. Flat metric trajectories are honest signal.
- **chain_of_thought** improved cadence_score (0.55 → 0.70), bigram_typicality (0.69 → 0.76), and mctd (1.03 → 0.97), but unresolved_leading_tone climbed (2 → 5). Translation: the model is voicing leading tones more aggressively while improving overall harmonic flow, but isn't resolving them all.
- **improved_prompt** had pcs/ctnctr improvements offset by parallel_fifth_octave climbing 3 → 8. Translation: chords got denser and richer-sounding, but the denser stacks introduced more positional voice-pair coincidences.

None of these stories were obvious from listening alone. The metrics make the trade-offs visible.

---

## Files

- `util/harmonization_metrics.py` — implementation
- `basic_agent_framework/<experiment>/test.ipynb` — wiring (per-round table + pipeline summary cell)
- `basic_agent_framework/experiments/<experiment>/<model_tag>/<bwv>_iterations.txt` — auto-saved metric blocks per round + final pipeline summary
