import type { DecisionDifference } from "../decision-types";
import { displayValue, fieldLabel } from "../decision-labels";
export function DecisionDiff({
  difference,
}: {
  difference: DecisionDifference;
}) {
  return (
    <section className="panel decision-diff">
      <div className="panel-heading">
        <h2>场景变更 · 判断如何改变</h2>
        <span>{difference.changed ? "有实际变化" : "条件与结论一致"}</span>
      </div>
      <div className="demand-body">
        {!difference.changed && (
          <p>已比较两次快照，输入条件、目标、候选与结论一致。</p>
        )}
        {difference.input_changes.map((c) => (
          <p key={c.field}>
            <strong>{fieldLabel(c.field)}</strong>：{displayValue(c.before)} →{" "}
            {displayValue(c.after)}
          </p>
        ))}
        {difference.rule_changes.map((c, i) => (
          <p key={i}>
            命中规则：{c.before.map((r) => r.id).join("、") || "无"} →{" "}
            {c.after.map((r) => r.id).join("、") || "无"}
          </p>
        ))}
        {difference.target_changes.map((c) => (
          <p key={c.metric}>
            <strong>{fieldLabel(c.metric)} 目标</strong>：
            {c.before
              .map((t) => `${t.operator} ${t.value}${t.unit}`)
              .join("；") || "无"}{" "}
            →{" "}
            {c.after
              .map((t) => `${t.operator} ${t.value}${t.unit}`)
              .join("；") || "无"}
          </p>
        ))}
        <p>
          候选新增 {difference.candidate_changes.added.length} · 移除{" "}
          {difference.candidate_changes.removed.length} · 判断改变{" "}
          {difference.candidate_changes.outcome_changes.length}
        </p>
        {difference.conclusion_changes.map((c) => (
          <p key={c.field}>
            结论 {fieldLabel(c.field)}：{displayValue(c.before)} →{" "}
            {displayValue(c.after)}
          </p>
        ))}
        {difference.manual_overrides.map((c, i) => (
          <p key={i}>
            人工修改：{c.before.value} → {c.after.value}；{c.reason}
          </p>
        ))}
        <small>{difference.note}</small>
      </div>
    </section>
  );
}
