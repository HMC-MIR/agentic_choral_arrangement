"""conversion — ABC ↔ MusicXML format conversion utilities.

Wraps the EasyABC tools (abc2xml.py, xml2abc.py) bundled in this package.
Both converters invoke the scripts as subprocesses using the same Python
interpreter so they run in isolation with their own dependencies.
"""

import argparse
import subprocess
import sys
from pathlib import Path

# EasyABC scripts live alongside this file in the util/ package directory.
_UTIL_DIR = Path(__file__).parent
_ABC2XML_SCRIPT = _UTIL_DIR / "abc2xml.py"
_XML2ABC_SCRIPT = _UTIL_DIR / "xml2abc.py"


def abc_to_musicxml(
    abc_path: Path,
    output_xml: Path | None = None,
) -> Path:
    """Convert an ABC notation file to MusicXML using abc2xml (EasyABC).

    If *output_xml* is omitted, the output path mirrors *abc_path* with a
    ``.musicxml`` extension. Returns the output path.
    """
    abc_path = abc_path.expanduser().resolve()
    if not abc_path.is_file():
        raise FileNotFoundError(f"ABC file not found: {abc_path}")

    if output_xml is None:
        output_xml = abc_path.with_suffix(".musicxml")

    output_xml = output_xml.expanduser().resolve()
    output_xml.parent.mkdir(parents=True, exist_ok=True)

    if not _ABC2XML_SCRIPT.is_file():
        raise FileNotFoundError(f"abc2xml.py not found: {_ABC2XML_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(_ABC2XML_SCRIPT), str(abc_path)],
        check=True,
        capture_output=True,
        text=True,
    )

    output_xml.write_text(result.stdout, encoding="utf-8")
    return output_xml


def part_musicxml_to_abc(
    part_xml: Path,
    output_abc: Path | None = None,
) -> Path:
    """Convert a single-part MusicXML file to ABC notation using xml2abc (EasyABC).

    If *output_abc* is omitted, the output path mirrors *part_xml* with a
    ``.abc`` extension. Returns the output path.
    """
    part_xml = part_xml.expanduser().resolve()
    if not part_xml.is_file():
        raise FileNotFoundError(f"Part MusicXML not found: {part_xml}")

    if output_abc is None:
        output_abc = part_xml.with_suffix(".abc")

    output_abc = output_abc.expanduser().resolve()
    output_abc.parent.mkdir(parents=True, exist_ok=True)

    if not _XML2ABC_SCRIPT.is_file():
        raise FileNotFoundError(f"xml2abc.py not found: {_XML2ABC_SCRIPT}")

    result = subprocess.run(
        [sys.executable, str(_XML2ABC_SCRIPT), str(part_xml)],
        check=True,
        capture_output=True,
        text=True,
    )

    output_abc.write_text(result.stdout, encoding="utf-8")
    return output_abc


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def _abc_to_xml_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Convert an ABC notation file to MusicXML using abc2xml (EasyABC)."
    )
    parser.add_argument("abc_path", type=Path, help="Path to the input ABC file.")
    parser.add_argument(
        "--output-xml",
        type=Path,
        default=None,
        help="Output MusicXML path. Defaults to input with .musicxml extension.",
    )
    args = parser.parse_args()
    xml_path = abc_to_musicxml(abc_path=args.abc_path, output_xml=args.output_xml)
    print(xml_path)


def _xml_to_abc_cli() -> None:
    parser = argparse.ArgumentParser(
        description="Convert a single-part MusicXML file to ABC notation using xml2abc (EasyABC)."
    )
    parser.add_argument("part_xml", type=Path, help="Path to the input MusicXML file.")
    parser.add_argument(
        "--output-abc",
        type=Path,
        default=None,
        help="Output ABC path. Defaults to input with .abc extension.",
    )
    args = parser.parse_args()
    abc_path = part_musicxml_to_abc(part_xml=args.part_xml, output_abc=args.output_abc)
    print(abc_path)


if __name__ == "__main__":
    import sys as _sys
    # Dispatch: python -m util.conversion abc2xml <args>  OR  python -m util.conversion xml2abc <args>
    if len(_sys.argv) > 1 and _sys.argv[1] == "xml2abc":
        _sys.argv.pop(1)
        _xml_to_abc_cli()
    else:
        _abc_to_xml_cli()
