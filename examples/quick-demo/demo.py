"""Synthetic, cross-platform end-to-end handoff demo. Run from the repo root."""

import json
import subprocess
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]


def audit(*arguments: object, expected_code: int) -> str:
    result = subprocess.run(
        [sys.executable, "-m", "artifact_audit", *(str(arg) for arg in arguments)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != expected_code:
        raise RuntimeError(
            f"Expected exit {expected_code}, got {result.returncode}: {result.stderr or result.stdout}"
        )
    return result.stdout


def main() -> None:
    scratch = ROOT / "work"
    scratch.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="artifact-audit-demo-", dir=scratch) as directory:
        base = Path(directory)
        bundle = base / "bundle"
        bundle.mkdir()
        (bundle / "keep.txt").write_text("unchanged synthetic file\n", encoding="utf-8")
        (bundle / "remove.txt").write_text("synthetic file to remove\n", encoding="utf-8")
        (bundle / "modify.txt").write_text("synthetic first version\n", encoding="utf-8")
        original = base / "original-seal.json"
        changed = base / "changed-seal.json"

        audit("seal", bundle, "--output", original, expected_code=0)
        clean = json.loads(audit("verify", bundle, "--manifest", original, "--json", expected_code=0))
        assert clean["valid"] and not (clean["missing"] or clean["modified"] or clean["unexpected"])
        print("Seal -> verify: PASS (exit 0)")

        (bundle / "modify.txt").write_text("synthetic second version\n", encoding="utf-8")
        (bundle / "remove.txt").unlink()
        (bundle / "add.txt").write_text("synthetic added file\n", encoding="utf-8")
        drift = json.loads(audit("verify", bundle, "--manifest", original, "--json", expected_code=1))
        assert not drift["valid"]
        assert drift["missing"] == ["remove.txt"]
        assert drift["modified"] == ["modify.txt"]
        assert drift["unexpected"] == ["add.txt"]
        print("After edit/remove/add -> verify: FAIL (expected exit 1)")

        audit("seal", bundle, "--output", changed, expected_code=0)
        difference = json.loads(audit("diff", original, changed, "--json", expected_code=1))
        assert difference["added"] == ["add.txt"]
        assert difference["removed"] == ["remove.txt"]
        assert difference["modified"] == ["modify.txt"]
        print("Diff: added add.txt | removed remove.txt | modified modify.txt")
        print("Synthetic demo complete; temporary files removed.")


if __name__ == "__main__":
    main()
