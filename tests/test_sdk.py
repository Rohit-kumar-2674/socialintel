import sys
import types
from pathlib import Path

import pytest
from socialintel.engine import Engine
from socialintel.models import InvestigationRequest, Profile, Verification
from socialintel.providers import Registry
from socialintel.sdk import (
    Manifest,
    PlatformAdapter,
    RetrievalError,
    validate_profile,
    validate_provider,
)


class FixtureAdapter(PlatformAdapter):
    manifest = Manifest(
        name="Synthetic contract fixture",
        platform="fixture-plugin",
        version="0.1.0",
        domains=["example.org"],
        status="EXPERIMENTAL",
        capabilities=["profile"],
        methods=["PUBLIC API"],
        limitations="Synthetic test only; never a real provider.",
        documentation_url="https://example.org/docs",
    )

    async def get_public_profile(self, target, ctx):
        return self.profile("synthetic", "https://example.org/synthetic", {"bio": "Synthetic fixture"}, "https://example.org/api")


@pytest.mark.parametrize("update", [
    {"status": "ONLINE"}, {"capabilities": ["private_messages"]},
    {"methods": ["BYPASS"]}, {"limitations": ""}, {"domains": ["127.0.0.1"]},
    {"domains": ["example.org/path"]}, {"domains": []},
    {"requirements": ["actual-secret-value"]}, {"version": "whatever"},
    {"capabilities": ["profile", "posts"]},
])
def test_rejects_misleading_or_invalid_manifest(update):
    provider = FixtureAdapter()
    provider.manifest = provider.manifest.model_copy(update=update)
    with pytest.raises(ValueError):
        validate_provider(provider)


def test_sdk_refuses_nonpublic_declaration():
    with pytest.raises(ValueError):
        Manifest.model_validate({**FixtureAdapter.manifest.model_dump(), "public_only": False})


def test_output_contract_prevents_promoting_hints_and_unsafe_sources():
    adapter = FixtureAdapter()
    profile = adapter.profile("example", "https://example.org/", {}, "https://example.org/api?key=secret&count=1")
    cleaned = validate_profile(profile, adapter)
    assert "secret" not in str(cleaned.model_dump())
    profile.fields["username"].verification = Verification.INDEX
    with pytest.raises(RetrievalError):
        validate_profile(profile, adapter)
    profile.fields["username"].verification = Verification.VERIFIED
    profile.fields["username"].source_url = "https://127.0.0.1/"
    with pytest.raises(RetrievalError):
        validate_profile(profile, adapter)


def test_plugin_loading_and_duplicates_do_not_mutate_shared_manifest(settings, monkeypatch):
    module = types.ModuleType("contract_fixture")
    module.create = lambda settings: FixtureAdapter()
    monkeypatch.setitem(sys.modules, "contract_fixture", module)
    settings.plugins = ("contract_fixture:create", "contract_fixture:create")
    registry = Registry(settings)
    assert registry.get("fixture-plugin").manifest.plugin
    assert not FixtureAdapter.manifest.plugin
    assert len(registry.plugin_errors) == 1


def test_plugin_configuration_failure_isolated(settings):
    class BrokenConfiguration(FixtureAdapter):
        def configured(self, settings):
            raise RuntimeError("synthetic-secret-must-not-leak")

    registry = Registry(settings)
    registry.providers["fixture-plugin"] = BrokenConfiguration()
    assert "synthetic-secret" not in str(registry.catalog(settings))
    assert registry.get("fixture-plugin") not in registry.discovery_providers(settings)


async def test_example_plugin_runs_shared_engine(settings, store, network, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).parents[1] / "plugins/example_provider/src"))
    settings.plugins = ("socialintel_example:create_provider",)
    engine = Engine(settings, store, network=network)
    assert engine.registry.plugin_errors == []
    result = await engine.investigate(InvestigationRequest(
        target="https://example.org/", platform="example-page", mode="selected",
    ))
    item = result["result"]["results"][0]
    assert item["status"] == "FOUND"
    assert item["profile"]["platform"] == "example-page"
    assert result["result"]["requests_made"] == 2
    rejected = await engine.investigate(InvestigationRequest(
        target="https://other.example/", platform="example-page", mode="selected",
    ))
    assert rejected["result"]["requests_made"] == 0
    assert rejected["result"]["results"][0]["status"] == "UNSUPPORTED BY THIS PROVIDER"
    await engine.close()


async def test_malformed_plugin_result_never_persisted_as_verified(settings, store, network):
    class Unverified(FixtureAdapter):
        async def get_public_profile(self, target, ctx):
            return Profile(id="bad", platform="fixture-plugin", username="example", url="https://example.org/", provider="fixture-plugin", verification=Verification.INDEX)

    registry = Registry(settings)
    registry.providers["fixture-plugin"] = Unverified()
    engine = Engine(settings, store, network=network, registry=registry)
    run = await engine.investigate(InvestigationRequest(target="example", platform="fixture-plugin", mode="selected"))
    assert run["result"]["summary"]["evidence"] == 0
    assert run["result"]["results"][0]["status"] == "ERROR"
    await engine.close()
