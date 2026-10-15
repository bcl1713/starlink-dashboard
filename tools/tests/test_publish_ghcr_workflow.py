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
    def test_backend_build_uses_root_context_without_changing_other_images(self):
        checker = load_checker_module()
        entries = checker.workflow_entries(WORKFLOW_PATH)
        by_image = {entry["image"].rsplit("/", 1)[-1]: entry for entry in entries}
        self.assertEqual(by_image["starlink-location"]["context"], ".")
        self.assertEqual(by_image["mission-planner"]["context"], "./frontend/mission-planner")
        self.assertEqual(by_image["gfs-worker"]["context"], "./backend/starlink-location")
        text = WORKFLOW_PATH.read_text().replace(
            "            context: .\n            file: ./backend/starlink-location/Dockerfile",
            "            context: ./backend/starlink-location\n            file: ./backend/starlink-location/Dockerfile",
        )
        self.assertTrue(any("starlink-location context must be ." in error for error in self.validate_workflow_text(text)))

    def test_backend_image_has_isolated_pinned_runtime_and_precise_build_inputs(self):
        dockerfile = (REPO_ROOT / "backend/starlink-location/Dockerfile").read_text()
        self.assertIn("FROM node:22.22.2-trixie-slim", dockerfile)
        self.assertIn("/opt/customer-briefing", dockerfile)
        self.assertIn("PLAYWRIGHT_BROWSERS_PATH", dockerfile)
        self.assertIn("fonts-dejavu-core", dockerfile)
        self.assertIn("poppler-utils", dockerfile)
        self.assertIn("COPY backend/starlink-location/requirements.txt", dockerfile)
        self.assertIn('ENTRYPOINT ["entrypoint.sh"]', dockerfile)
        self.assertIn("useradd -m -u 1000 appuser", dockerfile)
        ignore = REPO_ROOT / "backend/starlink-location/Dockerfile.dockerignore"
        self.assertTrue(ignore.exists(), "Root-context backend exclusion rules absent")
        self.assertEqual(ignore.read_text().splitlines()[0], "**")

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

    def test_gfs_worker_is_published_and_missing_worker_is_rejected(self) -> None:
        checker = load_checker_module()
        entries = checker.workflow_entries(WORKFLOW_PATH)
        worker = next((e for e in entries if e["image"].endswith("/gfs-worker")), None)
        self.assertEqual(
            worker,
            {
                "image": "ghcr.io/${{ github.repository }}/gfs-worker",
                "context": "./backend/starlink-location",
                "file": "./backend/starlink-location/Dockerfile.gfs",
            },
        )
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        row = """          - image: ghcr.io/${{ github.repository }}/gfs-worker
            context: ./backend/starlink-location
            file: ./backend/starlink-location/Dockerfile.gfs
"""
        self.assertIn(
            "missing publish matrix images: gfs-worker",
            self.validate_workflow_text(text.replace(row, "")),
        )

    def test_inventory_cannot_silently_omit_worker_package(self) -> None:
        text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn(
            "for package in starlink-location mission-planner prometheus gfs-worker; do",
            text,
        )
        mutated = text.replace("prometheus gfs-worker; do", "prometheus; do")
        self.assertIn(
            "GHCR inventory must query complete user package versions",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_missing_candidate_sha_build_argument(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "          build-args: |\n"
            "            ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}\n",
            "",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "build action must pass ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}",
            errors,
        )

    def test_rejects_candidate_sha_build_argument_relocated_to_metadata_action(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        candidate_sha_build_arg = (
            "          build-args: |\n"
            "            ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}\n"
        )
        mutated_workflow = workflow_text.replace(candidate_sha_build_arg, "").replace(
            "          tags: |\n"
            "            type=sha,format=long,prefix=sha-\n"
            "            type=ref,event=tag\n",
            "          tags: |\n"
            "            type=sha,format=long,prefix=sha-\n"
            "            type=ref,event=tag\n" + candidate_sha_build_arg,
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "build action must pass ACCEPTANCE_CANDIDATE_SHA=${{ github.sha }}",
            errors,
        )

    def test_rejects_stale_publish_action_when_expected_pin_is_commented(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "uses: actions/checkout@v7",
            "uses: actions/checkout@v4\n\n# uses: actions/checkout@v7",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "publish actions must be actions/checkout@v7, "
            "docker/login-action@v4, docker/setup-buildx-action@v4, "
            "docker/metadata-action@v6, docker/build-push-action@v7",
            errors,
        )

    def test_rejects_stale_shorthand_publish_action_when_expected_pin_is_disabled(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Check out source\n        uses: actions/checkout@v7",
            "      - name: Check out source\n"
            "        if: ${{ false }}\n"
            "        uses: actions/checkout@v7\n\n"
            "      - uses: actions/checkout@v4",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "publish actions must be actions/checkout@v7, "
            "docker/login-action@v4, docker/setup-buildx-action@v4, "
            "docker/metadata-action@v6, docker/build-push-action@v7",
            errors,
        )

    def test_rejects_publish_runner_when_ubuntu_latest_is_commented(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "runs-on: ubuntu-latest",
            "runs-on: ubuntu-22.04\n\n# runs-on: ubuntu-latest",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "publish runner must be ubuntu-latest, got ['ubuntu-22.04']",
            errors,
        )

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
        prometheus_entry = """          - image: ghcr.io/${{ github.repository }}/prometheus
            context: .
            file: ./deployment/prometheus/Dockerfile
"""

        errors = self.validate_workflow_text(
            workflow_text.replace(prometheus_entry, "")
        )

        self.assertIn("publish matrix must contain exactly 4 entries, got 3", errors)
        self.assertIn("missing publish matrix images: prometheus", errors)

    def test_rejects_retention_without_publish_dependency(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("needs: publish", "")
        )

        self.assertIn("retention job must depend on successful publish", errors)

    def test_rejects_retention_without_dev_success_condition(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("needs.publish.result == 'success'", "true")
        )

        self.assertIn(
            "retention job must run only for a successful publish on dev", errors
        )

    def test_rejects_retention_without_actions_write_permission(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("      actions: write", "      actions: read")
        )

        self.assertIn("retention job permissions must be least-privileged", errors)

    def test_rejects_retention_without_github_token_for_gh_commands(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("    env:\n      GH_TOKEN: ${{ github.token }}\n", "")
        )

        self.assertIn("retention gh commands must receive GH_TOKEN", errors)

    def test_rejects_retention_selection_without_paginated_json_plan(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("gh api --paginate --slurp", "gh api --slurp")
        )

        self.assertIn(
            "retention selection step must paginate complete JSON inputs", errors
        )

    def test_rejects_retention_runs_with_ref_qualified_workflow_paths(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            'map(.workflow_runs[] | .path |= split("@")[0]) | unique_by(.id)',
            "map(.workflow_runs[]) | unique_by(.id)",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "retention selection step must normalize workflow paths for the CLI plan",
            errors,
        )

    def test_rejects_artifact_deletion_that_is_not_exact_selected_id_endpoint(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace(
                'gh api --method DELETE "repos/${{ github.repository }}/actions/artifacts/$artifact_id"',
                'gh api --method DELETE "repos/${{ github.repository }}/actions/artifacts"',
            )
        )

        self.assertIn(
            "retention deletion step must delete only selected artifact IDs", errors
        )

    def test_rejects_disabled_artifact_deletion_step_with_inline_comment(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Delete only selected artifact IDs\n        run:",
            "      - name: Delete only selected artifact IDs\n"
            "        if: ${{ false }} # disabled\n"
            "        run:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "retention deletion step must delete only selected artifact IDs", errors
        )

    def test_rejects_ghcr_inventory_step_with_package_delete(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace(
                "          set -euo pipefail\n          for package",
                "          set -euo pipefail\n"
                '          gh api --method DELETE "orgs/${{ github.repository_owner }}/packages/container/example/versions/1"\n'
                "          for package",
            )
        )

        self.assertIn("GHCR inventory step must be report-only", errors)

    def test_rejects_wrong_ghcr_package_endpoint_or_incomplete_pages(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        endpoint = (
            "users/${{ github.repository_owner }}/packages/container/"
            "starlink-dashboard%2F$package/versions"
        )
        pagination = f'gh api --paginate --slurp "{endpoint}?per_page=100"'
        flatten = "jq '{versions: flatten, pagination: {complete: true}}'"
        for original, replacement in (
            (endpoint, endpoint.replace("users/", "orgs/")),
            (endpoint, endpoint.replace("starlink-dashboard%2F", "")),
            (endpoint, endpoint.replace("%2F", "/")),
            (pagination, pagination.replace("--paginate ", "")),
            (flatten, "jq '{versions: .[0], pagination: {complete: true}}'"),
        ):
            with self.subTest(replacement=replacement):
                mutated = workflow_text.replace(original, replacement)
                self.assertNotEqual(mutated, workflow_text)
                self.assertIn(
                    "GHCR inventory must query complete user package versions",
                    self.validate_workflow_text(mutated),
                )

    def test_rejects_commented_ghcr_query_with_wrong_live_query(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        query = (
            'gh api --paginate --slurp "users/${{ github.repository_owner }}/packages/'
            'container/starlink-dashboard%2F$package/versions?per_page=100"'
        )
        query_and_jq = (
            query + " |\n"
            "              jq '{versions: flatten, pagination: {complete: true}}'"
            ' > "retention/$package-versions.json"'
        )
        mutated = workflow_text.replace(
            query_and_jq,
            query.replace("users/", "orgs/")
            + " | jq '{versions: flatten, pagination: {complete: true}}'"
            + ' > "retention/$package-versions.json" # '
            + query,
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "GHCR inventory must query complete user package versions",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_commented_flatten_with_wrong_live_jq(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        flatten = "jq '{versions: flatten, pagination: {complete: true}}'"
        mutated = workflow_text.replace(
            flatten,
            "jq '{versions: .[0], pagination: {complete: true}}'"
            "\n              # " + flatten,
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "GHCR inventory must query complete user package versions",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_ghcr_inventory_that_exits_before_classification(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated = workflow_text.replace(
            "            python tools/github_retention_cli.py ghcr-inventory \\\n",
            "            exit 0\n"
            "            python tools/github_retention_cli.py ghcr-inventory \\\n",
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "GHCR inventory must query complete user package versions",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_ghcr_inventory_with_commented_classifier(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated = workflow_text.replace(
            "            python tools/github_retention_cli.py ghcr-inventory \\\n"
            '              --versions "retention/$package-versions.json" | tee "retention/$package-ghcr-inventory.json"',
            "            exit 0\n"
            "            # python tools/github_retention_cli.py ghcr-inventory \\\n"
            '            #   --versions "retention/$package-versions.json" | tee "retention/$package-ghcr-inventory.json"',
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "GHCR inventory must query complete user package versions",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_ghcr_inventory_with_extra_mutation(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated = workflow_text.replace(
            "          for package in starlink-location",
            '          gh api --method DELETE "users/${{ github.repository_owner }}/'
            'packages/container/starlink-dashboard%2Fstarlink-location/versions/1"\n'
            "          for package in starlink-location",
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "GHCR inventory step must be report-only",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_ghcr_inventory_without_packages_read(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated = workflow_text.replace("      packages: read", "      packages: write")
        self.assertIn(
            "retention job permissions must be least-privileged",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_equivalently_disabled_ghcr_inventory_step(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Inventory GHCR versions without mutation\n        run:",
            "      - name: Inventory GHCR versions without mutation\n"
            "        if: ${{ 1 == 0 }} # disabled\n"
            "        run:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn("GHCR inventory step must be report-only", errors)

    def test_rejects_disabled_artifact_deletion_step_with_false_and_dynamic_operand(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Delete only selected artifact IDs\n        run:",
            "      - name: Delete only selected artifact IDs\n"
            "        if: ${{ false && github.ref == 'refs/heads/dev' }}\n"
            "        run:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "retention deletion step must delete only selected artifact IDs", errors
        )

    def test_rejects_disabled_artifact_deletion_step_with_nested_dynamic_or_true(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Delete only selected artifact IDs\n        run:",
            "      - name: Delete only selected artifact IDs\n"
            "        if: ${{ false && (github.ref == 'refs/heads/dev' || true) }}\n"
            "        run:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn(
            "retention deletion step must delete only selected artifact IDs", errors
        )

    def test_rejects_disabled_upload_step_with_negated_true_or_dynamic_operand(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Upload retention plan\n        uses:",
            "      - name: Upload retention plan\n"
            "        if: ${{ !(true || github.ref == 'refs/heads/dev') }}\n"
            "        uses:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn("retention job must upload the selected artifact plan", errors)

    def test_accepts_node24_retention_upload_with_exact_default_archive_contract(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("uses: actions/upload-artifact@v7", workflow_text)
        self.assertEqual(self.validate_workflow_text(workflow_text), [])

    def test_rejects_node20_retention_upload(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated = workflow_text.replace(
            "uses: actions/upload-artifact@v7", "uses: actions/upload-artifact@v4"
        )
        self.assertNotEqual(mutated, workflow_text)
        self.assertIn(
            "retention job must upload the selected artifact plan",
            self.validate_workflow_text(mutated),
        )

    def test_rejects_damaged_retention_upload_contract(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        self.assertIn("uses: actions/upload-artifact@v7", workflow_text)
        self.assertEqual(self.validate_workflow_text(workflow_text), [])
        for original, replacement in (
            ("name: publish-retention-plan-${{ github.run_id }}", "name: other-plan"),
            ("path: retention/artifact-plan.json", "path: retention/other.json"),
            ("if-no-files-found: error", "if-no-files-found: warn"),
            (
                "if-no-files-found: error",
                "archive: false\n          if-no-files-found: error",
            ),
        ):
            with self.subTest(original=original, replacement=replacement):
                mutated = workflow_text.replace(original, replacement)
                self.assertNotEqual(mutated, workflow_text)
                self.assertIn(
                    "retention job must upload the selected artifact plan",
                    self.validate_workflow_text(mutated),
                )

    def test_rejects_retention_without_uploaded_plan(self) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")

        errors = self.validate_workflow_text(
            workflow_text.replace("uses: actions/upload-artifact@v7", "run: true")
        )

        self.assertIn("retention job must upload the selected artifact plan", errors)

    def test_rejects_equivalently_disabled_upload_step_with_inline_comment(
        self,
    ) -> None:
        workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
        mutated_workflow = workflow_text.replace(
            "      - name: Upload retention plan\n        uses:",
            "      - name: Upload retention plan\n"
            "        if: ${{ !true }} # disabled\n"
            "        uses:",
        )

        errors = self.validate_workflow_text(mutated_workflow)

        self.assertIn("retention job must upload the selected artifact plan", errors)


if __name__ == "__main__":
    unittest.main()
