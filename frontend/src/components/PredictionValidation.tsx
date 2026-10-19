import { useEffect, useRef, useState } from "react";
import { decisionApi } from "../decision-types";
type MetricView = {
  metric: string;
  unit: string;
  measured: number | null;
  own_fold_oof: {
    value: number;
    fold: number;
    group: string;
    selected_family_in_fold: string;
  } | null;
  oof_unavailable_reason: string | null;
  research_fitted_prediction: {
    value: number;
    state: string;
    interval: {
      lower: number;
      upper: number;
      center: number;
      family: string;
    } | null;
  } | null;
  n: number;
  groups: number;
  outer_selected: { mae: number };
  dummy: { mae: number };
  beats_dummy_mae: boolean;
  calibration: {
    family: string;
    n_calibration_groups: number;
    n_test_groups: number;
    group_coverage: number;
    width: number;
    limitations: string[];
  };
};
type ModelView = {
  status: string;
  reason?: string;
  note?: string;
  research_prediction_reason: string | null;
  model_cards_sha256?: string;
  metrics: MetricView[];
};
const fmt = (value: number | null | undefined) =>
  value === null || value === undefined
    ? "不可用"
    : value.toLocaleString("zh-CN", { maximumFractionDigits: 1 });
export function PredictionValidation({
  decisionId,
  candidateId,
}: {
  decisionId: string;
  candidateId: string;
}) {
  const [view, setView] = useState<ModelView | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const request = useRef(0);
  useEffect(() => {
    setView(null);
    setError("");
    setBusy(false);
    return () => {
      request.current++;
    };
  }, [decisionId, candidateId]);
  async function load() {
    const serial = ++request.current;
    setBusy(true);
    setError("");
    try {
      const result = await decisionApi<ModelView>(
        `/decisions/${decisionId}/models/${candidateId}`,
      );
      if (serial === request.current) setView(result);
    } catch (e) {
      if (serial === request.current) setError(String(e));
    } finally {
      if (serial === request.current) setBusy(false);
    }
  }
  return (
    <section className="prediction-validation">
      <h3>实测、离折验证与研究预测</h3>
      <p>逐项查看模型依据；硬要求继续使用上方实测与适用性判断。</p>
      <button className="secondary" disabled={busy} onClick={() => void load()}>
        {busy
          ? "正在核对模型…"
          : view
            ? "重新核对模型"
            : "查看模型验证与研究预测"}
      </button>
      {error && <p role="alert">{error}</p>}
      {view && (
        <>
          <p>{view.reason || view.note}</p>
          {view.research_prediction_reason && (
            <p className="demand-open">
              全量拟合预测不可用：{view.research_prediction_reason}
            </p>
          )}
          {view.metrics.map((m) => (
            <article key={m.metric}>
              <h4>
                {m.metric} <small>{m.unit}</small>
              </h4>
              <dl>
                <div>
                  <dt>当前快照实测</dt>
                  <dd>{fmt(m.measured)}</dd>
                </div>
                <div>
                  <dt>本指标自身离折预测</dt>
                  <dd>{fmt(m.own_fold_oof?.value)}</dd>
                </div>
                <div>
                  <dt>研究性全量拟合预测</dt>
                  <dd>{fmt(m.research_fitted_prediction?.value)}</dd>
                </div>
              </dl>
              {m.own_fold_oof ? (
                <p>
                  外层折 {m.own_fold_oof.fold} · {m.own_fold_oof.group} ·
                  此折选择 {m.own_fold_oof.selected_family_in_fold}
                </p>
              ) : (
                <p>{m.oof_unavailable_reason}</p>
              )}
              <p>
                验证 {m.n} 个操作键 / {m.groups} 个来源分组 · 外层MAE{" "}
                {fmt(m.outer_selected.mae)} · 均值基线MAE {fmt(m.dummy.mae)}
              </p>
              <strong className="research-result">
                {m.beats_dummy_mae
                  ? "该指标外层MAE优于均值基线"
                  : "该指标外层MAE未优于均值基线"}
              </strong>
              {m.research_fitted_prediction?.interval && (
                <p>
                  研究区间 [{fmt(m.research_fitted_prediction.interval.lower)},{" "}
                  {fmt(m.research_fitted_prediction.interval.upper)}
                  ]，来自单独校准模型{" "}
                  {m.research_fitted_prediction.interval.family}，中心{" "}
                  {fmt(m.research_fitted_prediction.interval.center)}。
                </p>
              )}
              <p>
                校准/测试分组 {m.calibration.n_calibration_groups}/
                {m.calibration.n_test_groups} · 测试组覆盖{" "}
                {fmt(m.calibration.group_coverage * 100)}% · 区间宽{" "}
                {fmt(m.calibration.width)}
              </p>
              <small>{m.calibration.limitations.join(" ")}</small>
            </article>
          ))}
          <p className="mono">
            模型档案 {view.model_cards_sha256?.slice(0, 16)}
          </p>
        </>
      )}
    </section>
  );
}
