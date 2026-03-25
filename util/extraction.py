"""extraction — Hymn and part extraction utilities.

Provides functions for locating hymn files from a dataset directory
and extracting individual SATB parts from multi-part MusicXML scores.
"""

import argparse
import random
import shutil
from pathlib import Path

from music21 import converter, stream


# ---------------------------------------------------------------------------
# Hymn extraction (from dataset)
# ---------------------------------------------------------------------------

MUSICXML_SUFFIXES = {".xml", ".musicxml"}


def _all_hymn_files(dataset_dir: Path) -> list[Path]:
    return [
        p
        for p in dataset_dir.iterdir()
        if p.is_file() and p.suffix.lower() in MUSICXML_SUFFIXES
    ]


def extract_hymn(
    dataset_dir: Path,
    hymn_stem: str,
    output_path: Path | None = None,
) -> Path:
    """Locate a hymn by filename stem, optionally copying it to *output_path*.

    Returns the path to the hymn file (source or copy).
    """
    dataset_dir = dataset_dir.expanduser().resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    matches: list[Path] = [
        p for p in _all_hymn_files(dataset_dir) if p.stem == hymn_stem
    ]

    if not matches:
        raise FileNotFoundError(
            f"No hymn with stem '{hymn_stem}' found in {dataset_dir}"
        )
    if len(matches) > 1:
        raise RuntimeError(
            f"Multiple hymns with stem '{hymn_stem}' found in {dataset_dir}: "
            + ", ".join(str(m) for m in matches)
        )

    hymn_path = matches[0]

    if output_path is None:
        return hymn_path

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(hymn_path, output_path)
    return output_path


def random_hymn(
    dataset_dir: Path,
    output_path: Path | None = None,
) -> Path:
    """Pick a random hymn from *dataset_dir*, optionally copying it to *output_path*.

    Returns the path to the selected hymn file.
    """
    dataset_dir = dataset_dir.expanduser().resolve()
    if not dataset_dir.is_dir():
        raise FileNotFoundError(f"Dataset directory not found: {dataset_dir}")

    candidates = _all_hymn_files(dataset_dir)
    if not candidates:
        raise FileNotFoundError(f"No MusicXML files found in {dataset_dir}")

    hymn_path = random.choice(candidates)

    if output_path is None:
        return hymn_path

    output_path = output_path.expanduser().resolve()
    output_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(hymn_path, output_path)
    return output_path


# ---------------------------------------------------------------------------
# Part extraction (SATB from MusicXML)
# ---------------------------------------------------------------------------

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
    """Extract a single SATB part from a multi-part MusicXML hymn file.

    *part_label* accepts S, A, T, B or full names (Soprano, Alto, Tenor, Bass).
    If *output_xml* is given, writes the extracted part as MusicXML.
    Returns the music21 Score for the extracted part.
    """
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


# ---------------------------------------------------------------------------
# CLI entry points
# ---------------------------------------------------------------------------


def _hymn_cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Given a dataset directory of MusicXML files, extract a single hymn "
            "by filename stem, or pick a random hymn."
        )
    )
    parser.add_argument("dataset_dir", type=Path)
    parser.add_argument("hymn_stem", nargs="?")
    parser.add_argument("--random", action="store_true")
    parser.add_argument("--output-path", type=Path)

    args = parser.parse_args()

    if args.random:
        selected_path = random_hymn(dataset_dir=args.dataset_dir, output_path=args.output_path)
    else:
        if args.hymn_stem is None:
            parser.error("hymn_stem is required unless --random is given.")
        selected_path = extract_hymn(
            dataset_dir=args.dataset_dir,
            hymn_stem=args.hymn_stem,
            output_path=args.output_path,
        )
    print(selected_path)


def _part_cli() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "For a single hymn MusicXML file, extract a specific part "
            "(S, A, T, or B) into its own MusicXML file."
        )
    )
    parser.add_argument("hymn_xml", type=Path)
    parser.add_argument("part_label", help="Part to extract (S, A, T, B).")
    parser.add_argument("--output-xml", type=Path, default=None)

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
    import sys
    # Dispatch based on script invocation hint
    # Usage: python -m util.extraction hymn <args>  OR  python -m util.extraction part <args>
    if len(sys.argv) > 1 and sys.argv[1] == "part":
        sys.argv.pop(1)
        _part_cli()
    else:
        _hymn_cli()
