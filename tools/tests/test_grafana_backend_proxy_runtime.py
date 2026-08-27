"""Opt-in runtime coverage for Grafana's backend datasource proxy."""

from __future__ import annotations

import os
from base64 import b64encode
from urllib.error import HTTPError
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pytest

RUN_ENV = "RUN_GRAFANA_PROXY_RUNTIME_TEST"
GRAFANA_URL_ENV = "GRAFANA_RUNTIME_URL"
GRAFANA_PASSWORD_ENV = "GRAFANA_ADMIN_PASSWORD"
PROXY_PATH = (
    "/api/datasources/proxy/uid/infinity/"
    "api/weather/radar/rainviewer/3/4/5.png"
)


class _NoRedirect(HTTPRedirectHandler):
    def redirect_request(self, *args: object, **kwargs: object) -> None:
        return None


def test_grafana_backend_proxy_reaches_rainviewer_redirect() -> None:
    """Prove an external Grafana port proxies the tile request to FastAPI."""
    if os.environ.get(RUN_ENV) != "1":
        pytest.skip(f"set {RUN_ENV}=1 after starting an isolated Compose stack")

    grafana_url = os.environ[GRAFANA_URL_ENV].rstrip("/")
    password = os.environ[GRAFANA_PASSWORD_ENV]
    credentials = b64encode(f"admin:{password}".encode()).decode()
    request = Request(
        f"{grafana_url}{PROXY_PATH}",
        headers={"Authorization": f"Basic {credentials}"},
    )

    with pytest.raises(HTTPError) as response:
        build_opener(_NoRedirect()).open(request, timeout=30)

    assert response.value.code == 307
    assert response.value.headers["Location"].startswith("https://")
