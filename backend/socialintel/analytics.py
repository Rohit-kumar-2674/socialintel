"""Explainable profile correlations, attributed graph edges, and observed changes."""

import re
from difflib import SequenceMatcher
from itertools import combinations
from urllib.parse import urlsplit

from .discovery import entities
from .models import Verification


def canonical(url):
    parsed = urlsplit(url)
    return ((parsed.hostname or "").removeprefix("www.") + parsed.path.rstrip("/")).lower()


def value(profile, name):
    return str(profile.fields[name].value) if name in profile.fields else ""


def correlate(profiles, evidence):
    correlations = []
    for a, b in combinations(profiles, 2):
        if a.platform == "website" or b.platform == "website":
            continue
        username = round(100 * SequenceMatcher(None, a.username.lower(), b.username.lower()).ratio())
        bios = (value(a, "bio"), value(b, "bio"))
        # Bounded token overlap avoids quadratic comparisons of untrusted long bios.
        tokens = [set(re.findall(r"\w+", bio[:4000].casefold())[:512]) for bio in bios]
        similarity = round(100 * len(tokens[0] & tokens[1]) / len(tokens[0] | tokens[1])) if all(tokens) else None
        cross = [
            link
            for link in a.links + b.links
            if (
                canonical(link.source_url) == canonical(a.url)
                and canonical(link.destination) == canonical(b.url)
            )
            or (
                canonical(link.source_url) == canonical(b.url)
                and canonical(link.destination) == canonical(a.url)
            )
        ]
        shared = sorted(
            {canonical(link.destination) for link in a.links}
            & {canonical(link.destination) for link in b.links}
        )
        same_name = (
            bool(value(a, "display_name"))
            and value(a, "display_name").casefold() == value(b, "display_name").casefold()
        )
        reasons = []
        if username == 100:
            reasons.append("Exact username; this alone does not establish identity.")
        if cross:
            reasons.append("A public profile explicitly links to the other profile.")
        if shared:
            reasons.append("Shared public links: " + ", ".join(shared[:3]) + "; shared links can be generic.")
        if same_name:
            reasons.append("Matching public display name.")
        if similarity is not None and similarity >= 70:
            reasons.append("Similar public biography text (heuristic text similarity).")
        if not reasons:
            continue
        level = "HIGH" if cross else "MEDIUM" if shared and same_name else "LOW"
        refs = [
            item["id"]
            for item in evidence
            if item.get("profile_id") in {a.id, b.id}
            and item.get("field") in {"username", "display_name", "bio", "public_link"}
        ]
        correlations.append(
            {
                "profile_a": a.id,
                "profile_b": b.id,
                "username_match": username,
                "profile_similarity": similarity,
                "cross_link_count": len(cross),
                "level": level,
                "reasoning": reasons,
                "evidence_ids": refs,
                "verification": Verification.INFERENCE.value,
                "interpretation": "Profile correlation only. Scores measure signals, not the probability of a shared identity.",
            }
        )
    return correlations


def analyze(target, profiles, evidence, web_results, contacts=False):
    nodes, edges, timeline, extracted = [], [], [], []
    nodes.append({"data": {"id": "target", "label": target, "type": "TARGET"}})
    node_ids = {"target"}

    def node(node_id, label, kind, **extra):
        if node_id not in node_ids:
            nodes.append({"data": {"id": node_id, "label": label, "type": kind, **extra}})
            node_ids.add(node_id)

    def edge(source, destination, kind, refs, source_url):
        if refs:
            edges.append(
                {
                    "data": {
                        "id": f"edge-{len(edges)}",
                        "source": source,
                        "target": destination,
                        "label": kind,
                        "evidence_ids": refs,
                        "source_url": source_url,
                    }
                }
            )

    profile_urls = {canonical(profile.url): profile.id for profile in profiles}
    for profile in profiles:
        refs = [item for item in evidence if item.get("profile_id") == profile.id]
        node(
            profile.id,
            f"{profile.platform} · {profile.username}",
            "WEBSITE" if profile.platform == "website" else "SOCIAL PROFILE",
            url=profile.url,
        )
        usernames = [item["id"] for item in refs if item["field"] == "username"]
        edge(
            "target",
            profile.id,
            "EXACT_USERNAME" if profile.username.casefold() == target.casefold() else "CANDIDATE_PROFILE",
            usernames,
            profile.url,
        )
        for link in profile.links:
            destination = profile_urls.get(canonical(link.destination), "url:" + link.destination)
            if destination not in profile_urls.values():
                node(
                    destination,
                    urlsplit(link.destination).hostname or link.destination,
                    "WEBSITE",
                    url=link.destination,
                )
            link_refs = [
                item["id"]
                for item in refs
                if item["field"] == "public_link" and item["value"] == link.destination
            ]
            edge(
                profile.id,
                destination,
                "EXPLICIT_CROSS_LINK" if destination in profile_urls.values() else "PUBLIC_BIO_LINK",
                link_refs,
                link.source_url,
            )
        for post in profile.posts:
            post_refs = [
                item["id"]
                for item in refs
                if item["field"] == "public_post" and item["source_url"] == post.url
            ]
            if post.published_at:
                timeline.append(
                    {
                        "id": f"{profile.id}:{post.id}",
                        "at": post.published_at,
                        "platform": profile.platform,
                        "type": post.kind,
                        "text": post.text,
                        "url": post.url,
                        "evidence_ids": post_refs,
                    }
                )
            extracted += entities(post.text, post.url, contacts)
        extracted += entities(value(profile, "bio"), profile.url, contacts)
        for field in ("organization", "location", "public_author"):
            if field in profile.fields:
                extracted.append(
                    {
                        "type": field.upper(),
                        "value": profile.fields[field].value,
                        "source_url": profile.fields[field].source_url,
                        "basis": "SOURCE-PROVIDED FIELD",
                    }
                )
    for index, result in enumerate(web_results):
        result_id = f"search:{index}"
        node(
            result_id,
            result["title"] or result["url"],
            "SEARCH RESULT",
            url=result["url"],
            verification=result["verification"],
        )
        refs = [
            item["id"]
            for item in evidence
            if item["field"] == "search_reference" and item["value"].get("url") == result["url"]
        ]
        edge("target", result_id, "DISCOVERED_VIA_SEARCH", refs, result["source_url"])
        if canonical(result["url"]) in profile_urls:
            edge(
                result_id,
                profile_urls[canonical(result["url"])],
                "CANDIDATE_VERIFIED_AT_SOURCE",
                refs,
                result["url"],
            )
    return {
        "correlations": correlate(profiles, evidence),
        "timeline": sorted(timeline, key=lambda item: item["at"], reverse=True),
        "graph": {"nodes": nodes, "edges": edges},
        "entities": extracted[:500],
    }


def compare(before, after):
    if before["request"]["target"].casefold() != after["request"]["target"].casefold():
        raise ValueError("Compare investigations of the same target.")

    def profiles(run):
        return {
            item["profile"]["id"]: item["profile"]
            for item in run["result"].get("results", [])
            if item.get("profile")
        }

    old, new = profiles(before), profiles(after)
    changes = []
    for key, profile in new.items():
        if key not in old:
            changes.append(
                {
                    "type": "NEW PUBLIC PROFILE OBSERVATION",
                    "profile": profile["url"],
                    "note": "New to these results; this does not establish when the account was created.",
                }
            )
            continue
        for name, field in profile["fields"].items():
            previous = old[key]["fields"].get(name)
            if previous and previous["value"] != field["value"]:
                changes.append(
                    {
                        "type": "PUBLIC FIELD CHANGED",
                        "field": name,
                        "profile": profile["url"],
                        "before": previous["value"],
                        "after": field["value"],
                        "sources": [previous["source_url"], field["source_url"]],
                    }
                )
        old_links = {link["destination"] for link in old[key]["links"]}
        for link in profile["links"]:
            if link["destination"] not in old_links:
                changes.append(
                    {"type": "NEW PUBLIC LINK", "profile": profile["url"], "url": link["destination"]}
                )
    for key, profile in old.items():
        if key not in new:
            changes.append(
                {
                    "type": "NOT OBSERVED IN THIS RUN",
                    "profile": profile["url"],
                    "note": "Absence does not establish account removal; inspect provider status and scope.",
                }
            )
    return {
        "before": before["id"],
        "after": after["id"],
        "changes": changes,
        "limitation": "Manual snapshot comparison. Collection scope, cache age, and provider availability may differ; no cause is inferred.",
    }
