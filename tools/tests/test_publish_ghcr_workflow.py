import importlib.util
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
    def test_every_image_has_an_explicit_resolvable_build_context_and_dockerfile(
        self,
    ) -> None:
        checker = load_checker_module()

        errors = checker.validate_publish_workflow(REPO_ROOT, WORKFLOW_PATH)

        self.assertEqual(errors, [])


if __name__ == "__main__":
    unittest.main()
