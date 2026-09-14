import hashlib
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from artifact_audit import generate_manifest, write_manifest


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


if __name__ == "__main__":
    unittest.main()
