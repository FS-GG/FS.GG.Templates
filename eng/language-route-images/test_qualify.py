#!/usr/bin/env python3

import importlib.util
from pathlib import Path
import unittest


QUALIFIER = Path(__file__).with_name("qualify.py")
SPEC = importlib.util.spec_from_file_location("language_route_image_qualifier", QUALIFIER)
qualifier = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(qualifier)


class ImmutableIdentityTests(unittest.TestCase):
    DIGEST = "a" * 64

    def test_accepts_and_normalizes_podman_image_id_forms(self) -> None:
        expected = f"sha256:{self.DIGEST}"
        self.assertEqual(expected, qualifier.immutable_image_id(self.DIGEST))
        self.assertEqual(expected, qualifier.immutable_image_id(expected))

    def test_accepts_only_prefixed_full_digest(self) -> None:
        expected = f"sha256:{self.DIGEST}"
        self.assertEqual(expected, qualifier.immutable_digest(expected))
        with self.assertRaises(RuntimeError):
            qualifier.immutable_digest(self.DIGEST)

    def test_rejects_nonimmutable_or_noncanonical_identifiers(self) -> None:
        rejected = (
            None,
            "latest",
            "localhost/example:latest",
            "a" * 63,
            "a" * 65,
            "A" * 64,
            " sha256:" + self.DIGEST,
            "sha256:" + self.DIGEST + " ",
            "sha512:" + self.DIGEST,
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    qualifier.immutable_image_id(value)

    def test_rejects_noncanonical_digests(self) -> None:
        rejected = (
            None,
            self.DIGEST,
            "sha256:" + "a" * 63,
            "sha256:" + "A" * 64,
            "sha512:" + self.DIGEST,
            "localhost/example@sha256:" + self.DIGEST,
        )
        for value in rejected:
            with self.subTest(value=value):
                with self.assertRaises(RuntimeError):
                    qualifier.immutable_digest(value)


class QualificationPlanTests(unittest.TestCase):
    def test_go_compiler_scratch_uses_scoped_executable_output(self) -> None:
        environment, commands = qualifier.qualification_plan("go")
        self.assertIn("TMPDIR=/output", environment)
        self.assertNotIn("TMPDIR=/tmp", environment)
        self.assertEqual([("verify-and-entrypoint", "/bin/bash", ["scripts/verify.sh"])], commands)

    def test_unknown_language_has_no_fallback_plan(self) -> None:
        with self.assertRaises(RuntimeError):
            qualifier.qualification_plan("unknown")


if __name__ == "__main__":
    unittest.main()
