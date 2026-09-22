import { useState } from "react";
import {
  Check,
  Minus,
  Code2,
  Puzzle,
  Activity,
  Database,
  Trash2,
  RefreshCw,
  Download,
} from "lucide-react";
import { api, date, post } from "./api";
import type { Health, Platform, Settings } from "./types";
import {
  Badge,
  Empty,
  ErrorNote,
  Notice,
  PageTitle,
  Source,
  useData,
} from "./ui";

export function Platforms({
  platforms,
  health,
}: {
  platforms: Platform[];
  health: Record<string, Health>;
}) {
  const [filter, setFilter] = useState("");
  const [implemented, setImplemented] = useState(false);
  const [detail, setDetail] = useState<string | null>(null);
  const features = [
    "profile",
    "links",
    "statistics",
    "posts",
    "timeline",
    "media",
  ];
  return (
    <>
      <PageTitle
        eyebrow="CAPABILITIES, NOT PROMISES"
        title="Platform explorer"
        description="Every adapter declares what it supports. Unimplemented platforms remain visible and clearly labelled."
      />
      <div className="filter-bar">
        <input
          aria-label="Filter platforms"
          placeholder="Find a platform…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <label className="inline-check">
          <input
            type="checkbox"
            checked={implemented}
            onChange={(e) => setImplemented(e.target.checked)}
          />
          Implemented only
        </label>
      </div>
      <div className="panel table-wrap">
        <table className="capability-table">
          <thead>
            <tr>
              <th>Platform</th>
              <th>Readiness</th>
              <th>Last observation</th>
              {features.map((feature) => (
                <th key={feature}>{feature}</th>
              ))}
              <th>Details</th>
            </tr>
          </thead>
          <tbody>
            {platforms
              .filter(
                (item) =>
                  item.name.toLowerCase().includes(filter.toLowerCase()) &&
                  (!implemented || item.capabilities.length > 0),
              )
              .map((item) => (
                <tr key={item.platform}>
                  <td data-label="Platform">
                    <strong>{item.name}</strong>
                    <small>
                      {item.methods.join(" · ") || "No collection method"}
                    </small>
                  </td>
                  <td data-label="Readiness">
                    <Badge>
                      {item.configured ? "EXPERIMENTAL" : item.status}
                    </Badge>
                    <small>{item.configured ? "Configured" : "Not configured"}</small>
                  </td>
                  <td data-label="Last observation">
                    <Badge>{health[item.platform]?.status || "NOT CHECKED"}</Badge>
                    <small>{date(health[item.platform]?.checked_at)}</small>
                  </td>
                  {features.map((feature) => (
                    <td data-label={feature} key={feature}>
                      {item.capabilities.includes(feature) ? (
                        <Check
                          size={15}
                          className="supported"
                          aria-label="Supported"
                        />
                      ) : (
                        <Minus
                          size={15}
                          className="muted"
                          aria-label="Unsupported"
                        />
                      )}
                    </td>
                  ))}
                  <td data-label="Details">
                    <button
                      className="text-button"
                      onClick={() =>
                        setDetail(
                          detail === item.platform ? null : item.platform,
                        )
                      }
                    >
                      Capabilities
                    </button>
                    {detail === item.platform && (
                      <div className="capability-detail">
                        <p>{item.limitations}</p>
                        <p>{item.configuration_note}</p>
                        <Source
                          url={item.documentation_url}
                          label="Provider documentation"
                        />
                      </div>
                    )}
                  </td>
                </tr>
              ))}
          </tbody>
        </table>
      </div>
      <Notice>
        Configured means credentials are present, not that a live lookup
        succeeded. ONLINE reflects a recent observed request. Matching usernames
        do not establish identity.
      </Notice>
    </>
  );
}

export function HealthPage({
  platforms,
  health,
  refresh,
}: {
  platforms: Platform[];
  health: Record<string, Health>;
  refresh: () => void;
}) {
  return (
    <>
      <PageTitle
        eyebrow="SOURCE AVAILABILITY"
        title="Platform health"
        description="Configuration plus the last observed request. No background profile monitoring."
        actions={
          <button onClick={refresh}>
            <RefreshCw size={16} />
            Refresh observations
          </button>
        }
      />
      <div className="health-grid">
        {platforms
          .filter((item) => item.capabilities.length)
          .map((item) => {
            const observed = health[item.platform];
            return (
              <article className="panel health-card" key={item.platform}>
                <header>
                  <Activity size={19} />
                  <h2>{item.name}</h2>
                  <Badge>
                    {observed?.status ||
                      (item.configured ? "NOT CHECKED" : "API REQUIRED")}
                  </Badge>
                </header>
                <dl className="record-details">
                  <dt>Last observation</dt>
                  <dd>{date(observed?.checked_at)}</dd>
                  <dt>Last successful check</dt>
                  <dd>{date(observed?.last_successful_check)}</dd>
                  <dt>Response time</dt>
                  <dd>
                    {observed
                      ? `${observed.response_time_ms} ms`
                      : "Not measured"}
                  </dd>
                  <dt>Cooldown ends</dt>
                  <dd>
                    {observed?.retry_at
                      ? date(observed.retry_at)
                      : "No recorded cooldown"}
                  </dd>
                </dl>
                <p className="muted">
                  {observed?.reason || item.configuration_note}
                </p>
                <small>{item.limitations}</small>
              </article>
            );
          })}
      </div>
      <Notice>
        Health changes when an investigation uses a provider. Rate-limited
        providers retain their cooldown; refreshing this page does not retry or
        bypass it.
      </Notice>
    </>
  );
}

export function Plugins({
  platforms,
  revision,
}: {
  platforms: Platform[];
  revision: number;
}) {
  const { data, error } = useData<{
    errors: { entry_point: string; error: string }[];
  }>("/plugins", revision);
  const custom = platforms.filter((item) => item.plugin);
  function exportManifest(item: Platform) {
    const { configured, configuration_note, ...manifest } = item;
    void configured;
    void configuration_note;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(manifest, null, 2)], {
        type: "application/json",
      }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${item.platform}-provider.json`;
    anchor.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  }
  return (
    <>
      <PageTitle
        eyebrow="EXTEND THE FRAMEWORK"
        title="Provider plugins"
        description="A shared provider contract, explicit capabilities, and attributed public data."
      />
      <div className="panel sdk-banner">
        <Code2 size={36} />
        <div>
          <h2>Build an adapter. Keep the evidence contract.</h2>
          <p>
            Implement PlatformAdapter, declare a validated manifest, and route
            public HTTPS requests through the bounded retrieval client.
          </p>
          <code>SOCIALINTEL_PLUGINS=my_package.provider:create_provider</code>
        </div>
      </div>
      <Notice>
        Plugins are trusted local Python code, not a sandbox. Review and install
        packages on the server, configure the entry point, then restart. The
        dashboard cannot upload or execute extension code.
      </Notice>
      {error && <ErrorNote>{error}</ErrorNote>}
      {data?.errors.map((item) => (
        <ErrorNote key={item.entry_point}>
          {item.entry_point}: {item.error}
        </ErrorNote>
      ))}
      {!custom.length && (
        <Empty title="No external plugins loaded">
          Built-in adapters are ready below. The repository's
          docs/PROVIDER_SDK.md and plugins/example_provider show the complete
          extension contract.
        </Empty>
      )}
      <div className="panel">
        <div className="panel-heading">
          <h2>
            <Puzzle size={18} />
            Registered adapters
          </h2>
          <span className="muted">Manifest export</span>
        </div>
        <div className="plugin-list">
          {platforms
            .filter((item) => item.capabilities.length)
            .map((item) => (
              <div key={item.platform}>
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {item.plugin ? "External plugin" : "Built-in"} · v
                    {item.version} · {item.capabilities.join(", ")}
                  </small>
                </span>
                <button onClick={() => exportManifest(item)}>
                  <Download size={15} />
                  Manifest
                </button>
              </div>
            ))}
        </div>
      </div>
    </>
  );
}

export function SettingsPage({
  settings,
  revision,
  refresh,
  lock,
}: {
  settings: Settings;
  revision: number;
  refresh: () => void;
  lock: () => void;
}) {
  const [days, setDays] = useState(90);
  const [preview, setPreview] = useState<{
    case_ids: string[];
    applied: boolean;
    cutoff: string;
  } | null>(null);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const audit = useData<{ at: string; action: string; resource_id: string }[]>(
    "/audit",
    revision,
  );
  async function act(work: () => Promise<unknown>, success: string) {
    setBusy(true);
    setError("");
    try {
      await work();
      setMessage(success);
      refresh();
    } catch (error) {
      setError(String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="LOCAL WORKSPACE"
        title="Settings"
        description="Server configuration, retention, and session controls."
      />
      {error && <ErrorNote>{error}</ErrorNote>}
      {message && <Notice>{message}</Notice>}
      <div className="settings-grid">
        <section className="panel panel-body">
          <h2>
            <Database size={18} />
            Storage & privacy
          </h2>
          <p>{settings.storage}</p>
          <p className="muted">
            Use operating-system disk encryption for data at rest. Deletion
            removes active records and clears the result cache; backups and disk
            snapshots require separate management.
          </p>
          <dl className="record-details">
            <dt>Deployment</dt>
            <dd>Single operator / one server worker</dd>
            <dt>Version</dt>
            <dd>{settings.version}</dd>
            <dt>Mastodon instance</dt>
            <dd>{settings.mastodon_instance}</dd>
          </dl>
          <button
            disabled={busy}
            onClick={() =>
              void act(
                () => api("/cache", { method: "DELETE" }),
                "Cached observations cleared.",
              )
            }
          >
            <Trash2 size={15} />
            Clear public-result cache
          </button>
        </section>
        <section className="panel panel-body">
          <h2>Session & API</h2>
          <p className="muted">
            Your bearer token stays in this browser tab's session storage or
            memory. Provider credentials remain on the server.
          </p>
          <button onClick={lock}>Lock this workspace</button>
          <p>
            <a href="/docs" target="_blank" rel="noreferrer">
              Open API documentation ↗
            </a>
          </p>
          <small>
            Swagger uses its Authorize control for authenticated requests. Do
            not place tokens in query parameters.
          </small>
        </section>
      </div>
      <section className="panel panel-body">
        <h2>Provider credentials</h2>
        <p className="muted">
          Set environment variables before starting the server. This view only
          shows whether values are present.
        </p>
        <div className="credential-grid">
          {Object.entries(settings.credentials).map(([name, present]) => (
            <div key={name}>
              <code>{name}</code>
              <Badge>{present ? "Present" : "Not configured"}</Badge>
            </div>
          ))}
        </div>
        <h3>Search services</h3>
        {settings.search_engines.map((item) => (
          <div className="search-config" key={item.name}>
            <strong className="capitalize">{item.name}</strong>
            <p>{item.limitation}</p>
            <small>
              {item.requirements.join(" + ") || "No available integration"}
            </small>
          </div>
        ))}
      </section>
      <section className="panel panel-body">
        <h2>Data retention</h2>
        <p className="muted">
          Delete archived cases that have not been updated within your chosen
          period. Preview the affected cases first.
        </p>
        <div className="retention-controls">
          <label>
            OLDER THAN · DAYS
            <input
              type="number"
              min={1}
              max={36500}
              value={days}
              onChange={(e) => {
                setDays(Number(e.target.value));
                setPreview(null);
              }}
            />
          </label>
          <button
            disabled={busy || days < 1 || days > 36500}
            onClick={() =>
              void act(
                async () =>
                  setPreview(await post(`/retention?days=${days}&apply=false`)),
                "Retention preview ready.",
              )
            }
          >
            Preview
          </button>
          <button
            className="danger"
            disabled={busy || !preview?.case_ids.length}
            onClick={() => {
              if (
                confirm(
                  `Delete ${preview?.case_ids.length} archived cases and their evidence?`,
                )
              )
                void act(
                  async () =>
                    setPreview(
                      await post(`/retention?days=${days}&apply=true`),
                    ),
                  "Retention applied.",
                );
            }}
          >
            Delete previewed cases
          </button>
        </div>
        {preview && (
          <p>
            {preview.applied ? "Deleted" : "Eligible"}:{" "}
            {preview.case_ids.length} archived cases · cutoff{" "}
            {date(preview.cutoff)}
          </p>
        )}
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>Audit log</h2>
          <span className="muted">Latest 200 local events</span>
        </div>
        <div className="audit-list">
          {audit.error && <ErrorNote>{audit.error}</ErrorNote>}
          {audit.data?.length ? (
            audit.data.map((item, index) => (
              <div key={index}>
                <time>{date(item.at)}</time>
                <strong>{item.action}</strong>
                <code>{item.resource_id}</code>
              </div>
            ))
          ) : (
            <p className="muted">No workspace changes recorded.</p>
          )}
        </div>
      </section>
    </>
  );
}
