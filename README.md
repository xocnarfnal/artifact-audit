# Artifact Audit

[![Tests](https://github.com/xocnarfnal/artifact-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/xocnarfnal/artifact-audit/actions/workflows/tests.yml)

Artifact Audit is a lightweight command-line tool for generating deterministic SHA-256 file manifests and verifying artifact integrity.

It is designed for automated workflows, review pipelines, reproducible research, and any process where unexpected file changes need to be detected reliably.

## Features

- Generate deterministic SHA-256 manifests
- Record file paths, hashes, and sizes
- Verify files against an existing manifest
- Detect modified files
- Detect missing files
- Detect unexpected files
- CI-friendly exit codes
- Machine-readable JSON manifests
- No runtime dependencies

## Requirements

Python 3.10 or newer.

## Installation

Install directly from PyPI:

```bash
pip install artifact-audit
```

Confirm the CLI is available:

```bash
artifact-audit --help
```

## Generate a Manifest

Generate a manifest for a directory:

```bash
artifact-audit generate ./data
```

By default, the manifest is written to:

```text
artifact-manifest.json
```

Specify another output path:

```bash
artifact-audit generate ./data --output my-manifest.json
```

Example manifest:

```json
{
  "algorithm": "sha256",
  "files": [
    {
      "path": "example.txt",
      "sha256": "a1b2c3...",
      "size": 128
    }
  ],
  "manifest_version": 1
}
```

## Verify Artifacts

Verify a directory against a manifest:

```bash
artifact-audit verify ./data --manifest artifact-manifest.json
```

If every artifact matches:

```text
Verification passed: all artifacts match the manifest.
```

If something changed:

```text
Verification failed.
Modified:
  - example.txt
```

Artifact Audit separately identifies missing, modified, and unexpected files.

## Exit Codes

| Exit code | Meaning |
| --- | --- |
| `0` | Verification passed |
| `1` | Verification failed |

This makes Artifact Audit suitable for CI pipelines and automated review workflows.

## Deterministic Output

Artifact Audit intentionally excludes timestamps and sorts file paths before generating a manifest.

For unchanged input files, repeated manifest generation produces identical output.

## Development

Run the test suite with:

```bash
python -m unittest discover -s tests -v
```

Tests also run automatically through GitHub Actions on every push and pull request to `main`.

## Project Status

Alpha.

The core manifest generation and verification workflow is implemented and tested.

## License

MIT License.
