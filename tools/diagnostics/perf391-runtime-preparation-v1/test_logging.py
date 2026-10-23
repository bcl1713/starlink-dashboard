"""Offline regression for the diagnostic local-driver compression default."""

import unittest

from prepare import compose


class DiagnosticLoggingTests(unittest.TestCase):
    def test_single_file_logging_explicitly_disables_compression(self):
        for role in ("A", "C"):
            _, override = compose(role)
            for name, service in override["services"].items():
                with self.subTest(role=role, service=name):
                    self.assertEqual(
                        service["logging"],
                        {
                            "driver": "local",
                            "options": {
                                "max-size": "10m",
                                "max-file": "1",
                                "compress": "false",
                            },
                        },
                    )


if __name__ == "__main__":
    unittest.main(verbosity=2)
