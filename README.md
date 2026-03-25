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


Files
-----

1. split_musicxml_to_midi.py
   - Input: one multi-part MusicXML file (for example, a 4-part hymn).
   - Output: one MusicXML file and one MIDI file per part.

2. extract_hymn.py
   - Input: a folder of MusicXML hymn files and the filename stem of one hymn or --random for a random hymn.
   - Output: the path to that hymn, or an optional copy of the file.

3. extract_part.py
   - Input: a single hymn MusicXML file and a part label (S, A, T, B).
   - Output: a new MusicXML file that contains only the requested part.

4. part_to_abc.py
   - Input: a single-part MusicXML file (for example, created by `extract_part.py`).
   - Output: an ABC notation file for that part.
   - Internally calls the local `xml2abc.py` script (from EasyABC).

5. abc_to_musicxml.py
   - Input: an ABC notation file.
   - Output: a MusicXML file made from that ABC.
   - Internally calls the local `abc2xml.py` script (from EasyABC).

Basic command examples
----------------------

Run these commands from inside the project folder:

1. Split a multi-part MusicXML into per-part MusicXML and MIDI:

   python3 split_musicxml_to_midi.py path/to/hymn.musicxml

2. From a dataset folder, pick out one hymn by stem:

   python3 extract_hymn.py path/to/dataset --output-path hymn.musicxml

3. From that hymn, extract the Alto part into its own MusicXML:

   python3 extract_part.py hymn.xml A --output-xml Alto.xml

4. Convert that Alto MusicXML file into ABC:

   python3 part_to_abc.py Alto.musicxml --output-abc Alto.abc

5. Convert the ABC file back into MusicXML:

   python3 abc_to_musicxml.py Alto.abc --output-xml Alto_abc_to_xml.musicxml

Data -- musicXML files
----------------------
Copyright (c) 2022 reedperkins

Licensed under the MIT License