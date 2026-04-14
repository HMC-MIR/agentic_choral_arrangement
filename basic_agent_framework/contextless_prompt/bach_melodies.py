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

    return single_voice_abc


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
