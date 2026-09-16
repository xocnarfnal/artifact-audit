import hashlib
import json
import os
import subprocess
import sys
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from artifact_audit import (
    AuditError,
    TOOL_VERSION,
    canonical_bytes,
    diff_manifests,
    generate_manifest,
    load_manifest,
    seal_manifest,
    verify_manifest,
    write_manifest,
)

KEY_ONE = b"synthetic-test-key-one-32-bytes!!"
KEY_TWO = b"synthetic-test-key-two-32-bytes!!"


def cli(*args, env=None):
    return subprocess.run([sys.executable, "-m", "artifact_audit", *map(str, args)],
                          capture_output=True, text=True, check=False, env=env)


class TestV2Seal(unittest.TestCase):
    def test_tool_version_matches_package_version(self):
        pyproject = (Path(__file__).parent.parent / "pyproject.toml").read_text(
            encoding="utf-8")
        package_version = next(
            line.split("=", 1)[1].strip().strip('"')
            for line in pyproject.splitlines()
            if line.startswith("version = ")
        )
        self.assertEqual(TOOL_VERSION, package_version)

    def test_canonical_bytes_and_repeatable_seal(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            (root / "b.txt").write_text("beta", encoding="utf-8")
            (root / "a.txt").write_text("alpha", encoding="utf-8")
            output = root / "artifact-manifest.json"
            first = seal_manifest(root, output, producer="synthetic-step")
            write_manifest(first, output)
            first_bytes = output.read_bytes()
            second = seal_manifest(root, output, producer="synthetic-step")
            write_manifest(second, output)
            self.assertEqual(output.read_bytes(), first_bytes)
            self.assertEqual(first, second)
            self.assertEqual(first_bytes, canonical_bytes(first))
            self.assertEqual([item["path"] for item in first["files"]], ["a.txt", "b.txt"])
            self.assertEqual(first["manifest_version"], 2)
            self.assertEqual(first["tool_version"], "0.2.2")
            self.assertNotIn("timestamp", first)
            self.assertNotIn("hostname", first)
            self.assertNotIn(str(root), first_bytes.decode("utf-8"))
            payload = {k: v for k, v in first.items() if k != "manifest_digest"}
            self.assertEqual(first["manifest_digest"],
                             hashlib.sha256(canonical_bytes(payload)).hexdigest())
            self.assertEqual(load_manifest(output), first)

    def test_empty_nested_unicode_and_path_separator(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            (root / "nested").mkdir(parents=True)
            output = Path(temp) / "seal.json"
            empty = seal_manifest(root, output)
            self.assertEqual(empty["files"], [])
            (root / "nested" / "café.txt").write_text("content", encoding="utf-8")
            seal = seal_manifest(root, output)
            self.assertEqual(seal["files"][0]["path"], "nested/café.txt")
            self.assertNotIn("\\", seal["files"][0]["path"])
            write_manifest(seal, output)
            self.assertTrue(verify_manifest(root, output)["valid"])

    def test_v2_added_removed_modified_and_json(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            (root / "keep.txt").write_text("old", encoding="utf-8")
            (root / "remove.txt").write_text("gone", encoding="utf-8")
            output = Path(temp) / "seal.json"
            write_manifest(seal_manifest(root, output), output)
            self.assertTrue(verify_manifest(root, output)["valid"])
            (root / "keep.txt").write_text("new", encoding="utf-8")
            (root / "remove.txt").unlink()
            (root / "add.txt").write_text("added", encoding="utf-8")
            report = verify_manifest(root, output)
            self.assertFalse(report["valid"])
            self.assertEqual(report["missing"], ["remove.txt"])
            self.assertEqual(report["modified"], ["keep.txt"])
            self.assertEqual(report["unexpected"], ["add.txt"])
            result = cli("verify", root, "--manifest", output, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout), report)
            self.assertEqual(result.stderr, "")

    def test_v1_generate_and_windows_style_manifest_path(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            (root / "nested").mkdir(parents=True)
            (root / "nested" / "file.txt").write_text("v1", encoding="utf-8")
            output = Path(temp) / "legacy.json"
            manifest = generate_manifest(root, output)
            self.assertEqual(manifest["manifest_version"], 1)
            write_manifest(manifest, output)
            self.assertTrue(verify_manifest(root, output)["valid"])
            manifest["files"][0]["path"] = "nested\\file.txt"
            write_manifest(manifest, output)
            self.assertTrue(verify_manifest(root, output)["valid"])
            self.assertEqual(cli("generate", root, "--output", output).returncode, 0)


class TestParentAndDiff(unittest.TestCase):
    def test_parent_match_missing_wrong_and_changed(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "bundle"
            root.mkdir()
            (root / "artifact.txt").write_text("handoff", encoding="utf-8")
            parent = base / "parent.json"
            wrong = base / "wrong.json"
            child = base / "child.json"
            write_manifest(generate_manifest(root, parent), parent)
            write_manifest(seal_manifest(root, child, parent=parent), child)
            self.assertEqual(verify_manifest(root, child, parent=parent)["parent_status"], "match")
            self.assertEqual(verify_manifest(root, child)["parent_status"], "missing")
            self.assertEqual(cli("verify", root, "--manifest", child, "--json").returncode, 1)
            write_manifest({"manifest_version": 1, "algorithm": "sha256", "files": []}, wrong)
            self.assertEqual(verify_manifest(root, child, parent=wrong)["parent_status"], "mismatch")
            parent.write_text(wrong.read_text(encoding="utf-8"), encoding="utf-8")
            self.assertEqual(verify_manifest(root, child, parent=parent)["parent_status"], "mismatch")
            parent.unlink()
            self.assertEqual(verify_manifest(root, child, parent=parent)["parent_status"], "missing")

    def test_parent_inside_bundle_is_excluded_and_broken_chain_errors(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            (root / "artifact.txt").write_text("handoff", encoding="utf-8")
            parent = root / "parent.json"
            child = root / "child.json"
            write_manifest(seal_manifest(root, parent), parent)
            manifest = seal_manifest(root, child, parent=parent)
            write_manifest(manifest, child)
            self.assertEqual([item["path"] for item in manifest["files"]], ["artifact.txt"])
            self.assertTrue(verify_manifest(root, child, parent=parent)["valid"])
            corrupted = json.loads(parent.read_text(encoding="utf-8"))
            corrupted["files"][0]["size"] += 1
            parent.write_text(json.dumps(corrupted), encoding="utf-8")
            result = cli("verify", root, "--manifest", child, "--parent", parent, "--json")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"], "invalid_manifest")
            self.assertNotIn(str(root), result.stdout)

    def test_diff_no_change_drift_metadata_and_v1_v2_equivalence(self):
        with TemporaryDirectory() as temp:
            base = Path(temp)
            root = base / "bundle"
            root.mkdir()
            (root / "stable.txt").write_text("stable", encoding="utf-8")
            (root / "remove.txt").write_text("remove", encoding="utf-8")
            old = base / "old.json"
            same = base / "same.json"
            new = base / "new.json"
            legacy = base / "legacy.json"
            write_manifest(seal_manifest(root, old), old)
            write_manifest(seal_manifest(root, same), same)
            write_manifest(generate_manifest(root, legacy), legacy)
            self.assertTrue(diff_manifests(old, same)["equivalent"])
            self.assertTrue(diff_manifests(legacy, old)["equivalent"])
            self.assertEqual(cli("diff", old, same, "--json").returncode, 0)
            (root / "remove.txt").unlink()
            (root / "stable.txt").write_text("modified", encoding="utf-8")
            (root / "added.txt").write_text("new", encoding="utf-8")
            write_manifest(seal_manifest(root, new), new)
            report = diff_manifests(old, new)
            self.assertFalse(report["equivalent"])
            self.assertEqual(report["added"], ["added.txt"])
            self.assertEqual(report["removed"], ["remove.txt"])
            self.assertEqual(report["modified"], ["stable.txt"])
            self.assertEqual(report["unchanged_count"], 0)
            result = cli("diff", old, new, "--json")
            self.assertEqual(result.returncode, 1)
            self.assertEqual(json.loads(result.stdout), report)
            write_manifest(seal_manifest(root, same, producer="synthetic-step"), same)
            self.assertEqual(diff_manifests(new, same)["metadata_changed"], ["producer"])

    def test_diff_incompatible_privacy_modes(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            (root / "artifact.txt").write_text("x", encoding="utf-8")
            raw = Path(temp) / "raw.json"
            redacted = Path(temp) / "redacted.json"
            write_manifest(seal_manifest(root, raw), raw)
            write_manifest(seal_manifest(root, redacted, redact_paths=True, path_key=KEY_ONE), redacted)
            result = cli("diff", raw, redacted, "--json")
            self.assertEqual(result.returncode, 2)
            self.assertEqual(json.loads(result.stdout)["error"], "incompatible_manifests")


class TestPrivacy(unittest.TestCase):
    def test_redaction_determinism_key_difference_and_verification(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            (root / "nested").mkdir(parents=True)
            (root / "nested" / "sensitive-name.txt").write_text("synthetic", encoding="utf-8")
            one = Path(temp) / "one.json"
            two = Path(temp) / "two.json"
            other = Path(temp) / "other.json"
            first = seal_manifest(root, one, redact_paths=True, path_key=KEY_ONE)
            write_manifest(first, one)
            second = seal_manifest(root, two, redact_paths=True, path_key=KEY_ONE)
            write_manifest(second, two)
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertNotIn("sensitive-name.txt", one.read_text(encoding="utf-8"))
            self.assertNotIn("nested", one.read_text(encoding="utf-8"))
            self.assertNotIn(KEY_ONE.decode("utf-8"), one.read_text(encoding="utf-8"))
            self.assertTrue(verify_manifest(root, one, path_key=KEY_ONE)["valid"])
            self.assertTrue(diff_manifests(one, two)["equivalent"])
            different = seal_manifest(root, other, redact_paths=True, path_key=KEY_TWO)
            write_manifest(different, other)
            self.assertNotEqual(first["files"][0]["path_id"], different["files"][0]["path_id"])
            with self.assertRaises(AuditError) as error:
                verify_manifest(root, one, path_key=KEY_TWO)
            self.assertEqual(error.exception.code, "wrong_path_key")
            with self.assertRaises(AuditError):
                diff_manifests(one, other)

    def test_cli_env_key_not_logged_and_missing_key_fails_on_empty_bundle(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            output = Path(temp) / "redacted.json"
            env = os.environ.copy()
            env["ARTIFACT_AUDIT_PATH_KEY"] = KEY_ONE.decode("utf-8")
            seal = cli("seal", root, "--output", output, "--redact-paths", env=env)
            self.assertEqual(seal.returncode, 0)
            self.assertNotIn(env["ARTIFACT_AUDIT_PATH_KEY"], seal.stdout + seal.stderr)
            self.assertNotIn(str(root), seal.stdout + seal.stderr)
            verify = cli("verify", root, "--manifest", output, "--json", env=env)
            self.assertEqual(verify.returncode, 0)
            env["ARTIFACT_AUDIT_PATH_KEY"] = KEY_TWO.decode("utf-8")
            wrong = cli("verify", root, "--manifest", output, "--json", env=env)
            self.assertEqual(wrong.returncode, 2)
            self.assertEqual(json.loads(wrong.stdout)["error"], "wrong_path_key")
            env.pop("ARTIFACT_AUDIT_PATH_KEY")
            missing = cli("verify", root, "--manifest", output, "--json", env=env)
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(json.loads(missing.stdout)["error"], "missing_path_key")


class TestInvalidInputs(unittest.TestCase):
    def test_root_action_uses_environment_for_user_inputs(self):
        action = (Path(__file__).parent.parent / "action.yml").read_text(encoding="utf-8")
        self.assertIn("using: composite", action)
        self.assertIn("AUDIT_PATH: ${{ inputs.path }}", action)
        self.assertIn("AUDIT_MANIFEST: ${{ inputs.manifest }}", action)
        self.assertIn('verify "$AUDIT_PATH" --manifest "$AUDIT_MANIFEST"', action)
        self.assertNotIn("path-key:\n", action)

    def test_missing_malformed_duplicate_unsafe_and_tampered_manifests(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            root.mkdir()
            output = Path(temp) / "seal.json"
            missing = cli("verify", root, "--manifest", output, "--json")
            self.assertEqual(missing.returncode, 2)
            self.assertEqual(json.loads(missing.stdout)["error"], "missing_manifest")
            output.write_text("{broken", encoding="utf-8")
            self.assertEqual(cli("verify", root, "--manifest", output).returncode, 2)
            output.write_text('{"manifest_version":1,"manifest_version":1}', encoding="utf-8")
            self.assertEqual(json.loads(cli("verify", root, "--manifest", output,
                                           "--json").stdout)["error"], "invalid_manifest")
            output.write_text('{"manifest_version":2,"algorithm":"sha256","files":NaN}',
                              encoding="utf-8")
            self.assertEqual(cli("verify", root, "--manifest", output, "--json").returncode, 2)
            output.write_text(
                '{"manifest_version":2,"tool":"artifact-audit","tool_version":"0.2.0",'
                '"algorithm":"sha256","path_mode":"relative","files":[],'
                '"producer":"\\ud800","manifest_digest":"' + '0' * 64 + '"}',
                encoding="utf-8")
            self.assertEqual(cli("verify", root, "--manifest", output, "--json").returncode, 2)
            write_manifest({"manifest_version": 1, "algorithm": "sha256",
                            "files": [{"path": "../outside.txt",
                                       "sha256": "0" * 64, "size": 0}]}, output)
            self.assertEqual(cli("verify", root, "--manifest", output).returncode, 2)
            (root / "file.txt").write_text("safe", encoding="utf-8")
            seal = seal_manifest(root, output)
            write_manifest(seal, output)
            damaged = json.loads(output.read_text(encoding="utf-8"))
            damaged["files"][0]["size"] += 1
            output.write_text(json.dumps(damaged), encoding="utf-8")
            self.assertEqual(json.loads(cli("verify", root, "--manifest", output,
                                           "--json").stdout)["error"], "invalid_manifest")

    def test_missing_directory_invalid_producer_and_symlink(self):
        with TemporaryDirectory() as temp:
            root = Path(temp) / "bundle"
            output = Path(temp) / "seal.json"
            self.assertEqual(cli("seal", root, "--output", output).returncode, 2)
            root.mkdir()
            with self.assertRaises(AuditError):
                seal_manifest(root, output, producer="bad\nproducer")
            target = root / "target.txt"
            target.write_text("synthetic", encoding="utf-8")
            link = root / "link.txt"
            try:
                link.symlink_to(target)
            except (OSError, NotImplementedError):
                self.skipTest("symlink creation unavailable")
            with self.assertRaises(AuditError) as error:
                seal_manifest(root, output)
            self.assertEqual(error.exception.code, "unsupported_file")


if __name__ == "__main__":
    unittest.main()
