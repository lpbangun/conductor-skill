#!/usr/bin/env python3
"""Regression tests for Conductor mission-contract validation."""
from __future__ import annotations

import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
spec = importlib.util.spec_from_file_location("validate_mission", ROOT / "scripts" / "validate_mission.py")
validator = importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(validator)


class MissionContractTests(unittest.TestCase):
    def setUp(self) -> None:
        self.doc = json.loads((ROOT / "templates" / "mission.json").read_text())

    def validate(self, *, approved: bool = False, active: bool = False) -> None:
        validator.validate(self.doc, require_approved=approved, require_active=active)

    def make_executable(self, repo: str) -> None:
        self.doc["mission"]["name"] = "Contract fixture"
        self.doc["mission"]["objective"] = "Verify a bounded conductor contract"
        self.doc["mission"]["repo"] = repo
        self.doc["mission"]["status"] = "approved"
        self.doc["mission"]["integrationBranch"] = "main"
        self.doc["mission"]["milestone"] = "fixture-acceptance"
        self.doc["mission"]["inScope"] = ["Mission validation"]
        self.doc["mission"]["outOfScope"] = ["Product code mutation"]
        self.doc["mission"]["acceptance"] = ["Validation matrix passes"]
        self.doc["authority"]["approvedBy"] = "user"
        self.doc["authority"]["approvedAt"] = "2026-07-25T00:00:00Z"
        self.doc["gates"]["focusedTests"] = ["python3 -m unittest"]
        self.doc["gates"]["broadTests"] = ["python3 -m compileall ."]

    def test_draft_template_is_structurally_valid(self):
        self.validate()

    def test_approved_gate_does_not_require_ledger_id(self):
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            self.doc["mission"]["objective"] = "Replace the cache layer with Redis"
            self.validate(approved=True)

    def test_active_gate_requires_real_ledger_id(self):
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            self.doc["mission"]["status"] = "active"
            with self.assertRaisesRegex(ValueError, "ledger.missionId"):
                self.validate(active=True)
            self.doc["ledger"]["missionId"] = "todo"
            with self.assertRaisesRegex(ValueError, "placeholder"):
                self.validate(active=True)
            self.doc["ledger"]["missionId"] = "fixture-123"
            self.validate(active=True)

    def test_approved_gate_rejects_missing_repo_and_placeholders(self):
        self.doc["mission"]["status"] = "approved"
        self.doc["authority"]["approvedBy"] = "user"
        self.doc["authority"]["approvedAt"] = "2026-07-25T00:00:00Z"
        with self.assertRaisesRegex(ValueError, "existing directory"):
            self.validate(approved=True)
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            self.doc["mission"]["name"] = "REPLACE: mission name"
            with self.assertRaisesRegex(ValueError, "placeholder text"):
                self.validate(approved=True)
            self.doc["mission"]["name"] = "Real mission"
            self.doc["gates"]["focusedTests"] = ["REPLACE: focused test command"]
            with self.assertRaisesRegex(ValueError, "placeholder command"):
                self.validate(approved=True)

    def test_enabled_dashboard_must_exist_for_approved_mission(self):
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            self.doc["dashboard"]["enabled"] = True
            self.doc["dashboard"]["path"] = str(Path(repo) / "missing-dashboard")
            with self.assertRaisesRegex(ValueError, "dashboard.path"):
                self.validate(approved=True)

    def test_count_budgets_reject_fractional_values(self):
        self.doc["budgets"]["maxWorkers"] = 2.5
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            self.validate()

    def test_max_full_suites_allows_extended_serial_gate_budget(self):
        self.doc["budgets"]["maxFullSuites"] = 8
        self.validate()
        self.doc["budgets"]["maxFullSuites"] = 101
        with self.assertRaisesRegex(ValueError, "maxFullSuites"):
            self.validate()

    # --- Workload-aware + pressure-aware resource admission budgets ---

    def test_template_has_no_max_swap_used_percent(self):
        self.assertNotIn("maxSwapUsedPercent", self.doc["budgets"])

    def test_template_has_workload_aware_pressure_defaults(self):
        budgets = self.doc["budgets"]
        self.assertEqual(budgets["maxWorkers"], 5)
        self.assertEqual(budgets["maxWeightedSlots"], 4.0)
        self.assertEqual(budgets["minAvailableRamGb"], 2)
        self.assertEqual(budgets["resourceSampleSeconds"], 10)
        self.assertEqual(budgets["maxMemoryPsiFullAvg10"], 5.0)
        self.assertEqual(budgets["maxSwapOutMiBPerSecond"], 64.0)
        classes = budgets["workloadClasses"]
        self.assertEqual(set(classes), {"light", "standard", "heavy"})
        self.assertEqual(classes["light"]["slotCost"], 0.5)
        self.assertEqual(classes["light"]["minAvailableRamGb"], 1.0)
        self.assertEqual(classes["standard"]["slotCost"], 1.0)
        self.assertEqual(classes["standard"]["minAvailableRamGb"], 2.0)
        self.assertEqual(classes["heavy"]["slotCost"], 2.0)
        self.assertEqual(classes["heavy"]["minAvailableRamGb"], 4.0)

    def test_max_workers_accepts_six_rejects_seven(self):
        self.doc["budgets"]["maxWorkers"] = 6
        self.validate()
        self.doc["budgets"]["maxWorkers"] = 7
        with self.assertRaisesRegex(ValueError, "maxWorkers"):
            self.validate()

    def test_max_workers_rejects_fractional(self):
        self.doc["budgets"]["maxWorkers"] = 3.5
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            self.validate()

    def test_max_weighted_slots_is_numeric_in_range(self):
        self.doc["budgets"]["maxWeightedSlots"] = 0.4
        with self.assertRaisesRegex(ValueError, "maxWeightedSlots"):
            self.validate()
        self.doc["budgets"]["maxWeightedSlots"] = 24.5
        with self.assertRaisesRegex(ValueError, "maxWeightedSlots"):
            self.validate()
        self.doc["budgets"]["maxWeightedSlots"] = "3"
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.validate()
        self.doc["budgets"]["maxWeightedSlots"] = True
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.validate()
        self.doc["budgets"]["maxWeightedSlots"] = 3.0
        self.validate()

    def test_min_available_ram_gb_rejects_non_numeric(self):
        self.doc["budgets"]["minAvailableRamGb"] = "2"
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.validate()

    def test_min_available_ram_gb_rejects_out_of_range(self):
        self.doc["budgets"]["minAvailableRamGb"] = 0.5
        with self.assertRaisesRegex(ValueError, "minAvailableRamGb"):
            self.validate()
        self.doc["budgets"]["minAvailableRamGb"] = 65
        with self.assertRaisesRegex(ValueError, "minAvailableRamGb"):
            self.validate()

    def test_resource_sample_seconds_is_integer_in_range(self):
        self.doc["budgets"]["resourceSampleSeconds"] = 4
        with self.assertRaisesRegex(ValueError, "resourceSampleSeconds"):
            self.validate()
        self.doc["budgets"]["resourceSampleSeconds"] = 61
        with self.assertRaisesRegex(ValueError, "resourceSampleSeconds"):
            self.validate()
        self.doc["budgets"]["resourceSampleSeconds"] = 10.5
        with self.assertRaisesRegex(ValueError, "must be an integer"):
            self.validate()

    def test_max_memory_psi_full_avg10_is_numeric_in_range(self):
        self.doc["budgets"]["maxMemoryPsiFullAvg10"] = 0.05
        with self.assertRaisesRegex(ValueError, "maxMemoryPsiFullAvg10"):
            self.validate()
        self.doc["budgets"]["maxMemoryPsiFullAvg10"] = 101
        with self.assertRaisesRegex(ValueError, "maxMemoryPsiFullAvg10"):
            self.validate()
        self.doc["budgets"]["maxMemoryPsiFullAvg10"] = "5"
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.validate()

    def test_max_swap_out_mib_per_second_is_numeric_in_range(self):
        self.doc["budgets"]["maxSwapOutMiBPerSecond"] = 0.05
        with self.assertRaisesRegex(ValueError, "maxSwapOutMiBPerSecond"):
            self.validate()
        self.doc["budgets"]["maxSwapOutMiBPerSecond"] = 4097
        with self.assertRaisesRegex(ValueError, "maxSwapOutMiBPerSecond"):
            self.validate()

    def test_max_swap_used_percent_rejected_if_present(self):
        self.doc["budgets"]["maxSwapUsedPercent"] = 50
        # Validator should reject unknown budget keys that are no longer part of the schema.
        with self.assertRaisesRegex(ValueError, "maxSwapUsedPercent"):
            self.validate()

    def test_every_unknown_budget_is_rejected(self):
        self.doc["budgets"]["alternateSwapOccupancyLimit"] = 75
        with self.assertRaisesRegex(ValueError, "alternateSwapOccupancyLimit"):
            self.validate()

    def test_missing_workload_classes_rejected(self):
        del self.doc["budgets"]["workloadClasses"]
        with self.assertRaisesRegex(ValueError, "workloadClasses"):
            self.validate()

    def test_workload_classes_require_light_standard_heavy(self):
        del self.doc["budgets"]["workloadClasses"]["heavy"]
        with self.assertRaisesRegex(ValueError, "heavy"):
            self.validate()

    def test_workload_class_unknown_field_rejected(self):
        self.doc["budgets"]["workloadClasses"]["standard"]["cpuShares"] = 2
        with self.assertRaisesRegex(ValueError, "cpuShares"):
            self.validate()

    def test_workload_class_slot_cost_and_reserve_validated(self):
        self.doc["budgets"]["workloadClasses"]["light"]["slotCost"] = 0
        with self.assertRaisesRegex(ValueError, "slotCost"):
            self.validate()
        self.doc["budgets"]["workloadClasses"]["light"]["slotCost"] = 0.5
        self.doc["budgets"]["workloadClasses"]["heavy"]["minAvailableRamGb"] = 0.25
        with self.assertRaisesRegex(ValueError, "minAvailableRamGb"):
            self.validate()
        self.doc["budgets"]["workloadClasses"]["heavy"]["minAvailableRamGb"] = True
        with self.assertRaisesRegex(ValueError, "must be numeric"):
            self.validate()

    def test_extra_workload_class_with_valid_shape_accepted(self):
        self.doc["budgets"]["workloadClasses"]["tiny"] = {
            "slotCost": 0.25,
            "minAvailableRamGb": 0.5,
        }
        self.validate()

    def test_push_requires_exact_target(self):
        self.doc["authority"]["pushAuthorized"] = True
        with self.assertRaisesRegex(ValueError, "authorizedPushTarget"):
            self.validate()

    def test_integration_owner_must_be_droid(self):
        self.doc["authority"]["integrationOwner"] = ""
        with self.assertRaisesRegex(ValueError, "integrationOwner"):
            self.validate()
        self.doc["authority"]["integrationOwner"] = "conductor"
        with self.assertRaisesRegex(ValueError, "must be 'droid'"):
            self.validate()
        self.doc["authority"]["integrationOwner"] = "droid"
        self.validate()

    # --- Release / deploy / cleanup authority fields ---

    def test_release_authority_requires_exact_target_when_authorized(self):
        self.doc["authority"]["releaseAuthorized"] = True
        with self.assertRaisesRegex(ValueError, "releaseTarget"):
            self.validate()
        self.doc["authority"]["releaseTarget"] = "REPLACE: release target"
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            with self.assertRaisesRegex(ValueError, "placeholder"):
                self.validate(approved=True)
            self.doc["authority"]["releaseTarget"] = ""
            with self.assertRaisesRegex(ValueError, "releaseTarget"):
                self.validate(approved=True)

    def test_deploy_authority_requires_exact_target_when_authorized(self):
        self.doc["authority"]["deployAuthorized"] = True
        with self.assertRaisesRegex(ValueError, "deployTarget"):
            self.validate()
        self.doc["authority"]["deployTarget"] = "REPLACE: deploy target"
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            with self.assertRaisesRegex(ValueError, "placeholder"):
                self.validate(approved=True)
            self.doc["authority"]["deployTarget"] = ""
            with self.assertRaisesRegex(ValueError, "deployTarget"):
                self.validate(approved=True)

    def test_cleanup_authority_requires_non_empty_targets_when_authorized(self):
        self.doc["authority"]["cleanupAuthorized"] = True
        with self.assertRaisesRegex(ValueError, "cleanupTargets"):
            self.validate()
        self.doc["authority"]["cleanupTargets"] = ["REPLACE: cleanup target"]
        with tempfile.TemporaryDirectory() as repo:
            self.make_executable(repo)
            with self.assertRaisesRegex(ValueError, "placeholder"):
                self.validate(approved=True)

    def test_cleanup_targets_must_be_string_array(self):
        self.doc["authority"]["cleanupTargets"] = "feature-branch"
        with self.assertRaisesRegex(ValueError, "cleanupTargets"):
            self.validate()

    def test_authority_defaults_are_false_null_empty(self):
        authority = self.doc["authority"]
        self.assertFalse(authority["releaseAuthorized"])
        self.assertFalse(authority["deployAuthorized"])
        self.assertFalse(authority["cleanupAuthorized"])
        self.assertEqual(authority.get("releaseTarget"), "")
        self.assertEqual(authority.get("deployTarget"), "")
        self.assertEqual(authority.get("cleanupTargets"), [])

    def test_release_deploy_cleanup_do_not_imply_each_other(self):
        # Release authorized alone must not imply deploy or cleanup.
        self.doc["authority"]["releaseAuthorized"] = True
        self.doc["authority"]["releaseTarget"] = "v1.2.3"
        self.validate()
        self.assertFalse(self.doc["authority"]["deployAuthorized"])
        self.assertFalse(self.doc["authority"]["cleanupAuthorized"])

    # --- PASS verdict parsing in check_close_evidence ---

    def test_pass_parsing_accepts_pass_and_pass_with_notes_only(self):
        from pathlib import Path as _Path
        spec_cc = importlib.util.spec_from_file_location(
            "check_close_evidence",
            ROOT / "scripts" / "check_close_evidence.py",
        )
        cce = importlib.util.module_from_spec(spec_cc)
        assert spec_cc.loader is not None
        spec_cc.loader.exec_module(cce)
        # Accept exact PASS / PASS_WITH_NOTES as first token.
        cce.require_pass("PASS focused-smoke", "tests")
        cce.require_pass("PASS_WITH_NOTES review", "tests")
        # Reject strings whose first token is not exactly PASS / PASS_WITH_NOTES.
        for bad in ("PASSED focused", "PASSABLE", "PASSING", "PASS-LIKE", "PASSORFAIL"):
            with self.assertRaisesRegex(ValueError, "PASS"):
                cce.require_pass(bad, "tests")


if __name__ == "__main__":
    unittest.main()
