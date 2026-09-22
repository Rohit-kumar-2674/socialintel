import { lazy, Suspense, useState } from "react";
import type { FormEvent } from "react";
import {
  ArrowRight,
  Square,
  RefreshCw,
  ExternalLink,
  Fingerprint,
  FileSearch,
  Network,
  SlidersHorizontal,
} from "lucide-react";
import { api, date, post, text } from "./api";
import type {
  Case,
  Evidence,
  Investigation,
  Platform,
  Settings,
} from "./types";
import {
  Badge,
  Empty,
  ErrorNote,
  go,
  Loading,
  Notice,
  PageTitle,
  Source,
  useData,
} from "./ui";
const Graph = lazy(() => import("./Graph"));

export function NewInvestigation({
  platforms,
  settings,
  cases,
  kind,
  onCreated,
}: {
  platforms: Platform[];
  settings: Settings;
  cases: Case[];
  kind: string;
  onCreated: (run: Investigation) => void;
}) {
  const [target, setTarget] = useState("");
  const [platform, setPlatform] = useState(kind === "new" ? "github" : "all");
  const [mode, setMode] = useState(kind === "new" ? "fallback" : "discovery");
  const [type, setType] = useState("auto");
  const [engine, setEngine] = useState(
    kind === "web"
      ? settings.search_engines.find((item) => item.configured)?.name || "none"
      : "none",
  );
  const [caseId, setCase] = useState("");
  const [posts, setPosts] = useState(false);
  const [follow, setFollow] = useState(false);
  const [variants, setVariants] = useState(false);
  const [contacts, setContacts] = useState(false);
  const [refresh, setRefresh] = useState(false);
  const [limits, setLimits] = useState(settings.limits);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const provider = platforms.find((item) => item.platform === platform);
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    try {
      const run = await post<Investigation>(
        kind === "web" ? "/search/web" : "/investigations",
        {
          target,
          platform,
          mode: platform === "all" ? "discovery" : mode,
          target_type: type,
          search_engine: engine,
          case_id: caseId || null,
          collect_posts: posts,
          follow_links: follow,
          variants,
          collect_contacts: contacts,
          refresh,
          limits,
        },
      );
      onCreated(run);
    } catch (error) {
      setError(
        error instanceof Error
          ? error.message
          : "Investigation could not start.",
      );
    } finally {
      setBusy(false);
    }
  }
  const bounds: Record<string, [number, number]> = {
    max_requests: [1, 100],
    max_candidates: [1, 50],
    max_platforms: [1, 12],
    max_pages: [0, 10],
    max_depth: [0, 2],
    max_seconds: [5, 180],
    max_posts: [0, 20],
  };
  return (
    <>
      <PageTitle
        eyebrow="RESEARCH WORKSPACE"
        title={
          kind === "username"
            ? "Global username search"
            : kind === "web"
              ? "Public web discovery"
              : "New investigation"
        }
        description="Start with a public identifier. Build an evidence trail you can verify."
      />
      <div className="investigate-layout">
        <form className="panel investigation-form" onSubmit={submit}>
          <div className="form-section">
            <span className="step-number">01</span>
            <div>
              <h2>Select platform</h2>
              <p className="muted">
                Choose a starting point for your investigation.
              </p>
            </div>
          </div>
          <label>
            PLATFORM
            <select
              aria-label="Platform"
              value={platform}
              onChange={(e) => {
                setPlatform(e.target.value);
                if (e.target.value === "all") setMode("discovery");
              }}
            >
              <option value="all">All Platforms · configured adapters</option>
              {platforms.map((item) => (
                <option key={item.platform} value={item.platform}>
                  {item.name}
                  {!item.capabilities.length
                    ? " · not implemented"
                    : !item.configured
                      ? " · API required"
                      : ""}
                </option>
              ))}
            </select>
          </label>
          {provider && (
            <div className="provider-explainer">
              <Badge>
                {provider.configured ? "Configured" : provider.status}
              </Badge>
              <p>{provider.limitations}</p>
            </div>
          )}
          <div className="form-section">
            <span className="step-number">02</span>
            <div>
              <h2>Define your target</h2>
              <p className="muted">
                Identifiers are research leads, not proof of identity.
              </p>
            </div>
          </div>
          <label>
            TARGET
            <div className="target-input">
              <span>@</span>
              <input
                required
                maxLength={500}
                value={target}
                onChange={(e) => setTarget(e.target.value)}
                placeholder="Username, public profile URL, or display name"
                autoComplete="off"
                spellCheck={false}
              />
            </div>
          </label>
          <div className="form-grid">
            <label>
              IDENTIFIER TYPE
              <select aria-label="Identifier type" value={type} onChange={(e) => setType(e.target.value)}>
                <option value="auto">Detect automatically</option>
                <option value="username">Username</option>
                <option value="url">Public profile URL</option>
                <option value="id">Platform-specific ID</option>
                <option value="display_name">Display name</option>
              </select>
            </label>
            <label>
              SAVE TO CASE
              <select aria-label="Save to case" value={caseId} onChange={(e) => setCase(e.target.value)}>
                <option value="">Create a new case</option>
                {cases
                  .filter((item) => item.status === "active")
                  .map((item) => (
                    <option key={item.id} value={item.id}>
                      {item.name}
                    </option>
                  ))}
              </select>
            </label>
          </div>
          <div className="form-section">
            <span className="step-number">03</span>
            <div>
              <h2>Set the scope</h2>
              <p className="muted">
                Discovery stays within the limits you choose.
              </p>
            </div>
          </div>
          <div className="mode-options">
            {[
              [
                "selected",
                "Platform only",
                "Check only the selected provider.",
              ],
              [
                "fallback",
                "Automatic fallback",
                "Continue elsewhere when the first source cannot confirm a profile.",
              ],
              [
                "discovery",
                "Full discovery",
                "Check configured providers and selected web indexes.",
              ],
            ].map(([value, label, note]) => (
              <label
                key={value}
                className={`mode-option ${mode === value ? "selected" : ""}`}
              >
                <input
                  type="radio"
                  name="mode"
                  value={value}
                  checked={mode === value}
                  disabled={platform === "all" && value !== "discovery"}
                  onChange={() => setMode(value)}
                />
                <span>
                  <strong>
                    {label}
                    {value === "fallback" && <small>RECOMMENDED</small>}
                  </strong>
                  <span>{note}</span>
                </span>
              </label>
            ))}
          </div>
          <label>
            PUBLIC SEARCH INDEX
            <select aria-label="Public search index" value={engine} onChange={(e) => setEngine(e.target.value)}>
              <option value="none">None · provider lookups only</option>
              {settings.search_engines.map((item) => (
                <option
                  key={item.name}
                  value={item.name}
                  disabled={!item.configured}
                >
                  {item.name}
                  {!item.configured
                    ? " · unavailable / configuration required"
                    : ""}
                </option>
              ))}
            </select>
          </label>
          {kind === "web" && engine === "none" && (
            <Notice>
              Configure Brave, an eligible Google account, or a custom search
              API in the server environment. Settings lists the required
              variables.
            </Notice>
          )}
          <details className="advanced">
            <summary>
              <SlidersHorizontal size={15} /> Collection options and limits
            </summary>
            <div className="check-grid">
              {[
                [posts, setPosts, "Collect supported public posts"],
                [follow, setFollow, "Follow public profile links"],
                [variants, setVariants, "Generate up to 3 username variants"],
                [
                  contacts,
                  setContacts,
                  "Extract explicitly published contact text",
                ],
                [refresh, setRefresh, "Refresh cached observations"],
              ].map(([value, setter, label]) => (
                <label key={String(label)}>
                  <input
                    type="checkbox"
                    checked={value as boolean}
                    onChange={(e) =>
                      (setter as (value: boolean) => void)(e.target.checked)
                    }
                  />
                  {label as string}
                </label>
              ))}
            </div>
            <div className="form-grid limits">
              {Object.entries(limits).map(([key, value]) => (
                <label key={key}>
                  {key.replace("max_", "Maximum ").replace("_", " ")}
                  <input
                    type="number"
                    min={bounds[key]?.[0]}
                    max={bounds[key]?.[1]}
                    value={value}
                    onChange={(e) =>
                      setLimits({ ...limits, [key]: Number(e.target.value) })
                    }
                  />
                </label>
              ))}
            </div>
          </details>
          {error && <ErrorNote>{error}</ErrorNote>}
          <div className="form-footer">
            <span>Public sources. Explicit uncertainty.</span>
            <button
              className="primary"
              disabled={busy || (kind === "web" && engine === "none")}
            >
              {busy ? "Starting…" : "Start investigation"}
              <ArrowRight size={17} />
            </button>
          </div>
        </form>
        <aside className="investigation-aside">
          <div className="panel aside-card">
            <span className="eyebrow">HOW IT WORKS</span>
            <h3>
              From identifier
              <br />
              to attributed evidence.
            </h3>
            <ol className="workflow-list">
              <li>
                <SearchIcon />
                Normalize the target
                <small>Respect platform-specific identifiers.</small>
              </li>
              <li>
                <Network size={17} />
                Discover public candidates
                <small>Use configured providers and search APIs.</small>
              </li>
              <li>
                <Fingerprint size={17} />
                Verify at the source
                <small>Keep search snippets unverified.</small>
              </li>
              <li>
                <FileSearch size={17} />
                Build your evidence trail
                <small>Preserve timestamps, links, and limitations.</small>
              </li>
            </ol>
          </div>
          <div className="aside-note">
            <strong>Same username ≠ same person.</strong>
            <p>
              Correlations compare public signals. A verified profile is still
              an unverified identity match.
            </p>
          </div>
        </aside>
      </div>
    </>
  );
}
function SearchIcon() {
  return <ExternalLink size={17} />;
}

export function InvestigationView({
  id,
  revision,
  onSelect,
  onChange,
}: {
  id: string;
  revision: number;
  onSelect: (id: string) => void;
  onChange: () => void;
}) {
  const {
    data: run,
    error,
    loading,
  } = useData<Investigation>(`/investigations/${id}`, revision, true);
  const [actionError, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function action(kind: string) {
    setBusy(true);
    try {
      const record = await post<Investigation>(`/investigations/${id}/${kind}`);
      onChange();
      if (kind === "rerun") {
        onSelect(record.id);
        go(`investigation/${record.id}`);
      }
    } catch (error) {
      setError(String(error));
    } finally {
      setBusy(false);
    }
  }
  if (loading && !run) return <Loading />;
  if (error || !run)
    return <ErrorNote>{error || "Investigation unavailable."}</ErrorNote>;
  const active = ["queued", "running"].includes(run.status);
  const result = run.result;
  return (
    <>
      <PageTitle
        eyebrow="INVESTIGATION"
        title={run.request.target}
        description={`${run.request.platform} · ${run.request.mode} · started ${date(run.started_at)}`}
        actions={
          <div className="button-group">
            <Badge>{run.status}</Badge>
            <button
              disabled={busy}
              onClick={() => void action(active ? "cancel" : "rerun")}
            >
              {active ? <Square size={15} /> : <RefreshCw size={15} />}{" "}
              {active ? "Cancel" : "Rerun with fresh data"}
            </button>
          </div>
        }
      />
      {actionError && <ErrorNote>{actionError}</ErrorNote>}
      {result.limitation && <Notice>{result.limitation}</Notice>}
      <div className="stats-row">
        <Stat
          label="PUBLIC PROFILES"
          value={
            result.summary?.profiles ??
            result.results.filter((item) => item.profile).length
          }
        />
        <Stat label="REQUESTS MADE" value={result.requests_made || 0} />
        <Stat label="SEARCH REFERENCES" value={result.web_results.length} />
        <Stat label="PROVIDER ISSUES" value={result.errors.length} />
      </div>
      {result.fallback?.started && (
        <Notice>
          Automatic discovery started. Primary result:{" "}
          <strong>{result.fallback.reason}</strong>. An unavailable source is an
          unknown result.
        </Notice>
      )}
      <div className="panel">
        <div className="panel-heading">
          <h2>Provider progress</h2>
          {active && (
            <span className="live-label">
              <i />
              Investigation running
            </span>
          )}
        </div>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Platform / target</th>
                <th>Result</th>
                <th>Source and limitations</th>
                <th>Collection</th>
              </tr>
            </thead>
            <tbody>
              {result.progress.map((progress, index) => {
                const item = result.results.find(
                  (value) =>
                    value.platform === progress.platform &&
                    value.target === progress.target,
                );
                return (
                  <tr key={`${progress.platform}-${index}`}>
                    <td data-label="Platform">
                      <strong className="capitalize">
                        {progress.platform}
                      </strong>
                      <small>{progress.target}</small>
                      {item?.variant && (
                        <span className="micro-label">
                          GENERATED SEARCH VARIANT
                        </span>
                      )}
                    </td>
                    <td data-label="Status">
                      <Badge>{progress.status}</Badge>
                    </td>
                    <td data-label="Source">
                      {item?.source_url && <Source url={item.source_url} />}
                      <p className="cell-note">
                        {item?.reason || "Waiting for provider response."}
                      </p>
                    </td>
                    <td data-label="Collection">
                      <span>
                        {item
                          ? item.cached
                            ? "Cached observation"
                            : `${item.duration_ms} ms`
                          : "In progress"}
                      </span>
                      <small>{item ? date(item.checked_at) : ""}</small>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
        {!result.progress.length && (
          <Empty
            title={
              active
                ? "Preparing the investigation"
                : "No provider lookups in this scope"
            }
          >
            Public web-only investigations may contain search references below.
          </Empty>
        )}
      </div>
      <div className="research-shortcuts">
        {[
          ["profiles", "Public profiles", Fingerprint],
          ["evidence", "Evidence", FileSearch],
          ["graph", "Relationship graph", Network],
        ].map(([route, label, Icon]) => {
          const Component = Icon as typeof Network;
          return (
            <button
              key={route as string}
              className="panel shortcut"
              onClick={() => {
                onSelect(id);
                go(route as string);
              }}
            >
              <Component size={20} />
              <span>{label as string}</span>
              <ArrowRight size={17} />
            </button>
          );
        })}
      </div>
      <div className="panel">
        <div className="panel-heading">
          <h2>Public web references</h2>
          <span className="muted">{result.search_status || "Pending"}</span>
        </div>
        {!result.web_results.length ? (
          <div className="panel-body muted">
            No search references collected.
          </div>
        ) : (
          <div className="web-results">
            {result.web_results.map((item) => (
              <article key={item.url}>
                <Badge>{item.classification}</Badge>
                <h3>
                  <Source url={item.url} label={item.title || item.url} />
                </h3>
                <p>{item.snippet}</p>
                <small>{item.verification}</small>
                <small>
                  {item.provider} · {date(item.collected_at)} ·{" "}
                  {item.source_status}
                </small>
              </article>
            ))}
          </div>
        )}
      </div>
      <Notice>
        Verified public sources are not verified identities.{" "}
        <button
          className="text-button"
          onClick={() => go(`cases/${run.case_id}`)}
        >
          Open case and research notes →
        </button>
      </Notice>
    </>
  );
}
export function Stat({ label, value }: { label: string; value: number }) {
  return (
    <div className="stat panel">
      <span>{label}</span>
      <strong>{value.toLocaleString()}</strong>
      <i className="stat-rule" />
    </div>
  );
}

export function ResearchView({
  page,
  run,
  revision,
}: {
  page: string;
  run: Investigation | null;
  revision: number;
}) {
  const [filter, setFilter] = useState("");
  const [sort, setSort] = useState("newest");
  if (!run)
    return (
      <Empty title="Select an investigation">
        Run a search or select a saved investigation to explore its public
        observations.
      </Empty>
    );
  const profiles = [
    ...new Map(
      run.result.results
        .filter((item) => item.profile)
        .map((item) => [item.profile!.id, item.profile!]),
    ).values(),
  ];
  if (page === "evidence")
    return <EvidenceView run={run} revision={revision} />;
  if (page === "graph")
    return (
      <>
        <Notice>
          Edges describe attributed public signals. A connection does not
          establish a shared identity. Select a node or edge to inspect its
          source.
        </Notice>
        {run.result.graph?.edges.length ? (
          <Suspense fallback={<Loading />}>
            <Graph data={run.result.graph} />
          </Suspense>
        ) : (
          <Empty title="No supported relationships yet">
            Collect profiles with public links or search references to create
            source-supported graph edges.
          </Empty>
        )}
        <Correlations run={run} />
      </>
    );
  if (page === "timeline") {
    const items = (run.result.timeline || [])
      .filter((item) =>
        `${item.text} ${item.platform} ${item.type}`
          .toLowerCase()
          .includes(filter.toLowerCase()),
      )
      .sort((a, b) =>
        sort === "oldest"
          ? a.at.localeCompare(b.at)
          : sort === "platform"
            ? a.platform.localeCompare(b.platform)
            : b.at.localeCompare(a.at),
      );
    return (
      <>
        <div className="filter-bar">
          <input
            aria-label="Filter timeline"
            placeholder="Filter by keyword, hashtag, platform, or content type…"
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
          />
          <select
            aria-label="Sort timeline"
            value={sort}
            onChange={(e) => setSort(e.target.value)}
          >
            <option value="newest">Newest first</option>
            <option value="oldest">Oldest first</option>
            <option value="platform">Platform</option>
          </select>
        </div>
        {items.length ? (
          <div className="timeline">
            {items.map((item) => (
              <article key={item.id} className="panel">
                <div className="timeline-dot" />
                <small>{date(item.at)}</small>
                <h3>
                  {item.platform} <Badge>{item.type}</Badge>
                </h3>
                <p className="preserve">{item.text}</p>
                <Source url={item.url} />
                <details>
                  <summary>Supporting evidence</summary>
                  {item.evidence_ids.map((id) => (
                    <small className="mono" key={id}>
                      {id}
                    </small>
                  ))}
                </details>
              </article>
            ))}
          </div>
        ) : (
          <Empty title="No public events in this view">
            Enable public-post collection when starting a supported provider
            investigation. No timeline events are invented from account
            estimates.
          </Empty>
        )}
      </>
    );
  }
  return (
    <>
      <div className="filter-bar">
        <input
          aria-label="Filter profiles"
          placeholder="Filter public profiles…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="muted">
          {profiles.length} source-verified candidate profiles
        </span>
      </div>
      {profiles.length ? (
        <div className="profile-grid">
          {profiles
            .filter((profile) =>
              `${profile.username} ${profile.platform}`
                .toLowerCase()
                .includes(filter.toLowerCase()),
            )
            .map((profile) => (
              <article key={profile.id} className="panel profile-card">
                <header>
                  <div className="platform-avatar">
                    {profile.platform.slice(0, 2).toUpperCase()}
                  </div>
                  <div>
                    <span className="eyebrow">{profile.platform}</span>
                    <h2>{profile.username}</h2>
                  </div>
                </header>
                <Badge>{profile.verification}</Badge>
                <p className="muted">Identity relationship: unverified</p>
                <Source url={profile.url} />
                <div className="profile-fields">
                  {Object.entries(profile.fields)
                    .filter(
                      ([name]) =>
                        !["username", "profile_url", "avatar"].includes(name),
                    )
                    .map(([name, field]) => (
                      <details key={name}>
                        <summary>
                          <span>{name.replaceAll("_", " ")}</span>
                          <strong>{text(field.value)}</strong>
                        </summary>
                        <div className="field-provenance">
                          <Source url={field.source_url} />
                          <small>
                            {date(field.collected_at)} · {field.method} ·{" "}
                            {field.provider}
                          </small>
                          <small>{field.verification}</small>
                        </div>
                      </details>
                    ))}
                </div>
                {profile.links.length > 0 && (
                  <div className="public-links">
                    <h4>Publicly declared links</h4>
                    {profile.links.map((link, index) => (
                      <Source
                        key={`${link.destination}-${index}`}
                        url={link.destination}
                      />
                    ))}
                  </div>
                )}
                <footer>
                  Collected {date(profile.collected_at)}
                  <small>Open each field to inspect its provenance.</small>
                </footer>
              </article>
            ))}
        </div>
      ) : (
        <Empty title="No verified public profiles">
          Review provider results for unavailable sources, access requirements,
          or negative public lookups.
        </Empty>
      )}
      <Correlations run={run} />
    </>
  );
}

function Correlations({ run }: { run: Investigation }) {
  const items = run.result.correlations || [];
  if (!items.length) return null;
  return (
    <div className="panel correlations">
      <div className="panel-heading">
        <h2>Correlation findings</h2>
        <span className="muted">Analytical indicators</span>
      </div>
      {items.map((item, index) => (
        <article key={index}>
          <div className="correlation-heading">
            <span className="mono">
              {item.profile_a} ↔ {item.profile_b}
            </span>
            <Badge>{item.level}</Badge>
          </div>
          <div className="signal-row">
            <span>
              Username similarity <strong>{item.username_match}%</strong>
            </span>
            <span>
              Bio text similarity{" "}
              <strong>
                {item.profile_similarity === null
                  ? "Unavailable"
                  : `${item.profile_similarity}%`}
              </strong>
            </span>
            <span>
              Explicit cross-links <strong>{item.cross_link_count}</strong>
            </span>
          </div>
          <ul>
            {item.reasoning.map((reason) => (
              <li key={reason}>{reason}</li>
            ))}
          </ul>
          <small>{item.interpretation}</small>
          <details>
            <summary>Supporting evidence ({item.evidence_ids.length})</summary>
            <p className="mono">{item.evidence_ids.join(" · ")}</p>
          </details>
        </article>
      ))}
    </div>
  );
}

function EvidenceView({
  run,
  revision,
}: {
  run: Investigation;
  revision: number;
}) {
  const [offset, setOffset] = useState(0);
  const [filter, setFilter] = useState("");
  const [checked, setChecked] = useState<Record<string, boolean>>({});
  const [checkError, setError] = useState("");
  const { data, error, loading } = useData<{
    items: Evidence[];
    total: number;
  }>(
    `/evidence?investigation_id=${run.id}&limit=100&offset=${offset}`,
    revision,
  );
  if (loading) return <Loading />;
  if (error) return <ErrorNote>{error}</ErrorNote>;
  return (
    <>
      <div className="filter-bar">
        <input
          aria-label="Filter evidence page"
          placeholder="Filter this page by field, platform, or value…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="muted">{data?.total || 0} evidence items</span>
      </div>
      {checkError && <ErrorNote>{checkError}</ErrorNote>}
      <Notice>
        Each observation keeps its collection method and source. A digest
        verifies stored data integrity; it does not authenticate the original
        source.
      </Notice>
      <div className="evidence-list">
        {data?.items
          .filter((item) =>
            `${item.field} ${item.platform} ${text(item.value)}`
              .toLowerCase()
              .includes(filter.toLowerCase()),
          )
          .map((item) => (
            <article className="panel evidence-card" key={item.id}>
              <header>
                <div>
                  <span className="eyebrow">
                    {item.platform} / {item.method}
                  </span>
                  <h3>{item.field.replaceAll("_", " ")}</h3>
                </div>
                <Badge>{item.confidence}</Badge>
              </header>
              <pre>{text(item.value)}</pre>
              <Source url={item.source_url} />
              <div className="evidence-meta">
                <span>{date(item.collected_at)}</span>
                <span>{item.provider}</span>
                <span>{item.verification}</span>
              </div>
              <details>
                <summary>Evidence ID and integrity</summary>
                <p className="mono">{item.id}</p>
                <p className="mono">SHA-256: {item.sha256}</p>
                <button
                  onClick={() => {
                    void api<Evidence>(`/evidence/${item.id}`)
                      .then((value) =>
                        setChecked({
                          ...checked,
                          [item.id]: !!value.integrity_valid,
                        }),
                      )
                      .catch((error) => setError(String(error)));
                  }}
                >
                  Verify stored digest
                </button>
                {checked[item.id] !== undefined && (
                  <Badge>
                    {checked[item.id]
                      ? "Digest matches stored observation"
                      : "INTEGRITY CHECK FAILED"}
                  </Badge>
                )}
                <p>{item.notes}</p>
              </details>
            </article>
          ))}
      </div>
      {!data?.total && (
        <Empty title="No evidence collected">
          Completed public observations and search references will appear here.
        </Empty>
      )}
      <div className="pagination">
        <button
          disabled={offset === 0}
          onClick={() => setOffset(Math.max(0, offset - 100))}
        >
          Previous
        </button>
        <span>
          {data?.total
            ? `${offset + 1}–${Math.min(offset + 100, data.total)} of ${data.total}`
            : "0 items"}
        </span>
        <button
          disabled={offset + 100 >= (data?.total || 0)}
          onClick={() => setOffset(offset + 100)}
        >
          Next
        </button>
      </div>
    </>
  );
}
