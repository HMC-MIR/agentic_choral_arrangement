"""midi_sonify — MIDI sonification helpers built on pretty_midi.

Provides loading, instrument inspection/selection, time-trimming,
measure-based trimming, audio synthesis, inline Jupyter playback,
and WAV export.
"""

from __future__ import annotations

import copy
import pathlib
import warnings
from typing import Callable

import numpy as np
import pretty_midi

# ---------------------------------------------------------------------------
# Private helpers
# ---------------------------------------------------------------------------


def _normalize(audio: np.ndarray, eps: float = 1e-9) -> np.ndarray:
    """Scale *audio* to [-1, 1]."""
    peak = np.max(np.abs(audio))
    if peak < eps:
        return audio
    return audio / peak


def _get_instrument_label(_index: int, inst: pretty_midi.Instrument) -> str:
    """Return the instrument name, falling back to the GM program name."""
    if inst.name and inst.name.strip():
        return inst.name.strip()
    if inst.is_drum:
        return "Drums"
    return pretty_midi.program_to_instrument_name(inst.program)


def _copy_pm_skeleton(
    pm: pretty_midi.PrettyMIDI,
    initial_tempo: float | None = None,
) -> pretty_midi.PrettyMIDI:
    """Create a new PrettyMIDI that preserves *pm*'s tempo map, time
    signatures, and key signatures.  ``_tick_scales`` is copied when the
    private attribute exists (pretty_midi <= 0.2.10); a ``RuntimeWarning``
    is issued if it is missing so the caller knows resolution may differ.
    """
    tempo = initial_tempo if initial_tempo is not None else pm.estimate_tempo()
    new_pm = pretty_midi.PrettyMIDI(initial_tempo=tempo)

    # Copy time-signature and key-signature events
    new_pm._time_signature_changes = copy.deepcopy(pm.time_signature_changes)
    new_pm._key_signature_changes = copy.deepcopy(pm.key_signature_changes)

    # Copy internal tick-scale mapping (private API — may break)
    if hasattr(pm, "_tick_scales"):
        new_pm._tick_scales = copy.deepcopy(pm._tick_scales)
    else:
        warnings.warn(
            "pretty_midi version does not expose _tick_scales; "
            "tempo resolution in the copy may differ.",
            RuntimeWarning,
            stacklevel=2,
        )
    return new_pm


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def load_midi(path: str | pathlib.Path) -> pretty_midi.PrettyMIDI:
    """Load a MIDI file, returning a ``PrettyMIDI`` object.

    Raises ``FileNotFoundError`` (with suggestions) if the path doesn't
    exist and ``RuntimeError`` on parse failures.
    """
    p = pathlib.Path(path)
    if not p.exists():
        siblings = sorted(p.parent.glob("*.mid")) + sorted(p.parent.glob("*.midi"))
        hint = ""
        if siblings:
            names = [s.name for s in siblings[:8]]
            hint = f" Did you mean one of: {', '.join(names)}?"
        raise FileNotFoundError(f"MIDI file not found: {p}{hint}")

    if p.suffix.lower() not in {".mid", ".midi", ".smf"}:
        warnings.warn(
            f"File extension '{p.suffix}' is not a typical MIDI extension.",
            UserWarning,
            stacklevel=2,
        )

    try:
        return pretty_midi.PrettyMIDI(str(p))
    except Exception as exc:
        raise RuntimeError(f"Failed to parse MIDI file {p}: {exc}") from exc


def list_instruments(pm: pretty_midi.PrettyMIDI) -> list[dict]:
    """Return a list of dicts summarising every instrument in *pm*."""
    results: list[dict] = []
    for idx, inst in enumerate(pm.instruments):
        notes = inst.notes
        info: dict = {
            "instrument_index": idx,
            "program": inst.program,
            "is_drum": inst.is_drum,
            "name": _get_instrument_label(idx, inst),
            "note_count": len(notes),
        }

        if notes:
            pitches = [n.pitch for n in notes]
            starts = [n.start for n in notes]
            ends = [n.end for n in notes]
            info["pitch_min"] = min(pitches)
            info["pitch_max"] = max(pitches)
            info["start_time"] = min(starts)
            info["end_time"] = max(ends)
            info["unique_pitches_count"] = len(set(pitches))

            # Approximate polyphony: sample ~200 time points
            t_min, t_max = info["start_time"], info["end_time"]
            n_samples = min(200, len(notes))
            sample_times = np.linspace(t_min, t_max, n_samples)
            counts = []
            for t in sample_times:
                count = sum(1 for n in notes if n.start <= t < n.end)
                counts.append(count)
            info["approximate_polyphony"] = float(np.mean(counts))
        else:
            info["pitch_min"] = None
            info["pitch_max"] = None
            info["start_time"] = None
            info["end_time"] = None
            info["unique_pitches_count"] = 0
            info["approximate_polyphony"] = 0.0

        results.append(info)
    return results


def select_instruments(
    pm: pretty_midi.PrettyMIDI,
    selector: int | list[int] | str | Callable[[int, pretty_midi.Instrument], bool],
) -> pretty_midi.PrettyMIDI:
    """Return a new ``PrettyMIDI`` containing only the matched instruments.

    *selector* can be:
    - ``int`` — single instrument index
    - ``list[int]`` — multiple indices
    - ``str`` — case-insensitive substring matched against instrument labels
    - ``callable(index, instrument) -> bool``
    """
    available = [
        f"  [{i}] {_get_instrument_label(i, inst)}"
        for i, inst in enumerate(pm.instruments)
    ]
    available_str = "\n".join(available)

    if isinstance(selector, int):
        indices = [selector]
    elif isinstance(selector, list):
        indices = selector
    elif isinstance(selector, str):
        needle = selector.lower()
        indices = [
            i
            for i, inst in enumerate(pm.instruments)
            if needle in _get_instrument_label(i, inst).lower()
        ]
    elif callable(selector):
        indices = [
            i
            for i, inst in enumerate(pm.instruments)
            if selector(i, inst)
        ]
    else:  # pragma: no branch — defensive guard for untyped callers
        raise TypeError(f"Unsupported selector type: {type(selector)}")  # type: ignore[unreachable]

    # Validate indices
    for i in indices:
        if i < 0 or i >= len(pm.instruments):
            raise IndexError(
                f"Instrument index {i} out of range "
                f"(0–{len(pm.instruments) - 1}).\n"
                f"Available instruments:\n{available_str}"
            )

    if not indices:
        raise ValueError(
            f"No instruments matched selector {selector!r}.\n"
            f"Available instruments:\n{available_str}"
        )

    new_pm = _copy_pm_skeleton(pm)
    for i in indices:
        new_pm.instruments.append(copy.deepcopy(pm.instruments[i]))
    return new_pm


def trim_time(
    pm: pretty_midi.PrettyMIDI,
    start_s: float = 0.0,
    end_s: float | None = None,
) -> pretty_midi.PrettyMIDI:
    """Return a new ``PrettyMIDI`` with events clipped to [start_s, end_s]
    and the timeline shifted so the result starts at 0.
    """
    if end_s is None:
        end_s = pm.get_end_time()
    if start_s < 0:
        raise ValueError(f"start_s must be >= 0, got {start_s}")
    if start_s > end_s:
        raise ValueError(f"start_s ({start_s}) must be <= end_s ({end_s})")

    # Determine initial tempo at start_s
    tempo_times, tempos = pm.get_tempo_changes()
    if len(tempos) == 0:
        init_tempo = 120.0
    else:
        # Find the last tempo change at or before start_s
        mask = tempo_times <= start_s
        init_tempo = float(tempos[mask][-1]) if mask.any() else float(tempos[0])

    new_pm = pretty_midi.PrettyMIDI(initial_tempo=init_tempo)

    # Copy time signatures: carry forward the active one at start_s
    active_ts = None
    for ts in pm.time_signature_changes:
        if ts.time <= start_s:
            active_ts = ts
    mid_window_ts = [ts for ts in pm.time_signature_changes if start_s < ts.time < end_s]
    if active_ts is not None and not any(ts.time <= start_s for ts in mid_window_ts):
        carried = copy.deepcopy(active_ts)
        carried.time = 0.0
        new_pm.time_signature_changes.append(carried)
    for ts in mid_window_ts:
        shifted = copy.deepcopy(ts)
        shifted.time = ts.time - start_s
        new_pm.time_signature_changes.append(shifted)

    # Copy key signatures in window
    for ks in pm.key_signature_changes:
        if start_s <= ks.time < end_s:
            shifted = copy.deepcopy(ks)
            shifted.time = ks.time - start_s
            new_pm.key_signature_changes.append(shifted)

    # Copy instruments with clipped notes, CCs, and pitch bends
    for inst in pm.instruments:
        new_inst = pretty_midi.Instrument(
            program=inst.program,
            is_drum=inst.is_drum,
            name=inst.name,
        )
        for note in inst.notes:
            if note.end <= start_s or note.start >= end_s:
                continue
            n = copy.deepcopy(note)
            n.start = max(n.start, start_s) - start_s
            n.end = min(n.end, end_s) - start_s
            new_inst.notes.append(n)

        for cc in inst.control_changes:
            if start_s <= cc.time < end_s:
                c = copy.deepcopy(cc)
                c.time -= start_s
                new_inst.control_changes.append(c)

        for pb in inst.pitch_bends:
            if start_s <= pb.time < end_s:
                b = copy.deepcopy(pb)
                b.time -= start_s
                new_inst.pitch_bends.append(b)

        new_pm.instruments.append(new_inst)

    return new_pm


def estimate_measure_times(pm: pretty_midi.PrettyMIDI) -> list[float]:
    """Return a list of measure-start times (in seconds) derived from the
    time-signature and tempo information in *pm*.

    Known limitation: uses the tempo at each measure's start for the
    entire measure, which is accurate for constant-tempo pieces.
    """
    end_time = pm.get_end_time()
    if end_time == 0:
        return [0.0]

    ts_changes = sorted(pm.time_signature_changes, key=lambda ts: ts.time)
    if not ts_changes:
        # Default 4/4
        ts_changes = [pretty_midi.TimeSignature(4, 4, 0.0)]

    measure_times: list[float] = []
    t = 0.0
    ts_idx = 0
    while t < end_time:
        measure_times.append(t)

        # Advance to current time-sig
        while ts_idx + 1 < len(ts_changes) and ts_changes[ts_idx + 1].time <= t:
            ts_idx += 1
        ts = ts_changes[ts_idx]

        # Duration of one measure in beats
        beats_per_measure = ts.numerator * (4.0 / ts.denominator)

        # Tempo at this point (BPM)
        tempo = pm.estimate_tempo()  # global fallback
        tempo_times, tempos = pm.get_tempo_changes()
        if len(tempos) > 0:
            mask = tempo_times <= t
            if mask.any():
                tempo = float(tempos[mask][-1])
            else:
                tempo = float(tempos[0])

        seconds_per_beat = 60.0 / tempo
        measure_duration = beats_per_measure * seconds_per_beat
        t += measure_duration

    return measure_times


def trim_measures(
    pm: pretty_midi.PrettyMIDI,
    start_measure: int = 1,
    end_measure: int | None = None,
) -> pretty_midi.PrettyMIDI:
    """Trim *pm* to the given 1-indexed measure range ``[start_measure, end_measure]``.

    Delegates to :func:`trim_time` after converting measures to seconds
    via :func:`estimate_measure_times`.
    """
    if start_measure < 1:
        raise ValueError(f"start_measure must be >= 1, got {start_measure}")

    mtimes = estimate_measure_times(pm)

    if start_measure > len(mtimes):
        raise ValueError(
            f"start_measure {start_measure} exceeds the number of "
            f"measures ({len(mtimes)})"
        )

    start_s = mtimes[start_measure - 1]

    if end_measure is None:
        end_s = pm.get_end_time()
    elif end_measure > len(mtimes):
        end_s = pm.get_end_time()
    else:
        # end_measure is inclusive — go up to the start of the *next* measure
        if end_measure < len(mtimes):
            end_s = mtimes[end_measure]
        else:
            end_s = pm.get_end_time()

    return trim_time(pm, start_s, end_s)


def synthesize(
    pm: pretty_midi.PrettyMIDI,
    sample_rate: int = 44100,
    sf2_path: str | None = None,
) -> np.ndarray:
    """Synthesize *pm* to a mono float64 numpy array.

    If *sf2_path* is provided, FluidSynth is used (requires ``pyfluidsynth``
    and the ``.sf2`` file); otherwise sine-wave synthesis is used.
    """
    if sf2_path is not None:
        try:
            audio = pm.fluidsynth(fs=sample_rate, sf2_path=sf2_path)
        except Exception as exc:
            warnings.warn(
                f"FluidSynth failed ({exc}); falling back to sine-wave synthesis.",
                RuntimeWarning,
                stacklevel=2,
            )
            audio = pm.synthesize(fs=sample_rate)
    else:
        audio = pm.synthesize(fs=sample_rate)

    # Ensure mono float64
    if audio.ndim > 1:
        audio = audio.mean(axis=0)
    audio = audio.astype(np.float64)
    return _normalize(audio)


def play_audio(
    audio: np.ndarray,
    sample_rate: int = 44100,
):
    """Return an ``IPython.display.Audio`` widget for inline playback."""
    from IPython.display import Audio

    return Audio(data=audio, rate=sample_rate, normalize=False)


def write_wav(
    path: str | pathlib.Path,
    audio: np.ndarray,
    sample_rate: int = 44100,
) -> None:
    """Write *audio* to a WAV file at *path*.

    Tries ``soundfile`` (float32), falls back to ``scipy.io.wavfile``
    (int16).  Raises ``ImportError`` with install hints if neither is
    available.
    """
    p = pathlib.Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)

    try:
        import soundfile as sf

        sf.write(str(p), audio.astype(np.float32), sample_rate)
        return
    except ImportError:
        pass

    try:
        from scipy.io import wavfile

        int16_audio = np.clip(audio * 32767, -32768, 32767).astype(np.int16)
        wavfile.write(str(p), sample_rate, int16_audio)
        return
    except ImportError:
        pass

    raise ImportError(
        "Neither 'soundfile' nor 'scipy' is installed. "
        "Install one of them:\n"
        "  pip install soundfile\n"
        "  pip install scipy"
    )
