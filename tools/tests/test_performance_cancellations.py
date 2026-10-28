"""Independent, fixed-time proof fixtures for the narrow client-abort protocol."""
import copy
import json
import subprocess
import tempfile
import unittest
from pathlib import Path

MODULE = Path(__file__).parents[1] / "acceptance/performance/cancellations.mjs"
MISSION = "synthetic-mission-a"
BEFORE = json.dumps(["store", "epoch", "simulation", "ordinary-leg1"], separators=(",", ":"))
TARGET = json.dumps(["store", "epoch", "simulation", "ordinary-leg2"], separators=(",", ":"))


def fixture(active=True, page=0):
    api = []
    def request(identifier, path, start, end, page=page, **terminal):
        query = {"mission_id": MISSION} if path.endswith(("events", "records")) else {}
        url = "http://fixture" + path + ("?mission_id=" + MISSION if query else "")
        row = dict(event="start", id=identifier, page=page, path=path, method="GET", url=url, query=query,
                   at=start, startedPhase="measured", resourceType="xhr", wallStartTimeMs=start * 1000, sourceIdentity=None)
        api.extend([row, dict(row, event="terminal", at=end, wallTimeMs=end * 1000,
                             status=200, outcome="success", **terminal)])
        return row
    canceled = request("cancel", "/api/v2/operator/events", 99.8, 100.2)
    api[-1].update(status=None, outcome="client_cancellation", errorText="net::ERR_ABORTED", cancellationCause="unknown", wallStartTimeSource="cdp")
    target = TARGET if active else json.dumps(["store", "epoch", "simulation", "idle:default"], separators=(",", ":"))
    context = dict(missionId=MISSION if active else None, operatingContextId="ordinary-leg2" if active else None)
    for p in {page, 1}:
        request(f"health-{p}", "/api/v2/operator/health", 100.21, 100.4, page=p, healthIdentity=target)
        request(f"context-{p}", "/api/v2/operator/context", 100.3, 100.5, page=p, context=context)
    if active:
        request("fresh-events", "/api/v2/operator/events", 100.3, 100.6, eventSource=dict(identity=target, missionId=MISSION))
        request("operator-records", "/api/v2/operator/records", 100.3, 100.7, page=1, responseSourceIdentity=target)
    operation = 0 if active else 1
    control = "/api/v2/missions/synthetic-mission-a/" + ("legs/synthetic-leg-2/activate" if active else "legs/deactivate")
    markers = [dict(stage="transition-begin", transition_id=f"transition-{operation}", operation=operation,
                    clock_seconds=100, wall_time_ms=100000, mission_id=MISSION, before_identity=BEFORE, records_active_after=active),
               dict(stage="transition-confirmed", transition_id=f"transition-{operation}", operation=operation,
                    clock_seconds=101, wall_time_ms=101000, mission_id=MISSION, target_identity=target,
                    records_active_after=active, control_path=control, control_result=dict(ok=True, status=200))]
    aborts = [dict(id="abort-0", page=page, method="GET", url=canceled["url"], sendWallTimeMs=99800,
                   abortWallTimeMs=100150, at=100.15, mechanism="xhr.abort")]
    return api, aborts, markers


class CancellationQualificationTests(unittest.TestCase):
    def qualify(self, data=None, oversized=None):
        with tempfile.TemporaryDirectory(prefix="issue393-cancel-test-") as folder:
            paths = {}
            for name, rows in zip(("api", "abort", "transition"), data or fixture()):
                path = Path(folder) / (name + ".jsonl")
                path.write_text("".join(json.dumps(row) + "\n" for row in rows))
                paths[name + "Path"] = str(path)
            if oversized == "line":
                Path(paths["abortPath"]).write_text("x" * (256 * 1024 + 1))
            if oversized == "file":
                with Path(paths["abortPath"]).open("wb") as stream:
                    stream.truncate(128 * 1024 * 1024 + 1)
            program = "const {qualifyCancellations}=await import(process.argv[1]); console.log(JSON.stringify(await qualifyCancellations(JSON.parse(process.argv[2]))));"
            result = subprocess.run(["node", "--input-type=module", "--eval", program, MODULE.resolve().as_uri(), json.dumps(paths)], capture_output=True, text=True, timeout=10)
            self.assertEqual(result.returncode, 0, result.stderr)
            return json.loads(result.stdout)

    def test_only_actual_abort_and_all_scope_recovery_proofs_qualify(self):
        for active in (True, False):
            for page in (0, 1):
                with self.subTest(active=active, page=page):
                    data = fixture(active, page)
                    result = self.qualify(data)
                    self.assertTrue(result["clean"], result)
                    expected = result["expected"][0]
                    self.assertEqual((expected["request_id"], expected["abort_id"], expected["page"]), ("cancel", "abort-0", page))
                    self.assertEqual(data[0][1]["cancellationCause"], "unknown")
                    self.assertEqual(len(result["source_sha256"]), 64)
                    self.assertEqual(set(result["input_sha256"]), {"api", "abort", "transition"})
                    self.assertTrue(expected["recovery_ids"]["operator_health"])

    def test_negative_proof_variants_remain_unexpected(self):
        mutations = {
            "no_actual_abort": lambda a,b,t: b.clear(),
            "wrong_scope": lambda a,b,t: a[0]["query"].update(mission_id="other"),
            "terminal_wrong_scope": lambda a,b,t: a[1].update(query={"mission_id":"other"}),
            "wrong_phase": lambda a,b,t: a[0].update(startedPhase="warmup"),
            "wrong_method": lambda a,b,t: a[0].update(method="POST"),
            "wrong_path": lambda a,b,t: a[0].update(path="/api/status"),
            "wrong_resource": lambda a,b,t: a[0].update(resourceType="fetch"),
            "wrong_error": lambda a,b,t: a[1].update(errorText="net::ERR_FAILED"),
            "wrong_abort_mechanism": lambda a,b,t: b[0].update(mechanism="assumed"),
            "ambiguous_abort": lambda a,b,t: b.append(dict(b[0], id="abort-other")),
            "late_abort_send": lambda a,b,t: b[0].update(sendWallTimeMs=99000),
            "early_abort": lambda a,b,t: b[0].update(abortWallTimeMs=99000),
            "abort_after_terminal": lambda a,b,t: b[0].update(abortWallTimeMs=100301),
            "abort_outside_transition": lambda a,b,t: b[0].update(at=111),
            "wrong_prior_source": lambda a,b,t: a[0].update(sourceIdentity=TARGET),
            "late_terminal": lambda a,b,t: a[1].update(at=111),
            "late_terminal_wall": lambda a,b,t: a[1].update(wallTimeMs=111000),
            "early_start": lambda a,b,t: a[0].update(at=97),
            "changed_store": lambda a,b,t: t[1].update(target_identity='["other","epoch","simulation","new"]'),
            "unchanged_source": lambda a,b,t: t[1].update(target_identity=BEFORE),
            "wrong_mission_marker": lambda a,b,t: t[0].update(mission_id="other"),
            "failed_control": lambda a,b,t: t[1].update(control_result={"ok":False,"status":500}),
            "wrong_control": lambda a,b,t: t[1].update(control_path="/anything"),
            "missing_confirmation": lambda a,b,t: t.pop(),
            "duplicate_marker": lambda a,b,t: t.append(copy.deepcopy(t[0])),
            "duplicate_abort_id": lambda a,b,t: b.append(copy.deepcopy(b[0])),
            "no_recovery": lambda a,b,t: a.__delitem__(slice(2,None)),
            "old_recovery_source": lambda a,b,t: a[-3].update(eventSource={"identity":BEFORE,"missionId":MISSION}),
            "old_request_new_response": lambda a,b,t: a[-4].update(at=100.1),
            "failed_recovery": lambda a,b,t: a[-3].update(status=503),
            "operator_records_wrong_source": lambda a,b,t: a[-1].update(responseSourceIdentity=BEFORE),
            "overview_stale_context_same_mission": lambda a,b,t: a[5].update(context={"missionId":MISSION,"operatingContextId":"ordinary-leg1"}),
            "operator_stale_context_same_mission": lambda a,b,t: a[9].update(context={"missionId":MISSION,"operatingContextId":"ordinary-leg1"}),
            "missing_terminal": lambda a,b,t: a.pop(),
            "duplicate_terminal": lambda a,b,t: a.append(copy.deepcopy(a[1])),
            "duplicate_start": lambda a,b,t: a.append(copy.deepcopy(a[0])),
            "unknown_terminal": lambda a,b,t: a.append(dict(a[1], id="unknown")),
        }
        for name, change in mutations.items():
            with self.subTest(name=name):
                data = fixture()
                change(*data)
                result = self.qualify(data)
                self.assertFalse(result["clean"], result)
                self.assertTrue(result["unexpected"], result)

    def test_preheader_abort_uses_positive_terminal_cdp_start_not_initial_zero(self):
        data = fixture()
        data[0][0]["wallStartTimeMs"] = 0
        result = self.qualify(data)
        self.assertTrue(result["clean"], result)
        self.assertEqual(result["expected"][0]["proof"]["request_wall_start_time_ms"], 99800)
        for terminal_start, source in ((0,"cdp"), (None,"cdp"), (99800,None), (99800,"playwright.timing.startTime"), (99800,"Date.now")):
            with self.subTest(terminal_start=terminal_start, source=source):
                data = fixture()
                data[0][1].update(wallStartTimeMs=terminal_start, wallStartTimeSource=source)
                self.assertFalse(self.qualify(data)["clean"])

    def test_no_cancellations_is_clean_only_with_complete_streams(self):
        api, _, _ = fixture()
        api = api[2:]
        self.assertTrue(self.qualify((api, [], []))["clean"])
        self.assertFalse(self.qualify((api[:-1], [], []))["clean"])

    def test_two_cancellations_for_same_page_transition_cannot_qualify(self):
        api, aborts, transitions = fixture()
        api.extend([dict(api[0], id="cancel-other", at=100.05, wallStartTimeMs=100050),
                    dict(api[1], id="cancel-other", at=100.25, wallStartTimeMs=100050, wallTimeMs=100250)])
        aborts.append(dict(aborts[0], id="abort-other", sendWallTimeMs=100050, abortWallTimeMs=100240, at=100.24))
        result = self.qualify((api, aborts, transitions))
        self.assertFalse(result["clean"])
        self.assertTrue(any("per page/transition" in item["reason"] for item in result["unexpected"]), result)

    def test_one_abort_cannot_be_reused_for_two_matching_cancellations(self):
        api, aborts, transitions = fixture()
        api.extend([dict(api[0], id="cancel-other"), dict(api[1], id="cancel-other")])
        result = self.qualify((api, aborts, transitions))
        self.assertFalse(result["clean"])
        self.assertTrue(any("qualify two" in item["reason"] for item in result["unexpected"]), result)

    def test_input_file_and_line_bounds_fail_closed(self):
        for bound in ("line", "file"):
            with self.subTest(bound=bound):
                result = self.qualify(oversized=bound)
                self.assertFalse(result["clean"])
                self.assertTrue(result["unexpected"])
