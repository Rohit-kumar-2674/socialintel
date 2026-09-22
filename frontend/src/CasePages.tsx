import { useState } from "react";
import type { FormEvent } from "react";
import {
  FolderPlus,
  ArrowUpRight,
  Download,
  Archive,
  Trash2,
  Upload,
  Save,
  FileText,
  GitCompareArrows,
} from "lucide-react";
import { api, date, download, post, text } from "./api";
import type { Case, Evidence, Json } from "./types";
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

export function CaseList({
  cases,
  refresh,
}: {
  cases: Case[];
  refresh: () => void;
}) {
  const [name, setName] = useState("");
  const [purpose, setPurpose] = useState("");
  const [filter, setFilter] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function create(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
    try {
      const record = await post<Case>("/cases", { name, purpose, tags: [] });
      refresh();
      go(`cases/${record.id}`);
    } catch (error) {
      setError(String(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="ORGANIZE YOUR RESEARCH"
        title="Cases"
        description="Keep targets, observations, research notes, and source material together."
      />
      <form className="panel create-case" onSubmit={create}>
        <FolderPlus size={22} />
        <label>
          CASE NAME
          <input
            required
            maxLength={140}
            value={name}
            onChange={(e) => setName(e.target.value)}
            placeholder="e.g. Brand impersonation review"
          />
        </label>
        <label>
          RESEARCH PURPOSE
          <input
            maxLength={2000}
            value={purpose}
            onChange={(e) => setPurpose(e.target.value)}
            placeholder="Describe the public-interest scope"
          />
        </label>
        <button className="primary" disabled={busy}>
          Create case
        </button>
      </form>
      {error && <ErrorNote>{error}</ErrorNote>}
      <div className="filter-bar">
        <input
          aria-label="Filter cases"
          placeholder="Search case names and tags…"
          value={filter}
          onChange={(e) => setFilter(e.target.value)}
        />
        <span className="muted">
          {cases.length} recent cases · up to 500 shown
        </span>
      </div>
      <div className="case-grid">
        {cases
          .filter((item) =>
            `${item.name} ${item.tags.join(" ")}`
              .toLowerCase()
              .includes(filter.toLowerCase()),
          )
          .map((item) => (
            <button
              className="panel case-card"
              key={item.id}
              onClick={() => go(`cases/${item.id}`)}
            >
              <header>
                <span className="folder-icon">
                  <FolderPlus size={21} />
                </span>
                <Badge>{item.status}</Badge>
              </header>
              <h2>{item.name}</h2>
              <p>{item.purpose || "No research purpose recorded."}</p>
              <div className="tags">
                {item.tags.map((tag) => (
                  <span key={tag}>{tag}</span>
                ))}
              </div>
              <footer>
                Updated {date(item.updated_at)}
                <ArrowUpRight size={17} />
              </footer>
            </button>
          ))}
      </div>
      {!cases.length && (
        <Empty title="A place for your evidence">
          Create a case above, or start an investigation to create one
          automatically.
        </Empty>
      )}
    </>
  );
}

export function CaseDetail({
  id,
  revision,
  refresh,
  onRun,
}: {
  id: string;
  revision: number;
  refresh: () => void;
  onRun: (id: string) => void;
}) {
  const {
    data: record,
    loading,
    error,
  } = useData<Case>(`/cases/${id}`, revision);
  if (loading) return <Loading />;
  if (error || !record)
    return <ErrorNote>{error || "Case unavailable."}</ErrorNote>;
  return (
    <CaseEditor
      key={`${record.id}-${record.updated_at}`}
      record={record}
      refresh={refresh}
      onRun={onRun}
    />
  );
}
function CaseEditor({
  record,
  refresh,
  onRun,
}: {
  record: Case;
  refresh: () => void;
  onRun: (id: string) => void;
}) {
  const [notes, setNotes] = useState(record.notes);
  const [tags, setTags] = useState(record.tags.join(", "));
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [source, setSource] = useState("");
  const [fields, setFields] = useState("");
  const [importNotes, setImportNotes] = useState("");
  const [before, setBefore] = useState(record.investigations?.[1]?.id || "");
  const [after, setAfter] = useState(record.investigations?.[0]?.id || "");
  const [comparison, setComparison] = useState<{
    changes: Json[];
    limitation: string;
  } | null>(null);
  const imported = useData<{ items: Evidence[]; total: number }>(
    `/evidence?case_id=${record.id}&limit=1000`,
  );
  async function act(
    work: () => Promise<unknown>,
    success: string,
    shouldRefresh = true,
  ) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await work();
      setMessage(success);
      if (shouldRefresh) refresh();
    } catch (error) {
      setError(error instanceof Error ? error.message : "Action failed.");
    } finally {
      setBusy(false);
    }
  }
  async function attach(file?: File) {
    if (!file) return;
    if (file.size > 5_000_000) {
      setError("Use a screenshot smaller than 5 MB.");
      return;
    }
    await act(async () => {
      const data = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result).split(",")[1]);
        reader.onerror = () => reject(new Error("Cannot read this file."));
        reader.readAsDataURL(file);
      });
      await post(`/cases/${record.id}/attachments`, {
        filename: file.name,
        source_url: source,
        data_base64: data,
      });
    }, "Screenshot saved.");
  }
  return (
    <>
      <PageTitle
        eyebrow="CASE WORKSPACE"
        title={record.name}
        description={
          record.purpose || "Add research context in your notes below."
        }
        actions={<Badge>{record.status}</Badge>}
      />
      <div className="case-actions">
        <button
          disabled={busy}
          onClick={() =>
            void act(
              () =>
                api(`/cases/${record.id}`, {
                  method: "PATCH",
                  body: JSON.stringify({
                    status:
                      record.status === "archived" ? "active" : "archived",
                  }),
                }),
              "Case status updated.",
            )
          }
        >
          <Archive size={16} />
          {record.status === "archived" ? "Reopen case" : "Archive case"}
        </button>
        <button onClick={() => go("reports")}>
          <Download size={16} />
          Reports
        </button>
        <button
          className="danger"
          disabled={busy}
          onClick={() => {
            if (
              confirm(
                "Delete this case, its investigations, evidence, and screenshots? This cannot be undone.",
              )
            )
              void act(async () => {
                await api(`/cases/${record.id}`, { method: "DELETE" });
                go("cases");
              }, "Case deleted.");
          }}
        >
          <Trash2 size={16} />
          Delete case
        </button>
      </div>
      {error && <ErrorNote>{error}</ErrorNote>}
      {message && <Notice>{message}</Notice>}
      <div className="case-detail-grid">
        <section className="panel panel-body">
          <h2>Research notes</h2>
          <label className="sr-only" htmlFor="case-notes">
            Research notes
          </label>
          <textarea
            id="case-notes"
            rows={8}
            maxLength={20000}
            value={notes}
            onChange={(e) => setNotes(e.target.value)}
            placeholder="Record scope, independent verification, open questions, and limitations…"
          />
          <label>
            TAGS · COMMA SEPARATED
            <input
              value={tags}
              onChange={(e) => setTags(e.target.value)}
              maxLength={490}
            />
          </label>
          <button
            className="primary"
            disabled={busy}
            onClick={() =>
              void act(
                () =>
                  api(`/cases/${record.id}`, {
                    method: "PATCH",
                    body: JSON.stringify({
                      notes,
                      tags: tags
                        .split(",")
                        .map((item) => item.trim())
                        .filter(Boolean),
                    }),
                  }),
                "Notes saved.",
              )
            }
          >
            <Save size={15} />
            Save notes
          </button>
        </section>
        <section className="panel panel-body">
          <h2>Case record</h2>
          <dl className="record-details">
            <dt>Case ID</dt>
            <dd className="mono">{record.id}</dd>
            <dt>Created</dt>
            <dd>{date(record.created_at)}</dd>
            <dt>Evidence items</dt>
            <dd>{record.evidence_count || 0}</dd>
            <dt>Screenshots</dt>
            <dd>{record.attachments?.length || 0} / 10</dd>
            <dt>Storage</dt>
            <dd>Local SQLite</dd>
          </dl>
          <Notice>
            Original observations remain immutable. Your notes provide
            interpretation and context.
          </Notice>
        </section>
      </div>
      <section className="panel">
        <div className="panel-heading">
          <h2>Investigation history</h2>
          <span className="muted">Manual snapshots · latest 100</span>
        </div>
        {record.investigations?.length ? (
          <div className="run-list">
            {record.investigations.map((item) => (
              <button
                key={item.id}
                onClick={() => {
                  onRun(item.id);
                  go(`investigation/${item.id}`);
                }}
              >
                <span>
                  <strong>{item.target}</strong>
                  <small>
                    {item.platform} · {item.mode} · {date(item.started_at)}
                  </small>
                </span>
                <Badge>{item.status}</Badge>
                <ArrowUpRight size={16} />
              </button>
            ))}
          </div>
        ) : (
          <Empty title="No investigations in this case">
            Choose this case when starting your next investigation.
          </Empty>
        )}
      </section>
      {(record.investigations?.length || 0) > 1 && (
        <section className="panel panel-body">
          <h2>
            <GitCompareArrows size={18} />
            Compare manual snapshots
          </h2>
          <div className="form-grid">
            <label>
              EARLIER SNAPSHOT
              <select
                value={before}
                onChange={(e) => setBefore(e.target.value)}
              >
                {record.investigations?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.target} · {date(item.started_at)}
                  </option>
                ))}
              </select>
            </label>
            <label>
              LATER SNAPSHOT
              <select value={after} onChange={(e) => setAfter(e.target.value)}>
                {record.investigations?.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.target} · {date(item.started_at)}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <button
            disabled={busy || before === after}
            onClick={() =>
              void act(
                async () =>
                  setComparison(
                    await api(`/compare?before=${before}&after=${after}`),
                  ),
                "Comparison complete.",
                false,
              )
            }
          >
            Compare observations
          </button>
          {comparison && (
            <div className="comparison">
              <Notice>{comparison.limitation}</Notice>
              {comparison.changes.length ? (
                comparison.changes.map((change, index) => (
                  <pre key={index}>{text(change)}</pre>
                ))
              ) : (
                <p>No changes detected among comparable observations.</p>
              )}
            </div>
          )}
        </section>
      )}
      <section className="panel panel-body">
        <h2>
          <Upload size={18} />
          Add user-provided material
        </h2>
        <p className="muted">
          Only import material from publicly accessible sources. Private messages,
          locked profiles, and paid content are outside this workspace's scope.
          Exports and screenshots are stored as unverified material. Importing
          never upgrades a claim to source-verified evidence.
        </p>
        <label>
          PUBLIC SOURCE URL
          <input
            type="url"
            value={source}
            onChange={(e) => setSource(e.target.value)}
            placeholder="https://example.org/public-profile"
          />
        </label>
        <div className="form-grid">
          <div>
            <label>
              EXPORTED FIELDS · JSON OBJECT
              <textarea
                rows={5}
                value={fields}
                onChange={(e) => setFields(e.target.value)}
                placeholder={'{"display_name": "Name shown in your export"}'}
              />
            </label>
            <label>
              IMPORT NOTES
              <input
                value={importNotes}
                onChange={(e) => setImportNotes(e.target.value)}
                maxLength={2000}
              />
            </label>
            <button
              disabled={busy || !source || !fields}
              onClick={() =>
                void act(async () => {
                  let parsed;
                  try {
                    parsed = JSON.parse(fields);
                  } catch {
                    throw new Error(
                      "Enter a valid JSON object containing simple field values.",
                    );
                  }
                  await post(`/cases/${record.id}/import`, {
                    source_url: source,
                    fields: parsed,
                    notes: importNotes,
                  });
                }, "Export fields saved.")
              }
            >
              <FileText size={16} />
              Import fields
            </button>
          </div>
          <div>
            <label>
              SCREENSHOT · PNG, JPEG, WEBP
              <input
                type="file"
                accept="image/png,image/jpeg,image/webp"
                disabled={busy}
                onChange={(e) => {
                  void attach(e.target.files?.[0]);
                  e.target.value = "";
                }}
              />
            </label>
            <p className="muted">
              Maximum 5 MB each. No facial recognition, hidden metadata
              recovery, or remote image loading.
            </p>
            {record.attachments?.map((item) => (
              <div className="attachment" key={item.id}>
                <span>
                  {item.filename}
                  <small>{Math.ceil(item.size / 1024)} KB · unverified</small>
                </span>
                <button
                  aria-label={`Download ${item.filename}`}
                  onClick={() =>
                    void act(
                      () => download(`/attachments/${item.id}`, item.filename),
                      "Screenshot downloaded.",
                      false,
                    )
                  }
                >
                  <Download size={16} />
                </button>
              </div>
            ))}
          </div>
        </div>
      </section>
      {(imported.data?.items.filter((item) => !item.investigation_id).length ||
        0) > 0 && (
        <section className="panel panel-body">
          <h2>Imported evidence</h2>
          {imported.data?.items
            .filter((item) => !item.investigation_id)
            .map((item) => (
              <article className="imported-item" key={item.id}>
                <strong>{item.field}</strong>
                <pre>{text(item.value)}</pre>
                <Source url={item.source_url} />
                <small>
                  {item.verification} · {date(item.collected_at)}
                </small>
                <small className="mono">SHA-256: {item.sha256}</small>
              </article>
            ))}
        </section>
      )}
    </>
  );
}

export function Reports({ cases }: { cases: Case[] }) {
  const [selected, setSelected] = useState(cases[0]?.id || "");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");
  const active = cases.find((item) => item.id === selected);
  async function exportReport(format: string) {
    setBusy(format);
    setError("");
    try {
      await download(
        `/reports/${selected}?format=${format}`,
        `${selected}.${format}`,
      );
    } catch (error) {
      setError(String(error));
    } finally {
      setBusy("");
    }
  }
  return (
    <>
      <PageTitle
        eyebrow="SHARE VERIFIED RESEARCH"
        title="Reports & exports"
        description="Portable case reports with evidence, provenance, limitations, and explicit uncertainty."
      />
      {!cases.length ? (
        <Empty title="No cases to export">
          Create a case and collect public observations before generating a
          report.
        </Empty>
      ) : (
        <>
          <div className="panel report-select">
            <FileText size={28} />
            <label>
              SELECT CASE
              <select
                aria-label="Select case"
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
              >
                {cases.map((item) => (
                  <option key={item.id} value={item.id}>
                    {item.name}
                  </option>
                ))}
              </select>
            </label>
            <Badge>{active?.status}</Badge>
          </div>
          {error && <ErrorNote>{error}</ErrorNote>}
          <div className="report-grid">
            {[
              [
                "html",
                "Readable report",
                "A self-contained, printable report with attributed observations.",
              ],
              [
                "md",
                "Markdown",
                "Research notes and evidence for review in a text editor or GitHub.",
              ],
              [
                "json",
                "Structured case export",
                "Investigation records, graph, timeline, evidence, and source metadata.",
              ],
              [
                "csv",
                "Evidence dataset",
                "A tabular evidence export with spreadsheet formula protection.",
              ],
            ].map(([format, title, note]) => (
              <article className="panel report-card" key={format}>
                <span className="format-icon">{format.toUpperCase()}</span>
                <h2>{title}</h2>
                <p className="muted">{note}</p>
                <button
                  disabled={!!busy || !selected}
                  onClick={() => void exportReport(format)}
                >
                  <Download size={16} />
                  {busy === format
                    ? "Generating…"
                    : `Download ${format.toUpperCase()}`}
                </button>
              </article>
            ))}
          </div>
          <Notice>
            This report contains information collected from publicly accessible
            sources. Correlations are analytical indicators and should not be
            treated as confirmed identity without independent verification.
          </Notice>
          <p className="muted">
            Reports include up to 100 investigations and 10,000 evidence items
            per case, with explicit export counts. Screenshots are downloaded
            separately from the case. HTML can be printed to PDF using your
            browser.
          </p>
        </>
      )}
    </>
  );
}
