# abc2midi_sonify — Overview

## What it is

`abc2midi_sonify.py` is an ABC notation sonification pipeline that converts ABC Plus files to audio. It shells out to the native `abc2midi` CLI tool for the ABC→MIDI step (getting correct tempo, fermatas, and instrument handling), then delegates to `midi_sonify` for everything after that.

The companion notebook `abc2midi_sonify_demo.ipynb` walks through the full workflow end-to-end on a 4-voice SATB hymn.

---

## Functions we built

### Private helpers (in `abc2midi_sonify.py`)

| Function | What it does |
|---|---|
| `_check_abc2midi()` | Verifies `abc2midi` is on PATH; raises a helpful install message if not |
| `_parse_abc_header(text)` | Parses the ABC header for title, composer, key, time signature, and tempo; also collects declared voice IDs |
| `_parse_tempo(raw)` | Handles ABC tempo strings in `1/4=100` or plain `120` form |
| `_mean_pitch(instrument)` | Computes mean MIDI pitch of a `pretty_midi.Instrument`'s notes |
| `_classify_voice(mean_pitch)` | Maps a mean pitch to a voice label (Soprano / Alto / Tenor / Bass) |

### Public API (in `abc2midi_sonify.py`)

| Function | What it does |
|---|---|
| `load_abc(path)` | Shells out to `abc2midi`, loads the resulting MIDI into a `PrettyMIDI`, parses the ABC header, and returns an `ABCScore` dataclass bundling everything together |
| `list_parts(score)` | Lists all parts with voice ID, voice label, mean pitch, note count, and pitch range |
| `select_parts(score, selector)` | Returns a new `ABCScore` filtered to matching parts; selector can be an index, list of indices, voice ID substring (`"S1V1"`), or voice label (`"Soprano"`) |
| `abc_to_midi(score)` | Returns the `PrettyMIDI` object from an `ABCScore` (passthrough — MIDI is already built at load time) |
| `sonify_part(score, selector)` | **Sonify a single part** — resolves the selector, synthesizes, returns `(audio, sample_rate)` |
| `sonify_parts(score, selectors)` | **Sonify multiple parts** — resolves each selector independently, merges into one MIDI, synthesizes, returns `(audio, sample_rate)` |
| `get_metadata(score)` | Returns title, composer, key, time signature, tempo, part count, and duration in seconds |
| `get_lyrics(source)` | Parses `w:` and `W:` lines directly from the raw ABC text; reassembles multi-section verses; accepts either an `ABCScore` or a file path |

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

### From `midi_sonify` (our own module, now in `old/`)

| Borrowed function | Used in |
|---|---|
| `midi_sonify.list_instruments(pm)` | `list_parts()` — base instrument info that we enrich with voice labels |
| `midi_sonify.select_instruments(pm, indices)` | `select_parts()` — does the actual MIDI instrument filtering |
| `midi_sonify.merge_midi(*pms)` | `sonify_parts()` — combines multiple PrettyMIDI objects before synthesis |
| `midi_sonify.synthesize(pm, ...)` | `sonify_part()` and `sonify_parts()` |
| `midi_sonify.trim_time(pm, start_s, end_s)` | Used directly in the demo notebook |
| `midi_sonify.trim_measures(pm, start, end)` | Used directly in the demo notebook |
| `midi_sonify.play_audio(audio)` | Used directly in the demo notebook |
| `midi_sonify.estimate_measure_times(pm)` | Used directly in the demo notebook |

### From external libraries

| Library | Used for |
|---|---|
| `abc2midi` (CLI, `brew install abcmidi`) | ABC Plus → MIDI conversion — the core conversion step |
| `pretty_midi` | MIDI object model used throughout |
| `subprocess` | Running `abc2midi` as a shell command |
| `numpy` | Mean pitch calculation |

---

## Can we select certain measures from a part?

**Not directly in `abc2midi_sonify`.** There is no `trim_measures` or `select_measures` wrapper in this module.

The pattern used in the demo notebook is to call `midi_sonify.trim_measures()` on the `PrettyMIDI` object after extracting it:

```python
# Select a voice, get its PrettyMIDI, then trim
bass_pm = abc.abc_to_midi(abc.select_parts(score, "Bass"))
bass_m1_8 = ms.trim_measures(bass_pm, 1, 8)
audio = ms.synthesize(bass_m1_8)
```

`midi_sonify.trim_measures` handles the measure→seconds conversion internally using the MIDI tempo and time signature events.

---

## Summary: what we have vs what we don't

| Capability | Available | How |
|---|---|---|
| Sonify a single part | ✅ | `abc.sonify_part(score, "Soprano")` |
| Sonify multiple parts mixed | ✅ | `abc.sonify_parts(score, ["Soprano", "Bass"])` |
| Select measures from a part | ⚠️ not wrapped | `ms.trim_measures(abc.abc_to_midi(abc.select_parts(score, ...)), 1, 8)` |
