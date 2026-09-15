# Contributing

Artifact Audit is a small Python CLI. Python 3.10 or newer is required. Clone the public repository, create a virtual environment if you want one, then install the checkout in editable mode:

~~~sh
python -m pip install -e .
python examples/quick-demo/demo.py
~~~

Keep changes deterministic and privacy-aware: avoid timestamps, machine-specific paths, credentials, and automatic network calls in ordinary local commands. Tests and examples must use synthetic temporary data. Never commit real manifests from personal or private files.

Run the full suite before opening a pull request:

~~~sh
python -m unittest discover -s tests -v
~~~

For packaging changes, build both distributions and check their metadata:

~~~sh
python -m pip install build twine
python -m build
python -m twine check dist/*
~~~

Use a focused branch and open a pull request against `main`. Explain behavior changes, compatibility effects, and privacy implications; a short description is enough for documentation-only work. Feature ideas are welcome as a [feature request](https://github.com/xocnarfnal/artifact-audit/issues/new/choose) or a small proposed PR, especially with a concrete workflow and testable acceptance criteria.

Never paste secrets, path-redaction keys, private manifests, sensitive filenames, or real personal/project data into public issues, tests, or PRs. Use synthetic examples and sanitize error output before sharing. For vulnerabilities, use [private reporting](https://github.com/xocnarfnal/artifact-audit/security/advisories/new) where available. The repository uses the [MIT license](LICENSE).
