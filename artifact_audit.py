import argparse
import hashlib
import json
from pathlib import Path


DEFAULT_MANIFEST = "artifact-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def generate_manifest(root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    files = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        # Avoid including the manifest itself.
        if path.resolve() == output:
            continue

        relative_path = path.relative_to(root).as_posix()

        files.append(
            {
                "path": relative_path,
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )

    return {
        "manifest_version": 1,
        "algorithm": "sha256",
        "files": files,
    }


def write_manifest(manifest: dict, output: Path) -> None:
    output.write_text(
        json.dumps(
            manifest,
            indent=2,
            sort_keys=True,
        )
        + "\n",
        encoding="utf-8",
    )


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate deterministic SHA-256 artifact manifests."
    )

    subparsers = parser.add_subparsers(dest="command", required=True)

    generate_parser = subparsers.add_parser(
        "generate",
        help="Generate a manifest for a directory.",
    )

    generate_parser.add_argument(
        "path",
        type=Path,
        help="Directory to audit.",
    )

    generate_parser.add_argument(
        "-o",
        "--output",
        type=Path,
        default=Path(DEFAULT_MANIFEST),
        help=f"Output manifest path. Default: {DEFAULT_MANIFEST}",
    )

    args = parser.parse_args()

    if args.command == "generate":
        manifest = generate_manifest(args.path, args.output)
        write_manifest(manifest, args.output)

        print(
            f"Manifest written to {args.output} "
            f"({len(manifest['files'])} files)"
        )


if __name__ == "__main__":
    main()
