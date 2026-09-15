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

Clone the repository:

```bash
git clone https://github.com/xocnarfnal/artifact-audit.git
cd artifact-audit

Install the package:

python -m pip install .

Confirm the CLI is available:

artifact-audit --help
Generate a Manifest

Generate a manifest for a directory:

artifact-audit generate ./data

By default, the manifest is written to:

artifact-manifest.json

Specify another output path:

artifact-audit generate ./data --output my-manifest.json

Example manifest:

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
Verify Artifacts

Verify a directory against a manifest:

artifact-audit verify ./data --manifest artifact-manifest.json

If every artifact matches:

Verification passed: all artifacts match the manifest.

If something changed, Artifact Audit reports the affected files:

Verification failed.
Modified:
  - example.txt

It separately identifies:

missing files
modified files
unexpected files
Exit Codes
Exit code	Meaning
0	Verification passed
1	Verification failed

This makes Artifact Audit suitable for CI pipelines and automated review workflows.

Deterministic Output

Artifact Audit intentionally excludes timestamps and sorts file paths before generating a manifest.

For unchanged input files, repeated manifest generation produces identical output.

Development

Run the test suite with:

python -m unittest discover -s tests -v

Tests also run automatically through GitHub Actions on every push and pull request to main.

Project Status

Alpha.

The core manifest generation and verification workflow is implemented and tested. Additional reporting and packaging improvements are planned.

License

MIT License.


### Commit

Commit message：

```text
Document installation and usage
