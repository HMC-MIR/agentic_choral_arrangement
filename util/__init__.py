"""util — shared utilities for the MIR agentic arrangement project.

Submodules
----------
midi_sonify    Core MIDI manipulation and synthesis (pretty_midi-based).
abc_sonify     ABC notation → audio pipeline via abc2midi.
conversion     ABC ↔ MusicXML format conversion (EasyABC wrappers).
extraction     Hymn dataset lookup and SATB part extraction.

Vendored
--------
abc2xml        EasyABC ABC → MusicXML converter (used by conversion.py).
xml2abc        EasyABC MusicXML → ABC converter (used by conversion.py).
"""

from .abc_sonify import (
    ABCScore,
    load_abc,
    list_parts,
    select_parts,
    abc_to_midi,
    sonify_part,
    sonify_parts,
    trim_time,
    trim_measures,
    estimate_measure_times,
    synthesize,
    play_audio,
    write_wav,
    get_metadata,
    get_lyrics,
)

from .conversion import abc_to_musicxml, part_musicxml_to_abc

from .extraction import extract_hymn, random_hymn, extract_part

__all__ = [
    # abc_sonify
    "ABCScore",
    "load_abc",
    "list_parts",
    "select_parts",
    "abc_to_midi",
    "sonify_part",
    "sonify_parts",
    "trim_time",
    "trim_measures",
    "estimate_measure_times",
    "synthesize",
    "play_audio",
    "write_wav",
    "get_metadata",
    "get_lyrics",
    # conversion
    "abc_to_musicxml",
    "part_musicxml_to_abc",
    # extraction
    "extract_hymn",
    "random_hymn",
    "extract_part",
]
