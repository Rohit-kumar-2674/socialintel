from urllib.parse import urlsplit
from urllib.robotparser import RobotFileParser

from bs4 import BeautifulSoup

from ..models import Manifest, Status
from ..security import RetrievalError, safe_url
from .base import PlatformAdapter, plain, public_links


class Website(PlatformAdapter):
    manifest = Manifest(
        name="Public website",
        platform="website",
        domains=[],
        status="EXPERIMENTAL",
        capabilities=["profile", "links", "metadata"],
        methods=["PUBLIC WEBPAGE"],
        limitations="Bounded HTTPS HTML pages only. Honors robots.txt; declines redirects, logins, bot challenges, and compressed responses. No JavaScript, paywall recovery, hidden metadata, or recursive scraping.",
        documentation_url="https://www.rfc-editor.org/rfc/rfc9309",
    )

    async def get_public_profile(self, target, ctx):
        if target.kind != "url":
            raise RetrievalError(
                Status.UNSUPPORTED, "The website adapter needs an explicit public HTTPS URL."
            )
        if ctx.budget.pages >= ctx.request.limits.max_pages:
            raise RetrievalError(Status.LIMITED, "Public webpage limit reached.")
        url = safe_url(target.value)
        host = urlsplit(url).hostname
        origin = f"https://{urlsplit(url).netloc}"
        ctx.budget.pages += 1
        robots = await ctx.network.get(f"{origin}/robots.txt", ctx.budget, hosts={host})
        if robots.status != 404:
            robot = RobotFileParser()
            robot.parse(robots.text().splitlines())
            if not robot.can_fetch("SocialIntel", url):
                raise RetrievalError(Status.LIMITED, "Collection disallowed by the site's robots.txt.")
            delay = robot.crawl_delay("SocialIntel") or robot.crawl_delay("*") or 1
            if delay > 30:
                raise RetrievalError(
                    Status.LIMITED, "Site crawl delay exceeds this investigation's collection window."
                )
        else:
            delay = 1
        response = await ctx.network.get(url, ctx.budget, hosts={host}, interval=max(1, delay))
        if response.status == 404:
            return None
        if "text/html" not in response.headers.get("content-type", "").lower():
            raise RetrievalError(Status.UNSUPPORTED, "Only ordinary public HTML pages are supported.")
        soup = BeautifulSoup(response.text(), "html.parser")
        if soup.select_one('input[type="password"], .g-recaptcha, .h-captcha, #challenge-form'):
            raise RetrievalError(Status.LIMITED, "Login or challenge page encountered; collection stopped.")
        # No hidden script data, JSON-LD, or arbitrary server metadata is parsed.
        for node in soup.select("script, style, noscript, template, [hidden], [aria-hidden=true]"):
            node.decompose()
        meta = {}
        for node in soup.select("meta[name], meta[property]")[:100]:
            key = node.get("name") or node.get("property")
            if key in {
                "description",
                "author",
                "og:title",
                "og:description",
                "og:site_name",
                "og:type",
                "og:image",
            }:
                meta[key] = plain(node.get("content", ""))
        data = {
            "display_name": plain(soup.title.get_text()) if soup.title else host,
            "bio": meta.get("description") or meta.get("og:description"),
            "domain": host,
            "public_author": meta.get("author"),
            "organization": meta.get("og:site_name"),
            **{key: value for key, value in meta.items() if key.startswith("og:")},
        }
        profile = self.profile(host, url, data, response.url, account_id=url, method="PUBLIC WEBPAGE")
        profile.links = public_links(str(soup), url, html=True)
        return profile
