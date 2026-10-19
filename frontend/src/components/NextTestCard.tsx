import type { TestAction } from "../decision-types";
import { fieldLabel } from "../decision-labels";
export function NextTestCard({
  cards,
  knownFailure = false,
  note,
}: {
  cards: TestAction[];
  knownFailure?: boolean;
  note?: string;
}) {
  return (
    <section className="validation-actions">
      <h3>下一步验证计划</h3>
      {knownFailure ? (
        <p>
          当前材料存在已知失败，先复核要求或创建新版本；不作为仅待补齐试验的可行候选。
        </p>
      ) : (
        cards.map((card) => (
          <article key={card.target_id}>
            <strong>
              {fieldLabel(card.metric)} ·{" "}
              {card.action === "confirm_applicability"
                ? "核验原试验适用性"
                : card.action === "collect_resource_evidence"
                  ? "补充资源证据"
                  : "取得同口径试验"}
            </strong>
            <p>{card.reason}</p>
            <small>
              方法：{card.test_method || "待确认"}；待确认条件：
              {card.conditions_to_confirm.map(fieldLabel).join("、") ||
                "见要求来源"}
            </small>
            <p>停止条件：{card.stop_condition}</p>
          </article>
        ))
      )}
      <small>{note || "旧版快照未包含验证计划，请重新生成。"}</small>
    </section>
  );
}
