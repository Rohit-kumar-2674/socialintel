import { useEffect, useState } from "react";
import type { ReactNode } from "react";
import { ArrowUpRight, Search, LoaderCircle, AlertCircle } from "lucide-react";
import { api, sourceUrl } from "./api";

export function useData<T>(path: string | null, revision = 0, poll = false) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let keepPolling = poll;
    setData(null);
    setError("");
    setLoading(true);
    async function load() {
      if (!path) {
        setLoading(false);
        return;
      }
      try {
        const value = await api<T>(path);
        if (value && typeof value === "object" && "status" in value) {
          keepPolling = poll && ["queued", "running"].includes(String(value.status));
        }
        if (active) {
          setData(value);
          setError("");
        }
      } catch (error) {
        if (active)
          setError(error instanceof Error ? error.message : "Request failed.");
      } finally {
        if (active) {
          setLoading(false);
          if (keepPolling) timer = setTimeout(load, 1800);
        }
      }
    }
    void load();
    return () => {
      active = false;
      clearTimeout(timer);
    };
  }, [path, revision, poll]);
  return { data, error, loading };
}
export function Badge({ children }: { children: ReactNode }) {
  const s = String(children).toUpperCase();
  const style = [
    "FOUND",
    "ONLINE",
    "COMPLETED",
    "ACTIVE",
    "VERIFIED PUBLIC SOURCE",
  ].includes(s)
    ? "good"
    : ["ERROR", "FAILED", "CANCELLED", "RATE LIMITED"].includes(s)
      ? "bad"
      : /POSSIBLE|LIMITED|REQUIRED|INFERENCE|UNVERIFIED|REFERENCE|EXPERIMENTAL|INCOMPLETE/.test(
            s,
          )
        ? "warn"
        : "neutral";
  return (
    <span className={`badge ${style}`}>
      <i />
      {children}
    </span>
  );
}
export function Source({ url, label }: { url: string; label?: string }) {
  const href = sourceUrl(url);
  return href ? (
    <a className="source-link" href={href} target="_blank" rel="noreferrer">
      {label || url}
      <ArrowUpRight size={13} />
    </a>
  ) : (
    <span className="muted">{label || "Source URL unavailable"}</span>
  );
}
export function Empty({
  title,
  children,
  action,
}: {
  title: string;
  children: ReactNode;
  action?: ReactNode;
}) {
  return (
    <div className="empty">
      <span className="empty-icon">
        <Search size={26} />
      </span>
      <h3>{title}</h3>
      <p>{children}</p>
      {action}
    </div>
  );
}
export function ErrorNote({ children }: { children: ReactNode }) {
  return (
    <div className="error-note" role="alert">
      <AlertCircle size={17} />
      <span>{children}</span>
    </div>
  );
}
export function Loading() {
  return (
    <div className="loading" role="status">
      <LoaderCircle className="spin" size={20} /> Loading workspace…
    </div>
  );
}
export function PageTitle({
  eyebrow,
  title,
  description,
  actions,
}: {
  eyebrow: string;
  title: string;
  description?: string;
  actions?: ReactNode;
}) {
  return (
    <div className="page-title">
      <div>
        <p className="eyebrow">{eyebrow}</p>
        <h1>{title}</h1>
        {description && <p className="muted">{description}</p>}
      </div>
      {actions}
    </div>
  );
}
export function Notice({ children }: { children: ReactNode }) {
  return <div className="notice">{children}</div>;
}
export const go = (route: string) => {
  location.hash = route;
};
