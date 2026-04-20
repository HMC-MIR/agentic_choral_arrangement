import argparse
import random
import shutil
from pathlib import Path


def _all_hymn_files(dataset_dir: Path) -> list[Path]:
    return [
        p
        for p in dataset_dir.iterdir()
        if p.is_file() and p.suffix.lower() in {".xml", ".musicxml"}
    ]


def extract_hymn(
    dataset_dir: Path,
    hymn_stem: str,
    output_path: Path | None = None,
) -> Path:
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
        # Ambiguous; require unique naming in the dataset
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


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Given a dataset directory of MusicXML files, extract a single hymn "
            "by filename stem, or pick a random hymn."
        )
    )
    parser.add_argument(
        "dataset_dir",
        type=Path,
        help="Directory containing MusicXML hymn files.",
    )
    parser.add_argument(
        "hymn_stem",
        nargs="?",
        help=(
            "Filename stem of the hymn to extract (e.g., '001_HolyHolyHoly'). "
            "If omitted and --random is set, a random hymn is chosen."
        ),
    )
    parser.add_argument(
        "--random",
        action="store_true",
        help="If set, ignore hymn_stem and choose a random hymn from the dataset.",
    )
    parser.add_argument(
        "--output-path",
        type=Path,
        help="Optional path to copy the hymn file to. If omitted, prints the source path.",
    )

    args = parser.parse_args()

    if args.random:
        selected_path = random_hymn(
            dataset_dir=args.dataset_dir,
            output_path=args.output_path,
        )
    else:
        if args.hymn_stem is None:
            parser.error("hymn_stem is required unless --random is given.")
        selected_path = extract_hymn(
            dataset_dir=args.dataset_dir,
            hymn_stem=args.hymn_stem,
            output_path=args.output_path,
        )
    print(selected_path)


if __name__ == "__main__":
    main()

