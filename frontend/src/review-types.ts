export type ReviewRequirement = {
  id: string;
  kind: "basic" | "technical_detail" | "bonus";
  source_page: number;
  title: string;
  requirement_paraphrase: string;
  status: string;
  status_label: string;
  delivered_scope: string;
  evidence_ids: string[];
};

export type ReviewSource = {
  id: string;
  title: string;
  standard: string;
  type: string;
  notice_date: string;
  page_publication_date: string;
  effective_date: string;
  replaces: string;
  url: string;
  verification_scope: string;
  verified_on: string;
};

export type Highlight = {
  id: string;
  title: string;
  question: string;
  case_id: string;
  mechanism: string;
  steps: string[];
  boundary: string;
};

export type ReviewOverview = {
  requirements: ReviewRequirement[];
  evidence: Record<
    string,
    {
      label: string;
      path: string;
      integrity: string;
      download_url: string | null;
    }
  >;
  highlights: Highlight[];
  sources: ReviewSource[];
  questions: { question: string; answer: string; requirement_ids: string[] }[];
  external_pending: string[];
  scope_note: string;
  current_data: {
    historical_keys: number;
    ac13_keys: number;
    complete_four_metric_ac13_keys: number;
    variants: number;
    identity_note: string;
  };
  case_replay: {
    scope: string;
    data: {
      cases?: {
        case?: string;
        case_id?: string;
        feasible_B1?: number;
        feasible_V2?: number;
        pool?: number;
        diagnosis?: string;
      }[];
    };
  };
};

export type DecisionReview = {
  id: string;
  sha256: string;
  review_sha256: string;
  decision_id: string;
  decision_sha256: string;
  generated_at: string;
  name: string;
  context_kind: string;
  status: string;
  scope: { scope_note: string; evidence_view_note: string };
  freshness: { current: boolean; reasons: string[] };
  numerical_summary: {
    candidate_count: number;
    feasible_count: number;
    states: Record<string, number>;
  };
  requirements: {
    target_id: string;
    label: string;
    metric: string;
    operator: string;
    value: string | number;
    unit: string;
    source: { kind: string; reference: string };
    issues: string[];
    test_method: string | null;
    conditions: Record<string, unknown>;
  }[];
  focus_candidates: {
    id: string;
    display_id: string;
    material_version: string;
    material_unknowns: string[];
    checks: {
      target_id: string;
      metric: string;
      value: unknown;
      unit: string | null;
      state: string;
      engineering_applicability: string;
      unresolved_dimensions: string[];
      source_preview: { sheet: string; cell: string; value: unknown }[];
      source_count: number;
    }[];
  }[];
  actions: {
    id: string;
    title: string;
    reason: string;
    needed: string[];
    owner_role: string;
  }[];
  diagnosis: { message: string; certificates: unknown[] };
  model_note: string;
  export_note: string;
};

export function saveJson(value: unknown, filename: string) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}
