let memoryToken = "";
export function token(): string {
  try {
    return sessionStorage.getItem("socialintel-token") || memoryToken;
  } catch {
    return memoryToken;
  }
}
export function setToken(value: string) {
  memoryToken = value;
  try {
    if (value) sessionStorage.setItem("socialintel-token", value);
    else sessionStorage.removeItem("socialintel-token");
  } catch {
    /* Memory works when storage is unavailable. */
  }
}
const fragment = new URLSearchParams(location.hash.slice(1));
if (fragment.has("token")) {
  setToken(fragment.get("token") || "");
  history.replaceState(null, "", location.pathname + location.search);
}
export class ApiError extends Error {
  constructor(
    message: string,
    public status: number,
  ) {
    super(message);
  }
}
export async function api<T>(
  path: string,
  options: RequestInit = {},
): Promise<T> {
  const response = await fetch("/api" + path, {
    ...options,
    headers: {
      Authorization: `Bearer ${token()}`,
      ...(options.body ? { "Content-Type": "application/json" } : {}),
      ...options.headers,
    },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    const detail =
      typeof body.detail === "string"
        ? body.detail
        : "Invalid request. Check the field values and limits.";
    throw new ApiError(detail, response.status);
  }
  return (response.status === 204 ? undefined : await response.json()) as T;
}
export const post = <T>(path: string, body?: unknown) =>
  api<T>(path, {
    method: "POST",
    ...(body === undefined ? {} : { body: JSON.stringify(body) }),
  });
export async function download(path: string, filename: string) {
  const response = await fetch("/api" + path, {
    headers: { Authorization: `Bearer ${token()}` },
  });
  if (!response.ok) {
    const body = await response.json().catch(() => ({}));
    throw new Error(body.detail || "Download failed.");
  }
  const url = URL.createObjectURL(await response.blob());
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
export function sourceUrl(value: string): string | undefined {
  try {
    const url = new URL(value);
    return url.protocol === "https:" && !url.username && !url.password
      ? url.href
      : undefined;
  } catch {
    return undefined;
  }
}
export function text(value: unknown): string {
  return typeof value === "object" && value !== null
    ? JSON.stringify(value, null, 2)
    : String(value ?? "NOT PUBLICLY AVAILABLE");
}
export function date(value?: string) {
  return value && !Number.isNaN(Date.parse(value))
    ? new Date(value).toLocaleString()
    : "Not observed";
}
