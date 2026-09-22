# Provider capability matrix

Generated from the built-in manifests for v0.1.0. Readiness is not a live availability guarantee.

| Platform | Readiness | Capabilities | Requirements | Limitations |
| --- | --- | --- | --- | --- |
| GitHub | EXPERIMENTAL | profile, links, statistics, posts, timeline | None | Unauthenticated public profiles and public repositories only. Repository updates are not social posts. No private data or numeric-ID resolution. |
| Bluesky | EXPERIMENTAL | profile, links, statistics, posts, timeline | None | Public AppView data only. Bare usernames are tried as username.bsky.social. Custom handles and DIDs are accepted; no identity resolution. |
| Reddit | API REQUIRED | profile, links, statistics, posts, timeline | REDDIT_ACCESS_TOKEN, REDDIT_USER_AGENT | Requires approved Reddit API access and an operator-supplied OAuth token. Only posts explicitly marked as belonging to public communities are collected. No token acquisition or private community access. |
| Mastodon | API REQUIRED | profile, links, statistics, posts, timeline, media | MASTODON_ACCESS_TOKEN | Queries one configured instance; not a search of the federation. Requires read:accounts (and read:statuses for posts). Locked accounts are not collected; only visibility=public statuses are retained. |
| YouTube | API REQUIRED | profile, links, statistics | YOUTUBE_API_KEY | Public channel metadata and visible statistics through Data API v3. Handles, channel IDs, and legacy /user/ URLs supported. Video collection is not implemented. Subscriber counts may be rounded by YouTube. |
| Twitch | API REQUIRED | profile, links | TWITCH_CLIENT_ID, TWITCH_ACCESS_TOKEN | Public Helix profile fields with an app access token. Email, follower lists, subscriber data, live location, and deprecated view counts are never collected. Posts are not implemented. |
| Public website | EXPERIMENTAL | profile, links, metadata | None | Bounded HTTPS HTML pages only. Honors robots.txt; declines redirects, logins, bot challenges, and compressed responses. No JavaScript, paywall recovery, hidden metadata, or recursive scraping. |
| Instagram | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Facebook | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| X / Twitter | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Threads | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| TikTok | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Snapchat | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| LinkedIn | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Pinterest | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Tumblr | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Telegram | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Discord | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Patreon | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| OnlyFans | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Fansly | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| SoundCloud | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Spotify | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Steam | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Medium | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Quora | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Flickr | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| VK | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |
| Weibo | NOT IMPLEMENTED | **UNSUPPORTED BY THIS PROVIDER** | None | UNSUPPORTED BY THIS PROVIDER. No collection adapter is implemented. Public search may discover unverified URLs. Private, locked, paid, and authentication-only content is excluded. |

## Public web discovery

Brave requires `BRAVE_SEARCH_API_KEY`. Google Custom Search JSON requires `GOOGLE_SEARCH_API_KEY` and `GOOGLE_SEARCH_ENGINE_ID`; it is available only to existing customers until its documented service discontinuation on **2027-01-01**, after which this adapter refuses requests. Standalone Bing Search APIs retired on **2025-08-11** and remain **UNAVAILABLE**, with no replacement falsely advertised. The custom search adapter accepts an explicitly configured public HTTPS JSON endpoint and optional bearer token.

The custom response is `{ "results": [{ "url": "https://example.org/", "title": "Example", "description": "Public index snippet" }] }`; query parameters are `q` and `count`. No HTML scraping of Google/Bing search, cookies, or CAPTCHA bypass is implemented. Search snippets are always unverified references; finding a URL never makes its platform supported.

## Official references checked 2026-09-22

- [Google Custom Search JSON API](https://developers.google.com/custom-search/v1/overview)
- [Bing Search APIs retirement](https://learn.microsoft.com/en-us/lifecycle/announcements/bing-search-api-retirement)
- [GitHub REST API versions](https://docs.github.com/en/rest/about-the-rest-api/api-versions)

Other provider documentation URLs are included in each manifest and the dashboard. Experimental implementations are tested with synthetic fixtures; this release does not claim a successful live lookup against every upstream service.
