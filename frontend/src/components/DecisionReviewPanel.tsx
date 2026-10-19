import { useEffect, useMemo, useState } from "react";
import { Download, FileCheck2, LoaderCircle, RefreshCw, X } from "lucide-react";
import { decisionApi } from "../decision-types";
import type { DecisionReview } from "../review-types";
import { saveJson } from "../review-types";
import { fieldLabel } from "../decision-labels";

const labels: Record<string, string> = {
  satisfied: "满足",
  failed: "不满足",
  missing: "缺测",
  incomparable: "不可比",
};
const sources: Record<string, string> = {
  constructed_demo: "构造演示",
  enterprise_reference: "企业参考",
  project_target: "项目自定",
  project_approved: "项目批准声明",
  normative: "规范声明",
};

export function DecisionReviewPanel({
  decisionId,
  onClose,
}: {
  decisionId: string;
  onClose?: () => void;
}) {
  const [review, setReview] = useState<DecisionReview | null>(null);
  const [error, setError] = useState("");
  const [refresh, setRefresh] = useState(0);
  const requestId = useMemo(() => crypto.randomUUID(), [decisionId, refresh]);
  useEffect(() => {
    let live = true;
    setReview(null);
    setError("");
    decisionApi<DecisionReview>("/review/reports", {
      decision_id: decisionId,
      request_id: requestId,
    })
      .then((data) => {
        if (live) setReview(data);
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [decisionId, requestId]);

  return (
    <section className="review-sheet panel" aria-label="选材复核单">
      <div className="review-sheet-heading">
        <div>
          <h2>
            <FileCheck2 size={20} />
            选材复核单
          </h2>
          <p>数值结论、工程缺口与下一步行动，保存在同一份复核记录中。</p>
        </div>
        <div className="review-buttons">
          <button
            className="secondary"
            onClick={() => setRefresh((r) => r + 1)}
          >
            <RefreshCw size={15} />
            重新生成
          </button>
          {onClose && (
            <button
              className="icon-button"
              onClick={onClose}
              aria-label="关闭复核单"
            >
              <X size={18} />
            </button>
          )}
        </div>
      </div>
      {error ? (
        <div className="message error" role="alert">
          {error}
          <button
            className="secondary"
            onClick={() => setRefresh((r) => r + 1)}
          >
            重试
          </button>
        </div>
      ) : !review ? (
        <div className="review-loading" role="status">
          <LoaderCircle className="spin" size={20} />
          正在核对冻结决策与原始依据…
        </div>
      ) : (
        <>
          <div
            className={
              "review-verdict " + (review.freshness.current ? "" : "outdated")
            }
          >
            <div>
              <strong>{review.name}</strong>
              <p>{review.diagnosis.message}</p>
              <small>{review.scope.evidence_view_note}</small>
            </div>
            <div className="review-verdict-numbers">
              <span>
                <b>{review.numerical_summary.feasible_count}</b> 数值满足
              </span>
              <span>
                <b>{review.numerical_summary.candidate_count}</b> 本次候选
              </span>
            </div>
          </div>
          <p className="review-scope-line">
            {review.freshness.current
              ? "生成时与当前输入一致"
              : `生成时快照已过期：${review.freshness.reasons.join("；")}`}
            。工程适用与发布等待外部核验。
          </p>
          <div className="review-two-columns">
            <div>
              <h3>要求从哪里来</h3>
              {review.requirements.map((t) => (
                <details className="review-target" key={t.target_id}>
                  <summary>
                    <span>
                      {fieldLabel(t.metric)} {t.operator} {String(t.value)}{" "}
                      {t.unit}
                    </span>
                    <small>{sources[t.source.kind] || t.source.kind}</small>
                  </summary>
                  <p>{t.source.reference}</p>
                  <p>
                    {t.test_method || "试验方法待确认"}；条件：
                    {Object.keys(t.conditions).length
                      ? JSON.stringify(t.conditions)
                      : "待补齐"}
                  </p>
                  <ul>
                    {t.issues.map((issue) => (
                      <li key={issue}>{issue}</li>
                    ))}
                  </ul>
                </details>
              ))}
            </div>
            <div>
              <h3>工程使用前还需要什么</h3>
              <ol className="review-action-list">
                {review.actions.map((a) => (
                  <li key={a.id}>
                    <strong>{a.title}</strong>
                    <p>{a.reason}</p>
                    <small>
                      所需：{a.needed.join("、")}；负责角色：{a.owner_role}
                    </small>
                  </li>
                ))}
              </ol>
            </div>
          </div>
          <details className="review-trace">
            <summary>
              查看优先复核候选的原值与来源（{review.focus_candidates.length}条）
            </summary>
            {review.focus_candidates.map((c) => (
              <div key={c.id}>
                <h3>{c.display_id}</h3>
                <p>
                  待核验组成：
                  {c.material_unknowns.map(fieldLabel).join("、") ||
                    "声明完整，待独立审核"}
                </p>
                <div className="table-scroll">
                  <table>
                    <thead>
                      <tr>
                        <th>项目</th>
                        <th>记录值</th>
                        <th>判断</th>
                        <th>原始依据预览</th>
                      </tr>
                    </thead>
                    <tbody>
                      {c.checks.map((check) => (
                        <tr key={check.target_id}>
                          <td>{fieldLabel(check.metric)}</td>
                          <td>
                            {check.value == null ? "—" : String(check.value)}{" "}
                            {check.unit}
                          </td>
                          <td>
                            {labels[check.state]}
                            <br />
                            <small>
                              {check.unresolved_dimensions.length
                                ? "方法或条件待核验"
                                : "仍需工程审核"}
                            </small>
                          </td>
                          <td>
                            {check.source_preview
                              .map((s) => `${s.sheet}!${s.cell}`)
                              .join("、") || "待补齐"}
                            {check.source_count > 6 && (
                              <small>
                                （展示6/{check.source_count}，完整来源见JSON）
                              </small>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            ))}
            {!review.focus_candidates.length && (
              <p>当前范围没有无已知失败的候选；请先复核要求或补充独立候选。</p>
            )}
          </details>
          <div className="review-export-row">
            <div>
              <small>
                生成于 {new Date(review.generated_at).toLocaleString("zh-CN")}
                。导出保留本次复核内容；后续输入变化需重新生成。
              </small>
              <p className="review-fingerprint">
                决策 {review.decision_sha256.slice(0, 16)}　复核{" "}
                {review.review_sha256.slice(0, 16)}
              </p>
            </div>
            <div className="review-buttons">
              <a
                className="secondary"
                href={`/v2/review/reports/${encodeURIComponent(review.id)}/report.html`}
                target="_blank"
                rel="noreferrer"
              >
                <FileCheck2 size={15} />
                打印复核单
              </a>
              <button
                className="secondary"
                onClick={() => saveJson(review, `${review.id}.json`)}
              >
                <Download size={15} />
                复核JSON
              </button>
            </div>
          </div>
        </>
      )}
    </section>
  );
}
