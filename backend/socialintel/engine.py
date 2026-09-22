"""One bounded investigation pipeline shared by the API, dashboard, and CLI."""

import asyncio
import hashlib
import json
import time
from urllib.parse import urlsplit

from .analytics import analyze
from .discovery import classify_url, normalize, variants
from .models import InvestigationRequest, ProviderResult, Status, Verification, now
from .providers import Registry
from .providers.base import Context
from .search_engines import SEARCH
from .security import Budget, Network, RetrievalError


class Engine:
    def __init__(self, settings, store, *, network=None, registry=None):
        self.settings, self.store = settings, store
        self.network = network or Network()
        self.network.cooldowns.update(store.network_cooldowns())
        self.network.on_cooldown = store.save_cooldown
        self.registry = registry or Registry(settings)
        self.jobs: dict[str, asyncio.Task] = {}
        self.queue = asyncio.Semaphore(2)

    def submit(self, request: InvestigationRequest):
        self.validate(request)
        if sum(not job.done() for job in self.jobs.values()) >= 8:
            raise ValueError("Investigation queue is full. Wait for a running investigation to finish.")
        record = self.store.create_investigation(request)
        task = asyncio.create_task(self.run(record["id"]))
        self.jobs[record["id"]] = task
        task.add_done_callback(lambda _: self.jobs.pop(record["id"], None))
        return record

    def validate(self, request):
        target = normalize(request.target, request.target_type, urlsplit(self.settings.mastodon_instance).hostname)
        if request.platform != "all":
            self.registry.get(request.platform)
        if request.platform == "all" and request.mode == "selected":
            raise ValueError("All platforms requires full discovery or fallback mode.")
        if target.kind == "url" and target.platform and request.platform not in (target.platform, "all"):
            raise ValueError("The profile URL belongs to a different platform. Select its platform or All Platforms.")

    async def cancel(self, investigation_id):
        task = self.jobs.get(investigation_id)
        if task and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)
        # A task cancelled before its first instruction cannot run its cleanup.
        row = self.store.get_investigation(investigation_id)
        if row["status"] in ("queued", "running"):
            self.store.save_investigation(investigation_id, row["result"], "cancelled")
        return self.store.get_investigation(investigation_id)

    async def close(self):
        jobs = dict(self.jobs)
        for task in jobs.values():
            task.cancel()
        await asyncio.gather(*jobs.values(), return_exceptions=True)
        for job_id in jobs:
            await self.cancel(job_id)
        await self.network.close()

    async def evaluate(self, adapter, target, ctx, variant=False):
        started = time.monotonic()
        platform = adapter.manifest.platform
        cache_key = hashlib.sha256(
            json.dumps(
                [
                    platform,
                    adapter.manifest.version,
                    target.model_dump(),
                    ctx.request.collect_posts,
                    ctx.request.collect_contacts,
                    ctx.request.limits.max_posts,
                    self.settings.mastodon_instance,
                ],
                sort_keys=True,
            ).encode()
        ).hexdigest()
        result = ProviderResult(platform=platform, target=target.value, status=Status.ERROR, variant=variant)
        try:
            ready, reason = adapter.configured(self.settings)
            if not adapter.manifest.capabilities:
                raise RetrievalError(Status.UNSUPPORTED, adapter.manifest.limitations)
            if not ready:
                raise RetrievalError(Status.API_REQUIRED, reason)
            health = self.store.health(platform)
            if health and health.get("retry_at") and health["retry_at"] > now():
                raise RetrievalError(
                    Status.RATE_LIMITED, "Persisted provider cooldown is active.", health["retry_at"]
                )
            if not ctx.request.refresh and (cached := self.store.cache_get(cache_key)):
                return ProviderResult.model_validate({**cached, "cached": True, "variant": variant})
            profile = await adapter.get_public_profile(target, ctx)
            if profile is None:
                result.status, result.reason = (
                    Status.NOT_FOUND,
                    "No public profile returned for this identifier. This does not establish that no private account exists.",
                )
            else:
                from .sdk import validate_profile

                profile = validate_profile(profile, adapter)
                profile.posts = []
                if (
                    ctx.request.collect_posts
                    and ctx.request.limits.max_posts
                    and "posts" in adapter.supported_features()
                ):
                    try:
                        profile.posts = (await adapter.get_public_posts(profile, ctx))[: ctx.request.limits.max_posts]
                        profile = validate_profile(profile, adapter)
                    except RetrievalError as error:
                        profile.posts = []
                        result.retry_at = error.retry_at
                        result.reason = (
                            f"Public profile collected. Posts: {error.status.value} — {error.reason}"
                        )
                    except Exception:
                        profile.posts = []
                        result.reason = "Public profile collected. Posts: ERROR — response did not match the supported schema."
                result.profile, result.status = profile, Status.FOUND
                result.source_url = profile.url
                result.reason = (
                    result.reason
                    or "Verified at the public source; relationship to the investigation target is unverified."
                )
            result.duration_ms = round((time.monotonic() - started) * 1000)
            self.store.cache_set(cache_key, result.model_dump(mode="json"))
        except RetrievalError as error:
            result.status, result.reason, result.retry_at = error.status, error.reason, error.retry_at
        except ValueError:
            result.status, result.reason = (
                Status.UNSUPPORTED,
                "Target URL or identifier failed provider validation.",
            )
        except Exception:
            result.status, result.reason = (
                Status.ERROR,
                "Provider response did not match the supported schema. Other providers continue.",
            )
        result.duration_ms = round((time.monotonic() - started) * 1000)
        previous = self.store.health(platform) or {}
        self.store.save_health(
            platform,
            {
                "status": "RATE LIMITED" if result.retry_at else "ONLINE"
                if result.status in (Status.FOUND, Status.NOT_FOUND)
                else result.status.value,
                "checked_at": result.checked_at,
                "last_successful_check": result.checked_at
                if result.status in (Status.FOUND, Status.NOT_FOUND)
                else previous.get("last_successful_check"),
                "response_time_ms": result.duration_ms,
                "retry_at": result.retry_at,
                "reason": result.reason,
                "capabilities": adapter.supported_features(),
                "probe": "Observed provider request; not an availability guarantee.",
            },
        )
        return result

    async def run(self, investigation_id):
        record = self.store.get_investigation(investigation_id)
        request = InvestigationRequest.model_validate(record["request"])
        result = record["result"]
        evidence = []
        profiles = {}
        budget = Budget(request.limits)
        target = normalize(
            request.target, request.target_type, urlsplit(self.settings.mastodon_instance).hostname
        )
        ctx = Context(self.network, budget, self.settings, request)
        result["normalized_target"] = target.model_dump()
        result["scope"] = {
            "limits": request.limits.model_dump(),
            "public_only": True,
            "search_engine": request.search_engine,
        }
        seen = set()
        visited_platforms = set()

        def save(status="running"):
            result["requests_made"] = budget.requests
            result["pages_requested"] = budget.pages
            self.store.save_investigation(investigation_id, result, status)

        def observe(body):
            item = self.store.add_evidence(record["case_id"], investigation_id, body)
            evidence.append(item)
            return item

        def collect(profile):
            if profile.id in profiles:
                return
            profiles[profile.id] = profile
            for name, field in profile.fields.items():
                observe(
                    {
                        "profile_id": profile.id,
                        "platform": profile.platform,
                        "field": name,
                        "value": field.value,
                        "source_url": field.source_url,
                        "collected_at": field.collected_at,
                        "method": field.method,
                        "verification": field.verification.value,
                        "provider": field.provider,
                        "confidence": "VERIFIED PUBLIC DATA",
                        "notes": "Source verification is not identity verification.",
                    }
                )
            for link in profile.links:
                observe(
                    {
                        "profile_id": profile.id,
                        "platform": profile.platform,
                        "field": "public_link",
                        "value": link.destination,
                        "source_url": link.source_url,
                        "collected_at": link.collected_at,
                        "method": profile.method,
                        "verification": profile.verification.value,
                        "provider": profile.provider,
                        "confidence": "VERIFIED PUBLIC DATA",
                        "notes": "Link publicly declared by this source.",
                    }
                )
            for post in profile.posts:
                observe(
                    {
                        "profile_id": profile.id,
                        "platform": profile.platform,
                        "field": "public_post",
                        "value": post.model_dump(),
                        "source_url": post.url,
                        "collected_at": profile.collected_at,
                        "method": profile.method,
                        "verification": profile.verification.value,
                        "provider": profile.provider,
                        "confidence": "VERIFIED PUBLIC DATA",
                        "notes": "Publication time is source-provided, not independently authenticated.",
                    }
                )

        async def check(adapter, check_target, variant=False, discovered_via="TARGET INPUT", depth=0):
            key = (adapter.manifest.platform, check_target.value.casefold(), check_target.kind)
            if key in seen or len(seen) >= request.limits.max_candidates:
                return None
            if (
                adapter.manifest.platform not in visited_platforms
                and len(visited_platforms) >= request.limits.max_platforms
            ):
                return None
            seen.add(key)
            visited_platforms.add(adapter.manifest.platform)
            progress = {
                "platform": adapter.manifest.platform,
                "target": check_target.value,
                "status": "CHECKING",
                "discovered_via": discovered_via,
                "depth": depth,
            }
            result["progress"].append(progress)
            save()
            item = await self.evaluate(adapter, check_target, ctx, variant)
            progress["status"] = item.status.value
            data = {**item.model_dump(mode="json"), "discovered_via": discovered_via, "depth": depth}
            result["results"].append(data)
            if item.profile:
                collect(item.profile)
            elif item.status not in (Status.NOT_FOUND, Status.POSSIBLE):
                result["errors"].append(
                    {"platform": item.platform, "status": item.status.value, "reason": item.reason}
                )
            save()
            return item

        async def search_web():
            if request.search_engine == "none":
                result["search_status"] = "DISABLED — no search provider selected."
                return
            provider = SEARCH.get(request.search_engine)
            if not provider:
                result["search_status"] = "UNAVAILABLE — standalone Bing Search APIs retired on 2025-08-11."
                return
            if not provider.configured(self.settings):
                result["search_status"] = (
                    "API REQUIRED — configure a supported search API. Google is for existing customers before 2027-01-01."
                )
                return
            # Quoted identifier searches only; no sensitive attribute enrichment.
            query_value = target.value.replace('"', " ")[:200]
            queries = [f'"{query_value}"', f'"{query_value}" profile']
            try:
                for query in queries:
                    items = await provider.search(query, ctx)
                    known = {item["url"] for item in result["web_results"]}
                    for item in items:
                        if (
                            item["url"] in known
                            or len(result["web_results"]) >= request.limits.max_candidates
                        ):
                            continue
                        known.add(item["url"])
                        item["query"], item["collected_at"] = query, now()
                        result["web_results"].append(item)
                        observe(
                            {
                                "platform": item["platform"] or "web",
                                "field": "search_reference",
                                "value": item,
                                "source_url": item["source_url"],
                                "collected_at": item["collected_at"],
                                "method": "SEARCH INDEX",
                                "verification": Verification.INDEX.value,
                                "provider": provider.name,
                                "confidence": "SEARCH INDEX REFERENCE",
                                "notes": "Snippet is an index hint, not independently verified evidence of its claims.",
                            }
                        )
                result["search_status"] = "COMPLETED"
            except RetrievalError as error:
                result["search_status"] = f"{error.status.value} — {error.reason}"
            except Exception:
                result["search_status"] = "ERROR — search response did not match the supported schema."
            save()
            for item in result["web_results"]:
                platform = item["platform"]
                if platform and item["username"] and platform in self.registry.providers:
                    found = await check(
                        self.registry.get(platform),
                        normalize(item["url"], "url"),
                        discovered_via="SEARCH INDEX",
                    )
                    item["source_status"] = (
                        found.status.value if found else "CANDIDATE LIMIT OR ALREADY CHECKED"
                    )
                else:
                    item["source_status"] = "UNVERIFIED WEB REFERENCE"

        async def pipeline():
            primary = request.platform
            if target.kind == "url" and target.platform and primary not in (target.platform, "all"):
                raise ValueError(
                    "The profile URL belongs to a different platform. Select its platform or All Platforms."
                )
            if target.kind == "url" and not target.platform and primary == "all":
                primary = "website"
            selected = None
            if primary != "all" and request.mode != "discovery":
                selected = await check(self.registry.get(primary), target)
            expand = (
                request.mode == "discovery"
                or primary == "all"
                or (request.mode == "fallback" and selected is not None and selected.status != Status.FOUND)
            )
            result["fallback"] = {
                "started": request.mode == "fallback" and expand,
                "reason": selected.status.value if selected else "Full discovery requested.",
            }
            search_target = target
            if target.kind == "url":
                info = classify_url(target.value, urlsplit(self.settings.mastodon_instance).hostname)
                if info["username"]:
                    search_target = normalize(info["username"], "username")
                if request.mode == "discovery":
                    await check(self.registry.get(info["platform"] or "website"), target)
            if expand:
                if search_target.kind == "username":
                    adapters = self.registry.discovery_providers(self.settings)
                    await asyncio.gather(
                        *[
                            check(adapter, search_target, discovered_via="GLOBAL USERNAME SEARCH")
                            for adapter in adapters
                        ]
                    )
                    if request.variants:
                        for variant in variants(search_target.value):
                            await asyncio.gather(
                                *[
                                    check(
                                        adapter,
                                        normalize(variant, "username"),
                                        True,
                                        "GENERATED SEARCH VARIANT",
                                    )
                                    for adapter in adapters
                                ]
                            )
                elif search_target.kind == "id":
                    result["identifier_note"] = (
                        "IDs are platform-specific; cross-platform ID equivalence is not assumed."
                    )
                    if target.value.startswith("did:"):
                        await check(self.registry.get("bluesky"), target)
                    elif primary != "all":
                        await check(self.registry.get(primary), target)
                await search_web()
            else:
                result["search_status"] = "NOT RUN — selected-platform scope or primary profile found."
            if request.follow_links:
                followed = set()
                for depth in range(1, request.limits.max_depth + 1):
                    links = [link for profile in list(profiles.values()) for link in profile.links]
                    for link in links:
                        if link.destination in followed:
                            continue
                        followed.add(link.destination)
                        info = classify_url(
                            link.destination, urlsplit(self.settings.mastodon_instance).hostname
                        )
                        if not info["safe"] or (info["platform"] and not info["username"]):
                            continue
                        platform = info["platform"] or "website"
                        if request.mode == "selected" and platform != primary:
                            continue
                        if platform in self.registry.providers:
                            await check(
                                self.registry.get(platform),
                                normalize(link.destination, "url"),
                                discovered_via=link.source_url,
                                depth=depth,
                            )

        status = "completed"
        try:
            async with self.queue:
                budget.started = time.monotonic()
                save()
                async with asyncio.timeout(request.limits.max_seconds):
                    await pipeline()
        except TimeoutError:
            status = "limited"
            result["limitation"] = (
                "Execution deadline reached. Collected observations are retained; pending work was cancelled."
            )
        except asyncio.CancelledError:
            status = "cancelled"
            result["limitation"] = "Investigation cancelled. Completed public observations are retained."
        except ValueError as error:
            status = "failed"
            result["limitation"] = str(error)
        except Exception:
            status = "failed"
            result["limitation"] = (
                "Investigation stopped after an internal processing error. Collected evidence is retained."
            )
        for progress in result["progress"]:
            if progress["status"] == "CHECKING":
                progress["status"] = "CANCELLED" if status == "cancelled" else "INCOMPLETE"
        result.update(
            analyze(
                target.value,
                list(profiles.values()),
                evidence,
                result["web_results"],
                request.collect_contacts,
            )
        )
        result["summary"] = {
            "platforms_checked": len(
                {
                    item["platform"]
                    for item in result["results"]
                    if item["status"] not in (Status.UNSUPPORTED.value, Status.API_REQUIRED.value)
                }
            ),
            "profiles": len(profiles),
            "verified_profiles": len(profiles),
            "possible_matches": len(result["web_results"]),
            "evidence": len(evidence),
            "public_urls": len({link.destination for profile in profiles.values() for link in profile.links}),
        }
        result["limitations"] = [
            "Public source verification does not establish identity.",
            "Unavailable and restricted sources are not negative existence findings.",
            "Collection is bounded and may be incomplete. Cached observations retain their original timestamps.",
            "Search snippets remain unverified references even when a linked profile is independently collected.",
        ]
        save(status)
        self.store.audit("investigation." + status, investigation_id)
        return self.store.get_investigation(investigation_id)

    async def investigate(self, request):
        self.validate(request)
        record = self.store.create_investigation(request)
        return await self.run(record["id"])
