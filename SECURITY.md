# Security and privacy

Artifact Audit runs locally. Ordinary generate, seal, verify, and diff operations do not upload files or transmit manifest content. Installation and GitHub Actions may use network services for package or action setup.

An ordinary manifest stores relative paths, file sizes, and SHA-256 content hashes. Filenames can reveal private metadata; file sizes and hashes can also identify known content. The optional producer label is user-supplied. Do not publish a manifest without reviewing what it reveals. No automatic timestamp, hostname, OS username, or absolute path is added to v2 seals.

Redacted mode uses HMAC-SHA256 over each forward-slash relative path with a secret supplied through an environment variable. The key is never stored in the manifest or printed by the CLI. Reuse the same key for verification and diff. Keep it high entropy, preferably at least 32 random bytes. A deterministic key check in the manifest allows wrong-key detection, including for empty bundles; it also enables offline guesses against weak keys. Redaction does not hide file sizes, hashes, file counts, or producer labels. A content hash is not encryption.

The v2 manifest payload digest checks for accidental mutation or corruption of the parsed manifest. The parent digest links a child to the canonical parent manifest. Neither is a digital signature. An adversary who can replace manifests can recompute their digests. v0.2.0 does not provide public-key signatures or authenticated provenance. A future signature feature can sign the existing canonical payload bytes without redefining file records.

Symbolic links are rejected so a sealed tree cannot silently read through them. Hard links and concurrent file mutation are not fully controlled; seal stable, trusted input directories for reproducible results. The CLI validates manifest record types, duplicate paths, unsafe relative paths, and v2 payload digests before comparison.

For a security issue, use the repository's [private vulnerability reporting](https://github.com/xocnarfnal/artifact-audit/security/advisories/new) when available. Avoid attaching real private artifacts to public issues.
