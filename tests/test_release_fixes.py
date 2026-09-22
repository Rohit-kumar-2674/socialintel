"""Regression coverage for release fixes using only synthetic, offline inputs."""

import pytest
from socialintel.engine import Engine
from socialintel.models import InvestigationRequest
from typer.testing import CliRunner


async def test_cancel_before_first_instruction(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = engine.submit(InvestigationRequest(target="example"))
    assert (await engine.cancel(record["id"]))["status"] == "cancelled"
    store.delete_case(record["case_id"])
    await engine.close()


async def test_shutdown_marks_even_unstarted_jobs_cancelled(settings, store, network):
    engine = Engine(settings, store, network=network)
    records = [engine.submit(InvestigationRequest(target=f"fixture-{n}")) for n in range(3)]
    await engine.close()
    assert all(store.get_investigation(record["id"])["status"] == "cancelled" for record in records)


async def test_platform_mismatch_rejected_before_case_creation(settings, store, network):
    engine = Engine(settings, store, network=network)
    with pytest.raises(ValueError, match="different platform"):
        engine.submit(InvestigationRequest(target="https://instagram.com/example/", platform="website"))
    assert store.cases() == []
    await engine.close()


def test_configured_token_never_printed(monkeypatch, tmp_path):
    from socialintel.cli import app

    secret = "synthetic-test-token-which-must-not-be-logged"
    monkeypatch.setenv("SOCIALINTEL_API_TOKEN", secret)
    monkeypatch.setenv("SOCIALINTEL_DATA_DIR", str(tmp_path))
    monkeypatch.setattr("uvicorn.run", lambda *args, **kwargs: None)
    result = CliRunner().invoke(app, ["serve"])
    assert result.exit_code == 0
    assert secret not in result.output
    assert "configured API token" in result.output
