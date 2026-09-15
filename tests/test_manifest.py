import hashlib
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from artifact_audit import (
    generate_manifest,
    verify_manifest,
    write_manifest,
)


class TestManifestGeneration(unittest.TestCase):
    def test_manifest_is_deterministic(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "b.txt").write_text("beta", encoding="utf-8")
            (root / "a.txt").write_text("alpha", encoding="utf-8")

            output = root / "artifact-manifest.json"

            first = generate_manifest(root, output)
            write_manifest(first, output)

            second = generate_manifest(root, output)

            self.assertEqual(first, second)

    def test_files_are_sorted_and_hashed(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "b.txt").write_text("beta", encoding="utf-8")
            (root / "a.txt").write_text("alpha", encoding="utf-8")

            output = root / "artifact-manifest.json"
            manifest = generate_manifest(root, output)

            self.assertEqual(
                [item["path"] for item in manifest["files"]],
                ["a.txt", "b.txt"],
            )

            expected_hash = hashlib.sha256(b"alpha").hexdigest()

            self.assertEqual(
                manifest["files"][0]["sha256"],
                expected_hash,
            )

    def test_output_manifest_is_excluded(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "data.txt").write_text("example", encoding="utf-8")

            output = root / "artifact-manifest.json"
            output.write_text("old manifest", encoding="utf-8")

            manifest = generate_manifest(root, output)

            paths = [item["path"] for item in manifest["files"]]

            self.assertNotIn("artifact-manifest.json", paths)


class TestManifestVerification(unittest.TestCase):
    def create_manifest(self, root: Path) -> Path:
        output = root / "artifact-manifest.json"
        manifest = generate_manifest(root, output)
        write_manifest(manifest, output)
        return output

    def test_verification_passes_when_files_match(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "data.txt").write_text("original", encoding="utf-8")
            output = self.create_manifest(root)

            result = verify_manifest(root, output)

            self.assertTrue(result["valid"])
            self.assertEqual(result["missing"], [])
            self.assertEqual(result["modified"], [])
            self.assertEqual(result["unexpected"], [])

    def test_verification_detects_modified_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            file_path = root / "data.txt"
            file_path.write_text("original", encoding="utf-8")

            output = self.create_manifest(root)

            file_path.write_text("changed", encoding="utf-8")

            result = verify_manifest(root, output)

            self.assertFalse(result["valid"])
            self.assertEqual(result["modified"], ["data.txt"])

    def test_verification_detects_missing_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            file_path = root / "data.txt"
            file_path.write_text("original", encoding="utf-8")

            output = self.create_manifest(root)

            file_path.unlink()

            result = verify_manifest(root, output)

            self.assertFalse(result["valid"])
            self.assertEqual(result["missing"], ["data.txt"])

    def test_verification_detects_unexpected_file(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            (root / "data.txt").write_text("original", encoding="utf-8")

            output = self.create_manifest(root)

            (root / "extra.txt").write_text("unexpected", encoding="utf-8")

            result = verify_manifest(root, output)

            self.assertFalse(result["valid"])
            self.assertEqual(result["unexpected"], ["extra.txt"])

    def test_cli_returns_exit_code_one_on_failure(self):
        with TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)

            file_path = root / "data.txt"
            file_path.write_text("original", encoding="utf-8")

            output = self.create_manifest(root)

            file_path.write_text("changed", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "artifact_audit",
                    "verify",
                    str(root),
                    "--manifest",
                    str(output),
                ],
                capture_output=True,
                text=True,
                check=False,
            )

            self.assertEqual(completed.returncode, 1)
            self.assertIn("Verification failed.", completed.stdout)


if __name__ == "__main__":
    unittest.main()
