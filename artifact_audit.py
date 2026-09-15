"""Deterministic local artifact seals, drift reports, and handoff checks."""

import argparse
import hashlib
import hmac
import json
import os
import re
import sys
from pathlib import Path

DEFAULT_MANIFEST = "artifact-manifest.json"
DEFAULT_KEY_ENV = "ARTIFACT_AUDIT_PATH_KEY"
TOOL_VERSION = "0.2.0"
_HEX64 = re.compile(r"^[0-9a-f]{64}$")
_ENV_NAME = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_KEY_CHECK_DOMAIN = b"artifact-audit:v2:path-key-check"


class AuditError(Exception):
    """An input or operational error with a safe public message."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


def canonical_bytes(value: dict) -> bytes:
    """Serialize as sorted UTF-8 JSON with compact separators and a newline."""
    return (json.dumps(value, sort_keys=True, ensure_ascii=False,
                       separators=(",", ":"), allow_nan=False) + "\n").encode("utf-8")


def _digest(value: dict) -> str:
    try:
        return hashlib.sha256(canonical_bytes(value)).hexdigest()
    except (UnicodeError, ValueError, TypeError):
        raise AuditError("invalid_manifest", "manifest cannot be serialized canonically") from None


def _hash_and_size(path: Path) -> tuple[str, int]:
    digest = hashlib.sha256()
    size = 0
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
            size += len(chunk)
    return digest.hexdigest(), size


def sha256_file(path: Path) -> str:
    return _hash_and_size(path)[0]


def _root_directory(root: Path) -> Path:
    root = root.resolve()
    if not root.exists():
        raise AuditError("missing_directory", "directory does not exist")
    if not root.is_dir():
        raise AuditError("invalid_directory", "path is not a directory")
    return root


def collect_files(root: Path, excluded: Path | None = None,
                  extra_excluded: Path | None = None) -> list[dict]:
    """Read only regular files within root; reject symbolic links."""
    root = _root_directory(root)
    excluded_paths = {p.resolve() for p in (excluded, extra_excluded) if p}
    files = []
    for path in root.rglob("*"):
        if path.is_symlink():
            raise AuditError("unsupported_file", "symbolic links are not supported")
        resolved = path.resolve()
        if not resolved.is_relative_to(root):
            raise AuditError("unsupported_file", "file resolves outside the directory")
        if not path.is_file():
            continue
        if resolved in excluded_paths:
            continue
        file_hash, size = _hash_and_size(path)
        files.append({"path": path.relative_to(root).as_posix(),
                      "sha256": file_hash, "size": size})
    files.sort(key=lambda item: item["path"])
    return files


def generate_manifest(root: Path, output: Path) -> dict:
    """Keep the 0.1.x v1 schema for existing generate callers."""
    return {"manifest_version": 1, "algorithm": "sha256",
            "files": collect_files(root, excluded=output)}


def _key(path_key: bytes | None, env_name: str) -> bytes:
    if path_key is None:
        if not _ENV_NAME.fullmatch(env_name):
            raise AuditError("invalid_key_env", "invalid path key environment variable name")
        value = os.environ.get(env_name)
        if not value:
            raise AuditError("missing_path_key", "path key environment variable is missing")
        path_key = value.encode("utf-8")
    if not isinstance(path_key, bytes) or len(path_key) < 16:
        raise AuditError("invalid_path_key", "path key must be at least 16 bytes")
    return path_key


def _path_id(key: bytes, path: str) -> str:
    return hmac.new(key, path.encode("utf-8"), hashlib.sha256).hexdigest()


def _key_check(key: bytes) -> str:
    return hmac.new(key, _KEY_CHECK_DOMAIN, hashlib.sha256).hexdigest()


def seal_manifest(root: Path, output: Path, *, producer: str | None = None,
                  parent: Path | None = None, redact_paths: bool = False,
                  path_key: bytes | None = None,
                  path_key_env: str = DEFAULT_KEY_ENV) -> dict:
    """Create a v2 seal without timestamps or local machine metadata."""
    if producer is not None and (not producer or len(producer) > 128 or
                                 any(ord(char) < 32 for char in producer)):
        raise AuditError("invalid_producer", "producer must be 1-128 printable characters")
    if path_key is not None and not redact_paths:
        raise AuditError("invalid_options", "path key requires redacted paths")
    if parent is not None and parent.resolve() == output.resolve():
        raise AuditError("invalid_options", "parent and output must be different files")
    key = _key(path_key, path_key_env) if redact_paths else None
    records = collect_files(root, excluded=output, extra_excluded=parent)
    if key is not None:
        records = [{"path_id": _path_id(key, item["path"]),
                    "sha256": item["sha256"], "size": item["size"]}
                   for item in records]
        records.sort(key=lambda item: item["path_id"])
    payload = {"manifest_version": 2, "tool": "artifact-audit",
               "tool_version": TOOL_VERSION, "algorithm": "sha256",
               "path_mode": "hmac-sha256" if key else "relative",
               "files": records}
    if producer is not None:
        payload["producer"] = producer
    if parent is not None:
        payload["parent_digest"] = _digest(load_manifest(parent))
    if key is not None:
        payload["path_key_check"] = _key_check(key)
    return {**payload, "manifest_digest": _digest(payload)}


def write_manifest(manifest: dict, output: Path) -> None:
    if manifest.get("manifest_version") == 2:
        output.write_bytes(canonical_bytes(manifest))
    else:
        output.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                          encoding="utf-8")


def _unique_pairs(pairs: list[tuple]) -> dict:
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditError("invalid_manifest", "manifest has duplicate JSON keys")
        result[key] = value
    return result


def _invalid_constant(_value: str):
    raise AuditError("invalid_manifest", "manifest contains an invalid JSON constant")


def _valid_hex(value: object) -> bool:
    return isinstance(value, str) and bool(_HEX64.fullmatch(value))


def _valid_path(value: object, *, v1: bool) -> str:
    if not isinstance(value, str) or not value or "\x00" in value:
        raise AuditError("invalid_manifest", "manifest has an invalid path")
    if not v1 and "\\" in value:
        raise AuditError("invalid_manifest", "v2 paths must use forward slashes")
    normalized = value.replace("\\", "/") if v1 else value
    if (normalized.startswith("/") or re.match(r"^[A-Za-z]:", normalized) or
            any(part in ("", ".", "..") for part in normalized.split("/"))):
        raise AuditError("invalid_manifest", "manifest has an unsafe path")
    return normalized


def validate_manifest(manifest: object) -> dict:
    if not isinstance(manifest, dict):
        raise AuditError("invalid_manifest", "manifest must be a JSON object")
    version = manifest.get("manifest_version")
    if type(version) is not int or version not in (1, 2):
        raise AuditError("invalid_manifest", "unsupported manifest version")
    if manifest.get("algorithm") != "sha256":
        raise AuditError("invalid_manifest", "unsupported hashing algorithm")
    records = manifest.get("files")
    if not isinstance(records, list):
        raise AuditError("invalid_manifest", "files must be a list")
    if version == 2:
        allowed = {"manifest_version", "tool", "tool_version", "algorithm",
                   "path_mode", "files", "manifest_digest", "producer",
                   "parent_digest", "path_key_check"}
        if (set(manifest) - allowed or manifest.get("tool") != "artifact-audit" or
                not isinstance(manifest.get("tool_version"), str) or
                not manifest["tool_version"]):
            raise AuditError("invalid_manifest", "invalid v2 manifest metadata")
        mode = manifest.get("path_mode")
        if mode not in ("relative", "hmac-sha256"):
            raise AuditError("invalid_manifest", "unsupported path mode")
        if (mode == "hmac-sha256") != ("path_key_check" in manifest):
            raise AuditError("invalid_manifest", "invalid privacy metadata")
        if "path_key_check" in manifest and not _valid_hex(manifest["path_key_check"]):
            raise AuditError("invalid_manifest", "invalid path key check")
        if "parent_digest" in manifest and not _valid_hex(manifest["parent_digest"]):
            raise AuditError("invalid_manifest", "invalid parent digest")
        if "producer" in manifest and (not isinstance(manifest["producer"], str) or
                                        not manifest["producer"]):
            raise AuditError("invalid_manifest", "invalid producer")
        if not _valid_hex(manifest.get("manifest_digest")):
            raise AuditError("invalid_manifest", "invalid manifest digest")
        payload = {key: value for key, value in manifest.items() if key != "manifest_digest"}
        if not hmac.compare_digest(manifest["manifest_digest"], _digest(payload)):
            raise AuditError("invalid_manifest", "manifest payload digest does not match")
    else:
        mode = "relative"
    identifier = "path_id" if mode == "hmac-sha256" else "path"
    seen = set()
    previous = None
    for record in records:
        if (not isinstance(record, dict) or
                not {identifier, "sha256", "size"} <= set(record)):
            raise AuditError("invalid_manifest", "invalid file record")
        if version == 2 and set(record) != {identifier, "sha256", "size"}:
            raise AuditError("invalid_manifest", "invalid v2 file record fields")
        item_id = record[identifier]
        if identifier == "path":
            item_id = _valid_path(item_id, v1=version == 1)
        elif not _valid_hex(item_id):
            raise AuditError("invalid_manifest", "invalid path identifier")
        if item_id in seen or (version == 2 and previous is not None and item_id < previous):
            raise AuditError("invalid_manifest", "duplicate or unsorted file records")
        seen.add(item_id)
        previous = item_id
        if (not _valid_hex(record["sha256"]) or type(record["size"]) is not int or
                record["size"] < 0):
            raise AuditError("invalid_manifest", "invalid file hash or size")
    return manifest


def load_manifest(path: Path) -> dict:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise AuditError("missing_manifest", "manifest file does not exist") from None
    except (OSError, UnicodeError):
        raise AuditError("unreadable_manifest", "manifest file cannot be read") from None
    try:
        manifest = json.loads(raw, object_pairs_hook=_unique_pairs,
                              parse_constant=_invalid_constant)
    except (ValueError, TypeError):
        raise AuditError("invalid_manifest", "manifest is not valid JSON") from None
    return validate_manifest(manifest)


def _record_map(manifest: dict) -> dict[str, dict]:
    identifier = "path_id" if manifest.get("path_mode") == "hmac-sha256" else "path"
    return {_valid_path(item[identifier], v1=True) if identifier == "path" else item[identifier]: item
            for item in manifest["files"]}


def verify_manifest(root: Path, manifest_path: Path, *, parent: Path | None = None,
                    path_key: bytes | None = None,
                    path_key_env: str = DEFAULT_KEY_ENV) -> dict:
    root = _root_directory(root)
    manifest = load_manifest(manifest_path)
    mode = manifest.get("path_mode", "relative")
    key = None
    if mode == "hmac-sha256":
        key = _key(path_key, path_key_env)
        if not hmac.compare_digest(_key_check(key), manifest["path_key_check"]):
            raise AuditError("wrong_path_key", "path key does not match the manifest")
    elif path_key is not None:
        raise AuditError("invalid_options", "path key supplied for a non-redacted manifest")
    current_records = collect_files(root, excluded=manifest_path, extra_excluded=parent)
    if key is not None:
        current_records = [{"path_id": _path_id(key, item["path"]),
                            "sha256": item["sha256"], "size": item["size"]}
                           for item in current_records]
    expected = _record_map(manifest)
    identifier = "path_id" if key else "path"
    current = {item[identifier]: item for item in current_records}
    missing = sorted(expected.keys() - current.keys())
    unexpected = sorted(current.keys() - expected.keys())
    modified = sorted(item for item in expected.keys() & current.keys()
                      if expected[item]["sha256"] != current[item]["sha256"] or
                      expected[item]["size"] != current[item]["size"])
    parent_status = "not_required"
    if "parent_digest" in manifest:
        if parent is None or not parent.exists():
            parent_status = "missing"
        else:
            parent_status = ("match" if _digest(load_manifest(parent)) ==
                             manifest["parent_digest"] else "mismatch")
    elif parent is not None:
        raise AuditError("invalid_options", "manifest has no parent link")
    valid = not (missing or modified or unexpected) and parent_status in ("not_required", "match")
    return {"valid": valid, "manifest_version": manifest["manifest_version"],
            "path_mode": mode, "missing": missing, "modified": modified,
            "unexpected": unexpected, "parent_status": parent_status}


def diff_manifests(old_path: Path, new_path: Path) -> dict:
    old = load_manifest(old_path)
    new = load_manifest(new_path)
    old_mode = old.get("path_mode", "relative")
    new_mode = new.get("path_mode", "relative")
    if old_mode != new_mode:
        raise AuditError("incompatible_manifests", "manifests use different path modes")
    if old_mode == "hmac-sha256" and old["path_key_check"] != new["path_key_check"]:
        raise AuditError("incompatible_manifests", "redacted manifests use different path keys")
    before = _record_map(old)
    after = _record_map(new)
    added = sorted(after.keys() - before.keys())
    removed = sorted(before.keys() - after.keys())
    modified = sorted(item for item in before.keys() & after.keys()
                      if before[item]["sha256"] != after[item]["sha256"] or
                      before[item]["size"] != after[item]["size"])
    unchanged_count = len(before.keys() & after.keys()) - len(modified)
    metadata_changed = sorted(field for field in ("producer", "parent_digest")
                              if old.get(field) != new.get(field))
    equivalent = not (added or removed or modified or metadata_changed)
    return {"equivalent": equivalent, "path_mode": old_mode,
            "added": added, "removed": removed, "modified": modified,
            "unchanged_count": unchanged_count, "metadata_changed": metadata_changed}


def _print_report(report: dict, command: str, as_json: bool) -> None:
    if as_json:
        sys.stdout.buffer.write(canonical_bytes(report))
        return
    if command == "verify":
        print("Verification passed: all artifacts match the manifest." if report["valid"]
              else "Verification failed.")
        labels = (("Missing", "missing"), ("Modified", "modified"),
                  ("Unexpected", "unexpected"))
    else:
        print("Manifests equivalent." if report["equivalent"] else "Manifest drift detected.")
        labels = (("Added", "added"), ("Removed", "removed"), ("Modified", "modified"))
    for label, field in labels:
        if report[field]:
            print(f"{label}:")
            for item in report[field]:
                print(f"  - {json.dumps(item, ensure_ascii=True)}")
    if command == "verify" and report["parent_status"] not in ("not_required", "match"):
        print(f"Parent: {report['parent_status']}")
    if command == "diff":
        print(f"Unchanged: {report['unchanged_count']}")
        if report["metadata_changed"]:
            print("Handoff metadata changed: " + ", ".join(report["metadata_changed"]))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Seal, verify, and diff local artifact bundles.")
    subparsers = parser.add_subparsers(dest="command", required=True)
    generate = subparsers.add_parser("generate", help="Generate a legacy v1 manifest.")
    generate.add_argument("path", type=Path)
    generate.add_argument("-o", "--output", type=Path, default=Path(DEFAULT_MANIFEST))
    seal = subparsers.add_parser("seal", help="Create a deterministic v2 artifact seal.")
    seal.add_argument("path", type=Path)
    seal.add_argument("-o", "--output", type=Path, default=Path(DEFAULT_MANIFEST))
    seal.add_argument("--producer")
    seal.add_argument("--parent", type=Path)
    seal.add_argument("--redact-paths", action="store_true")
    seal.add_argument("--path-key-env", default=DEFAULT_KEY_ENV)
    verify = subparsers.add_parser("verify", help="Verify files and optional handoff parent.")
    verify.add_argument("path", type=Path)
    verify.add_argument("-m", "--manifest", type=Path, default=Path(DEFAULT_MANIFEST))
    verify.add_argument("--parent", type=Path)
    verify.add_argument("--path-key-env", default=DEFAULT_KEY_ENV)
    verify.add_argument("--json", action="store_true")
    diff = subparsers.add_parser("diff", help="Compare two validated manifests.")
    diff.add_argument("old", type=Path)
    diff.add_argument("new", type=Path)
    diff.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "generate":
            manifest = generate_manifest(args.path, args.output)
            write_manifest(manifest, args.output)
            print(f"Manifest written ({len(manifest['files'])} files)")
            return 0
        if args.command == "seal":
            manifest = seal_manifest(args.path, args.output, producer=args.producer,
                                     parent=args.parent, redact_paths=args.redact_paths,
                                     path_key_env=args.path_key_env)
            write_manifest(manifest, args.output)
            print(f"Seal written ({len(manifest['files'])} files)")
            return 0
        if args.command == "verify":
            report = verify_manifest(args.path, args.manifest, parent=args.parent,
                                     path_key_env=args.path_key_env)
            _print_report(report, "verify", args.json)
            return 0 if report["valid"] else 1
        report = diff_manifests(args.old, args.new)
        _print_report(report, "diff", args.json)
        return 0 if report["equivalent"] else 1
    except AuditError as error:
        if getattr(args, "json", False):
            sys.stdout.buffer.write(canonical_bytes({"error": error.code, "valid": False}))
        else:
            print(f"Artifact Audit error: {error}", file=sys.stderr)
        return 2
    except OSError:
        if getattr(args, "json", False):
            sys.stdout.buffer.write(canonical_bytes({"error": "io_error", "valid": False}))
        else:
            print("Artifact Audit error: file operation failed", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
