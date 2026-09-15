# Changelog

## 0.2.0

- Add deterministic v2 seals with sizes, SHA-256 hashes, optional producer, optional parent digest, and a canonical manifest payload digest.
- Add HMAC-SHA256 redacted path identifiers from an environment-provided key, with wrong-key detection.
- Add parent handoff verification, manifest diff, and stable JSON reports for verify and diff.
- Add a root GitHub Action for directory verification and expand CI across supported Python versions and Windows.
- Keep v1 generate output and v1 verification for 0.1.x compatibility.
- Document privacy limits, manifest integrity limits, and reproducible workflows.

## 0.1.1

- Existing deterministic v1 manifest generation and verification package release.
