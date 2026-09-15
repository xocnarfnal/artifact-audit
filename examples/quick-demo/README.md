# Quick demo: seal, verify, detect drift

From the repository root with Python 3.10 or newer, run:

~~~sh
python examples/quick-demo/demo.py
~~~

The runner creates only synthetic text files in an ignored temporary `work/` directory. It seals the bundle, verifies a pass (exit 0), changes one file, removes another, adds a third, verifies the expected drift failure (exit 1), and diffs the old/new seals. It asserts each outcome and cleans up its files. No credentials, actual artifact data, or network access are needed; installation is not required from a checkout.

Expected output:

~~~text
Seal -> verify: PASS (exit 0)
After edit/remove/add -> verify: FAIL (expected exit 1)
Diff: added add.txt | removed remove.txt | modified modify.txt
Synthetic demo complete; temporary files removed.
~~~

To try path redaction separately, provide a high-entropy `ARTIFACT_AUDIT_PATH_KEY` through your shell or secret manager and run `artifact-audit seal ./bundle --output redacted-seal.json --redact-paths`. Never commit or paste a real key. See [privacy limits](../../SECURITY.md): path redaction does not hide file sizes, content hashes, or file counts.
