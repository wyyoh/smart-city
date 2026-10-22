import type {
  Demand,
  DemandRequest,
  DecisionCandidate,
  MaterialDecision,
} from "./decision-types";
import type { CandidateDetail, CandidateSummary } from "./research-types";

export const creativeBase = "/v5/design";
export async function creativeApi<T>(
  path: string,
  body?: unknown,
  signal?: AbortSignal,
): Promise<T> {
  const response = await fetch(
    creativeBase + path,
    body === undefined
      ? { signal }
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
          signal,
        },
  );
  if (!response.ok) {
    const result = await response
      .json()
      .catch(() => ({ detail: "读取失败，请稍后重试。" }));
    throw new Error(
      typeof result.detail === "string"
        ? result.detail
        : "请检查输入的目标、理由与字段。",
    );
  }
  return response.json() as Promise<T>;
}
export type CreativeCase = {
  id: string;
  title: string;
  question: string;
  mechanism: string;
  action: string;
  targets: Record<string, number>;
  rap_min_pct: number | null;
  example_request: DemandRequest;
};
export type CaseRun = {
  id: string;
  created_at: string;
  sha256: string;
  case_id: string;
  title: string;
  question: string;
  identity: string;
  decision: MaterialDecision;
  adjustment_reason: string;
  baseline: {
    method: string;
    feasible_ids: string[];
    same_feasible_set: boolean;
    note: string;
  };
  run_request: {
    target_overrides: Record<string, number>;
    adjustment_reason: string;
    rap_min_pct: number | null;
  };
};
export type PreferenceComparison = {
  id?: string;
  created_at?: string;
  sha256: string;
  kind: string;
  priority_order: string[];
  reason: string;
  source_decision_sha256: string;
  same_feasible_set: boolean;
  comparison: MaterialDecision["comparison"];
  candidates: DecisionCandidate[];
  explanations: {
    id: string;
    rank: number;
    tied_with: string[];
    values: {
      metric: string;
      label: string;
      value: number;
      unit: string;
      margin: number | null;
    }[];
    first_difference_from_first: {
      metric: string;
      label: string;
      value: number;
      first_value: number;
      unit: string;
    } | null;
  }[];
};
export type Exploration = {
  decision_id: string;
  decision_sha256: string;
  parent: DecisionCandidate;
  demand_context: Demand;
  scope_sha256: string;
  total_parent_hypotheses: number;
  total: number;
  items: CandidateSummary[];
  locked_fields: string[];
  empty_reason: string | null;
};
export type DesignDraft = {
  id: string;
  title: string;
  created_at: string;
  sha256: string;
  parent_recipe_id: string;
  hypothesis_id: string;
  design_intent: string;
  demand_context: Demand;
  hypothesis: CandidateDetail;
  measured_performance: null;
  inherits_parent_measurements: false;
  actual_changes: {
    oil_stone_ratio_pct: { before: number; after: number; unit: string };
  };
};
export type SavedSummary = {
  id: string;
  title: string;
  created_at: string;
  case_id?: string;
  parent_recipe_id?: string;
  design_intent?: string;
  sha256: string;
};
export type AdjustmentResult = {
  changes: { metric: string; before: number; after: number; unit: string }[];
  before_feasible_ids: string[];
  after_feasible_ids: string[];
  note: string;
  pool_size: number;
};
export const metricNames: Record<string, string> = {
  DS: "动稳定度",
  strain: "弯拉应变",
  TSR: "冻融劈裂比",
  residual: "残留稳定度比",
  rap_min_pct: "名义RAP最低比例",
};
export const metricUnits: Record<string, string> = {
  DS: "次/mm",
  strain: "με",
  TSR: "%",
  residual: "%",
  rap_min_pct: "%",
};
export const displayNumber = (v: unknown, digits = 2) =>
  typeof v === "number"
    ? v.toLocaleString("zh-CN", { maximumFractionDigits: digits })
    : "未知";
export const candidateName = (row: DecisionCandidate) =>
  `${row.scheme.fields.source_code.value} / ${row.display_id}`;
