export interface Target {
  metric: string;
  operator: ">" | ">=" | "<" | "<=" | "between";
  value: number;
  upper?: number | null;
  source_kind: string;
  reference?: string | null;
  test_method?: string | null;
  conditions?: string | null;
}
export interface Scenario {
  name: string;
  maintenance_method: string;
  layer: string;
  distress_type: string;
  climate_zone: string | null;
  traffic_level: string | null;
  targets: Target[];
  candidate_ids: string[] | null;
  available_sources?: string[] | null;
  rap_min_pct: number;
  priority: string;
  case_id: string | null;
  context_kind: string;
  budget?: number | null;
}
export interface Evidence {
  value: number;
  unit: string;
  n_recorded: number;
  n_independent_assumed: number | null;
  suspected_derived_mean?: boolean;
  range: number[];
  source_kind: string;
  raw_labels?: {
    sheet: string;
    row: number;
    cell: string;
    raw_value: number;
    value: number;
    transform: string;
    suspected_derived_mean?: boolean;
  }[];
  observation_id?: string;
  test_group?: string;
  conditions?: string;
}
export interface Observation {
  id: string;
  recipe_id: string;
  metric: string;
  value: number;
  unit: string;
  state: string;
  data_scope: string;
  use_for_recommendation: boolean;
  created_at: string;
  payload: {
    test_group: string;
    method: string;
    conditions: string;
    source_reference: string;
    sample_count: number;
    supersedes_id?: string;
    review?: { reviewer: string; note: string; conditions_confirmed: boolean };
  };
}
export interface Recipe {
  id: string;
  display_id: string;
  dataset_id: string;
  source: string;
  gradation: string;
  product: string;
  oil_stone_ratio_pct: number | null;
  binder_content_pct: number | null;
  rap_nominal_pct: number | null;
  parent_id: string | null;
  kind: string;
  metrics: Record<string, number>;
  evidence: Record<string, Evidence>;
  payload: {
    fixture_id?: string;
    flags: string[];
    changes?: Record<string, { before: unknown; after: unknown }>;
    note?: string;
    gradation?: {
      curve: (number | null)[];
      sieves_mm: number[];
      curve_reference: string;
      rap_mass_basis: string;
      components: unknown[];
    } | null;
  };
  observations?: Observation[];
  passes_targets?: boolean;
  status?: string;
  failed_metrics?: string[];
  missing_metrics?: string[];
}
export interface Snapshot {
  id: string;
  created_at: string;
  results: Recipe[];
  recommended_for_review: string[];
  summary: {
    total: number;
    needs_review: number;
    needs_test: number;
    excluded: number;
  };
  scenario: Scenario;
  snapshot_sha256: string;
  empty_reason: string | null;
  next_tests: { recipe_id: string; metric: string; reason: string }[];
  versions: { dataset_revision: number; dataset_sha256: string };
}
export interface Case {
  id: string;
  title: string;
  family: string;
  provenance: string;
  scenario: Scenario;
}
export interface Dataset {
  id: string;
  filename: string;
  sha256: string;
  revision: number;
  imported_at: string;
  summary: {
    specimen_total: number;
    gradation_blocks: number;
    source_codes: number;
    operational_recipes: number;
    suspected_mean_DS_groups: number;
    formula_errors: { sheet: string; cell: string; value: string }[];
    curve_mismatches: unknown[];
    conditional_aliases: string[];
  };
}
export const metrics: Record<
  string,
  { name: string; short: string; unit: string }
> = {
  DS: { name: "动稳定度", short: "DS", unit: "次/mm" },
  strain: { name: "最大弯拉应变", short: "低温应变", unit: "με" },
  TSR: { name: "冻融劈裂强度比", short: "TSR", unit: "%" },
  residual: { name: "残留稳定度比", short: "残留稳定度", unit: "%" },
  stability: { name: "稳定度", short: "稳定度", unit: "kN" },
  flow: { name: "流值", short: "流值", unit: "mm" },
  VV: { name: "空隙率", short: "空隙率", unit: "%" },
  VMA: { name: "矿料间隙率", short: "VMA", unit: "%" },
};
export const core = ["DS", "strain", "TSR", "residual"];
export const fmt = (n: number | null | undefined, digits = 1) =>
  n == null
    ? "—"
    : n.toLocaleString("zh-CN", { maximumFractionDigits: digits });
export const flags: Record<string, string> = {
  component_curve_requires_review: "原料与级配曲线需核对",
  preblended_curve_without_component_weights: "仅有预混级配，分档比例缺失",
  gradation_key_unmatched: "级配身份未匹配",
  oil_input_requires_review: "油石比录入待复核",
  product_alias_unconfirmed_90_suffix: "90#与90#-3别名待确认",
  test_conditions_unverified: "试验条件待确认",
  rap_mass_basis_unconfirmed: "RAP计量基准待确认",
  all_parent_performance_invalidated: "父方案性能依据已失效",
  requires_new_tests: "微调方案需重新试验",
};
