export const researchBase = "/v4/research";

export async function researchApi<T>(path: string, body?: unknown, signal?: AbortSignal): Promise<T> {
  const response = await fetch(researchBase + path, body === undefined ? { signal } : {
    method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify(body), signal,
  });
  if (!response.ok) {
    const error = await response.json().catch(() => ({ detail: "研究资料暂时不可用，请刷新后重试。" }));
    throw new Error(typeof error.detail === "string" ? error.detail : "输入内容不符合要求，请检查计划数量与筛选条件。");
  }
  return response.json() as Promise<T>;
}

export type MetricKey = "DS" | "strain" | "TSR" | "residual";
export const researchMetrics: Record<MetricKey, { label: string; unit: string }> = {
  DS: { label: "动稳定度", unit: "次/mm" }, strain: { label: "最大弯拉应变", unit: "με" },
  TSR: { label: "冻融劈裂比", unit: "%" }, residual: { label: "残留稳定度比", unit: "%" },
};
export type ResearchFilters = { source: string; kind: "all" | "oil_ratio" | "nominal_blend"; supported_only: boolean; q: string };
export type CandidateSummary = { id: string; parent_id: string; source_code: string; gradation: string; product: string;
  kind: string; oil_stone_ratio_pct: number; rap_nominal_pct: number; change_label: string; within_observed_support: boolean;
  measured_performance: null; engineering_release_allowed: false };
export type CandidateList = { total: number; offset: number; limit: number; items: CandidateSummary[]; scope_sha256: string };
export type SourceReference = { sheet: string; row: number; cell: string; value: number; raw_value: number; transform: string; cached_formula?: string | null };
export type CandidateDetail = { summary: CandidateSummary;
  candidate: { id: string; prediction: Record<MetricKey, number>; predicted_change_vs_parent_prediction: Record<MetricKey, number>;
    model_std_not_calibrated: Record<MetricKey, number>; measured_performance: null; inherits_parent_measurements: false;
    unknowns: string[]; nominal_component_weights: number[] };
  parent: { id: string; source_code: string; gradation: string; product: string; oil_stone_ratio_pct: number;
    metrics: Partial<Record<MetricKey, { value: number; unit: string; references: SourceReference[] }>>; curve_reference: string };
  components: { row: number; type: string; size: string; before: number; after: number; delta_percentage_points: number }[];
  interpretation: string };
export type ExperimentRow = { metric: MetricKey; label: string; unit: string; baseline_mae: number; candidate_mae: number;
  relative_improvement: number; repeats_better_than_mean: number; head_acceptance_fraction?: number };
export type ResearchOverview = { scope_sha256: string; compatibility: { matches: boolean; reason: string | null };
  counts: { hypotheses: number; within_observed_support: number; input_alias_groups: number; observed_conflict_groups: number;
    masked_curve_alias_groups: number; source_cells: number }; sources: string[];
  latest_experiment: { outer_folds: number; repeats: number; rows: ExperimentRow[]; exact_reproduction: boolean; note: string };
  previous_experiment: { repeats: number; rows: ExperimentRow[]; note: string };
  evidence: { id: string; title: string; url: string; sha256: string }[]; limits: string[] };
export type SourceAudit = { input_alias_groups: number; groups_with_observed_conflict: number; masked_curve_alias_groups: number;
  dataset: { dataset_id: string }; issues: { id: string; state: string; conflicting_metrics: MetricKey[];
  label_ranges: Record<MetricKey, number | null>; interpretation: string;
  entries: { id: string; source_code: string; gradation: string; product: string; curve_input_masked: boolean;
    labels: Partial<Record<MetricKey, { value: number; unit: string; references: SourceReference[]; suspected_derived_mean: boolean }>> }[];
  questions: { field: string; question: string; answer: null; reference: null }[] }[] };
export type ResearchPlan = { id: string; title: string; created_at: string; sha256: string; scope_sha256: string;
  filters: ResearchFilters; selected_formulations: number; formulations: CandidateDetail[]; selection_method: string;
  required_before_testing: string[]; note: string; engineering_release_allowed: false; laboratory_results: null };
