"""Portable reports that preserve sources, uncertainty, and evidence checksums."""

import csv
import html
import io
import json
import re
from datetime import UTC, datetime

DISCLAIMER = (
    "This report contains information collected from publicly accessible sources. "
    "Correlations are analytical indicators and should not be treated as confirmed identity without independent verification."
)


def report_data(store, case_id):
    case = store.get_case(case_id)
    investigations = [store.get_investigation(item["id"]) for item in case["investigations"]]
    evidence = store.evidence(case_id=case_id, limit=10000)
    return {
        "format_version": "1.0",
        "generated_at": datetime.now(UTC).isoformat(),
        "disclaimer": DISCLAIMER,
        "case": case,
        "investigations": investigations,
        "evidence": evidence["items"],
        "export_limits": {
            "investigations_included": len(investigations),
            "maximum_investigations": 100,
            "evidence_total": evidence["total"],
            "evidence_included": len(evidence["items"]),
        },
        "integrity_note": "SHA-256 detects changes relative to this stored digest. It does not prove source authenticity or legal chain of custody.",
        "attachment_note": "Screenshot metadata and hashes are included; download original files separately. User-provided material is unverified.",
    }


def safe_cell(value):
    text = (
        json.dumps(value, ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    return (
        "'" + text
        if text.lstrip().startswith(("=", "+", "-", "@", "\t", "\r")) or text.startswith(("\t", "\r", "\n"))
        else text
    )


def md(value):
    text = (
        json.dumps(value, ensure_ascii=False)
        if isinstance(value, (dict, list))
        else str(value if value is not None else "")
    )
    text = html.escape(text).replace("\n", " ").replace("\r", " ")
    return re.sub(r"([\\`*_{}\[\]()#+.!|>~-])", r"\\\1", text)


def render_report(store, case_id, format="html"):
    data = report_data(store, case_id)
    if format == "json":
        return json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False), "application/json"
    if format == "csv":
        output = io.StringIO(newline="")
        writer = csv.writer(output)
        keys = [
            "id",
            "case_id",
            "investigation_id",
            "platform",
            "field",
            "value",
            "source_url",
            "collected_at",
            "method",
            "verification",
            "confidence",
            "provider",
            "notes",
            "sha256",
        ]
        writer.writerow(keys)
        for item in data["evidence"]:
            writer.writerow([safe_cell(item.get(key)) for key in keys])
        return output.getvalue(), "text/csv"
    if format == "md":
        lines = [
            f"# {md(data['case']['name'])}",
            "",
            DISCLAIMER,
            "",
            f"Generated: {md(data['generated_at'])}",
            "",
            "## Scope and research notes",
            "",
            md(data["case"]["purpose"]),
            "",
            md(data["case"]["notes"]),
        ]
        for run in data["investigations"]:
            result = run["result"]
            lines += [
                "",
                "## Investigation",
                "",
                f"Target: {md(run['request']['target'])}",
                "",
                f"Mode: {md(run['request']['mode'])} · Status: {md(run['status'])}",
                "",
                "| Platform | Status | Source | Limitation |",
                "| --- | --- | --- | --- |",
            ]
            for item in result.get("results", []):
                lines.append(
                    "| "
                    + " | ".join(
                        md(item.get(key, "")) for key in ("platform", "status", "source_url", "reason")
                    )
                    + " |"
                )
            lines += ["", "### Correlations", ""]
            for correlation in result.get("correlations", []):
                lines.append(
                    f"- {md(correlation['level'])}: {md(correlation['reasoning'])}; evidence {md(correlation['evidence_ids'])}"
                )
            lines += ["", "### Timeline", ""]
            lines += [
                f"- {md(item['at'])} · {md(item['platform'])} · {md(item['text'])} · {md(item['url'])}"
                for item in result.get("timeline", [])
            ]
            lines += ["", "### Limitations", "", md(result.get("limitation", ""))]
            lines += [f"- {md(value)}" for value in result.get("limitations", [])]
        lines += [
            "",
            "## Attributed evidence",
            "",
            "| ID | Field | Value | Source | Collected | Verification |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
        for item in data["evidence"]:
            lines.append(
                "| "
                + " | ".join(
                    md(item.get(key, ""))
                    for key in ("id", "field", "value", "source_url", "collected_at", "verification")
                )
                + " |"
            )
        lines += [
            "",
            data["integrity_note"],
            "",
            data["attachment_note"],
            "",
            "Export coverage: " + md(data["export_limits"]),
        ]
        return "\n".join(lines), "text/markdown"
    if format != "html":
        raise ValueError("Supported reports: html, md, json, csv.")

    def esc(value):
        return html.escape(str(value if value is not None else ""), quote=True)

    sections = []
    for run in data["investigations"]:
        result = run["result"]
        rows = "".join(
            f"<tr><td>{esc(item['platform'])}</td><td>{esc(item['status'])}</td><td>{esc(item['reason'])}</td></tr>"
            for item in result.get("results", [])
        )
        correlations = "".join(
            f"<li><strong>{esc(item['level'])}</strong> · {esc('; '.join(item['reasoning']))}<br><small>Evidence: {esc(', '.join(item['evidence_ids']))}</small></li>"
            for item in result.get("correlations", [])
        )
        timeline = "".join(
            f"<li>{esc(item['at'])} · {esc(item['platform'])}<p>{esc(item['text'])}</p><code>{esc(item['url'])}</code></li>"
            for item in result.get("timeline", [])
        )
        sections.append(
            f"<section><h2>{esc(run['request']['target'])}</h2><p>{esc(run['request']['mode'])} · {esc(run['status'])} · {esc(run['started_at'])}</p>"
            f"<h3>Platforms checked</h3><table><thead><tr><th>Platform</th><th>Result</th><th>Reason</th></tr></thead><tbody>{rows}</tbody></table>"
            f"<h3>Correlation analysis</h3><ul>{correlations or '<li>No supported correlations.</li>'}</ul>"
            f"<h3>Public timeline</h3><ul>{timeline or '<li>No public events collected.</li>'}</ul>"
            f"<h3>Limitations</h3><p>{esc(result.get('limitation', ''))}</p><ul>"
            + "".join(f"<li>{esc(value)}</li>" for value in result.get("limitations", []))
            + "</ul></section>"
        )
    observations = "".join(
        f"<article><header><strong>{esc(item['field'])}</strong><small>{esc(item['platform'])} · {esc(item['verification'])}</small></header>"
        f"<pre>{esc(json.dumps(item['value'], ensure_ascii=False, indent=2) if isinstance(item['value'], (dict, list)) else item['value'])}</pre>"
        f"<p>Source: <code>{esc(item['source_url'])}</code></p><p>{esc(item['collected_at'])} · {esc(item['method'])} · {esc(item['provider'])}</p>"
        f"<small>{esc(item['id'])}<br>SHA-256: {esc(item['sha256'])}</small></article>"
        for item in data["evidence"]
    )
    return (
        f"""<!doctype html><html lang="en"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(data["case"]["name"])} · SocialIntel report</title><style>
body{{font:15px/1.6 system-ui,sans-serif;color:#17232e;background:#f2f5f8;margin:0;padding:40px}}main{{max-width:1040px;margin:auto}}
h1{{font-size:36px;letter-spacing:-1px}}h2{{margin-top:36px}}small{{display:block;color:#506274}}section,article{{padding:24px;background:white;border:1px solid #dce3ea;border-radius:12px;margin:16px 0}}
table{{width:100%;border-collapse:collapse}}td,th{{padding:10px;border-bottom:1px solid #dde4eb;text-align:left;vertical-align:top}}pre,code{{white-space:pre-wrap;overflow-wrap:anywhere;font-size:12px}}p{{overflow-wrap:anywhere}}
.notice{{border-left:4px solid #117e94;padding:16px;background:#e8f4f7}}@media(max-width:600px){{body{{padding:14px}}section,article{{padding:14px}}table{{font-size:12px}}}}@media print{{body{{background:white;padding:0}}article{{break-inside:avoid}}}}
</style><main><p>SOCIALINTEL / PUBLIC-SOURCE RESEARCH</p><h1>{esc(data["case"]["name"])}</h1><p>{esc(data["generated_at"])}</p>
<p class="notice">{DISCLAIMER}</p><h2>Scope and research notes</h2><p>{esc(data["case"]["purpose"])}</p><p>{esc(data["case"]["notes"])}</p>
{"".join(sections)}<h2>Evidence and sources</h2>{observations}<section><h2>Report integrity and coverage</h2><p>{esc(data["integrity_note"])}</p><p>{esc(data["attachment_note"])}</p><code>{esc(data["export_limits"])}</code></section></main></html>""",
        "text/html",
    )
