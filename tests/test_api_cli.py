import json
import time

import httpx
import pytest
from conftest import FixtureNetwork, fixture_response
from fastapi.testclient import TestClient
from socialintel.api import create_app
from socialintel.cli import app
from socialintel.providers import Registry
from typer.testing import CliRunner


@pytest.fixture
def client(settings, store):
    application = create_app(
        settings, store=store, network=FixtureNetwork(httpx.MockTransport(fixture_response))
    )
    with TestClient(application) as client:
        client.headers["Authorization"] = "Bearer " + settings.token
        yield client


def test_auth_origin_host_and_size_boundaries(client):
    assert client.get("/api/cases", headers={"Authorization": ""}).status_code == 401
    assert client.get("/api/cases", headers={"Host": "evil.example"}).status_code == 400
    assert client.get("/api/cases", headers={"Origin": "https://evil.example"}).status_code == 403
    assert client.post("/api/cases", content="{}", headers={"Content-Length": "9999999"}).status_code == 413
    assert client.get("/api/cases").headers["X-Content-Type-Options"] == "nosniff"
    assert client.get("/api/cases").headers["Cache-Control"] == "no-store"


def test_case_import_export_lifecycle(client):
    case = client.post("/api/cases", json={"name": "Synthetic API test"}).json()
    response = client.post(
        f"/api/cases/{case['id']}/import",
        json={"source_url": "https://example.org/", "fields": {"bio": "Public export"}, "notes": "Synthetic"},
    )
    assert response.status_code == 201
    item = response.json()["items"][0]
    assert item["verification"].startswith("USER-PROVIDED")
    assert client.get(f"/api/evidence/{item['id']}").json()["integrity_valid"]
    assert (
        client.patch(
            f"/api/cases/{case['id']}", json={"notes": "Updated notes", "tags": ["review"]}
        ).status_code
        == 200
    )
    for format in ("html", "md", "json", "csv"):
        report = client.get(f"/api/reports/{case['id']}?format={format}")
        assert report.status_code == 200 and "attachment" in report.headers["Content-Disposition"]
    assert client.delete(f"/api/cases/{case['id']}").status_code == 204
    assert client.get(f"/api/evidence/{item['id']}").status_code == 404


def test_api_investigation_runs_shared_pipeline(client):
    response = client.post("/api/investigations", json={"target": "example", "platform": "instagram"})
    assert response.status_code == 202
    run = response.json()
    for _ in range(50):
        record = client.get(f"/api/investigations/{run['id']}").json()
        if record["status"] not in ("queued", "running"):
            break
        time.sleep(0.01)
    assert record["status"] == "completed"
    assert record["result"]["results"][0]["status"] == "UNSUPPORTED BY THIS PROVIDER"
    assert record["result"]["summary"]["verified_profiles"] == 2
    assert client.get("/api/overview").json()["counts"]["investigations"] == 1
    assert client.get("/api/settings").json()["single_user"] is True


def test_api_invalid_inputs_and_secrets_absence(client, monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fixture-secret-123")
    assert "fixture-secret" not in client.get("/api/settings").text
    assert client.post("/api/investigations", json={"target": "https://127.0.0.1/"}).status_code == 400
    assert (
        client.post(
            "/api/investigations", json={"target": "example", "limits": {"max_requests": 500}}
        ).status_code
        == 422
    )
    assert client.get("/api/evidence?limit=100000").status_code == 422
    assert (
        client.post("/api/search/web", json={"target": "example", "search_engine": "none"}).status_code == 400
    )
    assert client.get("/openapi.json").json()["paths"]["/api/cases"]["get"]["security"] == [
        {"BearerAuth": []}
    ]


def test_cli_platforms_cases_reports_and_noninteractive_help(tmp_path, monkeypatch):
    monkeypatch.setenv("SOCIALINTEL_DATA_DIR", str(tmp_path))
    runner = CliRunner()
    result = runner.invoke(app, ["platforms", "--json"])
    assert result.exit_code == 0
    assert len(json.loads(result.stdout)) >= 29
    case = runner.invoke(app, ["case", "create", "--name", "Synthetic CLI"])
    assert case.exit_code == 0
    record = json.loads(case.stdout)
    assert runner.invoke(app, ["case", "list"]).exit_code == 0
    output = tmp_path / "report.html"
    result = runner.invoke(app, ["report", record["id"], "--output", str(output)])
    assert result.exit_code == 0 and output.exists()
    assert runner.invoke(app, ["report", record["id"], "--output", str(output)]).exit_code != 0
    assert runner.invoke(app, ["case", "delete", record["id"], "--yes"]).exit_code == 0
    assert runner.invoke(app, []).exit_code == 0


def test_bad_plugins_are_isolated(settings):
    settings.plugins = ("not_installed:factory", "path;bad:factory")
    registry = Registry(settings)
    assert len(registry.plugin_errors) == 2
    assert registry.get("github").manifest.name == "GitHub"


def test_weak_api_token_rejected(settings, store):
    settings.token = "too-short"
    with pytest.raises(ValueError, match="32"):
        create_app(settings, store=store)
