import asyncio

import httpx
from conftest import FixtureNetwork, fixture_response
from socialintel.analytics import compare
from socialintel.engine import Engine
from socialintel.models import InvestigationRequest, Limits, Status


async def test_default_fallback_preserves_unsupported_primary(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(InvestigationRequest(target="example", platform="instagram"))
    assert record["status"] == "completed"
    result = record["result"]
    assert result["results"][0]["status"] == Status.UNSUPPORTED.value
    assert result["fallback"]["started"] is True
    assert {item["platform"] for item in result["results"] if item["profile"]} == {"github", "bluesky"}
    assert result["correlations"][0]["level"] == "HIGH"
    assert "identity" in result["correlations"][0]["interpretation"].lower()
    evidence = store.evidence(case_id=record["case_id"])["items"]
    assert evidence and all(
        item["source_url"] and item["collected_at"] and item["provider"] for item in evidence
    )
    ids = {item["id"] for item in evidence}
    assert all(set(edge["data"]["evidence_ids"]).issubset(ids) for edge in result["graph"]["edges"])
    assert all(store.get_evidence(item["id"])["integrity_valid"] for item in evidence)
    await engine.close()


async def test_selected_mode_does_not_expand(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(
        InvestigationRequest(target="example", platform="instagram", mode="selected", follow_links=True)
    )
    assert len(record["result"]["results"]) == 1
    assert record["result"]["requests_made"] == 0
    await engine.close()


async def test_found_primary_stops_default_fallback(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(InvestigationRequest(target="example", platform="github"))
    assert len(record["result"]["results"]) == 1
    assert not record["result"]["fallback"]["started"]
    await engine.close()


async def test_partial_provider_failure_does_not_stop_other_sources(settings, store):
    def handler(request):
        if request.url.host == "api.github.com":
            return httpx.Response(403)
        return fixture_response(request)

    network = FixtureNetwork(httpx.MockTransport(handler))
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(
        InvestigationRequest(target="example", platform="all", mode="discovery")
    )
    statuses = {item["platform"]: item["status"] for item in record["result"]["results"]}
    assert statuses == {"github": "LIMITED", "bluesky": "FOUND"}
    assert record["status"] == "completed"
    await engine.close()


async def test_search_results_verified_separately(settings, store, network, monkeypatch):
    monkeypatch.setenv("BRAVE_SEARCH_API_KEY", "fixture-key")
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(
        InvestigationRequest(target="Example Person", platform="all", mode="discovery", search_engine="brave")
    )
    results = record["result"]["web_results"]
    assert len(results) == 2
    assert all("NOT INDEPENDENTLY VERIFIED" in item["verification"] for item in results)
    assert any(
        item["status"] == "FOUND" and item["platform"] == "github" for item in record["result"]["results"]
    )
    assert any(
        item["status"] == Status.UNSUPPORTED.value and item["platform"] == "twitter"
        for item in record["result"]["results"]
    )
    assert "fixture-key" not in str(record)
    await engine.close()


async def test_cache_keeps_original_collection_times_and_refresh(settings, store, network):
    engine = Engine(settings, store, network=network)
    request = InvestigationRequest(target="example", mode="selected")
    first = await engine.investigate(request)
    second = await engine.investigate(request.model_copy(update={"case_id": first["case_id"]}))
    cached = second["result"]["results"][0]
    assert cached["cached"] and second["result"]["requests_made"] == 0
    assert cached["profile"]["collected_at"] == first["result"]["results"][0]["profile"]["collected_at"]
    refreshed = await engine.investigate(request.model_copy(update={"refresh": True}))
    assert not refreshed["result"]["results"][0]["cached"]
    await engine.close()


async def test_hard_request_and_candidate_limits(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(
        InvestigationRequest(
            target="example123",
            platform="all",
            mode="discovery",
            variants=True,
            follow_links=True,
            collect_posts=True,
            limits=Limits(max_requests=1, max_candidates=2),
        )
    )
    assert record["result"]["requests_made"] == 1
    assert len(record["result"]["results"]) <= 2
    await engine.close()


async def test_public_link_chain_and_timeline(settings, store, network):
    engine = Engine(settings, store, network=network)
    record = await engine.investigate(
        InvestigationRequest(target="example", collect_posts=True, follow_links=True)
    )
    assert any(item["platform"] == "website" for item in record["result"]["results"])
    assert record["result"]["timeline"]
    assert record["result"]["pages_requested"] <= 5
    await engine.close()


async def test_cancellation_persists_partial_status(settings, store):
    entered = asyncio.Event()

    async def handler(request):
        entered.set()
        await asyncio.Event().wait()

    network = FixtureNetwork(httpx.MockTransport(handler))
    engine = Engine(settings, store, network=network)
    record = engine.submit(InvestigationRequest(target="example"))
    await asyncio.wait_for(entered.wait(), 2)
    cancelled = await engine.cancel(record["id"])
    assert cancelled["status"] == "cancelled"
    assert all(progress["status"] != "CHECKING" for progress in cancelled["result"]["progress"])
    await engine.close()


async def test_comparison_does_not_infer_removal(settings, store, network):
    engine = Engine(settings, store, network=network)
    first = await engine.investigate(InvestigationRequest(target="example", mode="selected"))
    second = {**first, "id": "later", "result": {"results": []}}
    changes = compare(first, second)["changes"]
    assert changes[0]["type"] == "NOT OBSERVED IN THIS RUN"
    assert "removal" in changes[0]["note"]
    await engine.close()


def test_restart_marks_unfinished_work_interrupted(store):
    record = store.create_investigation(InvestigationRequest(target="example"))
    store.recover()
    assert store.get_investigation(record["id"])["status"] == "interrupted"
