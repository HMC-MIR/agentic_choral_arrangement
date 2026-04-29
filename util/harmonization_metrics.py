"""
harmonization_metrics.py
------------------------
Evaluation metrics for 2-voice ABC harmonizations produced by the
hub-and-spoke pipeline.

Per-harmonization metrics (one harmonization → one dict of numbers):
    Rule violations:
        doubled_leading_tone
        unresolved_leading_tone
        parallel_fifth_octave
    Melody-chord fit (Yeh 2021 family, simplified):
        ctnctr        chord-tone to non-chord-tone ratio  (higher = better)
        pcs           pitch consonance score              (higher = better)
        mctd          melody-chord tonal distance         (lower  = better)
    Harmonic / structural:
        cadence_score          (higher = better)
        diatonic_coverage      (higher = better)
        bigram_typicality      (higher = better)

Pipeline metrics (across iterations of one run):
    approve_rate
    avg_rounds_to_approve
    per_iteration  (list of metric dicts)
    metric_delta   (list of metric-name -> [delta_round_i_to_i+1])

Design notes:
    - Parsing is regex-based, not music21-based. music21's ABC reader does
      not reliably handle `[abc]` chord stacks alongside `V:n` voice
      declarations and `%%MIDI` directives, and silently produces wrong
      offsets when it does parse. Regex parsing is deterministic for the
      narrow subset our pipeline emits.
    - music21 IS used for two things only: detecting fermata positions on
      the source corpus chorale (for cadence locations), and converting
      pitch-class chords to Roman numerals (via `roman.romanNumeralFromChord`).
    - Key signature is applied: a plain `c` under `K:A` resolves to C#.
"""

from __future__ import annotations

import re
import functools
from html import escape
from typing import Optional


# ──────────────────────────────────────────────────────────────────────────────
# Per-BWV configuration
# ──────────────────────────────────────────────────────────────────────────────

# (tonic_letter, mode, leading_tone_pitch_class)
# Pitch classes use C=0, C#=1, ..., B=11.
BWV_KEY = {
    "bwv253": ("A", "major", 8),   # A major → leading tone G# = 8
    "bwv255": ("D", "minor", 1),   # D minor → raised LT C# = 1
    "bwv269": ("G", "major", 6),   # G major → F# = 6
    "bwv274": ("E", "major", 3),   # E major → D# = 3
}

# Sharp keys add accidentals in the order F C G D A E B
SHARP_ORDER = ["F", "C", "G", "D", "A", "E", "B"]
FLAT_ORDER = ["B", "E", "A", "D", "G", "C", "F"]

# Number of sharps/flats per major key (negative = flats)
KEY_FIFTHS = {
    "C": 0, "G": 1, "D": 2, "A": 3, "E": 4, "B": 5, "F#": 6, "C#": 7,
    "F": -1, "Bb": -2, "Eb": -3, "Ab": -4, "Db": -5, "Gb": -6, "Cb": -7,
}

# Minor keys share signature with their relative major (a minor 3rd above)
RELATIVE_MAJOR = {"Am": "C", "Em": "G", "Bm": "D", "F#m": "A", "C#m": "E",
                  "Dm": "F", "Gm": "Bb", "Cm": "Eb", "Fm": "Ab"}


def _key_signature_accidentals(key_str: str) -> dict[str, int]:
    """Return a dict mapping letter (C..B) → semitone offset (+1 sharp, -1 flat).

    Examples:
        K:A     → {'F': +1, 'C': +1, 'G': +1}
        K:Dm    → {'B': -1}
        K:C     → {}
    """
    key_str = key_str.strip()
    # Normalize: K:A, K:Amaj, K:Amin, K:Am
    m = re.match(r"^([A-G][#b]?)(m|min|maj|major|minor)?$", key_str, re.IGNORECASE)
    if not m:
        return {}
    tonic, mode = m.group(1), (m.group(2) or "").lower()
    tonic = tonic[0].upper() + tonic[1:].lower()  # e.g. "a" -> "A", "ab" -> "Ab"

    # Resolve minor → relative major signature
    if mode in ("m", "min", "minor"):
        key_lookup = RELATIVE_MAJOR.get(tonic + "m", "C")
    else:
        key_lookup = tonic

    n_fifths = KEY_FIFTHS.get(key_lookup, 0)
    accs: dict[str, int] = {}
    if n_fifths > 0:
        for letter in SHARP_ORDER[:n_fifths]:
            accs[letter] = +1
    elif n_fifths < 0:
        for letter in FLAT_ORDER[: -n_fifths]:
            accs[letter] = -1
    return accs


# ──────────────────────────────────────────────────────────────────────────────
# ABC pitch parsing
# ──────────────────────────────────────────────────────────────────────────────

# One pitch token: optional accidental, letter, optional octave marks, optional duration
# Examples: A, ^c, _b', ^^F, =c, A,, c''
# (We do not yet attach the duration here — duration is on the chord/note token level.)
_PITCH_TOKEN = re.compile(r"([_^=]{0,2})([A-Ga-g])([,']*)")

# Token in a melody body: pitch+duration OR rest+duration
_NOTE_OR_REST = re.compile(
    r"(?:([_^=]{0,2})([A-Ga-gz])([,']*))(\d*)(/\d*)?",
)

# A chord stack like `[A,EAc]` followed by an optional duration `2`, `3/2`, `/2`
_CHORD_STACK = re.compile(r"\[([^\]]+)\](\d*)(/\d*)?")

_LETTER_TO_PC = {"C": 0, "D": 2, "E": 4, "F": 5, "G": 7, "A": 9, "B": 11}


def _abc_pitch_to_midi(accidental: str, letter: str, octave_marks: str,
                       key_accs: dict[str, int]) -> int:
    """Convert one ABC pitch token to a MIDI number, applying key signature.

    ABC convention:
        Uppercase letter (A..G)  → octave 3, e.g. C = MIDI 48
        Lowercase letter (a..g)  → octave 4, e.g. c = MIDI 60 (middle C)
        Each `,` after letter   → -1 octave
        Each `'` after letter   → +1 octave
    """
    base_pc = _LETTER_TO_PC[letter.upper()]
    base_octave = 4 if letter.islower() else 3
    midi = (base_octave + 1) * 12 + base_pc  # C3 = (3+1)*12 + 0 = 48 ✓

    for c in octave_marks:
        if c == "'":
            midi += 12
        elif c == ",":
            midi -= 12

    # Explicit accidental overrides key signature
    if accidental:
        for ch in accidental:
            if ch == "^":
                midi += 1
            elif ch == "_":
                midi -= 1
            elif ch == "=":
                # natural — neither key sig nor sharps/flats apply
                return midi
        return midi

    # No explicit accidental — apply key signature
    midi += key_accs.get(letter.upper(), 0)
    return midi


def _parse_duration(num_str: str, slash_str: str) -> float:
    """Parse the optional N or /D or N/D suffix on an ABC note/chord token.

    Returns the multiplier in units of L (default note length).
        ""        → 1
        "2"       → 2
        "/2"      → 0.5
        "/"       → 0.5  (shorthand for /2)
        "3/2"     → 1.5
        "/3"      → 1/3
    """
    num = int(num_str) if num_str else 1
    if not slash_str:
        return float(num)
    # slash_str is like "/", "/2", "/4"
    denom_str = slash_str[1:]
    denom = int(denom_str) if denom_str else 2
    return num / denom


# ──────────────────────────────────────────────────────────────────────────────
# Extract V:1 melody and V:2 chord stacks from a 2-voice ABC string
# ──────────────────────────────────────────────────────────────────────────────

def _extract_header_and_voices(abc_text: str) -> tuple[dict, str, str]:
    """Split a 2-voice ABC string into (headers, V:1 body, V:2 body).

    headers is a dict with keys: 'L' (default note length, e.g. 0.25),
    'M' (meter numerator/denominator tuple), 'K' (raw key string).
    """
    lines = abc_text.splitlines()
    headers = {"L": 0.25, "M": (4, 4), "K": "C"}
    v1_lines: list[str] = []
    v2_lines: list[str] = []
    current_voice = None  # None | 1 | 2

    for raw in lines:
        line = raw.strip()
        if not line:
            continue
        if line.startswith("L:"):
            mm = re.search(r"1/(\d+)", line)
            if mm:
                headers["L"] = 1.0 / int(mm.group(1))
            continue
        if line.startswith("M:"):
            mm = re.search(r"(\d+)/(\d+)", line)
            if mm:
                headers["M"] = (int(mm.group(1)), int(mm.group(2)))
            continue
        if line.startswith("K:"):
            headers["K"] = line[2:].strip()
            continue
        if line.startswith("V:1"):
            current_voice = 1
            continue
        if line.startswith("V:2"):
            current_voice = 2
            continue
        if line.startswith(("X:", "T:", "C:", "%%", "I:", "w:")):
            continue
        # Body lines: route to the current voice
        if current_voice == 1:
            v1_lines.append(line)
        elif current_voice == 2:
            v2_lines.append(line)

    return headers, " ".join(v1_lines), " ".join(v2_lines)


def _tokenize_v1_melody(v1_body: str, L_unit: float,
                        key_accs: dict[str, int]) -> list[tuple[float, float, int]]:
    """Return list of (start_beat, duration_beats, midi_pitch) for soprano notes.

    `start_beat` and `duration_beats` are in *quarter-note* units (since L_unit
    is in fractions of a whole note and we multiply by 4).
    Rests are skipped — they do not appear in the soprano list.
    """
    # Strip decorations and bar-number comments first
    body = v1_body
    body = re.sub(r"%\d+", "", body)               # bar-number markers
    body = re.sub(r"![^!]+!", "", body)             # !fermata! etc.
    body = body.replace("$", "")                    # line-break markers
    body = body.replace("|]", "|").replace(":|", "|").replace("|:", "|")
    # Strip barlines — they do not affect duration accumulation
    body = body.replace("|", " ")

    notes: list[tuple[float, float, int]] = []
    pos = 0
    cursor = 0.0  # in L units

    while pos < len(body):
        # Skip whitespace
        if body[pos].isspace():
            pos += 1
            continue
        m = _NOTE_OR_REST.match(body, pos)
        if not m:
            pos += 1
            continue
        accidental, letter_or_z, octave_marks, num_str, slash_str = m.groups()
        dur_units = _parse_duration(num_str, slash_str)
        if letter_or_z != "z":
            midi = _abc_pitch_to_midi(accidental, letter_or_z, octave_marks, key_accs)
            notes.append((cursor * L_unit * 4, dur_units * L_unit * 4, midi))
        cursor += dur_units
        pos = m.end()

    return notes


def _tokenize_v2_chords(v2_body: str, L_unit: float,
                        key_accs: dict[str, int]) -> list[tuple[float, float, list[int]]]:
    """Return list of (start_beat, duration_beats, [midi_pitches]) for V:2 chord stacks.

    Bare rests (z) are skipped — they appear in templates before the LLM fills V:2.
    """
    body = v2_body
    body = re.sub(r"%\d+", "", body)
    body = re.sub(r"![^!]+!", "", body)
    body = body.replace("$", "")
    body = body.replace("|]", "|").replace(":|", "|").replace("|:", "|")

    chords: list[tuple[float, float, list[int]]] = []
    cursor = 0.0  # in L units
    pos = 0

    while pos < len(body):
        ch = body[pos]
        if ch.isspace() or ch == "|":
            pos += 1
            continue
        if ch == "[":
            m = _CHORD_STACK.match(body, pos)
            if not m:
                pos += 1
                continue
            inner, num_str, slash_str = m.groups()
            dur_units = _parse_duration(num_str, slash_str)
            # Parse pitches inside the brackets
            pitches: list[int] = []
            inner_pos = 0
            while inner_pos < len(inner):
                if inner[inner_pos].isspace():
                    inner_pos += 1
                    continue
                pm = _PITCH_TOKEN.match(inner, inner_pos)
                if not pm:
                    inner_pos += 1
                    continue
                acc, letter, oct_marks = pm.groups()
                if letter.lower() == "z":
                    inner_pos = pm.end()
                    continue
                try:
                    pitches.append(_abc_pitch_to_midi(acc, letter, oct_marks, key_accs))
                except KeyError:
                    pass
                inner_pos = pm.end()
            if pitches:
                chords.append((cursor * L_unit * 4, dur_units * L_unit * 4, pitches))
            cursor += dur_units
            pos = m.end()
            continue
        # A bare note like z (rest) outside chord stack
        m = _NOTE_OR_REST.match(body, pos)
        if m:
            _, letter_or_z, _, num_str, slash_str = m.groups()
            dur_units = _parse_duration(num_str, slash_str)
            cursor += dur_units
            pos = m.end()
        else:
            pos += 1

    return chords


# ──────────────────────────────────────────────────────────────────────────────
# Beat alignment: pair each soprano note with the V:2 chord active at its onset
# ──────────────────────────────────────────────────────────────────────────────

def _chord_at_beat(chords: list[tuple[float, float, list[int]]],
                   beat: float) -> Optional[list[int]]:
    """Return the chord active at a given beat (or None if no chord)."""
    for start, dur, pitches in chords:
        if start <= beat < start + dur + 1e-9:
            return pitches
    return None


# ──────────────────────────────────────────────────────────────────────────────
# Metric primitives
# ──────────────────────────────────────────────────────────────────────────────

# Yeh 2021-style consonance weights, keyed by interval class (0..6)
_CONSONANCE = {
    0: 1.0,    # unison / octave
    1: -1.0,   # m2 / M7
    2: -0.2,   # M2 / m7
    3: 0.8,    # m3 / M6
    4: 0.8,    # M3 / m6
    5: 0.4,    # P4
    6: -1.0,   # tritone
    7: 0.7,    # P5  (we expand interval class 5 below for P5/P4)
    # Note: traditional interval-class folding maps semitones %12 ≤6 then folded.
    # We use the mapping below (semitones → weight directly) for clarity.
}

# Direct semitone-difference → consonance weight (folded mod 12, then mod 12->ic)
def _consonance_weight(semitones: int) -> float:
    """Map a semitone interval (any int) to Yeh 2021 consonance weight.

    Folds to interval class 0..6 then looks up:
       0 (unison/octave) = 1.0
       1 (m2/M7)         = -1.0
       2 (M2/m7)         = -0.2
       3 (m3/M6)         = 0.8
       4 (M3/m6)         = 0.8
       5 (P4)            = 0.4
       6 (tritone)       = -1.0
    PERFECT FIFTH (7 semitones) folds to ic=5 (which is P4=0.4) under this
    mapping, but Yeh distinguishes them. We special-case P5 BEFORE folding.
    """
    abs_st = abs(semitones)
    folded_oct = abs_st % 12
    if folded_oct == 0:
        return 1.0
    if folded_oct == 7:           # perfect fifth (or fourth-inverted)
        return 0.7
    if folded_oct == 5:           # perfect fourth
        return 0.4
    ic = folded_oct if folded_oct <= 6 else 12 - folded_oct
    return {1: -1.0, 2: -0.2, 3: 0.8, 4: 0.8, 6: -1.0}.get(ic, 0.0)


# ──────────────────────────────────────────────────────────────────────────────
# Rule-violation metrics
# ──────────────────────────────────────────────────────────────────────────────

def _doubled_leading_tone(chords: list[list[int]], lt_pc: int) -> int:
    """Count chords where the leading-tone pitch class appears more than once."""
    n = 0
    for pitches in chords:
        if sum(1 for p in pitches if p % 12 == lt_pc) > 1:
            n += 1
    return n


def _unresolved_leading_tone(chords: list[list[int]], lt_pc: int) -> int:
    """Count consecutive chord pairs where chord N has the leading tone but
    chord N+1 contains no tonic (lt_pc + 1 mod 12)."""
    tonic_pc = (lt_pc + 1) % 12
    n = 0
    for i in range(len(chords) - 1):
        cur_pcs = {p % 12 for p in chords[i]}
        nxt_pcs = {p % 12 for p in chords[i + 1]}
        if lt_pc in cur_pcs and tonic_pc not in nxt_pcs:
            n += 1
    return n


def _parallel_fifth_octave(chords: list[list[int]]) -> int:
    """Detect parallel P5 / P8 between consecutive chords using a positional
    pseudo-voice heuristic.

    For each chord pair, sort pitches ascending. For each adjacent pair of
    pseudo-voices (position i and i+1) within a chord, measure the harmonic
    interval. If the *same* P5 (7 semitones) or P8 (12 semitones) interval
    appears at the same positional pair in two consecutive chords, count it
    as a parallel-motion violation.
    """
    n = 0
    for i in range(len(chords) - 1):
        cur = sorted(chords[i])
        nxt = sorted(chords[i + 1])
        common_positions = min(len(cur), len(nxt)) - 1
        for j in range(common_positions):
            iv_cur = cur[j + 1] - cur[j]
            iv_nxt = nxt[j + 1] - nxt[j]
            if iv_cur == iv_nxt and iv_cur in (7, 12):
                n += 1
    return n


# ──────────────────────────────────────────────────────────────────────────────
# Yeh 2021 melody-chord fit metrics
# ──────────────────────────────────────────────────────────────────────────────

def _ctnctr(soprano_notes: list[tuple[float, float, int]],
            chords: list[tuple[float, float, list[int]]]) -> Optional[float]:
    if not soprano_notes:
        return None
    matches = 0
    for start, _, midi in soprano_notes:
        chord = _chord_at_beat(chords, start)
        if chord is None:
            continue
        sop_pc = midi % 12
        chord_pcs = {p % 12 for p in chord}
        if sop_pc in chord_pcs:
            matches += 1
    return matches / len(soprano_notes)


def _pcs(soprano_notes: list[tuple[float, float, int]],
         chords: list[tuple[float, float, list[int]]]) -> Optional[float]:
    if not soprano_notes:
        return None
    scores: list[float] = []
    for start, _, midi in soprano_notes:
        chord = _chord_at_beat(chords, start)
        if chord is None:
            continue
        weights = [_consonance_weight(midi - p) for p in chord]
        if weights:
            scores.append(sum(weights) / len(weights))
    return sum(scores) / len(scores) if scores else None


def _mctd(soprano_notes: list[tuple[float, float, int]],
          chords: list[tuple[float, float, list[int]]]) -> Optional[float]:
    if not soprano_notes:
        return None
    distances: list[float] = []
    for start, _, midi in soprano_notes:
        chord = _chord_at_beat(chords, start)
        if chord is None:
            continue
        sop_pc = midi % 12
        # Minimum chromatic pitch-class distance (folded to 0..6)
        dists = []
        for p in chord:
            d = abs(sop_pc - p % 12) % 12
            d = min(d, 12 - d)
            dists.append(d)
        if dists:
            distances.append(min(dists))
    return sum(distances) / len(distances) if distances else None


# ──────────────────────────────────────────────────────────────────────────────
# Roman-numeral analysis (uses music21 lazily)
# ──────────────────────────────────────────────────────────────────────────────

def _roman_numeral(pitch_classes: list[int], tonic_letter: str, mode: str) -> Optional[str]:
    """Return Roman numeral string for a chord, or None if music21 can't classify.
    Uses the music21.roman.romanNumeralFromChord helper.
    """
    try:
        from music21 import chord as m21chord, key as m21key, roman as m21roman, pitch as m21pitch
    except ImportError:
        return None
    if not pitch_classes:
        return None
    try:
        # Build music21 Chord from pitch classes (pick octave 4 arbitrarily)
        pitches = [m21pitch.Pitch(midi=60 + (pc - 60) % 12) for pc in pitch_classes]
        ch = m21chord.Chord(pitches)
        k = m21key.Key(tonic_letter, mode)
        rn = m21roman.romanNumeralFromChord(ch, k)
        return rn.romanNumeral  # e.g. 'V', 'ii', 'V7'
    except Exception:
        return None


# ──────────────────────────────────────────────────────────────────────────────
# Cadence score — needs fermata positions from the source corpus piece
# ──────────────────────────────────────────────────────────────────────────────

@functools.lru_cache(maxsize=8)
def _fermata_beats(bwv: str) -> tuple[float, ...]:
    """Return beat positions (in quarter notes from start of *bar 1*) of every
    fermata in the source chorale's soprano line.

    Subtracts the pickup-measure duration so the offsets line up with V:2,
    which is generated for measures 1..N (pickup excluded by load_bach_melody).
    """
    try:
        from music21 import corpus
    except ImportError:
        return ()
    try:
        score = corpus.parse(f"bach/{bwv}")
    except Exception:
        return ()
    soprano = score.parts[0]

    # Detect pickup duration (measure number 0 if present)
    pickup_dur = 0.0
    for m in soprano.getElementsByClass("Measure"):
        if m.number == 0:
            pickup_dur = float(m.duration.quarterLength)
            break

    beats: list[float] = []
    for n in soprano.flatten().notes:
        for expr in getattr(n, "expressions", []):
            if expr.__class__.__name__ == "Fermata":
                rel = float(n.offset) - pickup_dur
                if rel >= 0:
                    beats.append(rel)
                break
    return tuple(beats)


def _classify_cadence(rn_pre: Optional[str], rn_at: Optional[str]) -> float:
    """Score a two-chord cadence:
        V → I = 1.0  (authentic)
        IV → I = 0.8 (plagal)
        any → V = 0.6 (half)
        else = 0.0
    """
    if rn_at is None:
        return 0.0
    pre = (rn_pre or "").rstrip("0123456789")
    at = rn_at.rstrip("0123456789")
    if pre == "V" and at == "I":
        return 1.0
    if pre == "IV" and at == "I":
        return 0.8
    if at == "V":
        return 0.6
    return 0.0


def _cadence_score(chords: list[tuple[float, float, list[int]]],
                   bwv: str,
                   tonic_letter: str,
                   mode: str) -> Optional[float]:
    fermata_offsets = _fermata_beats(bwv)
    if not fermata_offsets or not chords:
        return None
    scores: list[float] = []
    for off in fermata_offsets:
        # Find the chord covering that fermata beat
        idx_at = None
        for i, (start, dur, _) in enumerate(chords):
            if start <= off < start + dur + 1e-9:
                idx_at = i
                break
        if idx_at is None:
            # Fermata may be past our excerpt — skip
            continue
        rn_at = _roman_numeral(chords[idx_at][2], tonic_letter, mode)
        rn_pre = (_roman_numeral(chords[idx_at - 1][2], tonic_letter, mode)
                  if idx_at > 0 else None)
        scores.append(_classify_cadence(rn_pre, rn_at))
    return sum(scores) / len(scores) if scores else None


# ──────────────────────────────────────────────────────────────────────────────
# Diatonic coverage and bigram typicality
# ──────────────────────────────────────────────────────────────────────────────

_DIATONIC_MAJOR = {"I", "ii", "iii", "IV", "V", "vi", "vii", "vii°"}


@functools.lru_cache(maxsize=1)
def _bigram_rubric() -> dict[tuple[str, str], float]:
    """Hand-built common-practice progression strength table.

    Built once per session.  Keys are (RN_from, RN_to) Roman-numeral strings
    (without inversion / extension digits).  Values in [0, 1].
    """
    table = {
        ("I", "IV"): 1.0, ("I", "V"): 1.0, ("I", "ii"): 1.0, ("I", "vi"): 1.0,
        ("ii", "V"): 1.0, ("ii", "vii°"): 0.9, ("ii", "vii"): 0.9,
        ("IV", "V"): 1.0, ("IV", "I"): 0.9,
        ("V", "I"): 1.0, ("V", "vi"): 0.8,
        ("vi", "ii"): 0.9, ("vi", "IV"): 0.9, ("vi", "V"): 0.8,
        ("iii", "vi"): 0.8, ("iii", "IV"): 0.7,
    }
    return table


def _strip_rn(rn: Optional[str]) -> Optional[str]:
    if rn is None:
        return None
    return re.sub(r"[0-9]+$", "", rn).rstrip("/")


def _diatonic_coverage(chords: list[list[int]],
                       tonic_letter: str,
                       mode: str) -> Optional[float]:
    if not chords:
        return None
    diatonic_count = 0
    classified = 0
    for pitches in chords:
        rn = _strip_rn(_roman_numeral(pitches, tonic_letter, mode))
        if rn is None:
            continue
        classified += 1
        if rn in _DIATONIC_MAJOR or rn in {"i", "iv", "v", "VI", "VII", "III"}:
            diatonic_count += 1
    return diatonic_count / classified if classified else None


def _bigram_typicality(chords: list[list[int]],
                       tonic_letter: str,
                       mode: str) -> Optional[float]:
    if len(chords) < 2:
        return None
    rubric = _bigram_rubric()
    rns = [_strip_rn(_roman_numeral(p, tonic_letter, mode)) for p in chords]
    scores: list[float] = []
    for i in range(len(rns) - 1):
        a, b = rns[i], rns[i + 1]
        if a is None or b is None:
            scores.append(0.1)  # treat unclassifiable as chromatic
            continue
        if (a, b) in rubric:
            scores.append(rubric[(a, b)])
        elif a in _DIATONIC_MAJOR and b in _DIATONIC_MAJOR:
            scores.append(0.5)
        else:
            scores.append(0.1)
    return sum(scores) / len(scores) if scores else None


# ──────────────────────────────────────────────────────────────────────────────
# Top-level entry points
# ──────────────────────────────────────────────────────────────────────────────

def compute_metrics(abc_text: str, bwv: str = "bwv253") -> dict:
    """Compute all per-harmonization metrics for one ABC string.

    Returns a flat dict with these keys (numeric or None on failure):
        doubled_leading_tone, unresolved_leading_tone, parallel_fifth_octave,
        ctnctr, pcs, mctd,
        cadence_score, diatonic_coverage, bigram_typicality.
    On parse failure adds 'error' key with the exception message.
    """
    out = {k: None for k in (
        "doubled_leading_tone", "unresolved_leading_tone", "parallel_fifth_octave",
        "ctnctr", "pcs", "mctd",
        "cadence_score", "diatonic_coverage", "bigram_typicality",
    )}

    try:
        headers, v1_body, v2_body = _extract_header_and_voices(abc_text)
        key_accs = _key_signature_accidentals(headers["K"])
        sop_notes = _tokenize_v1_melody(v1_body, headers["L"], key_accs)
        chord_events = _tokenize_v2_chords(v2_body, headers["L"], key_accs)
        chord_pitch_lists = [c[2] for c in chord_events]

        if bwv in BWV_KEY:
            tonic_letter, mode, lt_pc = BWV_KEY[bwv]
        else:
            tonic_letter, mode, lt_pc = "C", "major", 11

        out["doubled_leading_tone"] = _doubled_leading_tone(chord_pitch_lists, lt_pc)
        out["unresolved_leading_tone"] = _unresolved_leading_tone(chord_pitch_lists, lt_pc)
        out["parallel_fifth_octave"] = _parallel_fifth_octave(chord_pitch_lists)

        out["ctnctr"] = _ctnctr(sop_notes, chord_events)
        out["pcs"] = _pcs(sop_notes, chord_events)
        out["mctd"] = _mctd(sop_notes, chord_events)

        out["cadence_score"] = _cadence_score(chord_events, bwv, tonic_letter, mode)
        out["diatonic_coverage"] = _diatonic_coverage(chord_pitch_lists, tonic_letter, mode)
        out["bigram_typicality"] = _bigram_typicality(chord_pitch_lists, tonic_letter, mode)
    except Exception as e:
        out["error"] = f"{type(e).__name__}: {e}"
    return out


def compute_pipeline_metrics(iterations: list, bwv: str = "bwv253",
                             max_iterations: int = 3) -> dict:
    """Aggregate metrics across iterations of one harmonization run.

    Returns:
        {
            'summary': {
                'approve_rate': float in [0,1],
                'avg_rounds_to_approve': int,
                'n_iterations': int,
            },
            'per_iteration': [metric_dict for each iteration],
            'metric_delta': {metric_name: [delta_round_i_to_i+1, ...]},
        }
    """
    per_iter = [compute_metrics(it.harmonization, bwv=bwv) for it in iterations]

    n = len(iterations)
    n_approved = sum(1 for it in iterations if it.approved)
    first_approve = next((i + 1 for i, it in enumerate(iterations) if it.approved), None)
    summary = {
        "approve_rate": n_approved / n if n else 0.0,
        "avg_rounds_to_approve": first_approve if first_approve is not None else max_iterations,
        "n_iterations": n,
    }

    metric_keys = [k for k in per_iter[0].keys() if k != "error"] if per_iter else []
    deltas: dict[str, list[Optional[float]]] = {k: [] for k in metric_keys}
    for k in metric_keys:
        for i in range(len(per_iter) - 1):
            a, b = per_iter[i][k], per_iter[i + 1][k]
            if a is None or b is None:
                deltas[k].append(None)
            else:
                deltas[k].append(b - a)

    return {"summary": summary, "per_iteration": per_iter, "metric_delta": deltas}


# ──────────────────────────────────────────────────────────────────────────────
# Display: HTML table + plaintext summary
# ──────────────────────────────────────────────────────────────────────────────

# Per-metric: (lower-is-better?, green-threshold, red-threshold)
# For higher-is-better metrics: green if ≥ green_thr, red if ≤ red_thr, else amber.
# For lower-is-better: green if ≤ green_thr, red if ≥ red_thr.
_METRIC_DIRECTION = {
    "doubled_leading_tone":     ("low",  0,    2),
    "unresolved_leading_tone":  ("low",  0,    2),
    "parallel_fifth_octave":    ("low",  0,    2),
    "ctnctr":                   ("high", 0.85, 0.65),
    "pcs":                      ("high", 0.5,  0.0),
    "mctd":                     ("low",  1.5,  3.0),
    "cadence_score":            ("high", 0.8,  0.4),
    "diatonic_coverage":        ("high", 0.85, 0.5),
    "bigram_typicality":        ("high", 0.7,  0.4),
    "approve_rate":             ("high", 0.66, 0.0),
    "avg_rounds_to_approve":    ("low",  1,    3),
    "n_iterations":             ("none", 0,    0),
}


def _color_for(metric: str, value) -> str:
    if value is None:
        return "#9ca3af"  # gray
    direction = _METRIC_DIRECTION.get(metric, ("none", 0, 0))
    kind, green, red = direction
    if kind == "none":
        return "#6b7280"
    if kind == "high":
        if value >= green:
            return "#16a34a"   # green
        if value <= red:
            return "#dc2626"   # red
        return "#d97706"       # amber
    if kind == "low":
        if value <= green:
            return "#16a34a"
        if value >= red:
            return "#dc2626"
        return "#d97706"
    return "#6b7280"


def _fmt_value(v) -> str:
    if v is None:
        return "—"
    if isinstance(v, float):
        return f"{v:.3f}"
    return str(v)


def format_metrics_html(metrics: dict) -> str:
    """Render a metric dict as a small HTML table with colored indicators.

    Suitable for `display(HTML(...))` in Jupyter. Inline styles only.
    """
    if "error" in metrics and metrics["error"]:
        return (f"<pre style='color:#dc2626; padding:6px; "
                f"border:1px solid #dc2626; border-radius:4px;'>"
                f"Metric parse error: {escape(str(metrics['error']))}</pre>")

    rows = []
    for k, v in metrics.items():
        if k == "error":
            continue
        color = _color_for(k, v)
        rows.append(
            f"<tr>"
            f"<td style='padding:4px 10px; border-bottom:1px solid #e5e7eb;'>"
            f"<code>{escape(k)}</code></td>"
            f"<td style='padding:4px 10px; border-bottom:1px solid #e5e7eb;'>"
            f"<span style='display:inline-block; width:10px; height:10px; "
            f"border-radius:50%; background:{color}; vertical-align:middle; "
            f"margin-right:8px;'></span>"
            f"<b>{_fmt_value(v)}</b></td>"
            f"</tr>"
        )
    return (
        "<table style='border-collapse:collapse; font-size:12px; "
        "background:#f9fafb; color:#111827;'>"
        + "".join(rows) +
        "</table>"
    )


def metrics_plaintext(metrics: dict) -> str:
    """Compact plaintext summary suitable for print() or .txt logs."""
    if "error" in metrics and metrics["error"]:
        return f"  metrics: ERROR — {metrics['error']}"
    lines = []
    for k, v in metrics.items():
        if k == "error":
            continue
        lines.append(f"  {k:<26s} {_fmt_value(v)}")
    return "\n".join(lines)


def format_progression_html(per_iteration: list[dict]) -> str:
    """Render an iterations × metrics table with green/red cells highlighting
    improvement vs the previous round (where applicable).
    """
    if not per_iteration:
        return "<i>No iterations to display.</i>"
    keys = [k for k in per_iteration[0].keys() if k != "error"]
    head = "".join(f"<th style='padding:4px 10px;'>R{i+1}</th>"
                   for i in range(len(per_iteration)))
    rows_html = []
    for k in keys:
        cells = []
        kind = _METRIC_DIRECTION.get(k, ("none", 0, 0))[0]
        for i, m in enumerate(per_iteration):
            v = m.get(k)
            cell_color = "#f9fafb"
            if i > 0 and v is not None:
                prev = per_iteration[i - 1].get(k)
                if prev is not None and isinstance(v, (int, float)) and isinstance(prev, (int, float)):
                    if kind == "high" and v > prev:
                        cell_color = "#dcfce7"   # light green
                    elif kind == "high" and v < prev:
                        cell_color = "#fee2e2"   # light red
                    elif kind == "low" and v < prev:
                        cell_color = "#dcfce7"
                    elif kind == "low" and v > prev:
                        cell_color = "#fee2e2"
            cells.append(
                f"<td style='padding:4px 10px; background:{cell_color}; "
                f"border:1px solid #e5e7eb;'>{_fmt_value(v)}</td>"
            )
        rows_html.append(
            f"<tr><td style='padding:4px 10px; border:1px solid #e5e7eb;'>"
            f"<code>{escape(k)}</code></td>" + "".join(cells) + "</tr>"
        )
    return (
        "<table style='border-collapse:collapse; font-size:12px; color:#111827;'>"
        f"<tr><th style='padding:4px 10px;'>metric</th>{head}</tr>"
        + "".join(rows_html) +
        "</table>"
    )
