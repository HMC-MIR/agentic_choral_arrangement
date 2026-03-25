import argparse
import subprocess
import sys
from pathlib import Path


def abc_to_musicxml(
    abc_path: Path,
    output_xml: Path | None = None,
) -> Path:
    """
    Using abc2xml.py (originally from the EasyABC project).
    """
    abc_path = abc_path.expanduser().resolve()
    if not abc_path.is_file():
        raise FileNotFoundError(f"ABC file not found: {abc_path}")

    if output_xml is None:
        output_xml = abc_path.with_suffix(".musicxml")

    output_xml = output_xml.expanduser().resolve()
    output_xml.parent.mkdir(parents=True, exist_ok=True)

    abc2xml_script = Path(__file__).with_name("abc2xml.py")
    if not abc2xml_script.is_file():
        raise FileNotFoundError(
            f"abc2xml.py not found next to this script: {abc2xml_script}"
        )

    # abc2xml writes MusicXML to stdout; capture it and write to the target file.
    result = subprocess.run(
        [sys.executable, str(abc2xml_script), str(abc_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    output_xml.write_text(result.stdout, encoding="utf-8")
    return output_xml


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Convert an ABC notation file back into MusicXML using "
            "abc2xml.py (EasyABC)."
        )
    )
    parser.add_argument(
        "abc_path",
        type=Path,
        help="Path to the input ABC file.",
    )
    parser.add_argument(
        "--output-xml",
        type=Path,
        default=None,
        help=(
            "Optional path for the output MusicXML file. If omitted, uses the "
            "input filename with a '.musicxml' extension."
        ),
    )

    args = parser.parse_args()
    xml_path = abc_to_musicxml(
        abc_path=args.abc_path,
        output_xml=args.output_xml,
    )
    print(xml_path)


if __name__ == "__main__":
    main()

