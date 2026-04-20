import argparse
from pathlib import Path

from music21 import converter, stream


PART_LABEL_MAP = {
    "S": 0,
    "SOPRANO": 0,
    "A": 1,
    "ALTO": 1,
    "T": 2,
    "TENOR": 2,
    "B": 3,
    "BASS": 3,
}


def _normalize_label(label: str) -> str:
    return label.strip().upper()


def extract_part(
    hymn_xml: Path,
    part_label: str,
    output_xml: Path | None = None,
) -> stream.Score:
    hymn_xml = hymn_xml.expanduser().resolve()
    if not hymn_xml.is_file():
        raise FileNotFoundError(f"Hymn XML not found: {hymn_xml}")

    score = converter.parse(str(hymn_xml))
    label_norm = _normalize_label(part_label)

    chosen_part = None
    for part in score.parts:
        names_to_check = []
        if getattr(part, "partName", None):
            names_to_check.append(str(part.partName))
        if getattr(part, "id", None):
            names_to_check.append(str(part.id))

        if any(_normalize_label(n).startswith(label_norm) for n in names_to_check):
            chosen_part = part
            break

    if chosen_part is None:
        if label_norm not in PART_LABEL_MAP:
            raise ValueError(f"Unrecognized part label: {part_label!r}")
        idx = PART_LABEL_MAP[label_norm]
        try:
            chosen_part = score.parts[idx]
        except IndexError as exc:
            raise IndexError(
                f"Requested part '{part_label}' (index {idx}) not found in score."
            ) from exc

    part_score = stream.Score()
    part_score.append(chosen_part)

    if output_xml is not None:
        output_xml = output_xml.expanduser().resolve()
        if output_xml.suffix.lower() == ".xml":
            output_xml = output_xml.with_suffix(".musicxml")
        output_xml.parent.mkdir(parents=True, exist_ok=True)
        part_score.write("musicxml", fp=str(output_xml))

    return part_score


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "For a single hymn MusicXML file, extract a specific part "
            "(S, A, T, or B) into its own MusicXML file."
        )
    )
    parser.add_argument(
        "hymn_xml",
        type=Path,
        help="Path to the input hymn MusicXML file.",
    )
    parser.add_argument(
        "part_label",
        help="Part to extract (e.g., S, A, T, B).",
    )
    parser.add_argument(
        "--output-xml",
        type=Path,
        default=None,
        help=(
            "Path to write the extracted part MusicXML file. "
            "If omitted, the file is not written; only a summary is printed."
        ),
    )

    args = parser.parse_args()
    part_score = extract_part(
        hymn_xml=args.hymn_xml,
        part_label=args.part_label,
        output_xml=args.output_xml,
    )

    part = part_score.parts[0]
    label = getattr(part, "partName", None) or getattr(part, "id", None) or "Unknown"
    print(f"Extracted part: {label}")


if __name__ == "__main__":
    main()

