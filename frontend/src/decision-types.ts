export type MetricDefinition = { label: string; unit: string; value_type: string; numeric_demo_supported: boolean; capability_gap?: string };
export type Requirement = { metric: string; operator: string; value: number | string; upper?: number | null; unit: string; test_method: string | null; conditions: Record<string, string | number | null>; comparison_basis: string | null; source: { kind: string; reference: string; confirmed: boolean } };
export type DemandRequest = {
  name: string; schema_version: "2.0"; context_kind: "constructed_demo" | "project";
  decision_id: string | null; segment_id: string | null;
  scene: { maintenance_method: string | null; layer: string | null; structure_type: string | null; climate: { class: string | null; source: string | null }; traffic: { class: string | null; source: string | null }; distress: { type: string | null; severity: string | null; mechanism: string | null } };
  inventory: { source_codes: string[] | null; product_versions: string[] | null; gradation_family: string | null };
  construction: { equipment: string[] | null; mixing_window: string | null; compaction_window: string | null; source: string | null };
  constraints: { budget: number | null; budget_unit: string | null; schedule_days: number | null; rap_min_pct: number | null; carbon_cap: number | null; carbon_unit: string | null };
  requested_metrics: string[]; project_targets: Requirement[];
};
export type DemandTarget = Requirement & { target_id: string; derived_by: string };
export type Demand = {
  id: string; kind: string; sha256: string; created_at: string; request: DemandRequest; targets: DemandTarget[];
  priority: string[]; requirements_complete: boolean; ready_for_candidate_retrieval: boolean;
  rules: { version: string; matches: { id: string; title: string; rationale: string; version: string }[] };
  open_items: { code: string; message: string; field?: string; metric?: string }[];
  conflicts: { code: string; message: string; target_ids: string[] }[];
  capability_gaps: { metric: string; message: string }[]; warnings: string[];
  overrides?: { target_id: string; before: DemandTarget; after: Requirement; reason: string }[];
  confirmed_by?: string; confirmation_status?: string;
};
export type SceneProfile = { id: string; title: string; rationale: string; example_request: DemandRequest };

export async function decisionApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch("/v2" + path, body === undefined ? {} : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body),
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(typeof error.detail === "string" ? error.detail : JSON.stringify(error.detail));
  }
  return response.json() as Promise<T>;
}
