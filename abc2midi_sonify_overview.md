# abc2midi_sonify — Overview

## What it is

`abc2midi_sonify.py` is an ABC notation sonification pipeline that converts ABC Plus files to audio. It shells out to the native `abc2midi` CLI tool for the ABC→MIDI step (getting correct tempo, fermatas, and instrument handling), then uses `midi_sonify` internally for MIDI manipulation and synthesis.

The companion notebook `abc2midi_sonify_demo.ipynb` walks through the full workflow end-to-end on a 4-voice SATB hymn using only `import abc2midi_sonify as abc` — no other imports needed.

---

## Why ABC → MIDI → audio?

There is no way to directly synthesize an ABC file to audio. ABC is a symbolic notation format — it describes pitches, durations, and structure as text, but contains no audio signal. To hear it you must first convert it to MIDI (a performance representation with timing and note events), and then synthesize the MIDI to a waveform using either sine-wave approximation or a SoundFont. `abc2midi` handles the first step; `midi_sonify.synthesize` handles the second.

---

## Functions we built

### Private helpers

| Function | What it does |
|---|---|
| `_check_abc2midi()` | Verifies `abc2midi` is on PATH; raises a helpful install message if not |
| `_parse_abc_header(text)` | Parses the ABC header for title, composer, key, time signature, tempo, and voice IDs |
| `_parse_tempo(raw)` | Handles ABC tempo strings in `1/4=100` or plain `120` form |
| `_mean_pitch(instrument)` | Computes mean MIDI pitch of a `pretty_midi.Instrument`'s notes |
| `_classify_voice(mean_pitch)` | Maps a mean pitch to a voice label (Soprano / Alto / Tenor / Bass) |

### Public API

| Function | What it does |
|---|---|
| `load_abc(path)` | Shells out to `abc2midi`, loads the resulting MIDI into a `PrettyMIDI`, parses the ABC header, returns an `ABCScore` |
| `list_parts(score)` | Lists all parts with voice ID, voice label, mean pitch, note count, pitch range, timing, and polyphony |
| `select_parts(score, selector)` | Returns a new `ABCScore` filtered to matching parts; selector can be an index, list of indices, voice ID (`"S1V1"`), or voice label (`"Soprano"`) |
| `abc_to_midi(score)` | Returns the raw `PrettyMIDI` object from an `ABCScore` (passthrough — MIDI is built at load time) |
| `sonify_part(score, selector)` | **Sonify a single part** — resolves the selector, synthesizes, returns `(audio, sample_rate)` |
| `sonify_parts(score, selectors)` | **Sonify multiple parts** — resolves each selector, merges into one MIDI, synthesizes, returns `(audio, sample_rate)` |
| `trim_time(score, start_s, end_s)` | **Select by time** — returns a new `ABCScore` clipped to `[start_s, end_s]` seconds |
| `trim_measures(score, start_measure, end_measure)` | **Select by measures** — returns a new `ABCScore` trimmed to the given 1-indexed measure range |
| `estimate_measure_times(score)` | Returns measure-start times in seconds derived from tempo and time signature |
| `synthesize(score, sf2_path)` | Synthesizes an `ABCScore` to a mono float64 numpy array (sine-wave or FluidSynth) |
| `play_audio(audio, sample_rate)` | Returns an `IPython.display.Audio` widget for inline Jupyter playback |
| `write_wav(path, audio, sample_rate)` | Writes audio to a WAV file |
| `get_metadata(score)` | Returns title, composer, key, time signature, tempo, part count, and duration in seconds |
| `get_lyrics(source)` | Parses `w:` and `W:` lines from the raw ABC text; reassembles multi-section verses; accepts an `ABCScore` or a file path |

### `ABCScore` dataclass

A container returned by `load_abc` and threaded through all other functions:

```python
@dataclasses.dataclass
class ABCScore:
    midi: pretty_midi.PrettyMIDI   # the converted MIDI
    voice_map: dict[str, int]      # voice_id → instrument index
    metadata: dict                 # parsed from ABC header
    abc_path: pathlib.Path         # original file path (needed by get_lyrics)
```

---

## Functions we borrow from libraries

### From `midi_sonify` (internal dependency, in `old/`)

`midi_sonify` is used internally — users never need to import it directly.

| Borrowed function | Used in |
|---|---|
| `midi_sonify.list_instruments(pm)` | `list_parts()` — base instrument info enriched with voice labels |
| `midi_sonify.select_instruments(pm, indices)` | `select_parts()` — MIDI instrument filtering |
| `midi_sonify.trim_time(pm, ...)` | `trim_time()` |
| `midi_sonify.trim_measures(pm, ...)` | `trim_measures()` |
| `midi_sonify.estimate_measure_times(pm)` | `estimate_measure_times()` |
| `midi_sonify.merge_midi(*pms)` | `sonify_parts()` — combines multiple PrettyMIDI objects |
| `midi_sonify.synthesize(pm, ...)` | `sonify_part()`, `sonify_parts()`, `synthesize()` |
| `midi_sonify.play_audio(audio)` | `play_audio()` |
| `midi_sonify.write_wav(path, audio)` | `write_wav()` |

### From external libraries

| Library | Used for |
|---|---|
| `abc2midi` (CLI, `brew install abcmidi`) | ABC Plus → MIDI conversion |
| `pretty_midi` | MIDI object model used throughout |
| `subprocess` | Running `abc2midi` as a shell command |
| `numpy` | Mean pitch calculation |

---

## Capability summary

| Capability | Available | How |
|---|---|---|
| Sonify a single part | ✅ | `abc.sonify_part(score, "Soprano")` |
| Sonify multiple parts mixed | ✅ | `abc.sonify_parts(score, ["Soprano", "Bass"])` |
| Select measures from a part | ✅ | `abc.trim_measures(abc.select_parts(score, "Bass"), 1, 8)` |
| Trim by time | ✅ | `abc.trim_time(score, 0.0, 10.0)` |
| FluidSynth / SoundFont playback | ✅ | `abc.synthesize(score, sf2_path="...")` |
| Extract lyrics | ✅ | `abc.get_lyrics(score)` |
