export const fieldLabels: Record<string, string> = {
  DS: "动稳定度",
  strain: "最大弯拉应变",
  TSR: "冻融劈裂强度比",
  residual: "残留稳定度",
  PG_grade: "PG等级",
  fatigue_life: "疲劳寿命",
  dynamic_modulus: "动态模量",
  test_method: "试验方法",
  temperature: "试验温度",
  load: "荷载",
  conditioning: "试件处理",
  loading_rate: "加载速率",
  aging: "老化条件",
  frequency: "频率",
  compaction: "压实条件",
  maintenance_method: "养护工法",
  layer: "结构层位",
  structure_type: "路面结构",
  mixing_window: "拌和窗口",
  compaction_window: "压实窗口",
  equipment: "设备",
  budget: "预算",
  rap_min_pct: "名义RAP下限",
  carbon_cap: "碳排上限",
  schedule_days: "供货期限",
  climate: "气候",
  traffic: "交通",
  class: "分组",
  source: "来源",
  distress: "病害",
  type: "类型",
  severity: "程度",
  mechanism: "成因",
  gradation_family: "级配族",
  source_codes: "料源范围",
  product_versions: "产品版本范围",
  context_kind: "使用范围",
  demo_case_id: "构造案例",
  requested_metrics: "性能需求",
  conditions: "条件",
  scene: "场景",
  inventory: "库存",
  construction: "施工条件",
  constraints: "资源要求",
  diagnosis: "诊断",
  review_first_ids: "优先复核候选",
};
export function fieldLabel(key: string) {
  return key
    .replace(/^condition\./, "")
    .split(".")
    .map((part) => fieldLabels[part] || part)
    .join("·");
}
const values: Record<string, string> = {
  demo_hot: "高温构造分组",
  demo_cold: "低温构造分组",
  demo_wet: "多雨构造分组",
  demo_heavy: "重载构造分组",
  demo_general: "一般交通构造分组",
  rutting: "车辙",
  thermal_cracking: "温缩裂缝",
  water_damage: "水损害",
  moderate: "中度",
  severe: "重度",
  mild: "轻度",
  numeric_feasible: "存在数值满足候选",
  known_conflict: "冻结池内已知冲突",
  evidence_insufficient: "证据不足",
  pool_empty: "候选池为空",
};
export function displayValue(value: unknown): string {
  if (value === null || value === undefined) return "未知";
  if (Array.isArray(value))
    return value.map(displayValue).join("、") || "空范围";
  if (typeof value === "object") return JSON.stringify(value);
  return values[String(value)] || String(value);
}
const exclusions: Record<string, string> = {
  source_not_in_inventory: "料源不在可用库存",
  product_version_not_in_inventory: "产品版本不在可用库存",
  gradation_family_mismatch: "级配族不匹配",
  incomplete_numeric_demo_scope: "不属于完整数值演示子池",
  maintenance_method_incompatible: "工法明确不兼容",
  layer_incompatible: "层位明确不兼容",
  structure_type_incompatible: "结构明确不兼容",
  equipment_incompatible: "设备明确不兼容",
  mixing_window_incompatible: "拌和窗口明确不兼容",
  compaction_window_incompatible: "压实窗口明确不兼容",
};
export function exclusionLabel(value: string) {
  return exclusions[value] || value;
}
