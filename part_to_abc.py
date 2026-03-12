import argparse
import subprocess
import sys
from pathlib import Path


def part_musicxml_to_abc(
    part_xml: Path,
    output_abc: Path | None = None,
) -> Path:
    """
    Convert a single-part MusicXML file into ABC notation using xml2abc.py
    from the EasyABC toolchain.

    This function uses the `xml2abc.py` script that is vendored in this
    repository (originally from the EasyABC project).
    """
    part_xml = part_xml.expanduser().resolve()
    if not part_xml.is_file():
        raise FileNotFoundError(f"Part MusicXML not found: {part_xml}")

    if output_abc is None:
        output_abc = part_xml.with_suffix(".abc")

    output_abc = output_abc.expanduser().resolve()
    output_abc.parent.mkdir(parents=True, exist_ok=True)

    # Call the local xml2abc.py script with the same Python interpreter.
    xml2abc_script = Path(__file__).with_name("xml2abc.py")
    if not xml2abc_script.is_file():
        raise FileNotFoundError(
            f"xml2abc.py not found next to this script: {xml2abc_script}"
        )

    # xml2abc writes ABC to stdout by default, so capture it and write it
    # directly into our target file.
    result = subprocess.run(
        [sys.executable, str(xml2abc_script), str(part_xml)],
        check=True,
        capture_output=True,
        text=True,
    )

    output_abc.write_text(result.stdout, encoding="utf-8")
    return output_abc


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert a single-part MusicXML file into ABC notation using "
            "xml2abc.py (EasyABC)."
        )
    )
    parser.add_argument(
        "part_xml",
        type=Path,
        help="Path to the input single-part MusicXML file.",
    )
    parser.add_argument(
        "--output-abc",
        type=Path,
        default=None,
        help=(
            "Optional path for the output ABC file. If omitted, uses the "
            "input filename with an '.abc' extension."
        ),
    )

    args = parser.parse_args()
    abc_path = part_musicxml_to_abc(
        part_xml=args.part_xml,
        output_abc=args.output_abc,
    )
    print(abc_path)


if __name__ == "__main__":
    main()