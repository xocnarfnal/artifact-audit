# Launch kit

These are drafts, not posts. Check each community's current rules and adjust the version/link after release before sharing. Share in relevant places only, once, and answer technical questions rather than asking for stars. No adoption or security claims are implied.

## Show HN

**Title:** Show HN: Artifact Audit – verify artifact handoffs and detect drift

**Body:** I built Artifact Audit, a small open-source Python CLI and GitHub Action for checking generated output bundles after a workflow handoff. It seals a folder into a deterministic JSON manifest, verifies the bundle later, and diffs two seals to show added, removed, and modified files. A child seal can refer to a parent seal by digest.

The optional redacted-path mode uses HMAC-derived identifiers instead of raw relative filenames. It still reveals file sizes, content hashes, and counts; neither the seal nor its parent link is a digital signature. The demo uses synthetic data and shows a pass, a deliberate fail, and a diff in under two minutes: [quick demo](https://github.com/xocnarfnal/artifact-audit/tree/main/examples/quick-demo). Code and Action: [repository](https://github.com/xocnarfnal/artifact-audit). I'd appreciate feedback on the handoff use case and where the interface is awkward.

## Reddit r/Python

**Title:** Artifact Audit: a small Python CLI for sealing and diffing output bundles

**Body:** I built a dependency-light Python tool for a specific problem: seal generated files, pass the folder and manifest to another job/reviewer, and detect missing, unexpected, or modified files. The manifest is deterministic JSON, and `diff` shows added/removed/modified records. There is an optional HMAC path-redaction mode, but sizes and hashes remain visible. This isn't a signature or a replacement for Git.

The [synthetic quick demo](https://github.com/xocnarfnal/artifact-audit/tree/main/examples/quick-demo) runs from a checkout on Python 3.10+. The [code and tests](https://github.com/xocnarfnal/artifact-audit) are MIT-licensed. If you've handled artifact handoffs in Python workflows, what would you want the CLI to report differently?

## Reddit DevOps / CI community

**Title:** A small GitHub Action to verify sealed artifacts across CI jobs

**Body:** Artifact Audit verifies a generated folder against a deterministic seal after a handoff. The root composite Action accepts `path` and `manifest`, installs the tagged Python source, runs `verify --json`, and exits nonzero on drift. There is a [complete synthetic two-job workflow](https://github.com/xocnarfnal/artifact-audit/blob/main/.github/examples/verify-handoff.yml) that uploads a bundle and seal together, then downloads and verifies them.

It reports missing/modified/unexpected files and supports redacted path identifiers if the key is provided through an environment secret. It does not upload your files to an Artifact Audit service or add telemetry. The manifest isn't authenticated, so protect it if a hostile actor could replace it. [Repository](https://github.com/xocnarfnal/artifact-audit). I'd value feedback on whether the job handoff example maps to your CI setup.

## GitHub social / short description

Artifact Audit is a local CLI and GitHub Action for sealing generated bundles and detecting drift after a workflow handoff. Deterministic JSON, added/removed/modified diffs, optional HMAC path identifiers, no telemetry. Synthetic demo: https://github.com/xocnarfnal/artifact-audit/tree/main/examples/quick-demo — feedback welcome.

## One-paragraph project description

Artifact Audit seals generated output folders into deterministic JSON manifests, verifies them after a workflow or review handoff, and compares two seals to identify added, removed, and modified artifacts. It supports parent handoff links, stable machine-readable reports and CI exit codes, a root GitHub Action, and optional HMAC-derived path identifiers that avoid raw filenames while leaving sizes and hashes visible. It runs locally without telemetry; manifests are not signatures or proof of authorship. A synthetic end-to-end demo is in the repository.

## Up to 280 characters

Seal a folder, hand it to another CI job, and detect added, missing, or modified files. Artifact Audit has deterministic JSON, an Action, and optional redacted paths (sizes/hashes stay visible). No telemetry. Demo: https://github.com/xocnarfnal/artifact-audit
