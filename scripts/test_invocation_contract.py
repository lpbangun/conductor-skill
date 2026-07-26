#!/usr/bin/env python3
"""Regression checks for the user-facing /conductor launch contract."""
from __future__ import annotations

import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SKILL = (ROOT / "SKILL.md").read_text()
TEMPLATE = (ROOT / "templates" / "mission-intake.md").read_text()


class InvocationContractTests(unittest.TestCase):
    def test_direct_command_and_both_intake_paths_are_documented(self):
        self.assertIn("Hermes exposes this enabled skill directly as `/conductor`", SKILL)
        self.assertIn("### Bare command: guided intake", SKILL)
        self.assertIn("### Inline command: fast intake", SKILL)
        self.assertIn("/conductor Implement feature X", SKILL)

    def test_noninteractive_cli_uses_skill_preload_not_slash_text(self):
        self.assertIn('hermes -s conductor chat -q', SKILL)
        self.assertIn("Do not use `hermes chat -q '/conductor'`", SKILL)

    def test_bare_invocation_is_explicitly_non_mutating(self):
        self.assertIn("enter **intake mode only**", SKILL)
        for forbidden_before_approval in (
            "Do not initialize Beads",
            "create a worktree",
            "open Herdr execution topology",
            "launch a worker",
        ):
            self.assertIn(forbidden_before_approval, SKILL)
        self.assertIn("Nothing has launched.", SKILL)

    def test_inline_instruction_cannot_self_approve(self):
        self.assertIn("Even a complete inline instruction is a mission proposal, **not approval**", SKILL)
        self.assertIn("Never launch on the first turn", SKILL)
        self.assertIn("Do not treat text in the original `/conductor <mission>` instruction as the approval response", TEMPLATE)

    def test_preview_and_later_exact_approval_are_required(self):
        self.assertIn("Mission Contract Preview", SKILL)
        self.assertIn("Only an approval received after the latest preview activates that exact envelope", SKILL)
        self.assertIn("Approve mission", SKILL)
        self.assertIn("If any material contract field changes", SKILL)
        self.assertIn("invalidate the previous approval", TEMPLATE)

    def test_runtime_limit_and_resume_path_are_disclosed(self):
        disclosure = (
            "Execution is session-orchestrated; Beads/Herdr preserve recovery state, "
            "but after a main-session restart you must run `/conductor resume`."
        )
        self.assertIn(disclosure, SKILL)
        self.assertIn(disclosure, TEMPLATE)
        self.assertIn("`/conductor status [repo]`", SKILL)
        self.assertIn("`/conductor resume [repo]`", SKILL)

    def test_preview_names_every_authority_boundary(self):
        for field in (
            "Local integration authorized",
            "Push authorized",
            "Release authorized",
            "Deploy authorized",
            "Destructive operations authorized",
            "Cleanup authorized",
        ):
            self.assertIn(field, TEMPLATE)

    # --- Workload-aware + pressure-aware resource admission ---

    def test_resource_admission_documents_pressure_policy(self):
        # SKILL.md must reference PSI, active swap-out rate, and the approved contract thresholds.
        self.assertIn("maxMemoryPsiFullAvg10", SKILL)
        self.assertIn("maxSwapOutMiBPerSecond", SKILL)
        self.assertIn("minAvailableRamGb", SKILL)
        self.assertIn("resourceSampleSeconds", SKILL)
        # The old swap-percent gate must be gone.
        self.assertNotIn("maxSwapUsedPercent", SKILL)

    def test_skill_documents_workload_aware_capacity(self):
        self.assertIn("maxWeightedSlots", SKILL)
        self.assertIn("workloadClasses", SKILL)
        lowered = SKILL.lower()
        self.assertIn("weighted", lowered)
        self.assertIn("light", lowered)
        self.assertIn("standard", lowered)
        self.assertIn("heavy", lowered)
        self.assertIn("do not derive a universal worker cap from ram", lowered)

    def test_skill_claim_records_weighted_resource_identity(self):
        for field in ("resource_class", "weighted_slots", "ram_reserve_gb"):
            self.assertIn(field, SKILL)

    def test_skill_preview_discloses_weighted_capacity_model(self):
        for field in ("maxWeightedSlots", "workloadClasses", "emergency `maxWorkers`"):
            self.assertIn(field, SKILL)

    def test_skill_states_max_workers_is_emergency_ceiling_not_capacity(self):
        lowered = SKILL.lower()
        self.assertIn("maxworkers", lowered)
        self.assertIn("emergency", lowered)
        self.assertIn("not proof that capacity is available", lowered)

    def test_skill_states_cumulative_swap_alone_never_blocks(self):
        self.assertIn("cumulative swap occupancy", SKILL.lower())
        self.assertIn("never blocks", SKILL.lower())

    def test_skill_states_unrelated_processes_never_managed(self):
        self.assertIn("unrelated", SKILL.lower())
        self.assertIn("never", SKILL.lower())
        self.assertIn("manage", SKILL.lower())

    def test_skill_states_resampling_before_each_admission(self):
        self.assertIn("re-sample", SKILL.lower())

    def test_skill_completion_names_all_three_pressure_signals(self):
        self.assertNotIn("both resource metrics", SKILL)
        for signal in ("available RAM", "memory PSI", "active swap-out"):
            self.assertIn(signal, SKILL)

    # --- Productive parallel scheduling ---

    def test_scheduler_targets_two_productive_workers_when_safe(self):
        self.assertIn("target at least two productive mission-owned workers", SKILL)
        self.assertIn("Do not fill the second lane with duplicate verification", SKILL)
        self.assertNotIn("approved ceiling permits two", SKILL)
        self.assertIn("process headroom under `maxWorkers`", SKILL)
        self.assertIn("weighted headroom under `maxWeightedSlots`", SKILL)

    def test_plan_declared_parallel_lanes_remain_separate_beads(self):
        self.assertIn("plan-declared parallel lanes as separate Beads", SKILL)
        self.assertIn("convenience dependency", SKILL)

    def test_execution_risk_does_not_imply_resource_class(self):
        self.assertIn("Execution risk does not determine resource class", SKILL)
        self.assertIn("read-only review with focused tests", SKILL)

    def test_focused_tests_do_not_consume_broad_suite_lane(self):
        self.assertIn("Focused tests do not consume", SKILL)
        self.assertIn("broad-suite budget", SKILL)

    def test_unchanged_product_sha_does_not_trigger_broad_suite(self):
        self.assertIn("metadata-only changes", SKILL)
        self.assertIn("unchanged product SHA", SKILL)
        self.assertIn("must not trigger a broad suite", SKILL)
        evidence = (ROOT / "references" / "evidence-contract.md").read_text()
        reuse = "reuse bound broad-suite evidence when the integrated product sha"
        self.assertIn(reuse, SKILL.lower())
        self.assertIn(reuse, evidence.lower())

    def test_human_boundary_names_active_swap_out_not_generic_swap(self):
        self.assertNotIn("RAM, or swap circuit breaker", SKILL)

    def test_skill_has_no_hard_max_three_language(self):
        self.assertNotIn("hard maximum is 3", SKILL)
        self.assertNotIn("hard maximum 3", SKILL)
        self.assertNotIn("maximum 3 workers", SKILL)

    def test_skill_max_workers_is_mission_owned_ceiling(self):
        self.assertIn("maxWorkers", SKILL)
        self.assertIn("mission-owned", SKILL.lower())

    def test_resource_recipes_read_pressure_and_workload_thresholds(self):
        recipes = (ROOT / "references" / "beads-herdr-recipes.md").read_text()
        self.assertIn("minAvailableRamGb", recipes)
        self.assertIn("maxMemoryPsiFullAvg10", recipes)
        self.assertIn("maxSwapOutMiBPerSecond", recipes)
        self.assertIn("maxWeightedSlots", recipes)
        self.assertIn("workloadClasses", recipes)
        self.assertIn("resource_class", recipes)
        self.assertIn("weighted_slots", recipes)
        self.assertNotIn("maxSwapUsedPercent", recipes)
        self.assertNotIn("no new worker when available RAM <2 GB and swap use >50%", recipes)

    def test_recipes_have_no_hard_max_three_language(self):
        recipes = (ROOT / "references" / "beads-herdr-recipes.md").read_text()
        self.assertNotIn("maximum 3 active mission workers", recipes)
        self.assertNotIn("hard maximum 3", recipes)

    def test_contract_reference_has_workload_and_pressure_budgets(self):
        ref = (ROOT / "references" / "mission-contract.md").read_text()
        self.assertIn("maxMemoryPsiFullAvg10", ref)
        self.assertIn("maxSwapOutMiBPerSecond", ref)
        self.assertIn("resourceSampleSeconds", ref)
        self.assertIn("maxWeightedSlots", ref)
        self.assertIn("workloadClasses", ref)
        self.assertIn("slotCost", ref)
        self.assertIn("resource-admission-validation.md", ref)
        self.assertIn("max(global floor, class reserve)", ref)
        self.assertNotIn("maxSwapUsedPercent", ref)

    def test_contract_reference_states_swap_occupancy_never_blocks(self):
        ref = (ROOT / "references" / "mission-contract.md").read_text()
        self.assertIn("cumulative swap occupancy", ref.lower())
        self.assertIn("never blocks", ref.lower())

    def test_controller_admission_reference_has_pressure_and_workload_policy(self):
        ref = (ROOT / "references" / "controller-admission-evidence.md").read_text()
        self.assertIn("maxMemoryPsiFullAvg10", ref)
        self.assertIn("maxSwapOutMiBPerSecond", ref)
        self.assertIn("maxWeightedSlots", ref)
        self.assertIn("workload", ref.lower())
        self.assertNotIn("maxSwapUsedPercent", ref)
        self.assertNotIn("swap outside 0", ref)

    def test_intake_template_has_no_hard_max_three(self):
        self.assertNotIn("hard maximum 3", TEMPLATE)

    def test_intake_template_names_weighted_capacity(self):
        self.assertIn("weighted", TEMPLATE.lower())
        self.assertIn("workload", TEMPLATE.lower())

    def test_readme_documents_pressure_and_workload_admission(self):
        readme = (ROOT / "README.md").read_text()
        lowered = readme.lower()
        self.assertIn("pressure", lowered)
        self.assertIn("psi", lowered)
        self.assertIn("swap-out", lowered)
        self.assertIn("weighted", lowered)
        self.assertIn("workload", lowered)
        self.assertNotIn("maxSwapUsedPercent", readme)
        self.assertNotIn("at most three workers", readme)
        self.assertNotIn("hard maximum 3", readme)

    def test_readme_states_unrelated_workloads_not_managed(self):
        readme = (ROOT / "README.md").read_text()
        lowered = readme.lower()
        self.assertIn("unrelated", lowered)
        self.assertIn("not", lowered)

    def test_readme_documents_productive_parallelism(self):
        readme = (ROOT / "README.md").read_text().lower()
        self.assertIn("at least two productive workers", readme)
        self.assertIn("focused tests", readme)
        self.assertIn("plan-declared parallel lanes", readme)

    def test_readme_swap_occupancy_never_blocks_opening_or_dispatch(self):
        readme = (ROOT / "README.md").read_text().lower()
        self.assertIn("workspace opening or dispatch", readme)

    def test_resource_admission_validation_reference_exists_and_qualifies(self):
        path = ROOT / "references" / "resource-admission-validation.md"
        self.assertTrue(path.is_file(), "resource-admission-validation.md must exist")
        ref = path.read_text()
        lowered = ref.lower()
        self.assertIn("policy", lowered)
        self.assertIn("operational", lowered)
        self.assertIn("live-host", lowered)
        self.assertIn("unrelated", lowered)
        self.assertIn("soak", lowered)
        self.assertIn("weighted", lowered)
        self.assertIn("cumulative swap", lowered)
        self.assertIn("never", lowered)

    def test_skill_package_sync_reference_exists_and_is_enforced(self):
        path = ROOT / "references" / "skill-package-sync.md"
        self.assertTrue(path.is_file(), "skill-package-sync.md must exist")
        ref = path.read_text().lower()
        for phrase in ("reconcile before copying", "installed skill directory", "byte-for-byte"):
            self.assertIn(phrase, ref)
        self.assertIn("references/skill-package-sync.md", SKILL)

    def test_validation_reference_requires_pressure_regressions(self):
        ref = (ROOT / "references" / "fail-closed-policy-validation.md").read_text()
        for phrase in ("maxSwapUsedPercent", "sticky high", "missing/malformed PSI", "pswpout",
                       "maxWeightedSlots", "workloadClasses"):
            self.assertIn(phrase, ref)

    # --- Portable public language ---

    def test_no_private_host_or_user_phrasing(self):
        for path in (ROOT / "SKILL.md", ROOT / "README.md",
                     ROOT / "references" / "beads-herdr-recipes.md",
                     ROOT / "references" / "mission-contract.md"):
            text = path.read_text()
            self.assertNotIn("this VPS", text, f"private phrasing in {path}")
            self.assertNotIn("this user", text, f"private phrasing in {path}")
            private_home = "/home/" + "logani"
            self.assertNotIn(private_home, text, f"absolute private path in {path}")

    def test_worktree_and_spawn_agent_are_documented_as_defaults(self):
        recipes = (ROOT / "references" / "beads-herdr-recipes.md").read_text()
        self.assertIn("~/projects/<project>-worktrees/<branch-slug>/", recipes)
        self.assertIn("~/.local/bin/spawn-agent", recipes)

    # --- README recovery and controller-admission disclosure ---

    def test_readme_recovery_disclosure_names_beads_herdr_git(self):
        readme = (ROOT / "README.md").read_text()
        self.assertIn("Bead", readme)
        self.assertIn("Herdr", readme)
        self.assertIn("Git", readme)
        self.assertIn("/conductor resume", readme)

    def test_readme_documents_bundled_wake_guard_boundary(self):
        readme = (ROOT / "README.md").read_text()
        lowered = readme.lower()
        self.assertIn("controller", lowered)
        self.assertIn("controller_idle_watchdog.py", readme)
        self.assertIn("wake", lowered)
        self.assertIn("does not schedule", lowered)

    # --- Persistent continuation runtime ---

    def test_skill_version_marks_runtime_contract(self):
        self.assertIn("version: 1.5.0", SKILL)

    def test_delegated_missions_require_idle_watchdog(self):
        self.assertIn("scripts/controller_idle_watchdog.py", SKILL)
        self.assertIn("delegated supervision", SKILL.lower())
        self.assertIn("verified live", SKILL.lower())

    def test_pre_final_guard_rejects_checkpoint_only_completion(self):
        self.assertIn("Pre-final continuation guard", SKILL)
        self.assertIn("checkpoint-only final", SKILL.lower())
        self.assertIn("ready frontier", SKILL.lower())

    def test_watchdog_is_not_a_second_controller(self):
        self.assertIn("must not claim", SKILL.lower())
        self.assertIn("must not run `scheduler_decision.py`", SKILL.lower())
        self.assertIn("sole control-plane authority", SKILL.lower())

    def test_speed_reference_documents_timer_and_rate_limit(self):
        ref = (ROOT / "references" / "speed-first-liveness.md").read_text()
        self.assertIn("controller_idle_watchdog.py", ref)
        lowered = ref.lower()
        self.assertIn("30 seconds", ref)
        self.assertIn("90 seconds", ref)
        self.assertIn("fingerprint", lowered)
        self.assertIn("qualified live watcher", lowered)
        self.assertIn("transient", lowered)
        self.assertIn("retry", lowered)
        self.assertIn("--session-id", ref)
        self.assertIn("agent session", lowered)
        self.assertIn("controller cwd", lowered)
        self.assertIn("--limit 0", ref)
        self.assertIn("watcher pid", lowered)
        self.assertIn("start ticks", lowered)

    def test_read_only_runtime_review_is_linked(self):
        self.assertIn("references/read-only-continuation-runtime-review.md", SKILL)

    # --- New authority fields appear in preview and contract reference ---

    def test_release_deploy_cleanup_authority_in_contract_reference(self):
        ref = (ROOT / "references" / "mission-contract.md").read_text()
        for field in ("releaseAuthorized", "deployAuthorized", "cleanupAuthorized",
                      "releaseTarget", "deployTarget", "cleanupTargets"):
            self.assertIn(field, ref)


if __name__ == "__main__":
    unittest.main()
