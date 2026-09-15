# Contributing

Artifact Audit is a small Python CLI. Keep changes deterministic and privacy-aware: avoid timestamps, machine-specific paths, credentials, and automatic network calls in ordinary local commands. Tests and examples must use synthetic temporary data. Never commit real manifests from personal or private files.

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

Describe behavior changes, compatibility effects, and privacy implications in the pull request. The repository uses the [MIT license](LICENSE).
