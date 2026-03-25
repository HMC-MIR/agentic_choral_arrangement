"""abc_sonify — ABC sonification via abc2midi + pretty_midi.

Uses the native ``abc2midi`` tool for ABC→MIDI conversion (correct
tempo, fermata, and instrument handling), then delegates to
``midi_sonify`` for inspection, selection, trimming, and synthesis.

No music21 dependency — only abc2midi (brew install abcmidi),
pretty_midi, and numpy.
"""

from __future__ import annotations

import copy
import dataclasses
import pathlib
import re
import shutil
import subprocess
import tempfile
from typing import Union

import numpy as np
import pretty_midi

from . import midi_sonify

# ---------------------------------------------------------------------------
# Dataclass
# ---------------------------------------------------------------------------


@dataclasses.dataclass
class ABCScore:
    """Container holding a PrettyMIDI converted from an ABC file."""

    midi: pretty_midi.PrettyMIDI
    voice_map: dict[str, int]  # voice_id → instrument index
    metadata: dict
    abc_path: pathlib.Path


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _check_abc2midi() -> None:
    """Raise RuntimeError if abc2midi is not on PATH."""
    if shutil.which("abc2midi") is None:
        raise RuntimeError(
            "abc2midi not found on PATH. Install it with:\n"
            "  brew install abcmidi          # macOS\n"
            "  sudo apt install abcmidi      # Debian/Ubuntu"
        )


def _parse_abc_header(text: str) -> tuple[dict, list[str]]:
    """Parse ABC header fields and return (metadata, ordered_voice_ids).

    Extracts T:, C:, M:, K:, Q:, and V: lines from the header.
    """
    metadata: dict = {
        "title": None,
        "composer": None,
        "key": None,
        "time_signature": None,
        "tempo_bpm": None,
    }
    voice_ids: list[str] = []

    for line in text.split("\n"):
        stripped = line.strip()

        # Title — first T: wins
        if stripped.startswith("T:") and metadata["title"] is None:
            metadata["title"] = stripped[2:].strip()

        # Composer — first C: wins
        elif stripped.startswith("C:") and metadata["composer"] is None:
            val = stripped[2:].strip()
            # Skip lines that are clearly not the composer
            if val.lower().startswith("words:") or val.lower().startswith("music:"):
                metadata["composer"] = val
            elif metadata["composer"] is None:
                metadata["composer"] = val

        # Time signature
        elif stripped.startswith("M:") and metadata["time_signature"] is None:
            metadata["time_signature"] = re.split(r"\s*%", stripped[2:].strip())[0].strip()

        # Key
        elif stripped.startswith("K:") and metadata["key"] is None:
            metadata["key"] = re.split(r"\s*%", stripped[2:].strip())[0].strip()

        # Tempo — header Q: or inline [Q:...]
        elif stripped.startswith("Q:") and metadata["tempo_bpm"] is None:
            metadata["tempo_bpm"] = _parse_tempo(stripped[2:].strip())

        # Voice declarations (header V: lines, not inline [V:...])
        elif re.match(r"^V:\s*(\S+)", stripped):
            m = re.match(r"^V:\s*(\S+)", stripped)
            vid = m.group(1)
            if vid not in voice_ids:
                voice_ids.append(vid)

    # Also look for inline [Q:...] if no header Q: was found
    if metadata["tempo_bpm"] is None:
        qm = re.search(r"\[Q:([^\]]+)\]", text)
        if qm:
            metadata["tempo_bpm"] = _parse_tempo(qm.group(1).strip())

    return metadata, voice_ids


def _parse_tempo(raw: str) -> float | None:
    """Parse an ABC tempo field like '1/4=100' → 100.0 or '120' → 120.0."""
    # "1/4=100" or "3/8=80"
    m = re.search(r"=\s*(\d+)", raw)
    if m:
        return float(m.group(1))
    # Plain number
    m = re.match(r"^\d+$", raw.strip())
    if m:
        return float(raw.strip())
    return None


def _mean_pitch(instrument: pretty_midi.Instrument) -> float:
    """Mean MIDI pitch from instrument.notes, or 0 if empty."""
    if not instrument.notes:
        return 0.0
    return float(np.mean([n.pitch for n in instrument.notes]))


def _classify_voice(mean_pitch: float) -> str:
    """Map a mean MIDI pitch to a voice label (Soprano/Alto/Tenor/Bass)."""
    if mean_pitch > 65:
        return "Soprano"
    elif mean_pitch > 58:
        return "Alto"
    elif mean_pitch > 50:
        return "Tenor"
    else:
        return "Bass"


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_abc(path: str | pathlib.Path) -> ABCScore:
    """Load an ABC file via abc2midi, returning an ABCScore.

    Raises FileNotFoundError if the file doesn't exist and
    RuntimeError if abc2midi is not installed or conversion fails.
    """
    p = pathlib.Path(path)
    if not p.exists():
        siblings = sorted(p.parent.glob("*.abc"))
        hint = ""
        if siblings:
            names = [s.name for s in siblings[:8]]
            hint = f" Did you mean one of: {', '.join(names)}?"
        raise FileNotFoundError(f"ABC file not found: {p}{hint}")

    _check_abc2midi()

    # Parse header
    text = p.read_text(encoding="utf-8", errors="replace")
    metadata, voice_ids = _parse_abc_header(text)

    # Convert ABC → MIDI via abc2midi
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        result = subprocess.run(
            ["abc2midi", str(p), "-o", tmp_path],
            capture_output=True,
            text=True,
        )
        if not pathlib.Path(tmp_path).exists() or pathlib.Path(tmp_path).stat().st_size == 0:
            raise RuntimeError(
                f"abc2midi failed to produce output.\n"
                f"stderr: {result.stderr}\nstdout: {result.stdout}"
            )

        pm = pretty_midi.PrettyMIDI(tmp_path)
    except Exception as exc:
        if isinstance(exc, RuntimeError):
            raise
        raise RuntimeError(f"abc2midi conversion failed for {p}: {exc}") from exc
    finally:
        pathlib.Path(tmp_path).unlink(missing_ok=True)

    # Build voice_map: voice_id → instrument index
    voice_map: dict[str, int] = {}
    for i, vid in enumerate(voice_ids):
        if i < len(pm.instruments):
            voice_map[vid] = i
            pm.instruments[i].name = vid

    return ABCScore(
        midi=pm,
        voice_map=voice_map,
        metadata=metadata,
        abc_path=p,
    )


def list_parts(score: ABCScore) -> list[dict]:
    """List all parts in the score with voice classification.

    Returns midi_sonify.list_instruments() output enriched with
    voice_id and voice label.
    """
    instruments = midi_sonify.list_instruments(score.midi)

    # Reverse map: index → voice_id
    idx_to_vid = {idx: vid for vid, idx in score.voice_map.items()}

    for info in instruments:
        i = info["instrument_index"]
        info["voice_id"] = idx_to_vid.get(i)
        mp = _mean_pitch(score.midi.instruments[i])
        info["mean_pitch"] = round(mp, 1)
        info["voice"] = _classify_voice(mp)

    return instruments


def select_parts(
    score: ABCScore,
    selector: Union[int, list[int], str],
) -> ABCScore:
    """Return a new ABCScore with only the matched parts.

    *selector* can be:
    - ``int`` — single instrument index
    - ``list[int]`` — multiple indices
    - ``str`` — matched against voice_id keys, voice labels
      (Soprano/Alto/Tenor/Bass), or instrument name substring
    """
    if isinstance(selector, str):
        needle = selector.lower()

        # Try voice_map keys first (e.g. "S1V1")
        indices = [
            idx for vid, idx in score.voice_map.items()
            if needle in vid.lower()
        ]

        # Try voice label (e.g. "Soprano", "Bass")
        if not indices:
            indices = [
                i for i, inst in enumerate(score.midi.instruments)
                if _classify_voice(_mean_pitch(inst)).lower() == needle
            ]

        # Fall back to instrument name substring
        if not indices:
            indices = [
                i for i, inst in enumerate(score.midi.instruments)
                if needle in (inst.name or "").lower()
            ]

        if not indices:
            available = [
                f"  [{idx}] {vid} ({_classify_voice(_mean_pitch(score.midi.instruments[idx]))})"
                for vid, idx in score.voice_map.items()
            ]
            raise ValueError(
                f"No parts matched selector {selector!r}.\n"
                f"Available parts:\n" + "\n".join(available)
            )
    elif isinstance(selector, int):
        indices = [selector]
    elif isinstance(selector, list):
        indices = selector
    else:
        raise TypeError(f"Unsupported selector type: {type(selector)}")

    new_pm = midi_sonify.select_instruments(score.midi, indices)

    # Remap voice_map for selected instruments
    new_voice_map: dict[str, int] = {}
    for new_i, old_i in enumerate(indices):
        for vid, idx in score.voice_map.items():
            if idx == old_i:
                new_voice_map[vid] = new_i
                break

    return ABCScore(
        midi=new_pm,
        voice_map=new_voice_map,
        metadata=score.metadata,
        abc_path=score.abc_path,
    )


def abc_to_midi(score: ABCScore) -> pretty_midi.PrettyMIDI:
    """Return the PrettyMIDI object from the score."""
    return score.midi


def sonify_part(
    score: ABCScore,
    selector: Union[int, str],
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> tuple[np.ndarray, int]:
    """Sonify a single part from *score*.

    Returns ``(audio, sample_rate)``.
    """
    part_score = select_parts(score, selector)
    audio = midi_sonify.synthesize(part_score.midi, sample_rate=sample_rate, sf2_path=sf2_path)
    return audio, sample_rate


def sonify_parts(
    score: ABCScore,
    selectors: list[Union[int, str]],
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> tuple[np.ndarray, int]:
    """Sonify multiple parts and combine them.

    Each selector is resolved independently, then all selected
    instruments are merged into one PrettyMIDI before synthesis.

    Returns ``(audio, sample_rate)``.
    """
    pms = []
    for sel in selectors:
        part_score = select_parts(score, sel)
        pms.append(part_score.midi)

    merged = midi_sonify.merge_midi(*pms)
    audio = midi_sonify.synthesize(merged, sample_rate=sample_rate, sf2_path=sf2_path)
    return audio, sample_rate


def trim_time(
    score: ABCScore,
    start_s: float = 0.0,
    end_s: float | None = None,
) -> ABCScore:
    """Return a new ABCScore with the timeline clipped to [start_s, end_s] seconds."""
    new_pm = midi_sonify.trim_time(score.midi, start_s, end_s)
    return ABCScore(midi=new_pm, voice_map=score.voice_map, metadata=score.metadata, abc_path=score.abc_path)


def trim_measures(
    score: ABCScore,
    start_measure: int = 1,
    end_measure: int | None = None,
) -> ABCScore:
    """Return a new ABCScore trimmed to [start_measure, end_measure] (1-indexed, inclusive)."""
    new_pm = midi_sonify.trim_measures(score.midi, start_measure, end_measure)
    return ABCScore(midi=new_pm, voice_map=score.voice_map, metadata=score.metadata, abc_path=score.abc_path)


def estimate_measure_times(score: ABCScore) -> list[float]:
    """Return measure-start times in seconds derived from tempo and time signature."""
    return midi_sonify.estimate_measure_times(score.midi)


def synthesize(
    score: ABCScore,
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> np.ndarray:
    """Synthesize an ABCScore to a mono float64 numpy array."""
    return midi_sonify.synthesize(score.midi, sample_rate=sample_rate, sf2_path=sf2_path)


def play_audio(audio: np.ndarray, sample_rate: int = 44100):
    """Return an IPython.display.Audio widget for inline playback."""
    return midi_sonify.play_audio(audio, sample_rate)


def write_wav(
    path: str | pathlib.Path,
    audio: np.ndarray,
    sample_rate: int = 44100,
) -> None:
    """Write audio to a WAV file."""
    midi_sonify.write_wav(path, audio, sample_rate)


def get_metadata(score: ABCScore) -> dict:
    """Return score metadata plus computed fields."""
    info = dict(score.metadata)
    info["num_parts"] = len(score.midi.instruments)
    info["duration_seconds"] = round(score.midi.get_end_time(), 2)
    return info


def get_lyrics(source: Union[ABCScore, str, pathlib.Path]) -> list[dict]:
    """Extract lyrics from the ABC file text.

    Accepts an ABCScore or a path. Parses ``w:`` (inline lyrics) and
    ``W:`` (footer lyrics) lines directly from the raw ABC text.

    Returns a list of dicts with keys: verse, voice, text.
    """
    if isinstance(source, ABCScore):
        p = source.abc_path
    else:
        p = pathlib.Path(source)

    text = p.read_text(encoding="utf-8", errors="replace")

    current_voice: str | None = None
    voice_sections: dict[str, list[list[str]]] = {}
    current_section: list[str] | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Track current voice from [V: ...] markers
        m = re.match(r"\[V:\s*(\S+)\]", stripped)
        if m:
            new_voice = m.group(1)
            if new_voice != current_voice:
                if current_voice and current_section:
                    voice_sections.setdefault(current_voice, []).append(
                        current_section
                    )
                current_voice = new_voice
                current_section = []
            elif current_section is None:
                current_section = []

        if stripped.startswith("w:"):
            lyric_text = stripped[2:].strip()
            if current_voice and lyric_text and current_section is not None:
                current_section.append(lyric_text)

    # Don't forget the last section
    if current_voice and current_section:
        voice_sections.setdefault(current_voice, []).append(current_section)

    def _clean_lyric(raw: str) -> str:
        cleaned = raw
        cleaned = re.sub(r"^\d+\.\s*~?\s*", "", cleaned)
        cleaned = cleaned.replace("~", " ")
        cleaned = re.sub(r"\s*\*\s*", " ", cleaned)
        cleaned = re.sub(r"\s*-\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    results: list[dict] = []
    for voice_id, sections in voice_sections.items():
        if not sections:
            continue

        first_section = sections[0]
        num_verses = len(first_section)

        verse_numbers: list[int] = []
        for raw_line in first_section:
            vm = re.match(r"(\d+)\.", raw_line)
            verse_numbers.append(int(vm.group(1)) if vm else 0)

        for v_idx in range(num_verses):
            v_num = verse_numbers[v_idx] if v_idx < len(verse_numbers) else v_idx + 1
            parts: list[str] = []
            for section in sections:
                if v_idx < len(section):
                    parts.append(_clean_lyric(section[v_idx]))
            full_text = " ".join(parts)
            if full_text:
                results.append({
                    "verse": v_num,
                    "voice": voice_id,
                    "text": full_text,
                })

    # Footer lyrics (W: lines)
    max_verse = max((r["verse"] for r in results), default=0)
    footer_lines: list[str] = []
    for line in text.split("\n"):
        stripped = line.strip()
        if stripped.startswith("W:"):
            footer_lines.append(stripped[2:].strip())

    if footer_lines:
        results.append({
            "verse": max_verse + 1,
            "voice": "all",
            "text": _clean_lyric(" ".join(footer_lines)),
        })

    return results
