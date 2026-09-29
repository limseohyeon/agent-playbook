from __future__ import annotations

import importlib.util
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
MODULE_PATH = (
    REPOSITORY_ROOT
    / "skills"
    / "global"
    / "github-issue-lifecycle"
    / "scripts"
    / "github_issue_lifecycle.py"
)
SPEC = importlib.util.spec_from_file_location("github_issue_lifecycle", MODULE_PATH)
assert SPEC and SPEC.loader
lifecycle = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = lifecycle
SPEC.loader.exec_module(lifecycle)


def item(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "title": "Title",
        "purpose": "Purpose",
        "in_scope": [],
        "out_of_scope": [],
        "acceptance_criteria": ["Done"],
        "dependencies": [],
        "labels": [],
        "priority": None,
        "template": None,
        "body": None,
    }
    value.update(overrides)
    return value


class GitHubIssueTemplateTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.templates = self.root / ".github" / "ISSUE_TEMPLATE"
        self.templates.mkdir(parents=True)
        self.git_root = mock.patch.object(lifecycle, "run_git", return_value=str(self.root))
        self.git_root.start()

    def tearDown(self) -> None:
        self.git_root.stop()
        self.temporary.cleanup()

    def tree(self, parent: dict[str, object], child: dict[str, object]) -> dict[str, object]:
        child["key"] = "child"
        return {"plan_id": "plan-id", "parent": parent, "children": [child]}

    def test_discovers_supported_templates_and_excludes_config(self) -> None:
        (self.templates / "feature.md").write_text("# Feature\n", encoding="utf-8")
        (self.templates / "bug.yml").write_text("name: Bug\n", encoding="utf-8")
        (self.templates / "config.yml").write_text("blank_issues_enabled: false\n", encoding="utf-8")

        self.assertEqual(
            lifecycle.discover_issue_templates(),
            [
                {"path": ".github/ISSUE_TEMPLATE/bug.yml", "format": "issue-form"},
                {"path": ".github/ISSUE_TEMPLATE/feature.md", "format": "markdown"},
            ],
        )

    def test_single_template_is_selected_automatically(self) -> None:
        (self.templates / "feature.md").write_text("# Feature\n", encoding="utf-8")
        tree = self.tree(item(body="# Feature\nDetails"), item(body="# Feature\nChild"))

        result = lifecycle.apply_template_policy(tree)

        self.assertEqual(result["parent"]["template"], ".github/ISSUE_TEMPLATE/feature.md")
        self.assertEqual(result["children"][0]["template"], ".github/ISSUE_TEMPLATE/feature.md")

    def test_template_requires_completed_body(self) -> None:
        (self.templates / "feature.md").write_text("# Feature\n", encoding="utf-8")
        tree = self.tree(item(body="# Feature\nDetails"), item())

        with self.assertRaisesRegex(lifecycle.UserError, "body is required"):
            lifecycle.apply_template_policy(tree)

    def test_multiple_templates_require_selection_for_each_item(self) -> None:
        (self.templates / "feature.md").write_text("# Feature\n", encoding="utf-8")
        (self.templates / "bug.yml").write_text("name: Bug\n", encoding="utf-8")
        tree = self.tree(item(body="# Feature\nDetails"), item(body="# Feature\nChild"))

        with self.assertRaisesRegex(lifecycle.UserError, "Multiple issue templates"):
            lifecycle.apply_template_policy(tree)

    def test_rendered_template_body_keeps_tracking_metadata(self) -> None:
        value = item(body="## Summary\n\nCompleted from template")

        rendered = lifecycle.render_description(value, "codex-plan:plan-id:parent", children=[])

        self.assertTrue(rendered.startswith("## Summary\n\nCompleted from template"))
        self.assertIn("<!-- Tracking ID: codex-plan:plan-id:parent -->", rendered)
        self.assertIn("## Child issues", rendered)


if __name__ == "__main__":
    unittest.main()
