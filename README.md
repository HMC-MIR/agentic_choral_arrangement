# MIR Agentic Arrangement

Music Information Retrieval toolkit for analysing and sonifying MIDI hymn arrangements.

## Project Structure

```
├── src/
│   └── midi_sonify.py          # MIDI loading, inspection, trimming, synthesis, playback
├── notebooks/
│   ├── midi_sonify_demo.ipynb   # Walkthrough of midi_sonify functions
│   └── music21_exploratory.ipynb# Part extraction with music21
├── data/
│   └── hymns/                   # Source MIDI files
│       └── Amazing_Grace_(nc)pope.mid
├── output/                      # Generated audio (gitignored)
└── README.md
```

## Setup

### 1. Create the conda environment

```bash
conda create -n mir python=3.13
conda activate mir
```

### 2. Install dependencies

**Required:**

```bash
pip install pretty_midi soundfile numpy
```

**For music21 notebook:**

```bash
pip install music21
```

**For natural-sounding audio (optional):**

```bash
brew install fluidsynth        # macOS
pip install pyfluidsynth
```

You'll also need a SoundFont (`.sf2`) file — [GeneralUser GS](https://schristiancollins.com/generaluser.php) is a good free option.

### 3. Run the notebooks

```bash
cd notebooks
jupyter notebook midi_sonify_demo.ipynb
```

## Sine Waves vs SoundFont

By default, `ms.synthesize()` uses **pure sine-wave synthesis** — each note is a simple tone with no attack, decay, or timbre. Notes sound discrete and robotic.

For realistic, connected playback, pass a SoundFont path:

```python
audio = ms.synthesize(pm, sf2_path="/path/to/GeneralUser_GS.sf2")
```

This uses FluidSynth under the hood, which renders sampled instruments with proper envelopes and articulation. If FluidSynth isn't available, it falls back to sine waves automatically with a warning.

## `midi_sonify` Quick Reference

```python
import sys, pathlib
sys.path.insert(0, str(pathlib.Path("../src")))
import midi_sonify as ms

pm = ms.load_midi("../data/hymns/Amazing_Grace_(nc)pope.mid")

ms.list_instruments(pm)                    # instrument summary dicts
ms.select_instruments(pm, "violin")        # filter by name substring
ms.select_instruments(pm, [0, 1])          # filter by index

ms.trim_time(pm, 0.0, 10.0)               # clip to time range (seconds)
ms.trim_measures(pm, 1, 5)                 # clip to measure range (1-indexed)
ms.estimate_measure_times(pm)              # measure start times in seconds

audio = ms.synthesize(pm)                  # numpy array (mono float64)
ms.play_audio(audio)                       # inline Jupyter playback widget
ms.write_wav("out.wav", audio)             # export to WAV
```
