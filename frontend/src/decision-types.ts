export type MetricDefinition = {
  label: string;
  unit: string;
  value_type: string;
  numeric_demo_supported: boolean;
  condition_keys: string[];
  capability_gap?: string;
};
export type Requirement = {
  metric: string;
  operator: string;
  value: number | string;
  upper?: number | null;
  unit: string;
  test_method: string | null;
  conditions: Record<string, string | number | null>;
  comparison_basis: string | null;
  source: { kind: string; reference: string; confirmed: boolean };
};
export type DemandRequest = {
  name: string;
  schema_version: "2.0";
  context_kind: "constructed_demo" | "project";
  demo_case_id?: string | null;
  decision_id: string | null;
  segment_id: string | null;
  scene: {
    maintenance_method: string | null;
    layer: string | null;
    structure_type: string | null;
    climate: { class: string | null; source: string | null };
    traffic: { class: string | null; source: string | null };
    distress: {
      type: string | null;
      severity: string | null;
      mechanism: string | null;
    };
  };
  inventory: {
    source_codes: string[] | null;
    product_versions: string[] | null;
    gradation_family: string | null;
  };
  construction: {
    equipment: string[] | null;
    mixing_window: string | null;
    compaction_window: string | null;
    source: string | null;
  };
  constraints: {
    budget: number | null;
    budget_unit: string | null;
    schedule_days: number | null;
    rap_min_pct: number | null;
    carbon_cap: number | null;
    carbon_unit: string | null;
  };
  requested_metrics: string[];
  project_targets: Requirement[];
};
export type DemandTarget = Requirement & {
  target_id: string;
  derived_by: string;
};
export type Demand = {
  id: string;
  kind: string;
  sha256: string;
  created_at: string;
  request: DemandRequest;
  targets: DemandTarget[];
  priority: string[];
  requirements_complete: boolean;
  ready_for_candidate_retrieval: boolean;
  rules: {
    version: string;
    matches: {
      id: string;
      title: string;
      rationale: string;
      version: string;
    }[];
  };
  open_items: {
    code: string;
    message: string;
    field?: string;
    metric?: string;
  }[];
  conflicts: { code: string; message: string; target_ids: string[] }[];
  capability_gaps: { metric: string; message: string }[];
  warnings: string[];
  overrides?: {
    target_id: string;
    before: DemandTarget;
    after: Requirement;
    reason: string;
  }[];
  confirmed_by?: string;
  confirmation_status?: string;
  case_application?: { id: string; title: string; source: string } | null;
};
export type SceneProfile = {
  id: string;
  title: string;
  rationale: string;
  example_request: DemandRequest;
};
export type Diagnosis = {
  status: string;
  message: string;
  scope_note: string;
  pool_sha256: string;
  confirmation_sha256: string;
  enumeration_complete?: boolean;
  certificates: {
    certificate_sha256: string;
    target_ids: string[];
    requirements: {
      metric: string;
      operator?: string;
      value?: number | string;
      unit?: string;
    }[];
    minimality_status: string;
    deletion_witnesses: {
      removed_target: string;
      candidate_id: string;
      display_id: string;
      kind: string;
    }[];
  }[];
};
export type DecisionDifference = {
  changed: boolean;
  input_changes: { field: string; before: unknown; after: unknown }[];
  rule_changes: { before: { id: string }[]; after: { id: string }[] }[];
  target_changes: {
    metric: string;
    before: Requirement[];
    after: Requirement[];
  }[];
  candidate_changes: {
    added: string[];
    removed: string[];
    outcome_changes: { id: string }[];
  };
  conclusion_changes: { field: string; before: unknown; after: unknown }[];
  manual_overrides: {
    before: Requirement;
    after: Requirement;
    reason: string;
  }[];
  note: string;
};
export type MaterialScheme = {
  recipe_id: string;
  display_id: string;
  material_version: string;
  dataset_id: string;
  kind: string;
  parent_id: string | null;
  fields: Record<
    string,
    {
      value: string | number | string[] | null;
      unit: string | null;
      reference: string | null;
      status: string;
    }
  >;
  components: {
    type: string;
    size: string;
    nominal_weight: number | null;
    row: number;
  }[];
  component_basis: string;
  flags: string[];
  note: string;
  gradation_curve: {
    sieves_mm: number[];
    passing_pct: (number | null)[];
    reference: string | null;
  };
  relation_paths: {
    target_id: string;
    metric: string;
    scene_rule_ids: string[];
    observation_id: string | null;
    sources: {
      sheet?: string;
      cell?: string;
      row?: number;
      reference?: string | null;
    }[];
  }[];
};
export type ConstraintCheck = {
  target_id: string;
  metric: string;
  state: string;
  value: number | string | null;
  required_value?: number | string;
  operator?: string;
  upper?: number | null;
  unit?: string;
  margin?: number | null;
  reason: string;
  eligibility?: {
    status: string;
    comparison_mode: string;
    unresolved_dimensions: string[];
    dimensions: {
      dimension: string;
      required: unknown;
      recorded: unknown;
      status: string;
    }[];
  };
};
export type TestAction = {
  candidate_id: string;
  display_id: string;
  target_id: string;
  metric: string;
  action: string;
  test_method: string | null;
  conditions_to_confirm: string[];
  required_conditions?: Record<string, unknown>;
  reason: string;
  stop_condition: string;
  pool_sha256: string;
};
export type DecisionCandidate = {
  id: string;
  display_id: string;
  status: string;
  checks: ConstraintCheck[];
  failed_targets: string[];
  unknown_targets: string[];
  passes_known_requirements: boolean;
  scheme: MaterialScheme;
  metrics: Record<string, number>;
  evidence: Record<
    string,
    import("./types").Evidence & {
      method?: string;
      structured_conditions?: Record<string, unknown>;
      conditions_status?: string;
      id?: string;
    }
  >;
  preference_rank?: number;
  pareto_front?: boolean;
  tied_with?: string[];
};
export type MaterialDecision = {
  id: string;
  sha256: string;
  created_at: string;
  pool_id: string;
  pool_sha256: string;
  confirmation_id: string;
  confirmation_sha256: string;
  demand: Demand;
  scope: {
    context_kind: string;
    dataset: { id: string; sha256: string; revision: number };
    evidence_view: string;
    scope_note: string;
    evidence_view_note: string;
    inventory_confirmed: boolean;
  };
  pool_summary: { catalogue_total: number; included: number; excluded: number };
  excluded_from_pool: { id: string; display_id: string; reasons: string[] }[];
  comparison: {
    review_first_ids: string[];
    feasible_ids: string[];
    front_ids: string[];
    rule: string;
    unknown_preferences: string[];
  };
  test_plan?: {
    cards: TestAction[];
    strategy: string;
    order_basis: string;
    note: string;
  };
  results: DecisionCandidate[];
  summary: Record<string, number>;
  diagnosis: Diagnosis;
};

export async function decisionApi<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/v2" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json() as Promise<T>;
}
