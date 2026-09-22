import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import {
  Activity,
  ArrowRight,
  ArrowUpRight,
  Boxes,
  Compass,
  FileCheck2,
  FileSearch,
  Fingerprint,
  FolderOpen,
  Globe2,
  LayoutDashboard,
  LockKeyhole,
  Menu,
  Network,
  Plus,
  Puzzle,
  RefreshCw,
  Search,
  Settings2,
  ShieldCheck,
  Waypoints,
  X,
} from "lucide-react";
import { api, date, setToken, token } from "./api";
import type {
  Case,
  Health,
  Investigation,
  Platform,
  RunSummary,
  Settings,
} from "./types";
import { Badge, Empty, ErrorNote, go, Loading, PageTitle, useData } from "./ui";
import {
  InvestigationView,
  NewInvestigation,
  ResearchView,
  Stat,
} from "./InvestigationPages";
import { CaseDetail, CaseList, Reports } from "./CasePages";
import { HealthPage, Platforms, Plugins, SettingsPage } from "./SystemPages";

const groups = [
  {
    label: "WORKSPACE",
    items: [
      ["dashboard", "Overview", LayoutDashboard],
      ["new", "New investigation", Search],
      ["cases", "Cases", FolderOpen],
    ],
  },
  {
    label: "DISCOVERY",
    items: [
      ["username", "Username search", Fingerprint],
      ["web", "Public web search", Globe2],
      ["platforms", "Platform explorer", Compass],
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      ["profiles", "Profiles", Boxes],
      ["evidence", "Evidence", FileCheck2],
      ["timeline", "Timeline", Activity],
      ["graph", "Relationship graph", Network],
      ["reports", "Reports", FileSearch],
    ],
  },
  {
    label: "SYSTEM",
    items: [
      ["health", "Platform health", Activity],
      ["plugins", "Plugins", Puzzle],
      ["settings", "Settings", Settings2],
    ],
  },
];

function Unlock({ onUnlock }: { onUnlock: () => void }) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    setError("");
    setToken(value.trim());
    try {
      await api("/settings");
      onUnlock();
    } catch (error) {
      setToken("");
      setError(error instanceof Error ? error.message : "Unable to connect.");
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="unlock">
      <div className="unlock-brand">
        <Waypoints size={32} />
        <span>
          SocialIntel<small>PUBLIC-SOURCE INTELLIGENCE</small>
        </span>
      </div>
      <form className="panel" onSubmit={submit}>
        <span className="empty-icon">
          <LockKeyhole size={25} />
        </span>
        <h1>
          Your research.
          <br />
          Your workspace.
        </h1>
        <p className="muted">
          Open the private session link printed by{" "}
          <code>socialintel serve</code>, or enter your configured API token.
        </p>
        <label>
          WORKSPACE TOKEN
          <input
            type="password"
            value={value}
            onChange={(e) => setValue(e.target.value)}
            autoComplete="off"
            required
            minLength={32}
            autoFocus
            placeholder="Enter your bearer token"
          />
        </label>
        {error && <ErrorNote>{error}</ErrorNote>}
        <button className="primary" disabled={busy}>
          {busy ? "Connecting…" : "Unlock workspace"}
          <ArrowRight size={17} />
        </button>
        <p className="small muted">
          Single-operator access · local storage · public sources only
        </p>
      </form>
      <p className="unlock-footer">Evidence before assumptions.</p>
    </main>
  );
}

export default function App() {
  const [authenticated, setAuthenticated] = useState(!!token());
  const [route, setRoute] = useState(location.hash.slice(1) || "dashboard");
  const [mobile, setMobile] = useState(false);
  const [revision, setRevision] = useState(0);
  const [runId, setRunId] = useState("");
  const refresh = () => setRevision((value) => value + 1);
  useEffect(() => {
    const changed = () => {
      setRoute(location.hash.slice(1) || "dashboard");
      setMobile(false);
      window.scrollTo(0, 0);
    };
    window.addEventListener("hashchange", changed);
    return () => window.removeEventListener("hashchange", changed);
  }, []);
  if (!authenticated)
    return (
      <Unlock
        onUnlock={() => {
          setAuthenticated(true);
          refresh();
        }}
      />
    );
  return (
    <Workspace
      route={route}
      mobile={mobile}
      setMobile={setMobile}
      revision={revision}
      refresh={refresh}
      runId={runId}
      setRunId={setRunId}
      lock={() => {
        setToken("");
        setAuthenticated(false);
      }}
    />
  );
}

function Workspace({
  route,
  mobile,
  setMobile,
  revision,
  refresh,
  runId,
  setRunId,
  lock,
}: {
  route: string;
  mobile: boolean;
  setMobile: (v: boolean) => void;
  revision: number;
  refresh: () => void;
  runId: string;
  setRunId: (v: string) => void;
  lock: () => void;
}) {
  const [page, id] = route.split("/");
  const platforms = useData<Platform[]>("/platforms", revision);
  const settings = useData<Settings>("/settings", revision);
  const cases = useData<Case[]>("/cases", revision);
  const runs = useData<RunSummary[]>("/investigations", revision);
  const overview = useData<{
    counts: Record<string, number>;
    recent: RunSummary[];
    health: Record<string, Health>;
    counting_note: string;
  }>("/overview", revision);
  const research = ["profiles", "evidence", "timeline", "graph"].includes(page);
  const activeId = runs.data?.some((run) => run.id === runId)
    ? runId
    : runs.data?.[0]?.id || "";
  const current = useData<Investigation>(
    research && activeId ? `/investigations/${activeId}` : null,
    revision,
  );
  const title =
    groups
      .flatMap((group) => group.items)
      .find((item) => item[0] === page)?.[1] || "Investigation";
  const commonError =
    platforms.error ||
    settings.error ||
    cases.error ||
    runs.error ||
    overview.error;
  const loading =
    platforms.loading ||
    settings.loading ||
    cases.loading ||
    runs.loading ||
    overview.loading;
  let content;
  if (commonError)
    content = (
      <div>
        <ErrorNote>{commonError}</ErrorNote>
        <div className="button-group">
          <button onClick={refresh}>Retry connection</button>
          <button onClick={lock}>Enter a new token</button>
        </div>
      </div>
    );
  else if (
    loading ||
    !platforms.data ||
    !settings.data ||
    !cases.data ||
    !runs.data ||
    !overview.data
  )
    content = <Loading />;
  else if (page === "dashboard")
    content = (
      <Overview
        data={overview.data}
        platforms={platforms.data}
        onRun={setRunId}
      />
    );
  else if (["new", "username", "web"].includes(page))
    content = (
      <NewInvestigation
        key={page}
        kind={page}
        platforms={platforms.data}
        settings={settings.data}
        cases={cases.data}
        onCreated={(run) => {
          setRunId(run.id);
          refresh();
          go(`investigation/${run.id}`);
        }}
      />
    );
  else if (page === "investigation" && id)
    content = (
      <InvestigationView
        id={id}
        revision={revision}
        onSelect={setRunId}
        onChange={refresh}
      />
    );
  else if (page === "cases")
    content = id ? (
      <CaseDetail
        id={id}
        revision={revision}
        refresh={refresh}
        onRun={setRunId}
      />
    ) : (
      <CaseList cases={cases.data} refresh={refresh} />
    );
  else if (page === "platforms")
    content = (
      <Platforms platforms={platforms.data} health={overview.data.health} />
    );
  else if (page === "health")
    content = (
      <HealthPage
        platforms={platforms.data}
        health={overview.data.health}
        refresh={refresh}
      />
    );
  else if (page === "reports") content = <Reports cases={cases.data} />;
  else if (page === "plugins")
    content = <Plugins platforms={platforms.data} revision={revision} />;
  else if (page === "settings")
    content = (
      <SettingsPage
        settings={settings.data}
        revision={revision}
        refresh={refresh}
        lock={lock}
      />
    );
  else if (research)
    content = (
      <>
        <PageTitle
          eyebrow="INVESTIGATION INTELLIGENCE"
          title={String(title)}
          description="Source-backed observations with transparent limitations."
        />
        <div className="panel run-selector">
          <span>INVESTIGATION</span>
          <select
            aria-label="Select investigation"
            value={activeId}
            onChange={(e) => setRunId(e.target.value)}
          >
            {!runs.data.length && (
              <option value="">No saved investigations</option>
            )}
            {runs.data.map((run) => (
              <option key={run.id} value={run.id}>
                {run.target} · {date(run.started_at)} · {run.status}
              </option>
            ))}
          </select>
          {activeId && (
            <button onClick={() => go(`investigation/${activeId}`)}>
              View progress
              <ArrowUpRight size={15} />
            </button>
          )}
        </div>
        {current.error ? (
          <ErrorNote>{current.error}</ErrorNote>
        ) : current.loading && activeId ? (
          <Loading />
        ) : (
          <ResearchView
            key={`${page}-${activeId}`}
            page={page}
            run={current.data}
            revision={revision}
          />
        )}
      </>
    );
  else
    content = (
      <Empty
        title="Page not found"
        action={
          <button onClick={() => go("dashboard")}>Return to overview</button>
        }
      >
        Choose a section from the workspace navigation.
      </Empty>
    );
  return (
    <div className="app-shell">
      <a
        href="#main-content"
        className="skip-link"
        onClick={(event) => {
          event.preventDefault();
          document.getElementById("main-content")?.focus();
        }}
      >
        Skip to content
      </a>
      {mobile && (
        <button
          className="nav-scrim"
          aria-label="Close navigation"
          onClick={() => setMobile(false)}
        />
      )}
      <aside className={`sidebar ${mobile ? "open" : ""}`}>
        <button className="brand" onClick={() => go("dashboard")}>
          <span className="brand-mark">
            <Waypoints size={27} />
          </span>
          <span>
            SocialIntel<small>PUBLIC INTELLIGENCE</small>
          </span>
        </button>
        <div className="workspace-switch">
          <span className="workspace-avatar">L</span>
          <span>
            Local workspace<small>Single-operator research</small>
          </span>
        </div>
        <nav aria-label="Main navigation">
          {groups.map((group) => (
            <div className="nav-group" key={group.label}>
              <p>{group.label}</p>
              {group.items.map(([key, label, Icon]) => {
                const Component = Icon as typeof Search;
                return (
                  <button
                    key={key as string}
                    className={
                      page === key ||
                      (page === "investigation" && key === "new")
                        ? "active"
                        : ""
                    }
                    aria-current={page === key ? "page" : undefined}
                    onClick={() => go(key as string)}
                  >
                    <Component size={17} />
                    <span>{label as string}</span>
                    {key === "new" && <Plus size={14} />}
                  </button>
                );
              })}
            </div>
          ))}
        </nav>
        <div className="sidebar-footer">
          <ShieldCheck size={17} />
          <div>
            Public sources only<small>Evidence before assumptions.</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header className="topbar">
          <div className="breadcrumb">
            <button
              className="mobile-menu icon-button"
              aria-label={mobile ? "Close navigation" : "Open navigation"}
              onClick={() => setMobile(!mobile)}
            >
              {mobile ? <X size={20} /> : <Menu size={20} />}
            </button>
            <span className="muted">Workspace</span>
            <span className="slash">/</span>
            <span>{String(title)}</span>
          </div>
          <div className="topbar-actions">
            <span className="local-pill">
              <i />
              Local storage
            </span>
            <button
              className="icon-button"
              aria-label="Refresh workspace"
              title="Refresh workspace"
              onClick={refresh}
            >
              <RefreshCw size={16} />
            </button>
            <button
              className="operator-avatar"
              aria-label="Lock workspace"
              title="Lock workspace"
              onClick={lock}
            >
              <LockKeyhole size={16} />
            </button>
          </div>
        </header>
        <main id="main-content" className="main-content" tabIndex={-1}>
          {content}
        </main>
        <footer className="workspace-footer">
          <span>
            SocialIntel <span className="version">v0.1.0</span>
          </span>
          <span>Public-source intelligence · human verification required</span>
          <span>Research release</span>
        </footer>
      </div>
    </div>
  );
}

function Overview({
  data,
  platforms,
  onRun,
}: {
  data: {
    counts: Record<string, number>;
    recent: RunSummary[];
    health: Record<string, Health>;
    counting_note: string;
  };
  platforms: Platform[];
  onRun: (id: string) => void;
}) {
  const supported = platforms.filter((item) => item.capabilities.length);
  const configured = supported.filter((item) => item.configured);
  return (
    <>
      <PageTitle
        eyebrow="YOUR RESEARCH, CONNECTED"
        title="Investigation overview"
        description="Discover public information. Understand the connections. Preserve the evidence."
        actions={
          <button className="primary" onClick={() => go("new")}>
            <Plus size={17} />
            New investigation
          </button>
        }
      />
      <div className="stats-row">
        <Stat label="INVESTIGATIONS" value={data.counts.investigations || 0} />
        <Stat label="ACTIVE CASES" value={data.counts.active_cases || 0} />
        <Stat
          label="PROFILE OBSERVATIONS"
          value={data.counts.verified_profiles || 0}
        />
        <Stat label="EVIDENCE ITEMS" value={data.counts.evidence || 0} />
      </div>
      <div className="overview-grid">
        <section className="panel recent-panel">
          <div className="panel-heading">
            <h2>Recent investigations</h2>
            <button className="text-button" onClick={() => go("cases")}>
              View cases
              <ArrowUpRight size={14} />
            </button>
          </div>
          {data.recent.length ? (
            <div className="run-list">
              {data.recent.map((run) => (
                <button
                  key={run.id}
                  onClick={() => {
                    onRun(run.id);
                    go(`investigation/${run.id}`);
                  }}
                >
                  <span className="run-icon">
                    <Fingerprint size={19} />
                  </span>
                  <span className="run-name">
                    <strong>{run.target}</strong>
                    <small>
                      {run.platform} · {run.mode}
                    </small>
                  </span>
                  <span className="run-meta">
                    <Badge>{run.status}</Badge>
                    <small>{date(run.started_at)}</small>
                  </span>
                  <ArrowUpRight size={15} />
                </button>
              ))}
            </div>
          ) : (
            <div className="welcome-investigation">
              <div className="constellation" aria-hidden="true">
                <svg viewBox="0 0 320 170">
                  <path d="M160 85L70 38M160 85L252 30M160 85L276 133M160 85L67 139M70 38L67 139M252 30L276 133" />
                  <circle cx="160" cy="85" r="27" />
                  <circle cx="70" cy="38" r="13" />
                  <circle cx="252" cy="30" r="10" />
                  <circle cx="276" cy="133" r="14" />
                  <circle cx="67" cy="139" r="10" />
                  <circle className="center" cx="160" cy="85" r="9" />
                </svg>
              </div>
              <h2>Every investigation starts with a question.</h2>
              <p>
                Enter a username or a public URL to start building
                <br className="desktop-break" /> your first source-attributed
                evidence trail.
              </p>
              <button onClick={() => go("new")}>
                Start your first investigation
                <ArrowRight size={16} />
              </button>
            </div>
          )}
          <div className="panel-caption">{data.counting_note}</div>
        </section>
        <section className="panel source-panel">
          <div className="panel-heading">
            <h2>Provider readiness</h2>
            <span className="count-pill">
              {configured.length}/{supported.length}
            </span>
          </div>
          <div className="source-list">
            {supported.map((item) => (
              <button key={item.platform} onClick={() => go("platforms")}>
                <span className={`source-monogram ${item.platform}`}>
                  {item.name.slice(0, 2)}
                </span>
                <span>
                  <strong>{item.name}</strong>
                  <small>
                    {item.capabilities.length} declared capabilities
                  </small>
                </span>
                <span
                  className={`readiness-dot ${data.health[item.platform]?.status === "ONLINE" ? "good" : item.configured ? "configured" : "missing"}`}
                  title={
                    data.health[item.platform]?.status ||
                    item.configuration_note
                  }
                />
              </button>
            ))}
          </div>
          <div className="panel-caption">
            <i className="dot blue" />
            Configured · live status available after lookup
          </div>
        </section>
      </div>
      <div className="section-heading">
        <h2>One workspace. A clear evidence trail.</h2>
        <span className="muted">Built for careful research</span>
      </div>
      <div className="feature-grid">
        <button className="panel feature-card" onClick={() => go("username")}>
          <span className="feature-icon">
            <Globe2 size={20} />
          </span>
          <h3>Discover across platforms</h3>
          <p>
            Start with one identifier. Check configured public sources with
            bounded fallback.
          </p>
          <span>
            Username search
            <ArrowUpRight size={14} />
          </span>
        </button>
        <button className="panel feature-card" onClick={() => go("evidence")}>
          <span className="feature-icon">
            <FileCheck2 size={20} />
          </span>
          <h3>Make every fact traceable</h3>
          <p>
            Inspect the source, collection method, timestamp, and verification
            for each field.
          </p>
          <span>
            Explore evidence
            <ArrowUpRight size={14} />
          </span>
        </button>
        <button className="panel feature-card" onClick={() => go("graph")}>
          <span className="feature-icon">
            <Network size={20} />
          </span>
          <h3>Connect signals carefully</h3>
          <p>
            Explore public links and explainable correlations without assuming
            identity.
          </p>
          <span>
            Relationship graph
            <ArrowUpRight size={14} />
          </span>
        </button>
      </div>
      <div className="ethics-bar">
        <ShieldCheck size={20} />
        <div>
          <strong>Source verification is not identity verification.</strong>
          <p>
            Matching usernames are leads. Independent evidence makes the
            difference.
          </p>
        </div>
        <button className="text-button" onClick={() => go("platforms")}>
          Understand provider limits
          <ArrowRight size={15} />
        </button>
      </div>
    </>
  );
}
