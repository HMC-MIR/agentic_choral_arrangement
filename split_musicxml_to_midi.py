import argparse
from pathlib import Path

from music21 import converter, stream


def split_musicxml_to_midi(
    input_xml: Path,
    output_xml_dir: Path,
    output_midi_dir: Path,
) -> None:
    score = converter.parse(str(input_xml))

    output_xml_dir.mkdir(parents=True, exist_ok=True)
    output_midi_dir.mkdir(parents=True, exist_ok=True)

    for idx, part in enumerate(score.parts, start=1):
        part_score = stream.Score()
        part_score.append(part)

        part_label = None
        if hasattr(part, "id") and part.id:
            part_label = part.id
        elif getattr(part, "partName", None):
            part_label = str(part.partName)

        if part_label:
            safe_label = "".join(
                c if c.isalnum() or c in ("-", "_") else "_" for c in part_label
            ).strip("_")
            if not safe_label:
                safe_label = f"part{idx}"
        else:
            safe_label = f"part{idx}"

        xml_filename = output_xml_dir / f"{safe_label}.musicxml"
        midi_filename = output_midi_dir / f"{safe_label}.mid"

        # Write MusicXML
        part_score.write("musicxml", fp=str(xml_filename))

        # Write MIDI
        part_score.write("midi", fp=str(midi_filename))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Split a multi-part MusicXML file into separate per-part "
            "MusicXML and MIDI files."
        )
    )
    parser.add_argument(
        "input_xml",
        type=Path,
        help="Path to the input multi-part MusicXML file.",
    )
    parser.add_argument(
        "--output-xml-dir",
        type=Path,
        default=Path("parts_xml"),
        help="Directory to store per-part MusicXML files (default: parts_xml).",
    )
    parser.add_argument(
        "--output-midi-dir",
        type=Path,
        default=Path("parts_midi"),
        help="Directory to store per-part MIDI files (default: parts_midi).",
    )

    args = parser.parse_args()
    split_musicxml_to_midi(
        input_xml=args.input_xml,
        output_xml_dir=args.output_xml_dir,
        output_midi_dir=args.output_midi_dir,
    )


if __name__ == "__main__":
    main()

