from __future__ import annotations

from games_intel.api.openapi import check_openapi, render_openapi, schema_dict


def test_exported_openapi_matches_live_schema() -> None:
    assert check_openapi() == []


def test_openapi_export_contains_catalog_contract() -> None:
    dumped = render_openapi()
    schema = schema_dict()
    assert "/api/v1/games" in dumped
    assert "GameCardRead" in schema["components"]["schemas"]
    assert "GameListResponse" in schema["components"]["schemas"]
    assert "/api/v1/monitor" in schema["paths"]
    assert "/api/v1/runs" in schema["paths"]
