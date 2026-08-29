import importlib.util
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
CHECKER_PATH = REPO_ROOT / "tools" / "check_publish_ghcr_workflow.py"
WORKFLOW_PATH = REPO_ROOT / ".github" / "workflows" / "publish-ghcr.yml"


def load_checker_module():
    spec = importlib.util.spec_from_file_location("publish_ghcr_checker", CHECKER_PATH)
    if spec is None or spec.loader is None:
        raise RuntimeError("Unable to load the GHCR workflow contract checker")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


class PublishGhcrWorkflowContractTests(unittest.TestCase):
    def validate_workflow_text(self, workflow_text: str) -> list[str]:
        checker = load_checker_module()
        with tempfile.TemporaryDirectory() as temporary_directory:
            workflow_path = Path(temporary_directory) / "publish-ghcr.yml"
            workflow_path.write_text(workflow_text, encoding="utf-8")
            return checker.validate_publish_workflow(REPO_ROOT, workflow_path)

    def test_every_image_has_an_explicit_resolvable_build_context_and_dockerfile(
        self,
    ) -> None:
        checker = load_checker_module()

        errors = checker.validate_publish_workflow(REPO_ROOT, WORKFLOW_PATH)

        self.assertEqual(errors, [])

    def test_rejects_duplicate_expected_publish_matrix_row(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        duplicate_entry = """          - image: ghcr.io/${{ github.repository }}/starlink-location
            context: ./backend/starlink-location
            file: ./backend/starlink-location/Dockerfile
"""

        errors = self.validate_workflow_text(workflow_text + duplicate_entry)

        self.assertIn("publish matrix must contain exactly 4 entries, got 5", errors)
        self.assertIn("duplicate publish matrix images: starlink-location", errors)

    def test_rejects_missing_expected_publish_matrix_row(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        grafana_entry = """          - image: ghcr.io/${{ github.repository }}/grafana
            context: .
            file: ./deployment/grafana/Dockerfile
"""

        errors = self.validate_workflow_text(workflow_text.replace(grafana_entry, ""))

        self.assertIn("publish matrix must contain exactly 4 entries, got 3", errors)
        self.assertIn("missing publish matrix images: grafana", errors)


if __name__ == "__main__":
    unittest.main()
