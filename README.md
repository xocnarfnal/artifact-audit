# Artifact Audit

Artifact Audit is an open-source project for verifying file integrity, generating reproducible manifests, and detecting unexpected artifact changes.

The goal is to provide a simple and deterministic way to audit files used in automated workflows, review pipelines, and reproducible research.

## Status

Early development.

## Planned Features

- Generate SHA-256 manifests for files and directories
- Verify files against an existing manifest
- Detect missing, modified, and unexpected files
- Produce machine-readable JSON audit reports
- Return CI-friendly exit codes
- Support reproducible and deterministic verification workflows

## Why Artifact Audit?

Automated workflows often depend on files produced across multiple stages. Small or unnoticed changes can make reviews difficult to reproduce.

Artifact Audit aims to make those changes explicit and independently verifiable.

## License

Open source. License information will be added shortly.
