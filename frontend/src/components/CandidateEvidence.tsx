import { useEffect, useRef, useState } from "react";
import type { DecisionCandidate } from "../decision-types";
import { fieldLabel, displayValue } from "../decision-labels";

export function CandidateEvidence({
  candidate,
  datasetId,
}: {
  candidate: DecisionCandidate;
  datasetId: string;
}) {
  const [raw, setRaw] = useState<{
      sheet: string;
      row: number;
      payload: {
        cells: Record<
          string,
          { value: unknown; formula: string | null; error: boolean }
        >;
      };
    } | null>(null),
    [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  const request = useRef(0);
  useEffect(() => {
    setRaw(null);
    setError("");
    setBusy(false);
    return () => {
      request.current++;
    };
  }, [candidate.id]);
  async function open(sheet: string, row: number) {
    const serial = ++request.current;
    setBusy(true);
    setError("");
    try {
      const response = await fetch(
        `/v1/evidence/${encodeURIComponent(datasetId)}/${encodeURIComponent(sheet)}/${row}`,
      );
      const body = await response.json();
      if (!response.ok) throw new Error(body.detail);
      if (serial === request.current) setRaw(body);
    } catch (e) {
      if (serial === request.current) setError(String(e));
    } finally {
      if (serial === request.current) setBusy(false);
    }
  }
  return (
    <section className="candidate-evidence">
      <h3>试验依据 · 可追到源单元格</h3>
      <p className="evidence-version">
        材料 {candidate.scheme.material_version.slice(0, 16)} · 数据 {datasetId}
      </p>
      {Object.entries(candidate.evidence)
        .filter(([key]) => candidate.checks.some((c) => c.metric === key))
        .map(([metric, e]) => (
          <article key={metric}>
            <div>
              <strong>{fieldLabel(metric)}</strong>
              <span>
                {Number(e.value.toFixed(2))} {e.unit}
              </span>
            </div>
            <small>
              历史记录范围{" "}
              {e.range?.map((v) => Number(v.toFixed(2))).join("–") || "未记录"}{" "}
              · {e.n_recorded} 条标签 · 暂按独立记录{" "}
              {e.n_independent_assumed ?? "未知"}；真实独立批次未确认
            </small>
            <p>
              {e.suspected_derived_mean
                ? "含疑似均值标签，未增加独立样本数。"
                : ""}{" "}
              方法：{e.method || "未披露"}；试验条件：
              {e.structured_conditions
                ? JSON.stringify(e.structured_conditions)
                : "见原记录，尚需核实适用性"}
              。
            </p>
            <div className="source-cells">
              {e.raw_labels?.map((label) => (
                <button
                  className="source-link"
                  key={label.sheet + label.cell}
                  onClick={() => void open(label.sheet, label.row)}
                >
                  {label.sheet}!{label.cell}
                </button>
              ))}
              {e.observation_id && <small>审核观察 {e.observation_id}</small>}
            </div>
          </article>
        ))}
      {!Object.keys(candidate.evidence).length && (
        <p className="demand-open">
          当前材料版本没有有效实测证据。父版本性能不继承。
        </p>
      )}
      {busy && <p role="status">读取原始行…</p>}
      {error && <p role="alert">{error}</p>}
      {raw && (
        <div className="raw-evidence" role="region" aria-label="原始行详情">
          <div>
            <strong>
              {raw.sheet} · 第{raw.row}行
            </strong>
            <button className="secondary" onClick={() => setRaw(null)}>
              关闭原始行
            </button>
          </div>
          <div className="table-scroll">
            <table>
              <thead>
                <tr>
                  <th>单元格</th>
                  <th>原始值</th>
                  <th>公式</th>
                  <th>单元格状态</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(raw.payload.cells).map(([key, value]) => (
                  <tr key={key}>
                    <td>{key}</td>
                    <td>{displayValue(value.value)}</td>
                    <td>{value.formula || "无公式"}</td>
                    <td>{value.error ? "表内错误" : "记录正常"}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </section>
  );
}
