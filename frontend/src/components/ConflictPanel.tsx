import type { Diagnosis } from "../decision-types";
const names: Record<string, string> = {
  DS: "动稳定度",
  strain: "弯拉应变",
  TSR: "TSR",
  residual: "残留稳定度",
};
export function ConflictPanel({ diagnosis }: { diagnosis: Diagnosis }) {
  return (
    <section
      className={"conflict-panel diagnosis-" + diagnosis.status}
      aria-label="决策诊断"
    >
      <div className="diagnosis-heading">
        <strong>
          {diagnosis.status === "known_conflict"
            ? "已知冲突 · 池内联合无解"
            : diagnosis.status === "evidence_insufficient"
              ? "证据不足 · 尚不能判定无解"
              : diagnosis.status === "pool_empty"
                ? "候选池为空"
                : "当前判断"}
        </strong>
        <span>
          {diagnosis.certificates.length
            ? `${diagnosis.certificates.length} 组冲突证书`
            : "范围内判断"}
        </span>
      </div>
      <p>{diagnosis.message}</p>
      {diagnosis.certificates.map((cert) => (
        <details key={cert.certificate_sha256} className="conflict-certificate">
          <summary>
            {cert.requirements
              .map(
                (r) =>
                  `${names[r.metric] || r.metric} ${r.operator || ""} ${r.value ?? ""}${r.unit || ""}`,
              )
              .join(" + ")}
            <span>
              {cert.minimality_status === "verified_inclusion_minimal"
                ? "包含关系下最小"
                : "最小已知失败覆盖，仍有未知"}
            </span>
          </summary>
          <p>删除任一要求后的候选见证：</p>
          <ul>
            {cert.deletion_witnesses.map((w) => (
              <li key={w.removed_target}>
                移除{" "}
                {w.removed_target.split(":").slice(-2, -1)[0] ||
                  w.removed_target}{" "}
                → {w.display_id}：
                {w.kind === "all_remaining_satisfied"
                  ? "满足该子集内其他要求"
                  : "未被排除，仍需补证据"}
              </li>
            ))}
          </ul>
          <small className="mono">
            证书 {cert.certificate_sha256.slice(0, 16)}
          </small>
        </details>
      ))}
      <small>{diagnosis.scope_note}</small>
      {diagnosis.enumeration_complete === false && (
        <p>目标较多，仅返回经验证的一组证书，未穷举所有冲突。</p>
      )}
    </section>
  );
}
