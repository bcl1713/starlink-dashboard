from pathlib import Path


REPOSITORY = Path(__file__).resolve().parents[2]
BACKEND_DOCKERFILE = REPOSITORY / "backend/starlink-location/Dockerfile"
FRONTEND_DOCKERFILE = REPOSITORY / "frontend/mission-planner/Dockerfile"


def test_backend_dockerfile_consumes_candidate_only_after_pip_install() -> None:
    source = BACKEND_DOCKERFILE.read_text(encoding="utf-8")

    assert source.index("RUN pip install --user --no-cache-dir -r requirements.txt") < source.index(
        "ARG ACCEPTANCE_CANDIDATE_SHA"
    )
    assert source.index("ARG ACCEPTANCE_CANDIDATE_SHA") < source.index(
        "COPY --chown=appuser:appuser main.py ."
    )
    assert 'RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"' in source


def test_frontend_dockerfile_consumes_candidate_only_after_npm_ci() -> None:
    source = FRONTEND_DOCKERFILE.read_text(encoding="utf-8")

    assert source.index("RUN npm ci") < source.index("ARG ACCEPTANCE_CANDIDATE_SHA")
    assert source.index("ARG ACCEPTANCE_CANDIDATE_SHA") < source.index("COPY . .")
    assert 'RUN test -n "$ACCEPTANCE_CANDIDATE_SHA"' in source
