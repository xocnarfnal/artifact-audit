# Artifact Audit

[![Tests](https://github.com/xocnarfnal/artifact-audit/actions/workflows/tests.yml/badge.svg)](https://github.com/xocnarfnal/artifact-audit/actions/workflows/tests.yml)
[![PyPI](https://img.shields.io/pypi/v/artifact-audit)](https://pypi.org/project/artifact-audit/)
[GitHub Marketplace Action](https://github.com/marketplace/actions/artifact-audit)

Seal a folder, hand it to another workflow or reviewer, and independently detect modified, missing, and unexpected artifacts. Artifact Audit is a local Python CLI and GitHub Action for deterministic bundle manifests, handoff verification, and drift reports. Optional privacy-aware path identifiers avoid exposing raw filenames in a seal; sizes and content hashes remain visible. It does not sign manifests or authenticate their authors.

Python 3.10–3.13 is supported. Install the package from [PyPI](https://pypi.org/project/artifact-audit/):

~~~sh
python -m pip install artifact-audit
artifact-audit --help
~~~

## Quick start

Run the [synthetic 30-second demo](https://github.com/xocnarfnal/artifact-audit/tree/main/examples/quick-demo) to see a clean verification, deliberate failure, and added/removed/modified diff. It works on Windows, macOS, and Linux from a repository checkout:

~~~sh
python examples/quick-demo/demo.py
~~~

For your own output bundle, create a v2 seal and verify it after a handoff:

~~~sh
artifact-audit seal ./output --output seal.json --producer build-step
artifact-audit verify ./output --manifest seal.json
~~~

Keep the seal outside the bundle when handing it to another job or reviewer. Exit codes are `0` for a match, `1` for drift, and `2` for invalid input. A verified seal only establishes a match with the supplied manifest; protect that manifest separately if adversarial tampering is in scope.

## Why not just sha256sum?

`sha256sum` is excellent for hashing files. Artifact Audit builds on file hashes to produce deterministic, machine-readable bundle manifests; verifies the whole folder, including missing and unexpected files; and diffs seals into added, removed, and modified records. It can link a child seal to a parent handoff, identify paths with a secret-derived HMAC instead of raw filenames, return stable JSON reports, and fail CI with distinct drift/input exit codes. The root GitHub Action runs verification in a workflow. Git is valuable for tracked source history but does not by itself verify arbitrary generated, untracked output bundles after a transfer. These features are workflow conveniences, not cryptographic proof of who produced a bundle.

The seal is canonical UTF-8 JSON: sorted keys, compact separators, one final newline, and file records sorted by identifier. With unchanged files, options, and tool version, repeat runs produce identical bytes. It contains no automatic timestamp, hostname, username, or absolute path. When the seal is inside the folder, that output file is excluded from the bundle. The producer value is optional and supplied by you.

Link the next stage to a previous manifest without storing its local path:

~~~sh
artifact-audit seal ./review-output --output review-seal.json --parent seal.json
artifact-audit verify ./review-output --manifest review-seal.json --parent seal.json
~~~

The child records a SHA-256 digest of the validated, canonical parent manifest. Verification reports a missing or mismatched parent. If a supplied parent manifest has a broken payload digest, it is invalid input. Parent links and self-digests detect accidental changes; they are not authentication against someone who can replace and recompute manifests.

Compare handoffs, including added, removed, and modified artifacts:

~~~sh
artifact-audit diff seal.json review-seal.json
artifact-audit diff seal.json review-seal.json --json
artifact-audit verify ./output --manifest seal.json --json
~~~

Diff compares file identifiers, SHA-256 hashes, sizes, optional producer, and parent link. It treats v1 and ordinary v2 path records as comparable; a schema/tool-version change alone is not artifact drift. Redacted and ordinary manifests cannot be compared, and two redacted manifests must use the same path key. JSON reports have stable field names and deterministic ordering. Verification reports valid, missing, modified, unexpected, parent_status, manifest_version, and path_mode. Diff reports equivalent, added, removed, modified, unchanged_count, metadata_changed, and path_mode. An input error emits a JSON object with error and valid=false when --json is selected.

## Private path identifiers

Ordinary manifests expose relative filenames, sizes, and content hashes. Filenames and hashes can be sensitive metadata. Redacted mode replaces each normalized relative path with an HMAC-SHA256 path identifier. Keep a high-entropy secret in an environment variable; do not put it in a command argument, manifest, or repository. Use the same key to verify and compare redacted seals.

~~~sh
# Supply ARTIFACT_AUDIT_PATH_KEY through your shell or secret manager first.
artifact-audit seal ./private-output --output private-seal.json --redact-paths
artifact-audit verify ./private-output --manifest private-seal.json --json
~~~

The default variable name is ARTIFACT_AUDIT_PATH_KEY. Use --path-key-env NAME on seal or verify if your workflow uses another variable. The key must be at least 16 UTF-8 bytes; a random 32-byte or stronger value is recommended. The manifest includes a deterministic HMAC key check so a wrong key fails safely even for an empty folder. That check also lets an attacker test guesses offline if the key is weak. Redaction hides raw paths, not file sizes, content hashes, producer labels, or the existence and count of files. SHA-256 hashes are not encryption. Read [SECURITY.md](https://github.com/xocnarfnal/artifact-audit/blob/main/SECURITY.md) before sharing manifests.

## GitHub Action

Another repository can verify an artifact directory using the root composite action. This is a step excerpt; see the [complete cross-job handoff workflow](https://github.com/xocnarfnal/artifact-audit/blob/main/.github/examples/verify-handoff.yml) for a copyable example:

~~~yaml
steps:
  - uses: actions/checkout@v7
  - uses: xocnarfnal/artifact-audit@v0.2.1
    with:
      path: ./output
      manifest: ./seal.json
~~~

For a redacted seal, supply the key as a step environment variable from a repository secret:

~~~yaml
  - uses: xocnarfnal/artifact-audit@v0.2.1
    with:
      path: ./output
      manifest: ./private-seal.json
    env:
      ARTIFACT_AUDIT_PATH_KEY: ${{ secrets.ARTIFACT_AUDIT_PATH_KEY }}
~~~

The action installs Artifact Audit from its tagged source and runs verify with JSON output. It needs only the directory and manifest; it does not send artifact files to Artifact Audit or a remote service. Pip installation itself contacts package infrastructure for build requirements. Never publish a sensitive manifest blindly. The `path-key-env` input optionally names a different key environment variable; it never accepts a key value.

## Compatibility and exit codes

The 0.1.x commands remain available:

~~~sh
artifact-audit generate ./output --output legacy.json
artifact-audit verify ./output --manifest legacy.json
~~~

Generate continues writing the v1 shape and its existing pretty JSON output. Verify accepts both v1 and v2; seal writes v2. V1 manifests have no parent link, privacy mode, or payload digest. V1 backslash paths are normalized for Windows/POSIX comparison. New v2 paths use forward slashes.

| Code | Meaning |
| --- | --- |
| 0 | Verification passed, or diff found equivalent artifacts and handoff metadata. |
| 1 | File drift or a missing/mismatched parent; diff found file or handoff metadata drift. |
| 2 | Missing/malformed input, invalid payload or parent, missing/wrong privacy key, incompatible diff modes, or file operation error. |

Ordinary local generate, seal, verify, and diff operations make no network transmission. The program rejects symbolic links to avoid reading through them. Manifests are plain local files; keep them under the same access controls as the artifacts they describe.

## Development

Run synthetic tests with:

~~~sh
python -m unittest discover -s tests -v
~~~

CI covers Python 3.10, 3.11, 3.12, and 3.13 on Ubuntu, plus 3.12 on Windows. It also builds distributions, checks package metadata, runs the synthetic demo, and smoke-tests the reusable action. See [CONTRIBUTING.md](https://github.com/xocnarfnal/artifact-audit/blob/main/CONTRIBUTING.md), [CHANGELOG.md](https://github.com/xocnarfnal/artifact-audit/blob/main/CHANGELOG.md), and [adoption measurement guidance](https://github.com/xocnarfnal/artifact-audit/blob/main/docs/ADOPTION.md).

Artifact Audit is released under the [MIT license](https://github.com/xocnarfnal/artifact-audit/blob/main/LICENSE).
