from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = REPOSITORY_ROOT / "scripts" / "install_playbook.py"
SPEC = importlib.util.spec_from_file_location("install_playbook", MODULE_PATH)
assert SPEC and SPEC.loader
installer = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = installer
SPEC.loader.exec_module(installer)


class InstallPlaybookTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.home = Path(self.temporary.name)
        self.home_patch = mock.patch.object(installer, "home", return_value=self.home)
        self.home_patch.start()
        self.artifacts = installer.discover_artifacts()
        self.rule = next(
            artifact
            for artifact in self.artifacts
            if artifact.category == "rules"
            and artifact.name == "response-readability-and-structure"
        )
        self.skill = next(
            artifact
            for artifact in self.artifacts
            if artifact.category == "skills"
            and artifact.name == "agent-playbook-installer"
        )

    def tearDown(self) -> None:
        self.home_patch.stop()
        self.temporary.cleanup()

    def test_skill_copy_detects_local_modification(self) -> None:
        plan = installer.plan_copy(self.skill)
        self.assertIsInstance(plan, installer.PlannedCopy)
        installer.install_plan(plan, force=False, dry_run=False)
        self.assertEqual(installer.copy_install_status(plan), "installed")

        installed_skill = plan.dest_root / "SKILL.md"
        installed_skill.write_text("locally modified\n", encoding="utf-8")
        self.assertEqual(installer.copy_install_status(plan), "modified destination")
        with self.assertRaises(SystemExit):
            installer.uninstall_plan(plan, force=False, dry_run=False)

    def test_skill_copy_detects_added_file(self) -> None:
        plan = installer.plan_copy(self.skill)
        self.assertIsInstance(plan, installer.PlannedCopy)
        installer.install_plan(plan, force=False, dry_run=False)
        (plan.dest_root / "local-note.txt").write_text("keep me\n", encoding="utf-8")

        self.assertEqual(installer.copy_install_status(plan), "modified destination")
        with self.assertRaises(SystemExit):
            installer.uninstall_plan(plan, force=False, dry_run=False)

    def test_rule_install_preserves_unmanaged_agents_content(self) -> None:
        agents = installer.codex_agents_path()
        agents.parent.mkdir(parents=True)
        agents.write_text("# Personal instructions\n", encoding="utf-8")

        installer.sync_codex_rules(
            [self.rule], self.artifacts, uninstall=False, force=False, dry_run=False
        )

        result = agents.read_text(encoding="utf-8")
        self.assertIn("# Personal instructions", result)
        self.assertIn(installer.MANAGED_RULES_START, result)
        self.assertEqual(installer.codex_rule_status(self.rule), "installed")

    def test_untracked_managed_rule_block_is_reported(self) -> None:
        agents = installer.codex_agents_path()
        agents.parent.mkdir(parents=True)
        agents.write_text(installer.managed_rules_text([self.rule]), encoding="utf-8")

        self.assertEqual(installer.codex_rule_status(self.rule), "unmanaged destination")

    def test_rule_install_migrates_exact_legacy_body_without_duplication(self) -> None:
        agents = installer.codex_agents_path()
        agents.parent.mkdir(parents=True)
        heading = "# Response Readability and Structure"
        agents.write_text(installer.rule_body(self.rule), encoding="utf-8")

        installer.sync_codex_rules(
            [self.rule], self.artifacts, uninstall=False, force=False, dry_run=False
        )

        result = agents.read_text(encoding="utf-8")
        self.assertEqual(result.count(heading), 1)
        self.assertEqual(result.count(installer.MANAGED_RULES_START), 1)

    def test_modified_rule_block_requires_force(self) -> None:
        installer.sync_codex_rules(
            [self.rule], self.artifacts, uninstall=False, force=False, dry_run=False
        )
        agents = installer.codex_agents_path()
        text = agents.read_text(encoding="utf-8")
        agents.write_text(text.replace("Generated from", "Locally changed"), encoding="utf-8")

        with self.assertRaises(SystemExit):
            installer.sync_codex_rules(
                [self.rule],
                self.artifacts,
                uninstall=False,
                force=False,
                dry_run=False,
            )

    def test_rule_uninstall_removes_only_managed_block(self) -> None:
        agents = installer.codex_agents_path()
        agents.parent.mkdir(parents=True)
        agents.write_text("# Personal instructions\n", encoding="utf-8")
        installer.sync_codex_rules(
            [self.rule], self.artifacts, uninstall=False, force=False, dry_run=False
        )

        installer.sync_codex_rules(
            [self.rule], self.artifacts, uninstall=True, force=False, dry_run=False
        )

        self.assertEqual(agents.read_text(encoding="utf-8"), "# Personal instructions\n")
        self.assertFalse(installer.codex_rules_state_path().exists())


if __name__ == "__main__":
    unittest.main()
