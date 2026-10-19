import type { MaterialScheme } from "../decision-types";
const labels: Record<string, string> = {
  source_code: "料源标识",
  product: "产品标识",
  gradation: "级配",
  oil_stone_ratio_pct: "油石比",
  binder_content_pct: "计算沥青用量",
  rap_nominal_pct: "名义RAP",
  modifier: "改性剂",
  additive: "助剂",
  mixing_window: "拌和窗口",
  compaction_window: "压实窗口",
  equipment: "设备",
};
export function MaterialSchemeCard({ scheme }: { scheme: MaterialScheme }) {
  return (
    <section className="material-scheme">
      <div className="material-title">
        <h3>{scheme.display_id} · 材料组成</h3>
        <small>
          {scheme.kind === "variant" ? "微调版本 · 待验证" : "历史操作键"}
        </small>
      </div>
      <dl className="material-fields">
        {Object.entries(scheme.fields).map(([key, field]) => (
          <div key={key}>
            <dt>{labels[key] || key}</dt>
            <dd>
              {field.value === null ? (
                <span className="unknown">未披露 / 待确认</span>
              ) : (
                <>
                  {typeof field.value === "number"
                    ? Number(field.value.toFixed(2))
                    : Array.isArray(field.value)
                      ? field.value.join("、")
                      : field.value}{" "}
                  {field.unit}
                </>
              )}
              {field.status === "mass_basis_unconfirmed" && (
                <small>质量基准待确认</small>
              )}
            </dd>
          </div>
        ))}
      </dl>
      <details>
        <summary>组成明细、关系路径与版本</summary>
        <p>{scheme.note}</p>
        {scheme.components.length > 0 && (
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>组分</th>
                  <th>规格</th>
                  <th>表内名义权重</th>
                  <th>来源</th>
                </tr>
              </thead>
              <tbody>
                {scheme.components.map((c, i) => (
                  <tr key={i}>
                    <td>{c.type}</td>
                    <td>{c.size}</td>
                    <td>
                      {c.nominal_weight === null
                        ? "未知"
                        : (c.nominal_weight * 100).toFixed(2) + "%"}
                    </td>
                    <td>级配!{c.row}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
        {scheme.relation_paths.map((path) => (
          <p key={path.target_id}>
            场景 {path.scene_rule_ids.join(" / ") || "项目输入"} → {path.metric}
            要求 → 当前材料版本 → {path.observation_id || "缺少观察"} →{" "}
            {path.sources
              .map((s) => (s.cell ? `${s.sheet}!${s.cell}` : s.reference))
              .join("、") || "待补来源"}
          </p>
        ))}
        <p className="mono">
          {scheme.material_version}
          <br />
          {scheme.dataset_id}
        </p>
      </details>
    </section>
  );
}
