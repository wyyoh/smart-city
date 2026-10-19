import { useEffect, useRef, useState } from "react";
import {
  Download,
  Layers3,
  LoaderCircle,
  RefreshCw,
  FileText,
} from "lucide-react";
import { decisionApi } from "../decision-types";
import type {
  DecisionCandidate,
  DecisionDifference,
  Demand,
  MaterialDecision,
} from "../decision-types";
import { DemandCard } from "./DemandCard";
import { MaterialSchemeCard } from "./MaterialSchemeCard";
import { ConflictPanel } from "./ConflictPanel";
import { DecisionDiff } from "./DecisionDiff";
import { NextTestCard } from "./NextTestCard";
import { CandidateEvidence } from "./CandidateEvidence";
import { PredictionValidation } from "./PredictionValidation";
import { fieldLabel, exclusionLabel } from "../decision-labels";

export const checkLabel: Record<string, string> = {
  satisfied: "满足",
  failed: "不满足",
  missing: "缺测",
  incomparable: "不可比",
};
const stateLabel: Record<string, string> = {
  numeric_review: "数值满足 · 适用待审",
  evidence_review: "证据满足 · 待工程审核",
  needs_evidence: "需补证据",
  excluded: "未满足硬要求",
};
const metricLabel: Record<string, string> = {
  DS: "动稳定度",
  strain: "弯拉应变",
  TSR: "TSR",
  residual: "残留稳定度",
};
const number = (value: unknown) =>
  typeof value === "number"
    ? value.toLocaleString("zh-CN", { maximumFractionDigits: 1 })
    : value === null || value === undefined
      ? "—"
      : String(value);

function VariantEditor({
  candidate,
  onCreated,
}: {
  candidate: DecisionCandidate;
  onCreated: () => void;
}) {
  const [oil, setOil] = useState(""),
    [rap, setRap] = useState(""),
    [product, setProduct] = useState(""),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  async function save() {
    setBusy(true);
    setMessage("");
    try {
      const response = await fetch(`/v1/recipes/${candidate.id}/variants`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          ...(oil ? { oil_stone_ratio_pct: Number(oil) } : {}),
          ...(rap ? { rap_nominal_pct: Number(rap) } : {}),
          ...(product ? { product } : {}),
          note,
        }),
      });
      const result = await response.json();
      if (!response.ok)
        throw new Error(
          typeof result.detail === "string"
            ? result.detail
            : JSON.stringify(result.detail),
        );
      setMessage(
        `已创建 ${result.display_id}。新版本无父实测；重新检索后比较，并制定验证计划。`,
      );
      onCreated();
      setOil("");
      setRap("");
      setProduct("");
      setNote("");
    } catch (e) {
      setMessage(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <details className="variant-editor">
      <summary>微调并创建材料新版本</summary>
      <p>空白字段保持原组成；所有父版本性能证据失效，需对新版本重新验证。</p>
      <div className="demand-fields">
        <label>
          新油石比/%
          <input
            type="number"
            min="0.01"
            max="20"
            value={oil}
            onChange={(e) => setOil(e.target.value)}
          />
        </label>
        <label>
          新名义RAP/%
          <input
            type="number"
            min="0"
            max="100"
            value={rap}
            onChange={(e) => setRap(e.target.value)}
          />
        </label>
        <label>
          新产品标识
          <input value={product} onChange={(e) => setProduct(e.target.value)} />
        </label>
        <label>
          修改理由
          <input value={note} onChange={(e) => setNote(e.target.value)} />
        </label>
      </div>
      <button
        className="secondary"
        disabled={busy || !note.trim() || (!oil && !rap && !product)}
        onClick={() => void save()}
      >
        创建待验证版本
      </button>
      {message && <p role="status">{message}</p>}
    </details>
  );
}

export function DecisionWorkflow() {
  const [demand, setDemand] = useState<Demand | null>(null),
    [decision, setDecision] = useState<MaterialDecision | null>(null),
    [previous, setPrevious] = useState<MaterialDecision | null>(null);
  const [selected, setSelected] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [stale, setStale] = useState(false),
    [error, setError] = useState("");
  const [view, setView] = useState("all"),
    [filter, setFilter] = useState("all"),
    [page, setPage] = useState(0),
    [difference, setDifference] = useState<DecisionDifference | null>(null);
  const [history, setHistory] = useState<
      { id: string; name: string; created_at: string }[]
    >([]),
    [historyId, setHistoryId] = useState("");
  const serial = useRef(0),
    resultsRef = useRef<HTMLElement>(null);
  const [freshness, setFreshness] = useState<{
    current: boolean;
    reasons: string[];
  } | null>(null);
  async function checkFreshness() {
    if (!decision) return;
    const request = serial.current;
    try {
      const result = await decisionApi<{ current: boolean; reasons: string[] }>(
        `/decisions/${decision.id}/freshness`,
      );
      if (request === serial.current) setFreshness(result);
    } catch (e) {
      if (request === serial.current) setError(String(e));
    }
  }
  useEffect(() => {
    setFreshness(null);
    if (decision) void checkFreshness();
  }, [decision?.id]);
  const refreshHistory = () =>
    decisionApi<typeof history>("/decisions")
      .then(setHistory)
      .catch((e) => setError(String(e)));
  useEffect(() => {
    void refreshHistory();
    return () => {
      serial.current++;
    };
  }, []);
  function invalidate() {
    serial.current++;
    setDemand(null);
    setStale(true);
    setBusy(false);
    setDifference(null);
  }
  function accept(result: MaterialDecision) {
    setPrevious(decision);
    setDecision(result);
    setSelected(result.results.slice(0, 1).map((r) => r.id));
    setPage(0);
    setFilter("all");
    setStale(false);
    setDifference(null);
  }
  async function run() {
    if (!demand) return;
    const request = ++serial.current;
    setBusy(true);
    setError("");
    try {
      const pool = await decisionApi<{ id: string }>("/candidate-pools", {
        confirmation_id: demand.id,
        evidence_view: view,
      });
      if (request !== serial.current) return;
      const result = await decisionApi<MaterialDecision>("/decisions", {
        pool_id: pool.id,
      });
      if (request === serial.current) {
        accept(result);
        void refreshHistory();
        resultsRef.current?.scrollIntoView({
          behavior: "smooth",
          block: "start",
        });
      }
    } catch (e) {
      if (request === serial.current) setError(String(e));
    } finally {
      if (request === serial.current) setBusy(false);
    }
  }
  async function reopen() {
    const request = ++serial.current;
    setBusy(true);
    setError("");
    try {
      const result = await decisionApi<MaterialDecision>(
        "/records/" + encodeURIComponent(historyId),
      );
      if (request === serial.current) {
        accept(result);
        setDemand(null);
        setStale(true);
      }
    } catch (e) {
      if (request === serial.current) setError(String(e));
    } finally {
      if (request === serial.current) setBusy(false);
    }
  }
  async function comparePrevious() {
    if (!previous || !decision) return;
    const request = serial.current;
    try {
      const diff = await decisionApi<DecisionDifference>(
        `/decision-diff?before_id=${previous.id}&after_id=${decision.id}`,
      );
      if (request === serial.current) setDifference(diff);
    } catch (e) {
      setError(String(e));
    }
  }
  function exportSnapshot() {
    if (!decision) return;
    const url = URL.createObjectURL(
      new Blob([JSON.stringify(decision, null, 2)], {
        type: "application/json",
      }),
    );
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = decision.id + ".json";
    anchor.click();
    URL.revokeObjectURL(url);
  }
  function choose(id: string) {
    setSelected((current) =>
      current.includes(id)
        ? current.filter((x) => x !== id)
        : current.length < 3
          ? [...current, id]
          : current,
    );
  }
  const visible =
    decision?.results.filter(
      (r) =>
        filter === "all" ||
        (filter === "open"
          ? r.status === "needs_evidence"
          : filter === "review"
            ? r.passes_known_requirements
            : r.status === "excluded"),
    ) || [];
  return (
    <div className="decision-workflow">
      <DemandCard
        onConfirmed={(d) => {
          setDemand(d);
          setStale(true);
          setDifference(null);
        }}
        onInvalidated={invalidate}
      />
      <section className="panel generation-panel">
        <div>
          <h2>
            <Layers3 size={19} />
            03 冻结范围，生成材料方案
          </h2>
          <p>
            {demand
              ? `${demand.request.name} · ${demand.requirements_complete ? "需求已确认" : "存在待补充需求"}`
              : "先生成并确认上方需求卡"}
          </p>
        </div>
        <label>
          证据视图
          <select
            value={view}
            onChange={(e) => {
              serial.current++;
              setBusy(false);
              setDifference(null);
              setView(e.target.value);
              setStale(true);
            }}
          >
            <option value="all">完整目录 · 保留缺测候选</option>
            <option value="complete_numeric_demo">
              完整数值演示子池（排除缺测记录）
            </option>
          </select>
        </label>
        <button
          className="primary"
          disabled={busy || !demand?.ready_for_candidate_retrieval}
          onClick={() => void run()}
        >
          {busy ? (
            <LoaderCircle size={17} className="spin" />
          ) : (
            <Layers3 size={17} />
          )}
          冻结范围并生成方案
        </button>
      </section>
      {error && (
        <div role="alert" className="message error">
          {error}
          <button className="secondary" onClick={() => setError("")}>
            关闭
          </button>
        </div>
      )}
      <div className="decision-history">
        <label>
          重放历史快照
          <select
            value={historyId}
            onChange={(e) => setHistoryId(e.target.value)}
          >
            <option value="">选择已保存的决策记录</option>
            {history.map((h) => (
              <option value={h.id} key={h.id}>
                {new Date(h.created_at).toLocaleString("zh-CN")} · {h.name}
              </option>
            ))}
          </select>
        </label>
        <button
          className="secondary"
          disabled={!historyId || busy}
          onClick={() => void reopen()}
        >
          <RefreshCw size={15} />
          打开快照
        </button>
      </div>
      {decision && (
        <section
          ref={resultsRef}
          className="decision-results"
          aria-label="材料决策结果"
        >
          {stale && (
            <div className="message warning" role="status">
              当前展示的是已保存快照，不能代表最新输入。请确认需求后重新生成。
            </div>
          )}
          <div className="results-heading">
            <div>
              <h2>04 候选比较与验证行动</h2>
              <p>
                {decision.demand.request.name} ·{" "}
                {new Date(decision.created_at).toLocaleString("zh-CN")}
              </p>
            </div>
            <div className="report-actions">
              <a
                className="secondary"
                href={`/v2/decisions/${decision.id}/report.html`}
                target="_blank"
                rel="noreferrer"
              >
                <FileText size={15} />
                决策报告
              </a>
              <button className="secondary" onClick={exportSnapshot}>
                <Download size={15} />
                导出决策快照
              </button>
            </div>
          </div>
          <div className="pool-scope">
            <strong>
              本次范围 {decision.pool_summary.included} / 目录{" "}
              {decision.pool_summary.catalogue_total}
            </strong>
            <span>
              检索排除 {decision.pool_summary.excluded} ·{" "}
              {decision.scope.evidence_view === "all"
                ? "保留缺测记录"
                : "完整数值演示子池"}{" "}
              ·{" "}
              {decision.scope.inventory_confirmed
                ? "库存范围已声明"
                : "库存待确认"}
            </span>
            <small>
              {decision.scope.evidence_view_note} 池{" "}
              {decision.pool_sha256.slice(0, 12)}
            </small>
            <details>
              <summary>查看检索排除原因及数据版本</summary>
              <p>{decision.scope.scope_note}</p>
              <p className="mono">
                {decision.scope.dataset.id} · revision{" "}
                {decision.scope.dataset.revision}
              </p>
              {decision.excluded_from_pool.map((r) => (
                <p key={r.id}>
                  {r.display_id}：{r.reasons.map(exclusionLabel).join("、")}
                </p>
              ))}
            </details>
          </div>
          <div
            className={
              "version-receipt " +
              (freshness && !freshness.current ? "outdated" : "")
            }
          >
            <span>
              {freshness
                ? freshness.current
                  ? "数据、规则、代码与候选证据版本相符"
                  : `快照已过期：${freshness.reasons.join("；")}`
                : "正在核对证据版本…"}
            </span>
            <button className="secondary" onClick={() => void checkFreshness()}>
              重新核对版本
            </button>
          </div>
          <ConflictPanel diagnosis={decision.diagnosis} />
          <section className="panel candidate-comparison">
            <div className="comparison-toolbar">
              <div>
                <h3>候选方案</h3>
                <small>勾选最多3项并排比较组成、余量和未知条件</small>
              </div>
              <label>
                显示范围
                <select
                  value={filter}
                  onChange={(e) => {
                    setFilter(e.target.value);
                    setPage(0);
                  }}
                >
                  <option value="all">全部 {decision.results.length}</option>
                  <option value="review">
                    数值或证据满足 {decision.comparison.feasible_ids.length}
                  </option>
                  <option value="open">
                    需补证据 {decision.summary.needs_evidence}
                  </option>
                  <option value="failed">
                    硬要求失败 {decision.summary.excluded}
                  </option>
                </select>
              </label>
            </div>
            <div className="table-scroll">
              <table className="v2-candidate-table">
                <thead>
                  <tr>
                    <th>对比</th>
                    <th>材料身份</th>
                    {["DS", "strain", "TSR", "residual"].map((m) => (
                      <th key={m}>{metricLabel[m]}</th>
                    ))}
                    <th>当前判断</th>
                  </tr>
                </thead>
                <tbody>
                  {visible.slice(page * 8, page * 8 + 8).map((r) => (
                    <tr
                      key={r.id}
                      className={selected.includes(r.id) ? "selected" : ""}
                    >
                      <td>
                        <input
                          type="checkbox"
                          aria-label={`对比 ${r.display_id}`}
                          checked={selected.includes(r.id)}
                          disabled={
                            !selected.includes(r.id) && selected.length >= 3
                          }
                          onChange={() => choose(r.id)}
                        />
                      </td>
                      <td>
                        <button
                          className="candidate-id"
                          onClick={() => setSelected([r.id])}
                        >
                          <strong>{r.display_id}</strong>
                          <span>
                            {String(r.scheme.fields.source_code.value)} ·{" "}
                            {String(r.scheme.fields.gradation.value)}
                          </span>
                          <small>
                            {String(r.scheme.fields.product.value)} / 油石比{" "}
                            {number(r.scheme.fields.oil_stone_ratio_pct.value)}%
                          </small>
                        </button>
                      </td>
                      {["DS", "strain", "TSR", "residual"].map((m) => {
                        const checks = r.checks.filter((c) => c.metric === m);
                        return (
                          <td key={m}>
                            <strong>{number(r.metrics[m])}</strong>
                            {checks.map((c) => (
                              <small
                                className={"check-state " + c.state}
                                key={c.target_id}
                              >
                                {checkLabel[c.state]}
                                {c.margin !== null && c.margin !== undefined
                                  ? ` · 余量 ${c.margin >= 0 ? "+" : ""}${number(c.margin)}`
                                  : ""}
                              </small>
                            ))}
                          </td>
                        );
                      })}
                      <td>
                        <span className={"candidate-state " + r.status}>
                          {stateLabel[r.status]}
                        </span>
                        {r.preference_rank && (
                          <small>
                            偏好顺位 {r.preference_rank}
                            {r.tied_with?.length ? " · 并列" : ""}
                            {r.pareto_front ? " · 非支配" : ""}
                          </small>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!visible.length && (
              <p className="empty-candidates">
                此显示范围暂无候选，请调整筛选或检查库存。
              </p>
            )}
            <div className="table-pagination">
              <span>
                共 {visible.length} 项 · 第{" "}
                {Math.min(page + 1, Math.max(1, Math.ceil(visible.length / 8)))}{" "}
                / {Math.max(1, Math.ceil(visible.length / 8))} 页
              </span>
              <button
                className="secondary"
                disabled={page === 0}
                onClick={() => setPage((p) => p - 1)}
              >
                上一页
              </button>
              <button
                className="secondary"
                disabled={(page + 1) * 8 >= visible.length}
                onClick={() => setPage((p) => p + 1)}
              >
                下一页
              </button>
            </div>
            <p className="comparison-policy">
              {decision.comparison.rule} 未知偏好：
              {decision.comparison.unknown_preferences.join("、")}。
            </p>
          </section>
          <div className={"scheme-comparison schemes-" + selected.length}>
            {selected.map((id) => {
              const row = decision.results.find((r) => r.id === id)!;
              return (
                <section className="panel scheme-column" key={id}>
                  <MaterialSchemeCard scheme={row.scheme} />
                  <div className="constraint-details">
                    <h3>逐项判断与未知条件</h3>
                    {row.checks.map((c) => (
                      <div className="constraint-line" key={c.target_id}>
                        <strong>
                          {metricLabel[c.metric] || c.metric}
                          <span className={"check-state " + c.state}>
                            {checkLabel[c.state]}
                          </span>
                        </strong>
                        <p>
                          {number(c.value)} {c.unit || ""}{" "}
                          {c.operator
                            ? ` / 目标 ${c.operator} ${c.required_value}`
                            : ""}{" "}
                          {c.margin !== null && c.margin !== undefined
                            ? ` / 余量 ${number(c.margin)}`
                            : ""}
                        </p>
                        <small>{c.reason}</small>
                        {c.eligibility && (
                          <small>
                            工程适用：
                            {c.eligibility.status === "applicable"
                              ? "适用"
                              : c.eligibility.status === "inapplicable"
                                ? "不适用"
                                : "未知"}{" "}
                            · 待核验{" "}
                            {c.eligibility.unresolved_dimensions
                              .map(fieldLabel)
                              .join("、") || "无"}
                          </small>
                        )}
                      </div>
                    ))}
                  </div>
                  <CandidateEvidence
                    candidate={row}
                    datasetId={decision.scope.dataset.id}
                  />
                  <PredictionValidation
                    decisionId={decision.id}
                    candidateId={row.id}
                  />
                  <NextTestCard
                    cards={
                      decision.test_plan?.cards.filter(
                        (c) => c.candidate_id === row.id,
                      ) || []
                    }
                    knownFailure={row.failed_targets.length > 0}
                    note={decision.test_plan?.note}
                  />
                  <VariantEditor
                    candidate={row}
                    onCreated={() => {
                      setStale(true);
                      void checkFreshness();
                      void refreshHistory();
                    }}
                  />
                </section>
              );
            })}
          </div>
          {previous && (
            <button
              className="secondary difference-button"
              onClick={() => void comparePrevious()}
            >
              对比上次场景与当前判断
            </button>
          )}
          {difference && <DecisionDiff difference={difference} />}
          <p className="release-boundary">
            以上为选材研究原型。正式施工选用仍需工程师审核及独立试验验证。
          </p>
        </section>
      )}
    </div>
  );
}
