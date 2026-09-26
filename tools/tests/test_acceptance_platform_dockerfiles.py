from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
BACKEND_DOCKERFILE = REPOSITORY / "backend/starlink-location/Dockerfile"
FRONTEND_DOCKERFILE = REPOSITORY / "frontend/mission-planner/Dockerfile"
CANDIDATE = "ACCEPTANCE_CANDIDATE_SHA"


def _stages(source: str) -> list[list[str]]:
    stages: list[list[str]] = []
    for line in source.splitlines():
        if line.startswith("FROM "):
            stages.append([])
        if stages:
            stages[-1].append(line)
    assert stages, "Dockerfile must contain a FROM instruction"
    return stages


def test_backend_dockerfile_consumes_candidate_in_app_source_stage() -> None:
    stages = _stages(BACKEND_DOCKERFILE.read_text(encoding="utf-8"))
    app_copies = (
        "COPY --chown=appuser:appuser main.py .",
        "COPY --chown=appuser:appuser config.yaml .",
        "COPY --chown=appuser:appuser app/ ./app/",
        "COPY --chown=appuser:appuser tests/ ./tests/",
    )
    app_stage = next(stage for stage in stages if all(copy in stage for copy in app_copies))

    assert "COPY --from=builder --chown=appuser:appuser /root/.local /home/appuser/.local" in app_stage
    candidate_arg = app_stage.index(f"ARG {CANDIDATE}")
    candidate_run = app_stage.index(f'RUN test -n "${CANDIDATE}"')
    assert candidate_arg < candidate_run < min(app_stage.index(copy) for copy in app_copies)


def test_candidate_is_not_persisted_in_dockerfile_runtime_metadata() -> None:
    for dockerfile in (BACKEND_DOCKERFILE, FRONTEND_DOCKERFILE):
        source = dockerfile.read_text(encoding="utf-8")
        candidate_lines = [line for line in source.splitlines() if CANDIDATE in line]
        assert candidate_lines == [
            f"ARG {CANDIDATE}",
            f'RUN test -n "${CANDIDATE}"',
        ]
        assert not any(
            line.startswith(("ENV ", "LABEL ")) and CANDIDATE in line
            for line in source.splitlines()
        )


def test_frontend_dockerfile_consumes_candidate_only_after_npm_ci() -> None:
    stages = _stages(FRONTEND_DOCKERFILE.read_text(encoding="utf-8"))
    builder = stages[0]

    assert builder.index("RUN npm ci") < builder.index(f"ARG {CANDIDATE}")
    assert builder.index(f"ARG {CANDIDATE}") < builder.index("COPY . .")
    assert f'RUN test -n "${CANDIDATE}"' in builder
