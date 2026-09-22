import base64
import csv
import io
import json

import pytest
from socialintel.models import AttachmentRequest, CaseCreate, CaseUpdate, InvestigationRequest, now
from socialintel.reports import DISCLAIMER, render_report, safe_cell
from socialintel.storage import Evidence, digest


def add_observation(store, case_id, value="Synthetic fixture"):
    return store.add_evidence(
        case_id,
        None,
        {
            "platform": "user-export",
            "field": "bio",
            "value": value,
            "source_url": "https://example.org/",
            "collected_at": now(),
            "method": "USER EXPORT",
            "verification": "USER-PROVIDED — NOT INDEPENDENTLY VERIFIED",
            "confidence": "UNVERIFIED",
            "provider": "user-export",
            "notes": "Synthetic test",
        },
    )


def test_case_evidence_integrity_and_tamper_detection(store):
    case = store.create_case(CaseCreate(name="Synthetic case", tags=[" research ", "research"]))
    assert case["tags"] == ["research"]
    item = add_observation(store, case["id"])
    assert store.get_evidence(item["id"])["integrity_valid"]
    with store.session() as session:
        row = session.get(Evidence, item["id"])
        row.body = {**row.body, "value": "Changed"}
    assert not store.get_evidence(item["id"])["integrity_valid"]


def test_case_deletion_cascades_and_clears_cache(store):
    case = store.create_case(CaseCreate(name="Synthetic"))
    evidence = add_observation(store, case["id"])
    store.cache_set("fixture", {"value": "cached"})
    store.attach(
        case["id"],
        AttachmentRequest(
            filename="../../ignored.png", data_base64=base64.b64encode(b"\x89PNG\r\n\x1a\nfixture").decode()
        ),
    )
    store.delete_case(case["id"])
    with pytest.raises(KeyError):
        store.get_evidence(evidence["id"])
    assert store.cache_get("fixture") is None
    assert not store.cases()


def test_cannot_delete_running_case(store):
    record = store.create_investigation(InvestigationRequest(target="example"))
    with pytest.raises(ValueError, match="Cancel"):
        store.delete_case(record["case_id"])


def test_archived_case_requires_reopening(store):
    case = store.create_case(CaseCreate(name="Synthetic"))
    store.update_case(case["id"], CaseUpdate(status="archived"))
    with pytest.raises(ValueError, match="Reopen"):
        store.create_investigation(InvestigationRequest(target="example", case_id=case["id"]))


def test_rejects_html_disguised_as_screenshot(store):
    case = store.create_case(CaseCreate(name="Synthetic"))
    with pytest.raises(ValueError):
        store.attach(
            case["id"],
            AttachmentRequest(
                filename="image.png", data_base64=base64.b64encode(b"<script>alert(1)</script>").decode()
            ),
        )


def test_report_formats_escape_untrusted_data(store):
    case = store.create_case(CaseCreate(name='<script>alert("x")</script>'))
    add_observation(store, case["id"], '=HYPERLINK("https://attacker.example")\n<script>alert(1)</script>')
    rendered, mime = render_report(store, case["id"], "html")
    assert mime == "text/html" and "<script>" not in rendered and "&lt;script&gt;" in rendered
    assert DISCLAIMER in rendered
    markdown, _ = render_report(store, case["id"], "md")
    assert "<script>" not in markdown
    structured, _ = render_report(store, case["id"], "json")
    assert json.loads(structured)["evidence"][0]["verification"].startswith("USER-PROVIDED")
    output, _ = render_report(store, case["id"], "csv")
    rows = list(csv.DictReader(io.StringIO(output)))
    assert rows[0]["value"].startswith("'=")


@pytest.mark.parametrize(
    "value", ["=formula", " +formula", "-1+2", "@SUM(1)", "\tformula", "\rformula", "\n=formula"]
)
def test_csv_formula_prefix(value):
    assert safe_cell(value).startswith("'")


def test_digests_are_stable_and_retention_is_dry_run_by_default(store):
    assert digest({"a": 1, "b": 2}) == digest({"b": 2, "a": 1})
    case = store.create_case(CaseCreate(name="Synthetic"))
    assert store.prune(1)["applied"] is False
    assert store.get_case(case["id"])
