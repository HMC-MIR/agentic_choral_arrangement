Agentic Choral Arrangement Tools
================================

Setup
-----

1. Install Python 3.10+.
2. Install Python dependencies:

   pip3 install -r requirements.txt

3. The project vendors two converter scripts from the EasyABC project:
   `xml2abc.py` and `abc2xml.py`. You do not need to install EasyABC
   separately; these scripts are called directly by the helper tools
   below.

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