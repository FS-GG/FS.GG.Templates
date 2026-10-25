"""Inert controls for the publication gate; synthetic archives only, no toolchain code is launched."""
import sys
sys.dont_write_bytecode = True
import importlib.util
import io
import json
from pathlib import Path
import tempfile
import unittest
import warnings
import zipfile

HERE = Path(__file__).resolve().parent
spec = importlib.util.spec_from_file_location("release_gate", HERE / "verify-release-qualification.py")
gate = importlib.util.module_from_spec(spec)
spec.loader.exec_module(gate)

NUSPEC = b'<package><metadata><repository type="git" url="u" commit="%s" /></metadata></package>'


def archive(directory, name, entries, commit="a" * 40, stamp=(2026, 10, 24, 23, 46, 0)):
    path = Path(directory) / name
    with zipfile.ZipFile(path, "w") as package:
        package.writestr(zipfile.ZipInfo("X.nuspec", stamp), NUSPEC % commit.encode())
        for entry, data in entries.items():
            package.writestr(zipfile.ZipInfo(entry, stamp), data)
    return path


class ReleaseGate(unittest.TestCase):
    def setUp(self):
        self.owned = tempfile.TemporaryDirectory(prefix="polyglot-gate-")
        self.addCleanup(self.owned.cleanup)
        self.dir = Path(self.owned.name)
        self.polyglot = {"content/templates/fs-gg-go-cli/main.go": b"package main", "README.md": b"r"}
    def register(self, accepted):
        path = self.dir / "register.json"
        path.write_text(json.dumps({"schema": gate.REGISTER_SCHEMA, "accepted": accepted}))
        return path
    def entry(self, identity):
        return {"payloadIdentitySha256": identity, "package": "FS.GG.Workspace.Template 0.20.0",
                "evidence": "https://github.com/FS-GG/FS.GG.Templates/issues/441#issuecomment-1",
                "acceptance": "https://github.com/FS-GG/FS.GG.Templates/issues/441#issuecomment-2"}
    def test_legacy_archive_keeps_existing_gates(self):
        legacy = archive(self.dir, "legacy.nupkg", {"content/templates/fs-gg-console/a": b"a"})
        self.assertEqual(gate.main([str(legacy)], self.register([])), 0)
    def test_polyglot_archive_without_acceptance_is_refused(self):
        package = archive(self.dir, "new.nupkg", self.polyglot)
        with self.assertRaisesRegex(ValueError, "no independently accepted"):
            gate.main([str(package)], self.register([]))
    def test_accepted_payload_passes_across_repacks_and_commits(self):
        first = archive(self.dir, "first.nupkg", self.polyglot, commit="a" * 40)
        repacked = archive(self.dir, "second.nupkg", self.polyglot, commit="b" * 40, stamp=(2026, 10, 25, 1, 2, 4))
        self.assertEqual(gate.payload_identity(first), gate.payload_identity(repacked))
        self.assertEqual(gate.main([str(repacked)], self.register([self.entry(gate.payload_identity(first))])), 0)
    def test_any_payload_byte_changes_the_identity(self):
        accepted = archive(self.dir, "a.nupkg", self.polyglot)
        drifted = archive(self.dir, "b.nupkg", dict(self.polyglot, **{"content/templates/fs-gg-go-cli/main.go": b"package main "}))
        with self.assertRaisesRegex(ValueError, "no independently accepted"):
            gate.main([str(drifted)], self.register([self.entry(gate.payload_identity(accepted))]))
    def test_an_added_entry_changes_the_identity(self):
        accepted = archive(self.dir, "a.nupkg", self.polyglot)
        extra = archive(self.dir, "b.nupkg", dict(self.polyglot, extra=b"x"))
        self.assertNotEqual(gate.payload_identity(accepted), gate.payload_identity(extra))
    def test_nuspec_metadata_other_than_commit_changes_the_identity(self):
        accepted = archive(self.dir, "a.nupkg", self.polyglot)
        path = self.dir / "c.nupkg"
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("X.nuspec", (NUSPEC % (b"a" * 40)).replace(b'url="u"', b'url="v"'))
            for name, data in self.polyglot.items():
                package.writestr(name, data)
        self.assertNotEqual(gate.payload_identity(accepted), gate.payload_identity(path))
    def test_malformed_registers_are_refused(self):
        valid = self.entry("a" * 64)
        for document in [
            '{"schema":"x","accepted":[]}',
            '{"schema":"%s","accepted":[],"extra":1}' % gate.REGISTER_SCHEMA,
            '{"schema":"%s","accepted":[],"accepted":[]}' % gate.REGISTER_SCHEMA,
            json.dumps({"schema": gate.REGISTER_SCHEMA, "accepted": [dict(valid, payloadIdentitySha256="A" * 64)]}),
            json.dumps({"schema": gate.REGISTER_SCHEMA, "accepted": [dict(valid, evidence="http://example.com/x")]}),
            json.dumps({"schema": gate.REGISTER_SCHEMA, "accepted": [valid, valid]}),
            json.dumps({"schema": gate.REGISTER_SCHEMA, "accepted": [dict(valid, extra=1)]}),
        ]:
            path = self.dir / "bad.json"
            path.write_text(document)
            with self.assertRaises(ValueError):
                gate.load_register(path)
    def test_duplicate_entries_are_refused(self):
        path = self.dir / "dup.nupkg"
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("X.nuspec", NUSPEC % (b"a" * 40))
            package.writestr("content/templates/fs-gg-go-cli/main.go", b"one")
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                package.writestr("content/templates/fs-gg-go-cli/main.go", b"two")
        with self.assertRaisesRegex(ValueError, "duplicate archive entries"):
            gate.payload_identity(path)
    def test_renamed_entry_changes_the_identity(self):
        first = archive(self.dir, "a.nupkg", {"content/templates/fs-gg-go-cli/main.go": b"x"})
        renamed = archive(self.dir, "b.nupkg", {"content/templates/fs-gg-go-cli/other.go": b"x"})
        self.assertNotEqual(gate.payload_identity(first), gate.payload_identity(renamed))
    def test_nested_nuspec_commit_is_not_blanked(self):
        nested = "content/templates/fs-gg-go-cli/inner.nuspec"
        first = archive(self.dir, "a.nupkg", dict(self.polyglot, **{nested: NUSPEC % (b"a" * 40)}))
        second = archive(self.dir, "b.nupkg", dict(self.polyglot, **{nested: NUSPEC % (b"b" * 40)}))
        self.assertNotEqual(gate.payload_identity(first), gate.payload_identity(second))
    def test_exactly_one_top_level_nuspec_is_required(self):
        path = self.dir / "none.nupkg"
        with zipfile.ZipFile(path, "w") as package:
            package.writestr("content/templates/fs-gg-go-cli/main.go", b"x")
        with self.assertRaisesRegex(ValueError, "exactly one top-level nuspec"):
            gate.payload_identity(path)
    def test_committed_register_is_well_formed(self):
        self.assertIsInstance(gate.load_register(), list)
    def test_one_archive_argument_is_required(self):
        with self.assertRaisesRegex(ValueError, "one immutable archive"):
            gate.main([])

if __name__ == "__main__":
    unittest.main()
