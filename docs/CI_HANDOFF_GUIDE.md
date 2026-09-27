# Detect artifact drift between GitHub Actions jobs with a deterministic seal

Generated build output often crosses more than one workflow boundary:

```text
build job -> uploaded artifact -> review/test/deploy job
```

The second job usually assumes that the files it receives are the same files the first job produced. That assumption is easy to make and surprisingly awkward to verify once the bundle contains more than one file.

This guide shows a small pattern for GitHub Actions:

1. produce a folder;
2. seal it into a deterministic manifest;
3. hand off the folder and manifest together;
4. verify the folder in another job;
5. fail the workflow if a file is missing, modified, or unexpectedly added.

The example uses [Artifact Audit](https://github.com/xocnarfnal/artifact-audit), an MIT-licensed CLI and GitHub Action. The same pattern also works as a design idea if you prefer to build equivalent checks yourself.

## The problem

Suppose a build job produces:

```text
handoff/bundle/
  result.txt
  metadata.json
  reports/summary.txt
```

You can hash each file manually, but then you also need to answer a few other questions:

- Was an expected file removed?
- Did an unexpected file appear?
- Did a file change without changing its name?
- Can another job verify the entire bundle with one command?
- Can CI distinguish artifact drift from malformed input?
- Can the result be consumed as JSON?

A bundle manifest makes that easier.

Artifact Audit stores relative paths, SHA-256 hashes, and file sizes in deterministic JSON. Repeated sealing of unchanged input with the same options and tool version produces identical output.

## Step 1: produce and seal the bundle

In the producer job, install the CLI and create a seal:

```yaml
jobs:
  seal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: Produce and seal output
        shell: bash
        run: |
          mkdir -p handoff/bundle
          printf 'synthetic build output\n' > handoff/bundle/result.txt

          python -m pip install artifact-audit==0.2.2

          artifact-audit seal             handoff/bundle             --output handoff/seal.json
```

The seal is kept outside the bundle being sealed.

## Step 2: upload the bundle and seal together

Use the normal GitHub artifact handoff:

```yaml
      - name: Upload sealed handoff
        uses: actions/upload-artifact@v4
        with:
          name: sealed-handoff
          path: handoff/
```

Artifact Audit is not an artifact hosting service. In this example, GitHub stores the uploaded workflow artifact; Artifact Audit only creates and verifies the manifest.

## Step 3: verify in the receiving job

The receiving job downloads the handoff and verifies it using the public GitHub Action:

```yaml
  verify:
    needs: seal
    runs-on: ubuntu-latest
    steps:
      - name: Download sealed handoff
        uses: actions/download-artifact@v4
        with:
          name: sealed-handoff
          path: handoff/

      - name: Verify artifact handoff
        uses: xocnarfnal/artifact-audit@v0.2.2
        with:
          path: handoff/bundle
          manifest: handoff/seal.json
```

If the directory still matches the seal, verification exits successfully.

If a file was changed, deleted, or added, verification exits non-zero and reports the drift.

## Complete workflow

Here is the whole synthetic example:

```yaml
name: Verify an artifact handoff

on:
  workflow_dispatch:

permissions:
  contents: read

jobs:
  seal:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v7

      - uses: actions/setup-python@v7
        with:
          python-version: "3.12"

      - name: Produce and seal synthetic output
        shell: bash
        run: |
          mkdir -p handoff/bundle
          printf 'synthetic build output\n' > handoff/bundle/result.txt
          python -m pip install artifact-audit==0.2.2
          artifact-audit seal handoff/bundle --output handoff/seal.json

      - name: Upload bundle and seal together
        uses: actions/upload-artifact@v4
        with:
          name: sealed-handoff
          path: handoff/

  verify:
    needs: seal
    runs-on: ubuntu-latest
    steps:
      - name: Download sealed handoff
        uses: actions/download-artifact@v4
        with:
          name: sealed-handoff
          path: handoff/

      - name: Verify with Artifact Audit
        uses: xocnarfnal/artifact-audit@v0.2.2
        with:
          path: handoff/bundle
          manifest: handoff/seal.json
```

A copyable version lives in the repository at [`.github/examples/verify-handoff.yml`](https://github.com/xocnarfnal/artifact-audit/blob/main/.github/examples/verify-handoff.yml).

## What drift looks like

For a deliberately modified bundle, the CLI can report:

```text
Verification failed.
Modified:
  - report.txt
```

The tool distinguishes:

- missing files;
- modified files;
- unexpected files.

For automation, verification can also emit JSON.

Exit codes are:

| Exit code | Meaning |
| --- | --- |
| `0` | Verification passed |
| `1` | Artifact drift was detected |
| `2` | Invalid or malformed input / operational error |

That distinction matters in CI because "the files changed" is different from "the verifier could not interpret the manifest."

## A separate consumer test

The Action has also been exercised from a repository that is separate from the source repository:

[artifact-audit-consumer-example](https://github.com/xocnarfnal/artifact-audit-consumer-example)

That repository is maintainer-owned validation, not third-party adoption.

Its workflow does two things:

1. verifies a clean synthetic bundle;
2. deliberately changes a file and checks that the Action fails as expected while the overall test workflow remains green.

The merged-main validation run is public:

[Consumer validation workflow run](https://github.com/xocnarfnal/artifact-audit-consumer-example/actions/runs/35100485954)

This caught a real version-reporting bug in 0.2.1, which was fixed in 0.2.2. That is exactly the kind of defect a separate consumer test is useful for finding.

## Comparing two handoffs

Sometimes the useful question is not just "does this bundle match?" but "what changed between stage A and stage B?"

Artifact Audit can compare two seals:

```bash
artifact-audit diff build-seal.json review-seal.json
```

It reports added, removed, and modified records.

A child seal can also reference a parent seal by digest:

```bash
artifact-audit seal ./review-output   --output review-seal.json   --parent build-seal.json
```

That can be useful when you want an explicit chain between workflow stages.

## What about sensitive filenames?

Ordinary manifests contain relative paths, sizes, and hashes. Filenames themselves can be sensitive metadata.

Artifact Audit has an optional redacted-path mode that replaces raw relative paths with HMAC-SHA256 identifiers derived from a secret stored in an environment variable:

```bash
artifact-audit seal ./private-output   --output private-seal.json   --redact-paths
```

For GitHub Actions, the key can be supplied through a repository secret.

Redaction has limits:

- file sizes remain visible;
- content hashes remain visible;
- the number of files remains visible;
- a weak key can be guessed offline.

It is privacy reduction, not encryption.

## What this does not prove

A deterministic seal is useful for detecting drift against the supplied manifest. It does **not** prove who created the manifest.

If an attacker can replace both the artifact bundle and the manifest, they can recompute hashes.

So:

- protect the seal separately if hostile tampering is in scope;
- do not treat the manifest digest as a digital signature;
- use signing / attestation systems when producer identity or adversarial supply-chain security is the requirement.

The goal here is narrower: make ordinary CI handoffs explicit and reproducibly verifiable.

## When this pattern is useful

This is a reasonable fit when:

- one CI job generates a multi-file output bundle;
- another job, workflow, reviewer, or machine receives it;
- untracked/generated output is not naturally covered by Git history;
- you want CI to fail when files drift;
- you want a machine-readable explanation of what changed.

It is probably unnecessary if you only need to hash one static file.

## Try the demo

Two public examples are available:

- [30-second synthetic demo](https://github.com/xocnarfnal/artifact-audit/tree/main/examples/quick-demo)
- [separate consumer repository](https://github.com/xocnarfnal/artifact-audit-consumer-example)

Install the CLI:

```bash
python -m pip install artifact-audit
```

Or use the Marketplace Action:

```yaml
- uses: xocnarfnal/artifact-audit@v0.2.2
  with:
    path: ./output
    manifest: ./seal.json
```

Links:

- [GitHub repository](https://github.com/xocnarfnal/artifact-audit)
- [GitHub Marketplace](https://github.com/marketplace/actions/artifact-audit)
- [PyPI](https://pypi.org/project/artifact-audit/)

The project is still early. Feedback on whether this maps cleanly to real CI handoffs, especially where the interface is awkward, is more useful than a star.
