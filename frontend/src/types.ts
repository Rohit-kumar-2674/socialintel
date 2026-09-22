export type Json =
  string | number | boolean | null | Json[] | { [key: string]: Json };
export interface SourceField {
  value: Json;
  source_url: string;
  collected_at: string;
  method: string;
  verification: string;
  provider: string;
}
export interface Link {
  source_url: string;
  destination: string;
  kind: string;
  method: string;
  collected_at: string;
}
export interface Profile {
  id: string;
  platform: string;
  username: string;
  url: string;
  fields: Record<string, SourceField>;
  links: Link[];
  collected_at: string;
  verification: string;
  method: string;
  provider: string;
}
export interface ProviderResult {
  platform: string;
  target: string;
  status: string;
  reason: string;
  profile?: Profile;
  checked_at: string;
  duration_ms: number;
  cached: boolean;
  variant: boolean;
  source_url?: string;
  discovered_via: string;
  depth: number;
}
export interface Evidence {
  id: string;
  case_id: string;
  investigation_id?: string;
  platform: string;
  field: string;
  value: Json;
  source_url: string;
  collected_at: string;
  method: string;
  verification: string;
  provider: string;
  confidence: string;
  notes: string;
  sha256: string;
  integrity_valid?: boolean;
}
export interface Platform {
  platform: string;
  name: string;
  version: string;
  domains: string[];
  status: string;
  capabilities: string[];
  methods: string[];
  requirements: string[];
  limitations: string;
  documentation_url: string;
  configured: boolean;
  configuration_note: string;
  plugin: boolean;
}
export interface Health {
  status: string;
  checked_at: string;
  last_successful_check?: string;
  response_time_ms: number;
  reason: string;
  retry_at?: string;
  capabilities: string[];
}
export interface TimelineEvent {
  id: string;
  at: string;
  platform: string;
  type: string;
  text: string;
  url: string;
  evidence_ids: string[];
}
export interface Correlation {
  profile_a: string;
  profile_b: string;
  level: string;
  username_match: number;
  profile_similarity: number | null;
  cross_link_count: number;
  reasoning: string[];
  evidence_ids: string[];
  interpretation: string;
}
export interface WebResult {
  url: string;
  title: string;
  snippet: string;
  platform?: string;
  classification: string;
  verification: string;
  provider: string;
  source_url: string;
  collected_at: string;
  source_status: string;
}
export interface GraphElement {
  data: {
    id: string;
    label: string;
    type?: string;
    url?: string;
    source?: string;
    target?: string;
    evidence_ids?: string[];
    source_url?: string;
  };
}
export interface Investigation {
  id: string;
  case_id: string;
  status: string;
  request: {
    target: string;
    platform: string;
    mode: string;
    [key: string]: unknown;
  };
  started_at: string;
  finished_at?: string;
  result: {
    results: ProviderResult[];
    progress: {
      platform: string;
      target: string;
      status: string;
      discovered_via: string;
    }[];
    web_results: WebResult[];
    errors: { platform: string; status: string; reason: string }[];
    summary?: Record<string, number>;
    fallback?: { started: boolean; reason: string };
    search_status?: string;
    limitation?: string;
    limitations?: string[];
    timeline?: TimelineEvent[];
    correlations?: Correlation[];
    graph?: { nodes: GraphElement[]; edges: GraphElement[] };
    entities?: {
      type: string;
      value: string;
      source_url: string;
      basis: string;
    }[];
    requests_made?: number;
    pages_requested?: number;
  };
}
export interface RunSummary {
  id: string;
  case_id: string;
  target: string;
  platform: string;
  mode: string;
  status: string;
  started_at: string;
  summary: Record<string, number>;
}
export interface Attachment {
  id: string;
  filename: string;
  size: number;
  sha256: string;
  source_url: string;
  verification: string;
}
export interface Case {
  id: string;
  name: string;
  purpose: string;
  notes: string;
  tags: string[];
  status: string;
  created_at: string;
  updated_at: string;
  investigations?: RunSummary[];
  evidence_count?: number;
  attachments?: Attachment[];
}
export interface Settings {
  version: string;
  credentials: Record<string, boolean>;
  mastodon_instance: string;
  storage: string;
  single_user: boolean;
  search_engines: {
    name: string;
    configured: boolean;
    requirements: string[];
    limitation: string;
  }[];
  limits: Record<string, number>;
}
