"""Command-line client of the same local investigation engine used by the API."""

import asyncio
import json
import secrets
import sys
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import Settings
from .engine import Engine
from .models import CaseCreate, CaseUpdate, InvestigationRequest
from .providers import Registry
from .reports import render_report
from .storage import Store

app = typer.Typer(help="SocialIntel · attributed public-source investigations", no_args_is_help=False)
cases = typer.Typer(help="Create, review, archive, and delete local cases.")
platform = typer.Typer(help="Provider capabilities and last observed health.")
app.add_typer(cases, name="case")
app.add_typer(platform, name="platform")
console = Console(highlight=False)


def resources():
    settings = Settings()
    return settings, Store(settings.data_dir)


def print_result(record, json_output=False):
    if json_output:
        typer.echo(json.dumps(record, indent=2, ensure_ascii=False))
        return
    console.print(
        f"Case: {record['case_id']}\nInvestigation: {record['id']} · {record['status']}", markup=False
    )
    table = Table("Platform", "Identifier", "Status", "Source / limitation")
    for item in record["result"].get("results", []):
        table.add_row(
            item["platform"], item["target"], item["status"], item.get("source_url") or item["reason"]
        )
    console.print(table)
    console.print("Verified public sources are candidate profiles, not verified identities.")
    if record["result"].get("limitation"):
        console.print(record["result"]["limitation"], markup=False)


def execute(request, json_output=False):
    async def run():
        settings, store = resources()
        engine = Engine(settings, store)
        try:
            return await engine.investigate(request)
        finally:
            await engine.close()
            store.engine.dispose()

    try:
        record = asyncio.run(run())
        print_result(record, json_output)
        if record["status"] == "failed":
            raise typer.Exit(1)
    except ValueError as error:
        typer.echo(f"Invalid request: {error}", err=True)
        raise typer.Exit(2) from None


@app.callback(invoke_without_command=True)
def main(ctx: typer.Context):
    if ctx.invoked_subcommand:
        return
    if not sys.stdin.isatty():
        typer.echo(ctx.get_help())
        return
    console.print("\nSOCIALINTEL\nPublic-source investigation framework\n")
    registry = Registry(Settings())
    options = list(registry.providers.values())
    for index, provider in enumerate(options, 1):
        console.print(f"{index:02d}  {provider.manifest.name} · {provider.manifest.status}", markup=False)
    console.print("99  All Platforms")
    selection = typer.prompt("SELECT PLATFORM", type=int)
    if selection != 99 and not 1 <= selection <= len(options):
        raise typer.BadParameter("Choose a listed platform.")
    selected = "all" if selection == 99 else options[selection - 1].manifest.platform
    target = typer.prompt("TARGET · username, ID, public URL, or display name")
    console.print("1  Platform only\n2  Platform + automatic fallback (recommended)\n3  Full discovery")
    mode = typer.prompt("Search mode", default=2, type=int)
    if mode not in (1, 2, 3):
        raise typer.BadParameter("Mode must be 1, 2, or 3.")
    execute(
        InvestigationRequest(
            target=target,
            platform=selected,
            mode="discovery" if selected == "all" else {1: "selected", 2: "fallback", 3: "discovery"}[mode],
        )
    )


@app.command()
def platforms(json_output: bool = typer.Option(False, "--json")):
    """Show implemented features and honest provider limitations."""
    settings = Settings()
    catalog = Registry(settings).catalog(settings)
    if json_output:
        typer.echo(json.dumps(catalog, indent=2))
        return
    table = Table("Platform", "Configured", "Status", "Capabilities")
    for item in catalog:
        table.add_row(
            item["name"],
            "Yes" if item["configured"] else "No",
            item["status"],
            ", ".join(item["capabilities"]) or "Unsupported",
        )
    console.print(table)


@app.command()
def investigate(
    platform: str,
    target: str | None = None,
    all_platforms: bool = typer.Option(False, "--all"),
    fallback: bool = typer.Option(True, "--fallback/--no-fallback"),
    search_engine: str = typer.Option("none", "--search-engine"),
    case_id: str | None = typer.Option(None, "--case"),
    posts: bool = False,
    follow_links: bool = False,
    variants: bool = False,
    refresh: bool = False,
    target_type: str = "auto",
    json_output: bool = typer.Option(False, "--json"),
):
    """Investigate one platform; automatic fallback is the default."""
    if all_platforms and target is None:
        platform, target = "all", platform
    if target is None:
        raise typer.BadParameter("Provide PLATFORM TARGET, or --all TARGET.")
    try:
        request = InvestigationRequest(
            target=target,
            platform="all" if all_platforms else platform,
            mode="discovery" if all_platforms else "fallback" if fallback else "selected",
            case_id=case_id,
            search_engine=search_engine,
            collect_posts=posts,
            follow_links=follow_links,
            variants=variants,
            refresh=refresh,
            target_type=target_type,
        )
    except ValueError:
        raise typer.BadParameter("Invalid mode, target type, or search engine.") from None
    execute(request, json_output)


@app.command()
def search(target: str, search_engine: str = "none", json_output: bool = typer.Option(False, "--json")):
    """Check a username across configured public providers."""
    execute(
        InvestigationRequest(target=target, platform="all", mode="discovery", search_engine=search_engine),
        json_output,
    )


@app.command()
def discover(
    target: str,
    search_engine: str = "none",
    follow_links: bool = False,
    variants: bool = False,
    json_output: bool = typer.Option(False, "--json"),
):
    """Full discovery, with optional bounded public-link traversal and variants."""
    execute(
        InvestigationRequest(
            target=target,
            platform="all",
            mode="discovery",
            search_engine=search_engine,
            follow_links=follow_links,
            variants=variants,
        ),
        json_output,
    )


@cases.command("create")
def case_create(name: str = typer.Option("Untitled investigation", prompt=True), purpose: str = ""):
    _, store = resources()
    typer.echo(json.dumps(store.create_case(CaseCreate(name=name, purpose=purpose)), indent=2))


@cases.command("list")
def case_list():
    _, store = resources()
    typer.echo(json.dumps(store.cases(), indent=2))


@cases.command("show")
def case_show(case_id: str):
    _, store = resources()
    typer.echo(json.dumps(store.get_case(case_id), indent=2))


@cases.command("archive")
def case_archive(case_id: str):
    _, store = resources()
    store.update_case(case_id, CaseUpdate(status="archived"))
    typer.echo("Case archived.")


@cases.command("delete")
def case_delete(case_id: str, yes: bool = typer.Option(False, "--yes")):
    _, store = resources()
    store.get_case(case_id)
    if not yes:
        typer.confirm("Permanently delete this case, evidence, and screenshots?", abort=True)
    store.delete_case(case_id)
    typer.echo("Case deleted; shared result cache cleared.")


@platform.command("health")
def platform_health():
    settings, store = resources()
    typer.echo(
        json.dumps(
            {
                "catalog": Registry(settings).catalog(settings),
                "observed": store.health(),
                "note": "Configuration and last observed request; no background polling or live network probe.",
            },
            indent=2,
        )
    )


@app.command()
def report(case_id: str, format: str = "html", output: Path | None = None):
    """Export an attributed HTML, Markdown, JSON, or CSV report."""
    _, store = resources()
    content, _ = render_report(store, case_id, format)
    path = output or Path(f"{case_id}.{format}")
    if path.exists():
        raise typer.BadParameter("Output exists. Choose another --output path.")
    path.write_text(content, encoding="utf-8")
    typer.echo(str(path.resolve()))


@app.command()
def compare(before: str, after: str):
    """Compare two manually collected snapshots of the same target."""
    from .analytics import compare as compare_runs

    _, store = resources()
    typer.echo(
        json.dumps(compare_runs(store.get_investigation(before), store.get_investigation(after)), indent=2)
    )


@app.command()
def verify(evidence_id: str):
    """Check an evidence item's stored SHA-256 digest."""
    _, store = resources()
    item = store.get_evidence(evidence_id)
    typer.echo(
        json.dumps({"id": item["id"], "integrity_valid": item["integrity_valid"], "sha256": item["sha256"]})
    )
    if not item["integrity_valid"]:
        raise typer.Exit(1)


@app.command()
def retention(days: int = 90, apply: bool = False):
    """Preview deletion of old archived cases; --apply performs it."""
    _, store = resources()
    typer.echo(json.dumps(store.prune(days, apply), indent=2))


@app.command()
def serve(host: str = "127.0.0.1", port: int = 8000):
    """Run the authenticated local dashboard and API (one worker)."""
    import uvicorn

    from .api import create_app

    settings = Settings()
    if host not in ("127.0.0.1", "localhost", "::1") and not settings.token:
        raise typer.BadParameter(
            "Remote binding requires a strong SOCIALINTEL_API_TOKEN and configured allowed hosts."
        )
    generated_token = not settings.token
    settings.token = settings.token or secrets.token_urlsafe(32)
    application = create_app(settings)
    display_host = "127.0.0.1" if host == "0.0.0.0" else f"[{host}]" if ":" in host else host
    if generated_token:
        typer.echo(f"Open this private session link: http://{display_host}:{port}/#token={settings.token}")
        typer.echo("Treat the link as a password. Public sources only. Press Ctrl+C to stop.")
    else:
        typer.echo(f"Open http://{display_host}:{port}/ and enter your configured API token.")
        typer.echo("Public sources only. Press Ctrl+C to stop.")
    uvicorn.run(application, host=host, port=port, access_log=False, workers=1)
