"""Guard fixture boundaries before using these inputs in production acceptance."""

import unittest

from fixtures import build_workspace_fixture


class WorkspaceFixtureTest(unittest.TestCase):
    def test_reproducible_and_separate_identities(self):
        normal = build_workspace_fixture("normal")
        self.assertEqual(normal, build_workspace_fixture("normal"))
        busy = build_workspace_fixture("busy")
        self.assertNotEqual(normal["mission"]["id"], busy["mission"]["id"])
        self.assertEqual(len(normal["planned_commands"]), 1)
        self.assertEqual(len(busy["planned_commands"]), 5)
        self.assertEqual(len(busy["mission"]["legs"]), 2)

    def test_prerequisites_do_not_complete_operational_actions(self):
        for seed in ("normal", "busy"):
            fixture = build_workspace_fixture(seed)
            for command in fixture["planned_commands"]:
                self.assertEqual(command["record_type"], "call")
                self.assertEqual(command["payload"]["status"], "scheduled")
                self.assertIsNone(command["payload"]["conference_id"])
                self.assertIsNone(command["time"]["occurred_at"])
            self.assertNotIn("flight_phase", fixture)
            self.assertNotIn("expected_eta", fixture)
            self.assertNotIn("receipts", fixture)

    def test_rejects_unrecognized_scenarios(self):
        with self.assertRaises(ValueError):
            build_workspace_fixture("live")


if __name__ == "__main__":
    unittest.main()
