import argparse
import hashlib
import json
import sys
from pathlib import Path


DEFAULT_MANIFEST = "artifact-manifest.json"


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


def collect_files(root: Path, excluded: Path | None = None) -> list[dict]:
    root = root.resolve()
    excluded = excluded.resolve() if excluded else None

    files = []

    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue

        if excluded and path.resolve() == excluded:
            continue

        files.append(
            {
                "path": path.relative_to(root).as_posix(),
                "sha256": sha256_file(path),
                "size": path.stat().st_size,
            }
        )

    return files


def generate_manifest(root: Path, output: Path) -> dict:
    root = root.resolve()
    output = output.resolve()

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    return {
        "manifest_version": 1,
        "algorithm": "sha256",
        "files": collect_files(root, excluded=output),
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


def load_manifest(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def verify_manifest(root: Path, manifest_path: Path) -> dict:
    root = root.resolve()
    manifest_path = manifest_path.resolve()

    if not root.exists():
        raise FileNotFoundError(f"Path does not exist: {root}")

    if not root.is_dir():
        raise NotADirectoryError(f"Path is not a directory: {root}")

    if not manifest_path.exists():
        raise FileNotFoundError(f"Manifest does not exist: {manifest_path}")

    manifest = load_manifest(manifest_path)

    expected = {
        item["path"]: item
        for item in manifest.get("files", [])
    }

    current_files = collect_files(root, excluded=manifest_path)

    current = {
        item["path"]: item
        for item in current_files
    }

    expected_paths = set(expected)
    current_paths = set(current)

    missing = sorted(expected_paths - current_paths)
    unexpected = sorted(current_paths - expected_paths)

    modified = sorted(
        path
        for path in expected_paths & current_paths
        if (
            expected[path]["sha256"] != current[path]["sha256"]
            or expected[path]["size"] != current[path]["size"]
        )
    )

    valid = not missing and not modified and not unexpected

    return {
        "valid": valid,
        "missing": missing,
        "modified": modified,
        "unexpected": unexpected,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Generate and verify deterministic SHA-256 artifact manifests."
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

    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify a directory against an existing manifest.",
    )

    verify_parser.add_argument(
        "path",
        type=Path,
        help="Directory to verify.",
    )

    verify_parser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        default=Path(DEFAULT_MANIFEST),
        help=f"Manifest path. Default: {DEFAULT_MANIFEST}",
    )

    args = parser.parse_args()

    if args.command == "generate":
        manifest = generate_manifest(args.path, args.output)
        write_manifest(manifest, args.output)

        print(
            f"Manifest written to {args.output} "
            f"({len(manifest['files'])} files)"
        )

    elif args.command == "verify":
        result = verify_manifest(args.path, args.manifest)

        if result["valid"]:
            print("Verification passed: all artifacts match the manifest.")
            return

        print("Verification failed.")

        if result["missing"]:
            print("Missing:")
            for path in result["missing"]:
                print(f"  - {path}")

        if result["modified"]:
            print("Modified:")
            for path in result["modified"]:
                print(f"  - {path}")

        if result["unexpected"]:
            print("Unexpected:")
            for path in result["unexpected"]:
                print(f"  - {path}")

        sys.exit(1)


if __name__ == "__main__":
    main()
