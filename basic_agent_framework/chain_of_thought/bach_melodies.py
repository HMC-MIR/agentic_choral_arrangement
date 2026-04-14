"""
bach_melodies.py
----------------
Utilities for loading Bach chorale melodies from the music21 corpus and
converting them to the 2-voice ABC template format expected by the pipeline.

The core logic (music21 corpus → MusicXML → ABC → 2-voice template) is adapted
directly from notebooks/llm_benchmark.ipynb, which established this pattern.
"""

import re
import sys
import pathlib
import tempfile

# Allow importing util from the project root (two levels up: base/ → basic_agent_framework/ → project root)
sys.path.insert(0, str(pathlib.Path(__file__).parent.parent.parent))

from music21 import corpus, stream as m21stream
from util.conversion import part_musicxml_to_abc


# ──────────────────────────────────────────────────────────────────────────────
# Convenience list of Bach BWV chorales that are in music21's built-in corpus
# and have enough measures for an interesting demo (at least 8 measures).
# ──────────────────────────────────────────────────────────────────────────────

AVAILABLE_BWV = [
    "bwv253",   # "Bleib bei uns, Herr Jesu Christ" — key of A major
    "bwv255",   # "Durch Adams Fall ist ganz verderbt" — key of D minor
    "bwv269",   # "Aus meines Herzens Grunde" — key of G major
    "bwv274",   # "O Haupt voll Blut und Wunden" — key of E major
]


def load_bach_melody(bwv: str = "bwv253", measures: tuple[int, int] = (1, 8)) -> str:
    """Load a Bach chorale soprano melody from music21's corpus.

    Extracts the soprano (parts[0]), trims to the specified measure range,
    converts to ABC notation via MusicXML intermediate, and returns a clean
    single-voice ABC string.

    Args:
        bwv:      The BWV number string, e.g. "bwv253". Must be available in
                  music21's built-in Bach corpus.
        measures: (start, end) measure numbers to extract (inclusive).

    Returns:
        A single-voice ABC string representing the soprano melody.

    Raises:
        ValueError: If the BWV number is not found in music21's corpus.
    """
    # Parse the chorale from music21's built-in Bach corpus
    chorale = corpus.parse(f"bach/{bwv}")
    soprano_part = chorale.parts[0]

    # Extract the specified measure range
    soprano_excerpt = m21stream.Score([soprano_part.measures(*measures)])

    # Convert to ABC via MusicXML intermediate (same as llm_benchmark.ipynb)
    with tempfile.NamedTemporaryFile(suffix=".musicxml", delete=False, mode="w") as tmp_xml:
        tmp_xml_path = pathlib.Path(tmp_xml.name)

    try:
        soprano_excerpt.write("musicxml", fp=str(tmp_xml_path))
        abc_path = part_musicxml_to_abc(tmp_xml_path)
        single_voice_abc = abc_path.read_text(encoding="utf-8")
        abc_path.unlink(missing_ok=True)
    finally:
        tmp_xml_path.unlink(missing_ok=True)

    return _collapse_spurious_barlines(single_voice_abc)


# Matches a single note token: optional accidental, pitch letter or rest, octave marks,
# optional integer numerator, optional /denominator. Used to sum beats in a bar.
_NOTE_TOKEN = re.compile(r"[\^_=]?[A-Ga-gz][,']*(\d*)(/\d*)?")


def _bar_beats(segment: str) -> float:
    """Sum the note/rest durations in one bar segment, in units of L:.

    Strips decorations (!fermata! etc.), bar-number comments, and the $
    line-break marker before counting. Chords `[abc]` are not expected in
    V:1 (single-voice soprano melody) and would overcount if present —
    which is fine here because we only call this on pre-harmonization V:1.
    """
    t = re.sub(r"%\d+", "", segment)
    t = re.sub(r"![^!]+!", "", t)
    t = t.replace("$", "")
    total = 0.0
    for m in _NOTE_TOKEN.finditer(t):
        n = int(m.group(1)) if m.group(1) else 1
        denom = m.group(2)
        if denom:
            d_str = denom[1:]
            d = int(d_str) if d_str else 2
            total += n / d
        else:
            total += n
    return total


def _collapse_spurious_barlines(raw_abc: str) -> str:
    """Merge adjacent V:1 bars that each fall short of a full measure but
    whose durations sum to exactly one.

    music21's MusicXML→ABC export inserts an extra barline at fermata /
    phrase boundaries, splitting a single real measure into two pseudo-bars
    (e.g. `| !fermata!A3 |$ c |` for one 4/4 bar of A3 + c). The template
    builder then counts barlines and over-estimates the bar count, which
    makes V:2 have more z-rests than V:1 has real measures.

    The rule is principled, not chorale-specific: two adjacent bars that are
    each < one full measure and sum to exactly one full measure are, by
    construction, one real measure that was split. Drop the barline between.
    """
    lines = raw_abc.splitlines()

    m_line = next((l for l in lines if re.match(r"^\s*M:", l)), "M:4/4")
    mm = re.search(r"(\d+)/(\d+)", m_line)
    numerator = int(mm.group(1)) if mm else 4
    denominator = int(mm.group(2)) if mm else 4

    l_line = next((l for l in lines if re.match(r"^\s*L:", l)), "L:1/4")
    lm = re.search(r"1/(\d+)", l_line)
    l_denom = int(lm.group(1)) if lm else 4

    full_bar = numerator * l_denom / denominator  # bar length in L: units

    # Locate V:1 body: lines after K:, before any V:2 declaration.
    past_k = False
    body_start = body_end = None
    for i, line in enumerate(lines):
        s = line.strip()
        if past_k and body_start is None:
            body_start = i
        if re.match(r"^K:", s, re.I):
            past_k = True
        if body_start is not None and body_end is None:
            if re.match(r"^(V:2|\[V:2)", s):
                body_end = i
                break
    if body_start is None:
        return raw_abc
    if body_end is None:
        body_end = len(lines)

    # Music lines inside the V:1 body (skip lyrics, voice markers, directives).
    music_indices = [
        i for i in range(body_start, body_end)
        if lines[i].strip()
        and not re.match(r"^(w:|V:|%%MIDI|I:|\[V:)", lines[i].strip())
    ]
    if not music_indices:
        return raw_abc

    music_text = " ".join(lines[i] for i in music_indices)
    segments = re.split(r"\|", music_text)

    merged: list[str] = []
    i = 0
    while i < len(segments):
        if i + 1 < len(segments):
            a = _bar_beats(segments[i])
            b = _bar_beats(segments[i + 1])
            if 0 < a < full_bar and 0 < b < full_bar and abs(a + b - full_bar) < 1e-6:
                merged.append(f"{segments[i].rstrip()} {segments[i + 1].lstrip()}")
                i += 2
                continue
        merged.append(segments[i])
        i += 1

    new_body = "|".join(merged)

    # Rewrite: keep header (pre-body) and trailing (V:2 onward) lines as-is;
    # replace the original V:1 music lines with the merged single-line body.
    # Preserve lyric/directive lines that were interleaved.
    new_lines = list(lines[:body_start])
    music_inserted = False
    for i in range(body_start, body_end):
        s = lines[i].strip()
        is_music = bool(s) and not re.match(r"^(w:|V:|%%MIDI|I:|\[V:)", s)
        if is_music:
            if not music_inserted:
                new_lines.append(new_body)
                music_inserted = True
        else:
            new_lines.append(lines[i])
    new_lines.extend(lines[body_end:])
    return "\n".join(new_lines)


def clean_abc_for_llm(abc_str: str) -> str:
    """Strip ABC notation elements that confuse LLMs but don't affect audio.

    Removes:
      - Lyric lines (w: ...)
      - I:linebreak directives and $ inline line-break markers
      - !fermata! and other decoration markers
      - Trailing %N bar-number comments

    This pattern is taken directly from llm_benchmark.ipynb.
    """
    cleaned_lines = []
    for line in abc_str.splitlines():
        # Drop lyric lines and linebreak directives
        if re.match(r"^\s*(w:|I:linebreak)", line):
            continue
        # Remove inline $ line-break markers
        line = line.replace("$", "")
        # Remove !fermata! and similar decoration markers
        line = re.sub(r"![a-zA-Z]+!", "", line)
        # Remove trailing %N bar-number comments (e.g. "| %7")
        line = re.sub(r"\s*%\d+\s*$", "", line)
        if line.strip():
            cleaned_lines.append(line)
    return "\n".join(cleaned_lines)


def build_harmonization_template(single_voice_abc: str, title_override: str | None = None) -> str:
    """Transform a single-voice ABC string into a 2-voice harmonization template.

    Creates:
      - V:1 "Melody"  — the original soprano melody (unchanged)
      - V:2 "Chords"  — filled with rests (placeholder for the LLM to harmonize)

    The output uses the V:n header style (not [V:n] inline), which abc2midi
    requires to place both voices simultaneously starting at time 0.

    This is an exact replication of _build_two_voice_abc() from llm_benchmark.ipynb.

    Args:
        single_voice_abc: A single-voice ABC string (as returned by load_bach_melody).
        title_override:   Optional new title for the T: field.

    Returns:
        A 2-voice ABC string with V:1 containing the melody and V:2 all rests.
    """
    lines = single_voice_abc.strip().splitlines()

    # Separate header lines from body lines, stripping any existing voice declarations
    header_lines, body_lines = [], []
    past_key = False

    for line in lines:
        stripped = line.strip()
        if not past_key:
            # Skip any existing voice or MIDI declarations in the header
            if re.match(r"^(V:|%%MIDI|\[V:)", stripped):
                continue
            header_lines.append(line)
            if re.match(r"^K:", stripped, re.IGNORECASE):
                past_key = True  # Everything after K: is the body
        else:
            if re.match(r"^(V:|%%MIDI|\[V:)", stripped):
                continue
            if stripped:
                body_lines.append(line)

    # Optionally override the title
    if title_override:
        header_lines = [
            f"T:{title_override}" if re.match(r"^T:", line) else line
            for line in header_lines
        ]

    body = "\n".join(body_lines)

    # Parse time signature (M:) to know how many beats per bar
    m_line = next((l for l in header_lines if re.match(r"^M:", l)), "M:4/4")
    m_match = re.search(r"(\d+)/(\d+)", m_line)
    numerator = int(m_match.group(1)) if m_match else 4
    denominator = int(m_match.group(2)) if m_match else 4

    # Parse default note length (L:) for the rest unit
    l_line = next((l for l in header_lines if re.match(r"^L:", l)), "L:1/8")
    l_match = re.search(r"1/(\d+)", l_line)
    l_denom = int(l_match.group(1)) if l_match else 8

    # One whole-bar rest in terms of L: units
    rest_units = numerator * l_denom // denominator
    rest_per_bar = f"z{rest_units}"

    # Count bars in the melody body to generate matching V:2 rests.
    # Exclude lyric lines (w:) — their | characters are word separators, not barlines.
    music_lines = [l for l in body_lines if not re.match(r"^\s*w:", l)]
    num_bars = max(1, len(re.findall(r"\|", "\n".join(music_lines))))
    v2_body = " | ".join([rest_per_bar] * num_bars) + " |]"

    # Assemble the final 2-voice ABC string
    parts = (
        header_lines
        + [
            'V:1 name="Melody" clef=treble',
            "%%MIDI program 1 40",   # Violin sound for melody
            body,
            'V:2 name="Chords" clef=treble',
            "%%MIDI program 2 0",    # Piano sound for chords
            v2_body,
        ]
    )
    return "\n".join(parts)
