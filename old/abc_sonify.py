"""abc_sonify — ABC notation sonification helpers built on music21 + pretty_midi.

Provides ABC loading (with multi-voice splitting for ABC Plus format),
part inspection/selection, voice classification, metadata and lyrics
extraction, and conversion to PrettyMIDI so that all midi_sonify
functions (synthesize, play_audio, trim_*, write_wav) work directly
on the result.
"""

from __future__ import annotations

import pathlib
import re
import tempfile

import numpy as np
import pretty_midi
from music21 import converter, note as m21note, stream


# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _mean_pitch(part: stream.Part) -> float:
    """Return the mean MIDI pitch of all notes in *part*, or 0 if empty."""
    pitches = [n.pitch.midi for n in part.recurse().getElementsByClass(m21note.Note)]
    return float(np.mean(pitches)) if pitches else 0.0


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


def _split_abc_voices(text: str) -> dict[str, str]:
    """Split a multi-voice ABC Plus file into per-voice ABC strings.

    Returns a dict mapping voice ID (e.g. 'S1V1') to a complete
    single-voice ABC string that music21 can parse independently.
    """
    lines = text.split("\n")

    # Collect header lines (everything before the first [V: ...] music line)
    header_lines: list[str] = []
    music_lines: list[str] = []
    reached_music = False

    for line in lines:
        stripped = line.strip()
        # Skip %%staves directives (multi-voice layout, not needed per-voice)
        if stripped.startswith("%%staves"):
            continue
        # Skip V: header definitions (we'll handle voices ourselves)
        if re.match(r"^V:\s*\S+", stripped):
            continue
        # Skip %%MIDI beat/program lines (voice-specific MIDI hints)
        if stripped.startswith("%%MIDI"):
            continue
        # Detect first music line containing [V: ...]
        if not reached_music and re.search(r"\[V:\s*\S+\]", stripped):
            reached_music = True
        if reached_music:
            music_lines.append(line)
        else:
            header_lines.append(line)

    # Parse the music lines into voice-keyed buckets
    voice_ids: list[str] = []
    voice_music: dict[str, list[str]] = {}
    current_voice: str | None = None

    for line in music_lines:
        stripped = line.strip()
        # Skip comment-only lines (e.g. "% 5")
        if stripped.startswith("%") and not stripped.startswith("%%"):
            continue

        # Check for inline voice marker at start of line
        m = re.match(r"\[V:\s*(\S+)\](.*)", stripped)
        if m:
            current_voice = m.group(1)
            rest = m.group(2).strip()
            if current_voice not in voice_music:
                voice_ids.append(current_voice)
                voice_music[current_voice] = []
            if rest:
                voice_music[current_voice].append(rest)
        elif stripped.startswith("w:") or stripped.startswith("W:"):
            # Lyrics line — attach to current voice
            if current_voice and current_voice in voice_music:
                voice_music[current_voice].append(stripped)
        elif current_voice and stripped:
            voice_music[current_voice].append(stripped)

    # Extract inline tempo directives [Q:...] from music and promote to header.
    # e.g. "[Q:1/4=100] A | B A G" → header gets "Q:1/4=100", music keeps "A | B A G"
    tempo_header: str | None = None
    for vid in voice_ids:
        cleaned: list[str] = []
        for line in voice_music[vid]:
            qm = re.search(r"\[Q:([^\]]+)\]", line)
            if qm:
                if tempo_header is None:
                    tempo_header = f"Q:{qm.group(1)}"
                line = re.sub(r"\[Q:[^\]]+\]\s*", "", line)
            cleaned.append(line)
        voice_music[vid] = cleaned

    # Build per-voice ABC strings
    header = "\n".join(header_lines)
    if tempo_header:
        # Insert Q: line right before the K: line (required by ABC spec)
        header_with_tempo = []
        inserted = False
        for hl in header_lines:
            if not inserted and hl.strip().startswith("K:"):
                header_with_tempo.append(tempo_header)
                inserted = True
            header_with_tempo.append(hl)
        if not inserted:
            header_with_tempo.append(tempo_header)
        header = "\n".join(header_with_tempo)

    result: dict[str, str] = {}
    for vid in voice_ids:
        music = "\n".join(voice_music[vid])
        result[vid] = f"{header}\n{music}\n"

    return result


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_abc(path: str | pathlib.Path) -> stream.Score:
    """Parse an ABC file and return a music21 Score.

    Handles multi-voice ABC Plus files by splitting voices and parsing
    each independently, then combining into a single Score with separate
    Parts. Falls back to standard music21 parsing for single-voice files.

    Raises ``FileNotFoundError`` if the path doesn't exist and
    ``RuntimeError`` on parse failures.
    """
    p = pathlib.Path(path)
    if not p.exists():
        siblings = sorted(p.parent.glob("*.abc"))
        hint = ""
        if siblings:
            names = [s.name for s in siblings[:8]]
            hint = f" Did you mean one of: {', '.join(names)}?"
        raise FileNotFoundError(f"ABC file not found: {p}{hint}")

    text = p.read_text(encoding="utf-8", errors="replace")

    # Check for multi-voice ABC Plus format
    voice_abcs = _split_abc_voices(text)

    if len(voice_abcs) > 1:
        # Parse each voice separately and combine
        score = stream.Score()
        for vid, abc_text in voice_abcs.items():
            try:
                part_score = converter.parse(abc_text, format="abc")
            except Exception as exc:
                raise RuntimeError(
                    f"Failed to parse voice {vid} from {p}: {exc}"
                ) from exc

            # Extract the part(s) from the parsed result
            if isinstance(part_score, stream.Score) and part_score.parts:
                part = part_score.parts[0]
            elif isinstance(part_score, stream.Part):
                part = part_score
            else:
                part = stream.Part()
                for el in part_score.flatten():
                    part.append(el)

            part.partName = vid
            part.id = vid
            score.insert(0, part)

        # Copy metadata from first voice parse
        first_abc = next(iter(voice_abcs.values()))
        try:
            first_parsed = converter.parse(first_abc, format="abc")
            if hasattr(first_parsed, "metadata") and first_parsed.metadata:
                score.metadata = first_parsed.metadata
        except Exception:
            pass

        return score

    # Single-voice fallback: standard music21 parsing
    try:
        score = converter.parse(str(p))
    except Exception as exc:
        raise RuntimeError(f"Failed to parse ABC file {p}: {exc}") from exc

    if not isinstance(score, stream.Score):
        if isinstance(score, stream.Part):
            wrapped = stream.Score()
            wrapped.insert(0, score)
            score = wrapped
        else:
            raise RuntimeError(
                f"Expected a Score from {p}, got {type(score).__name__}"
            )
    return score


def list_parts(score: stream.Score) -> list[dict]:
    """Return a list of dicts summarising every part in *score*.

    Each dict contains: part_index, name, note_count, pitch_min, pitch_max,
    mean_pitch, voice, and duration.
    """
    results: list[dict] = []
    for idx, part in enumerate(score.parts):
        notes = list(part.recurse().getElementsByClass(m21note.Note))
        pitches = [n.pitch.midi for n in notes]
        mp = float(np.mean(pitches)) if pitches else 0.0

        info: dict = {
            "part_index": idx,
            "name": part.partName or part.id or f"Part {idx}",
            "note_count": len(notes),
            "mean_pitch": round(mp, 1),
            "voice": _classify_voice(mp),
        }

        if pitches:
            info["pitch_min"] = min(pitches)
            info["pitch_max"] = max(pitches)
        else:
            info["pitch_min"] = None
            info["pitch_max"] = None

        info["duration"] = float(part.duration.quarterLength)
        results.append(info)

    return results


def select_parts(
    score: stream.Score,
    selector: int | list[int] | str,
) -> stream.Score:
    """Return a new Score containing only the matched parts.

    *selector* can be:
    - ``int`` — single part index
    - ``list[int]`` — multiple indices
    - ``str`` — case-insensitive substring matched against part name
      **or** voice label (Soprano/Alto/Tenor/Bass)
    """
    parts = score.parts
    voice_labels = {"soprano", "alto", "tenor", "bass"}

    if isinstance(selector, int):
        indices = [selector]
    elif isinstance(selector, list):
        indices = selector
    elif isinstance(selector, str):
        needle = selector.lower()
        # First try matching voice labels
        if needle in voice_labels:
            indices = [
                i for i, part in enumerate(parts)
                if _classify_voice(_mean_pitch(part)).lower() == needle
            ]
        else:
            # Fall back to name substring match
            indices = [
                i for i, part in enumerate(parts)
                if needle in (part.partName or part.id or "").lower()
            ]
            # If no name match, also try voice label as substring
            if not indices:
                indices = [
                    i for i, part in enumerate(parts)
                    if needle in _classify_voice(_mean_pitch(part)).lower()
                ]
    else:
        raise TypeError(f"Unsupported selector type: {type(selector)}")

    available = [
        f"  [{i}] {part.partName or part.id or f'Part {i}'} "
        f"({_classify_voice(_mean_pitch(part))})"
        for i, part in enumerate(parts)
    ]
    available_str = "\n".join(available)

    for i in indices:
        if i < 0 or i >= len(parts):
            raise IndexError(
                f"Part index {i} out of range (0–{len(parts) - 1}).\n"
                f"Available parts:\n{available_str}"
            )

    if not indices:
        raise ValueError(
            f"No parts matched selector {selector!r}.\n"
            f"Available parts:\n{available_str}"
        )

    new_score = stream.Score()
    for i in indices:
        new_score.insert(0, parts[i])
    return new_score


def abc_to_midi(score: stream.Score) -> pretty_midi.PrettyMIDI:
    """Convert a music21 Score to a PrettyMIDI object via temp MIDI export."""
    with tempfile.NamedTemporaryFile(suffix=".mid", delete=False) as tmp:
        tmp_path = tmp.name

    score.write("midi", fp=tmp_path)

    try:
        pm = pretty_midi.PrettyMIDI(tmp_path)
    except Exception as exc:
        raise RuntimeError(
            f"Failed to load exported MIDI from music21: {exc}"
        ) from exc
    finally:
        pathlib.Path(tmp_path).unlink(missing_ok=True)

    return pm


def sonify_part(
    score: stream.Score,
    selector: int | str,
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> tuple[np.ndarray, int]:
    """Sonify a single part from *score*.

    *selector* is passed to :func:`select_parts` — use an index (``0``),
    voice ID substring (``"S1V1"``), or voice label (``"Soprano"``).

    Returns ``(audio, sample_rate)`` ready for ``ms.play_audio(audio)``.
    """
    from midi_sonify import synthesize

    part_score = select_parts(score, selector)
    pm = abc_to_midi(part_score)
    audio = synthesize(pm, sample_rate=sample_rate, sf2_path=sf2_path)
    return audio, sample_rate


def sonify_parts(
    score: stream.Score,
    selectors: list[int | str],
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> tuple[np.ndarray, int]:
    """Sonify multiple parts from *score* and mix them together.

    Each element of *selectors* is passed to :func:`select_parts` independently,
    then all selected parts are combined into one Score before conversion.

    Returns ``(audio, sample_rate)`` ready for ``ms.play_audio(audio)``.
    """
    from midi_sonify import synthesize

    combined = stream.Score()
    for sel in selectors:
        sub = select_parts(score, sel)
        for part in sub.parts:
            combined.insert(0, part)
    pm = abc_to_midi(combined)
    audio = synthesize(pm, sample_rate=sample_rate, sf2_path=sf2_path)
    return audio, sample_rate


def get_metadata(score: stream.Score) -> dict:
    """Extract metadata from the Score (title, composer, key, time signature, etc.)."""
    md = score.metadata
    info: dict = {}

    info["title"] = md.title if md and md.title else None
    info["composer"] = md.composer if md and md.composer else None

    # Key signature from first part
    keys = list(score.flatten().getElementsByClass("KeySignature"))
    if keys:
        info["key"] = keys[0].asKey().name
    else:
        info["key"] = None

    # Time signature from first part
    time_sigs = list(score.flatten().getElementsByClass("TimeSignature"))
    if time_sigs:
        ts = time_sigs[0]
        info["time_signature"] = f"{ts.numerator}/{ts.denominator}"
    else:
        info["time_signature"] = None

    # Tempo
    tempos = list(score.flatten().getElementsByClass("MetronomeMark"))
    if tempos:
        info["tempo_bpm"] = tempos[0].number
    else:
        info["tempo_bpm"] = None

    info["num_parts"] = len(score.parts)
    info["duration_quarters"] = float(score.duration.quarterLength)

    return info


def get_lyrics(path: str | pathlib.Path) -> list[dict]:
    """Extract lyrics directly from the ABC file text.

    Parses ``w:`` (inline lyrics) and ``W:`` (footer lyrics) lines.
    music21's ABC parser often doesn't attach ``w:`` lyrics to notes,
    so this reads from the raw file instead.

    In ABC hymn format, lyrics for each verse are spread across multiple
    music sections (one ``w:`` line per section). This function reassembles
    them by tracking verse numbers across sections.

    Returns a list of dicts with keys: verse, voice, text.
    """
    p = pathlib.Path(path)
    text = p.read_text(encoding="utf-8", errors="replace")

    current_voice: str | None = None

    # Collect w: lines grouped by voice, preserving section boundaries.
    # Each voice gets a list of "sections" (list of w: lines per music phrase).
    voice_sections: dict[str, list[list[str]]] = {}
    current_section: list[str] | None = None

    for line in text.split("\n"):
        stripped = line.strip()

        # Track current voice from [V: ...] markers
        m = re.match(r"\[V:\s*(\S+)\]", stripped)
        if m:
            new_voice = m.group(1)
            if new_voice != current_voice:
                # Save previous section
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
        """Clean ABC lyric formatting."""
        cleaned = raw
        # Remove verse number prefix (e.g. "1.~")
        cleaned = re.sub(r"^\d+\.\s*~?\s*", "", cleaned)
        cleaned = cleaned.replace("~", " ")
        cleaned = re.sub(r"\s*\*\s*", " ", cleaned)
        cleaned = re.sub(r"\s*-\s*", "", cleaned)
        cleaned = re.sub(r"\s+", " ", cleaned).strip()
        return cleaned

    # Reassemble verses. In ABC hymn format, the first section has
    # numbered w: lines (1.~..., 2.~...), subsequent sections continue
    # the same verses in the same order.
    results: list[dict] = []
    for voice_id, sections in voice_sections.items():
        if not sections:
            continue

        # Determine verse count from the first section
        first_section = sections[0]
        num_verses = len(first_section)

        # Parse verse numbers from first section
        verse_numbers: list[int] = []
        for raw_line in first_section:
            vm = re.match(r"(\d+)\.", raw_line)
            verse_numbers.append(int(vm.group(1)) if vm else 0)

        # Build full text for each verse across sections
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

    # Footer lyrics (W: lines — not voice-specific)
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
