import main


async def test_app_owns_catalog_runtime_and_closes_without_demand(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(main, "ORBITAL_CATALOG_PATH", tmp_path)

    def unexpected_client(**kwargs):
        raise AssertionError("Disabled orbital service must not create an HTTP client")

    monkeypatch.setattr(main.httpx, "AsyncClient", unexpected_client)
    main.initialize_orbital_catalog_runtime()
    service = main.app.state.orbital_catalog
    assert (await service.get_status())["active_viewers"] == 0
    assert not service.running
    await main.shutdown_orbital_catalog_runtime()
    assert not hasattr(main.app.state, "orbital_catalog")
    assert service.closed
