import { useEffect, useRef, useState } from "react";
import {
  ArrowLeft,
  Check,
  Download,
  ExternalLink,
  GitCompareArrows,
  LoaderCircle,
  PencilRuler,
} from "lucide-react";
import type {
  DecisionCandidate,
  DecisionDifference,
  MaterialDecision,
} from "../decision-types";
import { decisionApi } from "../decision-types";
import type { CandidateDetail } from "../research-types";
import { researchApi } from "../research-types";
import {
  candidateName,
  creativeApi,
  creativeBase,
  displayNumber as n,
  metricNames,
  metricUnits,
} from "../creative-types";
import type {
  AdjustmentResult,
  CaseRun,
  CreativeCase,
  DesignDraft,
  Exploration,
  PreferenceComparison,
  SavedSummary,
} from "../creative-types";
import { MaterialSchemeCard } from "./MaterialSchemeCard";
import { CandidateEvidence } from "./CandidateEvidence";
import { ConflictPanel } from "./ConflictPanel";
import { DecisionDiff } from "./DecisionDiff";
import "../creative.css";

const metricKeys = ["DS", "strain", "TSR", "residual"];
const palette = ["#007f82", "#315b87", "#bd6b24", "#725b89", "#53764c"];
function SavedLinks({
  id,
  label = "保存内容",
}: {
  id: string;
  label?: string;
}) {
  return (
    <div className="cw-links">
      <a href={`${creativeBase}/records/${id}/export.json`}>
        <Download size={14} />
        导出{label}
      </a>
      <a
        href={`${creativeBase}/records/${id}/print.html`}
        target="_blank"
        rel="noreferrer"
      >
        <ExternalLink size={14} />
        打印{label}
      </a>
    </div>
  );
}

function TradeoffChart({
  rows,
  decision,
  onSelect,
}: {
  rows: DecisionCandidate[];
  decision: MaterialDecision;
  onSelect: (id: string) => void;
}) {
  const [x, setX] = useState("TSR"),
    [y, setY] = useState("residual");
  const numeric = rows.filter(
    (r) => typeof r.metrics[x] === "number" && typeof r.metrics[y] === "number",
  );
  const threshold = (metric: string) =>
    decision.demand.targets.find(
      (t) => t.metric === metric && typeof t.value === "number",
    );
  const limits = (metric: string) => {
    const values = numeric.map((r) => r.metrics[metric]);
    const target = threshold(metric);
    if (target && typeof target.value === "number") values.push(target.value);
    const lo = Math.min(...values),
      hi = Math.max(...values),
      pad = Math.max((hi - lo) * 0.14, Math.abs(hi) * 0.005, 0.1);
    return [lo - pad, hi + pad];
  };
  const [xmin, xmax] = numeric.length ? limits(x) : [0, 1],
    [ymin, ymax] = numeric.length ? limits(y) : [0, 1];
  const px = (v: number) => 74 + ((v - xmin) / (xmax - xmin)) * 490;
  const py = (v: number) => 283 - ((v - ymin) / (ymax - ymin)) * 235;
  return (
    <div className="cw-chart">
      <div className="cw-chart-controls">
        <label>
          横轴
          <select
            value={x}
            onChange={(e) => {
              setX(e.target.value);
              if (e.target.value === y) setY(x);
            }}
          >
            {metricKeys.map((k) => (
              <option key={k} value={k}>
                {metricNames[k]}
              </option>
            ))}
          </select>
        </label>
        <label>
          纵轴
          <select
            value={y}
            onChange={(e) => {
              setY(e.target.value);
              if (e.target.value === x) setX(y);
            }}
          >
            {metricKeys.map((k) => (
              <option key={k} value={k}>
                {metricNames[k]}
              </option>
            ))}
          </select>
        </label>
      </div>
      <svg
        viewBox="0 0 620 344"
        role="img"
        aria-label={`${metricNames[x]}与${metricNames[y]}比较，${numeric.length}个数值可行方案；相同数值可在下方表格查看`}
      >
        <text x="74" y="22" className="cw-axis-title">
          {metricNames[y]} / {metricUnits[y]}
        </text>
        {[0, 1, 2, 3, 4].map((i) => {
          const xv = xmin + ((xmax - xmin) * i) / 4,
            yv = ymin + ((ymax - ymin) * i) / 4;
          return (
            <g key={i}>
              <line
                x1="74"
                x2="564"
                y1={py(yv)}
                y2={py(yv)}
                className="cw-grid"
              />
              <text x="64" y={py(yv) + 4} textAnchor="end">
                {n(yv, 1)}
              </text>
              <text x={px(xv)} y="307" textAnchor="middle">
                {n(xv, 1)}
              </text>
            </g>
          );
        })}
        <line x1="74" y1="283" x2="564" y2="283" className="cw-axis" />
        {[x, y].map((metric, i) => {
          const t = threshold(metric);
          return !t || typeof t.value !== "number" ? null : (
            <g key={metric}>
              {i === 0 ? (
                <line
                  x1={px(t.value)}
                  x2={px(t.value)}
                  y1="48"
                  y2="283"
                  className="cw-target-line"
                />
              ) : (
                <line
                  x1="74"
                  x2="564"
                  y1={py(t.value)}
                  y2={py(t.value)}
                  className="cw-target-line"
                />
              )}
              <text
                x={i === 0 ? px(t.value) + 5 : 560}
                y={i === 0 ? 42 : py(t.value) - 7}
                textAnchor={i === 0 ? "start" : "end"}
                className="cw-target-label"
              >
                要求 {t.operator} {n(t.value)}
              </text>
            </g>
          );
        })}
        {numeric.map((r) => (
          <g
            key={r.id}
            role="button"
            tabIndex={0}
            aria-label={`查看${candidateName(r)}，${metricNames[x]}${n(r.metrics[x])}，${metricNames[y]}${n(r.metrics[y])}`}
            onClick={() => onSelect(r.id)}
            onKeyDown={(e) => {
              if (e.key === "Enter" || e.key === " ") {
                e.preventDefault();
                onSelect(r.id);
              }
            }}
            className="cw-point"
          >
            <circle
              cx={px(r.metrics[x])}
              cy={py(r.metrics[y])}
              r="7"
              fill={
                palette[
                  numeric
                    .map((row) => row.id)
                    .sort()
                    .indexOf(r.id) % palette.length
                ]
              }
            />
            <text x={px(r.metrics[x]) + 11} y={py(r.metrics[y]) - 9}>
              {String(r.scheme.fields.source_code.value)}
            </text>
          </g>
        ))}
        <text x="564" y="335" textAnchor="end" className="cw-axis-title">
          {metricNames[x]} / {metricUnits[x]}
        </text>
      </svg>
      <p>
        虚线为本案例数值要求，点旁标注来源代码。图中只展示可比的数值可行方案，点击可定位下方记录。
      </p>
    </div>
  );
}

function DraftView({ draft }: { draft: DesignDraft }) {
  return (
    <article className="cw-saved-draft" aria-label="已保存设计草案">
      <div className="cw-section-title">
        <div>
          <h3>
            <Check size={17} />
            设计草案已保存
          </h3>
          <p>保存时的需求：{draft.demand_context.request.name}</p>
        </div>
        <SavedLinks id={draft.id} label="草案" />
      </div>
      <p className="cw-intent">{draft.design_intent}</p>
      <p>
        油石比 {n(draft.actual_changes.oil_stone_ratio_pct.before)}% →{" "}
        {n(draft.actual_changes.oil_stone_ratio_pct.after)}%；新配方实测：未知。
      </p>
      <details>
        <summary>回看保存的需求、父方案与改动</summary>
        <dl className="cw-requirements">
          {draft.demand_context.targets.map((t) => (
            <div key={t.target_id}>
              <dt>{metricNames[t.metric]}</dt>
              <dd>
                {t.operator} {n(t.value)} {t.unit}
              </dd>
            </div>
          ))}
        </dl>
        <p>
          父方案 {draft.parent_recipe_id}；设计假设 {draft.hypothesis_id}。
        </p>
        <p>保存内容指纹：{draft.sha256}</p>
      </details>
    </article>
  );
}

function DesignExplorer({
  run,
  parentId,
  onClose,
  onSaved,
}: {
  run: CaseRun;
  parentId: string;
  onClose: () => void;
  onSaved: () => void;
}) {
  const [locks, setLocks] = useState<string[]>([]),
    [supported, setSupported] = useState(true);
  const [context, setContext] = useState<Exploration | null>(null),
    [selected, setSelected] = useState("");
  const [detail, setDetail] = useState<CandidateDetail | null>(null),
    [intent, setIntent] = useState("");
  const [draft, setDraft] = useState<DesignDraft | null>(null),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  const pending = useRef<{ fingerprint: string; id: string } | null>(null);
  const lockKey = locks.join(",");
  useEffect(() => {
    const controller = new AbortController();
    setContext(null);
    setDetail(null);
    setSelected("");
    setError("");
    const params = new URLSearchParams({ supported_only: String(supported) });
    locks.forEach((k) => params.append("locked_fields", k));
    creativeApi<Exploration>(
      `/explorations/${run.decision.id}/${parentId}?${params}`,
      undefined,
      controller.signal,
    )
      .then((v) => {
        if (!controller.signal.aborted) {
          setContext(v);
          setSelected(v.items[0]?.id || "");
        }
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [run.decision.id, parentId, supported, lockKey]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController();
    setDetail(null);
    researchApi<CandidateDetail>(
      "/candidates/" + selected,
      undefined,
      controller.signal,
    )
      .then((v) => {
        if (!controller.signal.aborted) setDetail(v);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    return () => controller.abort();
  }, [selected]);
  function toggleLock(key: string) {
    setLocks((old) =>
      old.includes(key) ? old.filter((k) => k !== key) : [...old, key].sort(),
    );
  }
  async function save() {
    if (!context || !detail || detail.summary.id !== selected) return;
    setBusy(true);
    setError("");
    const input = {
      origin_decision_id: run.decision.id,
      expected_decision_sha256: run.decision.sha256,
      parent_recipe_id: parentId,
      hypothesis_id: selected,
      locked_fields: locks,
      design_intent: intent,
      research_scope_sha256: context.scope_sha256,
    };
    const fingerprint = JSON.stringify(input);
    if (pending.current?.fingerprint !== fingerprint)
      pending.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const value = await creativeApi<DesignDraft>("/drafts", {
        ...input,
        request_id: pending.current.id,
      });
      setDraft(value);
      onSaved();
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  const parent = run.decision.results.find((r) => r.id === parentId)!;
  return (
    <section className="cw-design-explorer" aria-label="带需求的配方探索">
      <div className="cw-section-title">
        <div>
          <h2>从 {candidateName(parent)} 继续设计</h2>
          <p>
            保留“{run.decision.demand.request.name}
            ”的要求，比较准确父配方的已有假设。
          </p>
        </div>
        <button className="cw-outline" onClick={onClose}>
          <ArrowLeft size={15} />
          返回方案比较
        </button>
      </div>
      <div className="cw-locks">
        <span>保持不变的组成</span>
        <label>
          <input
            type="checkbox"
            checked={locks.includes("oil_stone_ratio_pct")}
            onChange={() => toggleLock("oil_stone_ratio_pct")}
            disabled={busy}
          />
          油石比 {n(parent.scheme.fields.oil_stone_ratio_pct.value)}%
        </label>
        <label>
          <input
            type="checkbox"
            checked={locks.includes("nominal_component_weights")}
            onChange={() => toggleLock("nominal_component_weights")}
            disabled={busy}
          />
          各组分名义份额
        </label>
        <label>
          <input
            type="checkbox"
            checked={supported}
            onChange={(e) => setSupported(e.target.checked)}
            disabled={busy}
          />
          仅看观测范围内
        </label>
      </div>
      {error && (
        <p role="alert" className="cw-error">
          {error}
        </p>
      )}
      {!context ? (
        !error && <p role="status">读取此父配方的设计目录…</p>
      ) : (
        <>
          <p className="cw-caption">
            该父配方共有 {context.total_parent_hypotheses}{" "}
            个假设，当前锁定与范围内可查看 {context.total} 个。
          </p>
          {!context.total ? (
            <div className="cw-empty">
              <h3>当前没有匹配假设</h3>
              <p>{context.empty_reason}</p>
              <button className="cw-outline" onClick={() => setLocks([])}>
                解除组成锁定
              </button>
            </div>
          ) : (
            <>
              <label className="cw-hypothesis-select">
                选择设计假设
                <select
                  value={selected}
                  onChange={(e) => {
                    setSelected(e.target.value);
                    setDraft(null);
                  }}
                  disabled={busy}
                >
                  {context.items.map((r) => (
                    <option value={r.id} key={r.id}>
                      {r.change_label} · 油石比{n(r.oil_stone_ratio_pct)}% ·{" "}
                      {r.id.slice(-6)}
                    </option>
                  ))}
                </select>
              </label>
              {detail && detail.summary.id === selected ? (
                <>
                  <div className="cw-design-contrast">
                    <div>
                      <span>父配方油石比</span>
                      <strong>
                        {n(detail.parent.oil_stone_ratio_pct)}
                        <small>%</small>
                      </strong>
                      <p>
                        历史应变 {n(detail.parent.metrics.strain?.value)} με
                      </p>
                    </div>
                    <div>
                      <span>设计油石比</span>
                      <strong>
                        {n(detail.summary.oil_stone_ratio_pct)}
                        <small>%</small>
                      </strong>
                      <p>新方案实测：未知</p>
                    </div>
                    <div>
                      <span>本次改动</span>
                      <strong>
                        {n(
                          detail.summary.oil_stone_ratio_pct -
                            detail.parent.oil_stone_ratio_pct,
                        )}
                        <small>个百分点</small>
                      </strong>
                      <p>
                        {detail.summary.within_observed_support
                          ? "既定观测范围内的假设"
                          : "超出既定观测范围的假设"}
                      </p>
                    </div>
                  </div>
                  <details>
                    <summary>比较各组分名义份额</summary>
                    <div className="table-scroll">
                      <table>
                        <thead>
                          <tr>
                            <th>组分与原表行</th>
                            <th>父配方%</th>
                            <th>设计%</th>
                            <th>变化/百分点</th>
                          </tr>
                        </thead>
                        <tbody>
                          {detail.components
                            .filter((c) => c.before || c.after)
                            .map((c) => (
                              <tr key={c.row}>
                                <td>
                                  {c.type} · 级配!{c.row}
                                </td>
                                <td>{n(c.before * 100)}</td>
                                <td>{n(c.after * 100)}</td>
                                <td>{n(c.delta_percentage_points)}</td>
                              </tr>
                            ))}
                        </tbody>
                      </table>
                    </div>
                  </details>
                  <details>
                    <summary>查看新配方计算研究参考</summary>
                    <p>
                      下列为研究预测，未用于硬要求通过判定；父方案历史值与新方案预测不作实测增益比较。
                    </p>
                    <dl className="cw-requirements">
                      {metricKeys.map((m) => (
                        <div key={m}>
                          <dt>{metricNames[m]}</dt>
                          <dd>
                            {n(
                              detail.candidate.prediction[
                                m as keyof typeof detail.candidate.prediction
                              ],
                            )}{" "}
                            {metricUnits[m]}
                          </dd>
                        </div>
                      ))}
                    </dl>
                  </details>
                  <label className="cw-intent-input">
                    这次调整想解决什么问题？
                    <textarea
                      rows={3}
                      maxLength={2000}
                      placeholder="例如：保持组分不变，比较油石比增加0.1个百分点的设计方向；性能尚待判断。"
                      value={intent}
                      onChange={(e) => setIntent(e.target.value)}
                      disabled={busy}
                    />
                  </label>
                  <p className="cw-caption">
                    草案保存原需求、父配方、实际改动和设计理由。名义份额的质量基准继续待确认。
                  </p>
                  <button
                    className="cw-action"
                    disabled={busy || !intent.trim()}
                    onClick={() => void save()}
                  >
                    {busy ? (
                      <LoaderCircle className="spin" size={16} />
                    ) : (
                      <PencilRuler size={16} />
                    )}
                    保存设计草案
                  </button>
                </>
              ) : (
                <p role="status">读取假设组成…</p>
              )}
            </>
          )}
        </>
      )}
      {draft && <DraftView draft={draft} />}
    </section>
  );
}

export function CreativeWorkbench() {
  const [cases, setCases] = useState<CreativeCase[]>([]),
    [caseId, setCaseId] = useState("C1");
  const [run, setRun] = useState<CaseRun | null>(null),
    [previous, setPrevious] = useState<MaterialDecision | null>(null);
  const [difference, setDifference] = useState<DecisionDifference | null>(null),
    [preference, setPreference] = useState<PreferenceComparison | null>(null);
  const [primary, setPrimary] = useState("DS"),
    [reason, setReason] = useState("");
  const [selected, setSelected] = useState<string[]>([]),
    [exploreParent, setExploreParent] = useState<string | null>(null);
  const [busy, setBusy] = useState(false),
    [preferenceBusy, setPreferenceBusy] = useState(false),
    [saveBusy, setSaveBusy] = useState(false),
    [error, setError] = useState("");
  const [savedPreference, setSavedPreference] =
    useState<PreferenceComparison | null>(null);
  const [history, setHistory] = useState<SavedSummary[]>([]),
    [openedDraft, setOpenedDraft] = useState<DesignDraft | null>(null);
  const [targetInputs, setTargetInputs] = useState<Record<string, string>>({}),
    [rapInput, setRapInput] = useState("75");
  const [adjustReason, setAdjustReason] = useState(""),
    [preview, setPreview] = useState<AdjustmentResult | null>(null);
  const [adjustOpen, setAdjustOpen] = useState(false);
  const adjustmentRef = useRef<HTMLDetailsElement>(null);
  const serial = useRef(0),
    pendingSave = useRef<{ fingerprint: string; id: string } | null>(null);
  const designRef = useRef<HTMLElement>(null),
    candidatesRef = useRef<HTMLElement>(null);
  const activeIntent = useRef("");
  activeIntent.current = `${run?.decision.id}|${primary}`;
  const activeCase = cases.find((c) => c.id === caseId);
  const decision = run?.decision;
  const rows =
    preference?.candidates ||
    decision?.results.filter((r) => r.passes_known_requirements) ||
    [];
  const first = rows[0];
  useEffect(() => {
    if (adjustOpen) adjustmentRef.current?.scrollIntoView({ block: "start" });
  }, [adjustOpen]);
  const refreshHistory = () =>
    creativeApi<SavedSummary[]>("/history")
      .then(setHistory)
      .catch((e) => setError(e.message));
  useEffect(() => {
    const controller = new AbortController();
    const initialSerial = serial.current;
    creativeApi<{ cases: CreativeCase[] }>(
      "/cases",
      undefined,
      controller.signal,
    )
      .then((v) => setCases(v.cases))
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      });
    void refreshHistory();
    const params = new URLSearchParams(location.search),
      savedId = params.get("run");
    if (savedId)
      creativeApi<CaseRun>(
        "/records/" + encodeURIComponent(savedId),
        undefined,
        controller.signal,
      )
        .then((v) => {
          if (
            controller.signal.aborted ||
            serial.current !== initialSerial ||
            !v.decision
          )
            return;
          setCaseId(v.case_id);
          accept(v);
        })
        .catch((e) => {
          if (!controller.signal.aborted) setError(e.message);
        });
    return () => {
      controller.abort();
      serial.current++;
    };
  }, []);
  useEffect(() => {
    if (!decision) return;
    const controller = new AbortController();
    setPreferenceBusy(true);
    setSavedPreference(null);
    creativeApi<PreferenceComparison>(
      "/preferences",
      {
        decision_id: decision.id,
        expected_decision_sha256: decision.sha256,
        priority_order: [primary],
      },
      controller.signal,
    )
      .then((v) => {
        if (!controller.signal.aborted) setPreference(v);
      })
      .catch((e) => {
        if (!controller.signal.aborted) setError(e.message);
      })
      .finally(() => {
        if (!controller.signal.aborted) setPreferenceBusy(false);
      });
    return () => controller.abort();
  }, [decision?.id, primary]);
  useEffect(() => {
    if (!decision || !previous || previous.id === decision.id) return;
    let live = true;
    decisionApi<DecisionDifference>(
      `/decision-diff?before_id=${previous.id}&after_id=${decision.id}`,
    )
      .then((v) => {
        if (live) setDifference(v);
      })
      .catch((e) => {
        if (live) setError(e.message);
      });
    return () => {
      live = false;
    };
  }, [decision?.id, previous?.id]);
  useEffect(() => {
    if (exploreParent)
      designRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }, [exploreParent]);
  function accept(value: CaseRun) {
    const url = new URL(window.location.href);
    url.search = new URLSearchParams({
      view: "design",
      run: value.id,
    }).toString();
    window.history.replaceState({}, "", url);
    setRun(value);
    setPreference(null);
    setPrimary(value.decision.demand.priority[0]);
    setReason("");
    setSavedPreference(null);
    setSelected(value.decision.comparison.feasible_ids.slice(0, 3));
    setExploreParent(null);
    setPreview(null);
    setError("");
    setTargetInputs(
      Object.fromEntries(
        value.decision.demand.targets.map((t) => [t.metric, String(t.value)]),
      ),
    );
    setAdjustReason("");
    setOpenedDraft(null);
  }
  function selectCase(id: string) {
    const url = new URL(window.location.href);
    url.search = "view=design";
    window.history.replaceState({}, "", url);
    serial.current++;
    if (decision) setPrevious(decision);
    setCaseId(id);
    setRun(null);
    setPreference(null);
    setDifference(null);
    setExploreParent(null);
    setBusy(false);
    setPreferenceBusy(false);
    setPreview(null);
    setError("");
    setOpenedDraft(null);
  }
  async function execute(changes: Record<string, unknown> = {}) {
    const requestSerial = ++serial.current;
    setBusy(true);
    setError("");
    const before = decision || previous;
    try {
      const value = await creativeApi<CaseRun>(`/cases/${caseId}/runs`, {
        request_id: crypto.randomUUID(),
        ...changes,
      });
      if (serial.current !== requestSerial) return;
      setPrevious(before);
      setDifference(null);
      accept(value);
    } catch (e) {
      if (serial.current === requestSerial) setError((e as Error).message);
    } finally {
      if (serial.current === requestSerial) setBusy(false);
    }
  }
  function selectCandidate(id: string) {
    setSelected((old) => (old.includes(id) ? old : [...old.slice(-2), id]));
    candidatesRef.current?.scrollIntoView({ behavior: "auto", block: "start" });
  }
  function explore(id: string) {
    setOpenedDraft(null);
    setExploreParent(id);
  }
  async function savePreference() {
    if (!decision || !preference || !reason.trim()) return;
    setSaveBusy(true);
    setError("");
    const expectedIntent = activeIntent.current;
    const input = {
      decision_id: decision.id,
      expected_decision_sha256: decision.sha256,
      priority_order: [primary],
      reason,
      persist: true,
    };
    const fingerprint = JSON.stringify(input);
    if (pendingSave.current?.fingerprint !== fingerprint)
      pendingSave.current = { fingerprint, id: crypto.randomUUID() };
    try {
      const value = await creativeApi<PreferenceComparison>("/preferences", {
        ...input,
        request_id: pendingSave.current.id,
      });
      if (activeIntent.current === expectedIntent) setSavedPreference(value);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setSaveBusy(false);
    }
  }
  function adjustmentInput() {
    return {
      target_overrides: Object.fromEntries(
        Object.entries(targetInputs).map(([k, v]) => [k, Number(v)]),
      ),
      ...(caseId === "C4" ? { rap_min_pct: Number(rapInput) } : {}),
    };
  }
  const adjustmentValid =
    Object.values(targetInputs).every(
      (v) => v.trim() !== "" && Number.isFinite(Number(v)) && Number(v) >= 0,
    ) &&
    (caseId !== "C4" ||
      (rapInput.trim() !== "" &&
        Number.isFinite(Number(rapInput)) &&
        Number(rapInput) >= 0 &&
        Number(rapInput) <= 100));
  async function previewAdjustment() {
    if (!decision) return;
    setBusy(true);
    setError("");
    const requestSerial = serial.current;
    try {
      const v = await creativeApi<AdjustmentResult>(
        `/decisions/${decision.id}/adjustment-preview`,
        { expected_decision_sha256: decision.sha256, ...adjustmentInput() },
      );
      if (serial.current === requestSerial) setPreview(v);
    } catch (e) {
      if (serial.current === requestSerial) setError((e as Error).message);
    } finally {
      if (serial.current === requestSerial) setBusy(false);
    }
  }
  async function openDraft(id: string) {
    if (!id) {
      setOpenedDraft(null);
      return;
    }
    try {
      setOpenedDraft(
        await creativeApi<DesignDraft>("/records/" + encodeURIComponent(id)),
      );
    } catch (e) {
      setError((e as Error).message);
    }
  }
  return (
    <div className="cw-root">
      <header className="cw-heading">
        <h1>把养护需求变成可比较的材料方案</h1>
        <p>
          选一个工程问题，查看需求依据、比较性能取舍，再带着原要求继续设计。
        </p>
      </header>
      <p className="cw-scope">
        五个合理构造案例，使用企业工作簿历史数值；新配方以设计假设呈现。
      </p>
      {error && (
        <p className="cw-error" role="alert">
          {error}
        </p>
      )}
      <div className="cw-workspace">
        <nav className="cw-case-rail" aria-label="五个典型案例">
          {cases.map((c) => (
            <button
              key={c.id}
              aria-current={caseId === c.id ? "step" : undefined}
              className={caseId === c.id ? "active" : ""}
              onClick={() => selectCase(c.id)}
            >
              <span>
                {c.id} · {c.mechanism}
              </span>
              <strong>{c.title}</strong>
              <small>{c.question}</small>
            </button>
          ))}
        </nav>
        <div className="cw-paper">
          {!activeCase ? (
            <p role="status">读取案例…</p>
          ) : (
            <>
              <section className="cw-case-intro">
                <div>
                  <span className="cw-case-kind">{activeCase.mechanism}</span>
                  <h2>{activeCase.question}</h2>
                  <p>{activeCase.action}</p>
                </div>
                <button
                  className="cw-action"
                  disabled={busy}
                  onClick={() => void execute()}
                >
                  {busy && <LoaderCircle size={16} className="spin" />}
                  {run ? "重新运行原案例" : "确认案例要求并选材"}
                </button>
              </section>
              {!decision ? (
                <div className="cw-start">
                  <h3>本次采用的构造要求</h3>
                  <dl className="cw-requirements">
                    {Object.entries(activeCase.targets).map(([m, v]) => (
                      <div key={m}>
                        <dt>{metricNames[m]}</dt>
                        <dd>
                          &gt; {n(v)} <small>{metricUnits[m]}</small>
                        </dd>
                      </div>
                    ))}
                  </dl>
                  {activeCase.rap_min_pct !== null && (
                    <p>名义RAP ≥ {activeCase.rap_min_pct}%；质量基准待确认。</p>
                  )}
                  <p>
                    选材将保存需求、候选范围和判断结果；完整目录保留缺测项。
                  </p>
                </div>
              ) : (
                <>
                  <section className="cw-section" aria-label="场景需求解释">
                    <div className="cw-step-title">
                      <span>1</span>
                      <div>
                        <h2>这个场景，需要什么性能</h2>
                        <p>场景、规则和人工要求都保留各自来源。</p>
                      </div>
                    </div>
                    <p className="cw-scene-rationale">
                      {decision.demand.rules.matches
                        .map((r) => r.rationale)
                        .join("；")}
                    </p>
                    <dl className="cw-requirements">
                      {decision.demand.targets.map((t) => (
                        <div key={t.target_id}>
                          <dt>{metricNames[t.metric]}</dt>
                          <dd>
                            {t.operator} {n(t.value)} <small>{t.unit}</small>
                          </dd>
                        </div>
                      ))}
                    </dl>
                    {decision.demand.request.constraints.rap_min_pct !==
                      null && (
                      <p className="cw-resource-target">
                        本次要求：名义RAP ≥{" "}
                        {n(decision.demand.request.constraints.rap_min_pct)}
                        %；组成质量基准待确认。
                      </p>
                    )}
                    <details className="cw-source-detail">
                      <summary>为什么采用这些要求？查看出处与适用条件</summary>
                      {decision.demand.case_application && (
                        <p>{decision.demand.case_application.source}</p>
                      )}
                      {decision.demand.targets.map((t) => (
                        <article key={t.target_id}>
                          <h3>
                            {metricNames[t.metric]} {t.operator} {n(t.value)}{" "}
                            {t.unit}
                          </h3>
                          <p>{t.source.reference}</p>
                          <p>
                            方法：{t.test_method || "未披露"}；条件：
                            {Object.keys(t.conditions).length
                              ? JSON.stringify(t.conditions)
                              : "待确认"}
                            。
                          </p>
                        </article>
                      ))}
                      {decision.demand.overrides?.map((o) => (
                        <p key={o.target_id}>
                          人工调整：{metricNames[o.after.metric]}{" "}
                          {n(o.before.value)} → {n(o.after.value)}；理由：
                          {o.reason}
                        </p>
                      ))}
                    </details>
                    <div className="cw-baseline">
                      <span>
                        当前范围 <b>{decision.results.length}</b> 条
                      </span>
                      <span>
                        作品数值可行{" "}
                        <b>{decision.comparison.feasible_ids.length}</b> 条
                      </span>
                      <span>
                        同池B1可行 <b>{run!.baseline.feasible_ids.length}</b> 条
                      </span>
                      <strong>
                        {run!.baseline.same_feasible_set
                          ? "可行集合一致"
                          : "存在差异，需复核"}
                      </strong>
                    </div>
                    <p className="cw-caption">
                      {run!.baseline.method}
                      。一致时，作品的新增价值由需求解释、方案比选与调整记录展示。
                    </p>
                  </section>
                  <section className="cw-section" aria-label="多目标方案比选">
                    <div className="cw-step-title">
                      <span>2</span>
                      <div>
                        <h2>满足要求之后，怎样取舍</h2>
                        <p>保留硬要求，改变优先查看的指标。</p>
                      </div>
                    </div>
                    {decision.comparison.feasible_ids.length ? (
                      <>
                        <div
                          className="cw-preference-buttons"
                          role="group"
                          aria-label="优先查看的性能"
                        >
                          {metricKeys.map((m) => (
                            <button
                              key={m}
                              className={primary === m ? "active" : ""}
                              aria-pressed={primary === m}
                              onClick={() => {
                                setPrimary(m);
                                setPreference(null);
                                setSavedPreference(null);
                              }}
                              disabled={busy}
                            >
                              {metricNames[m]}优先
                            </button>
                          ))}
                        </div>
                        {preferenceBusy ? (
                          <p role="status">比较同一可行集合…</p>
                        ) : (
                          preference &&
                          first && (
                            <div className="cw-choice-reason">
                              <h3>当前优先查看 {candidateName(first)}</h3>
                              <p>
                                按
                                {preference.priority_order
                                  .map((m) => metricNames[m])
                                  .join("、")}
                                的顺序逐项比较；指标同值时继续比较下一项。
                              </p>
                              <p>
                                {metricNames[primary]}为{" "}
                                {n(first.metrics[primary])}{" "}
                                {metricUnits[primary]}。
                                {rows.filter(
                                  (r) =>
                                    r.metrics[primary] ===
                                    first.metrics[primary],
                                ).length > 1 &&
                                  `${rows.filter((r) => r.metrics[primary] === first.metrics[primary]).length}个候选在此指标并列，继续比较后续指标。`}
                              </p>
                              <details>
                                <summary>查看与其他候选的首个差别</summary>
                                {preference.explanations.slice(1).map((ex) => {
                                  const r = rows.find((r) => r.id === ex.id)!;
                                  const d = ex.first_difference_from_first;
                                  return (
                                    <p key={ex.id}>
                                      {candidateName(r)}：
                                      {d
                                        ? `首先在${d.label}不同，${n(d.value)} 对 ${n(d.first_value)} ${d.unit}。`
                                        : "全部参与比较的指标同值，并列保留。"}
                                    </p>
                                  );
                                })}
                              </details>
                              <p>
                                {preference.comparison.front_ids.length}
                                个非支配方案，
                                {preference.comparison.feasible_ids.length}
                                个可行方案。偏好切换没有改变硬要求或可行集合。
                              </p>
                            </div>
                          )
                        )}
                        <TradeoffChart
                          rows={rows}
                          decision={decision}
                          onSelect={selectCandidate}
                        />
                        <div className="table-scroll">
                          <table className="cw-candidate-table">
                            <thead>
                              <tr>
                                <th>比较</th>
                                <th>材料 / 来源</th>
                                {metricKeys.map((m) => (
                                  <th key={m}>
                                    {metricNames[m]}
                                    <small>{metricUnits[m]}</small>
                                  </th>
                                ))}
                                <th>优先顺位</th>
                              </tr>
                            </thead>
                            <tbody>
                              {rows.map((row) => (
                                <tr
                                  key={row.id}
                                  className={
                                    selected.includes(row.id) ? "selected" : ""
                                  }
                                >
                                  <td>
                                    <input
                                      type="checkbox"
                                      aria-label={`比较${candidateName(row)}`}
                                      checked={selected.includes(row.id)}
                                      disabled={
                                        !selected.includes(row.id) &&
                                        selected.length >= 3
                                      }
                                      onChange={(e) =>
                                        setSelected((old) =>
                                          e.target.checked
                                            ? [...old, row.id]
                                            : old.filter((id) => id !== row.id),
                                        )
                                      }
                                    />
                                  </td>
                                  <th scope="row">
                                    {candidateName(row)}
                                    <small>
                                      {row.pareto_front ? "非支配" : "可行"}
                                    </small>
                                  </th>
                                  {metricKeys.map((m) => (
                                    <td key={m}>
                                      {n(row.metrics[m])}
                                      <small>
                                        {(() => {
                                          const check = row.checks.find(
                                            (c) => c.metric === m,
                                          );
                                          return typeof check?.margin ===
                                            "number"
                                            ? `数值差额 ${n(check.margin)}`
                                            : "差额待确认";
                                        })()}
                                      </small>
                                    </td>
                                  ))}
                                  <td>{row.preference_rank}</td>
                                </tr>
                              ))}
                            </tbody>
                          </table>
                        </div>
                        <p className="cw-caption">
                          数值差额按当前要求计算，不表示工程安全系数。勾选最多三种材料查看组成与原始依据。
                        </p>
                        <div className="cw-save-preference">
                          <label>
                            选择这个优先顺序的理由
                            <input
                              value={reason}
                              maxLength={1000}
                              onChange={(e) => setReason(e.target.value)}
                              placeholder="例如：先满足水稳定要求，再优先保留残留稳定度余量。"
                            />
                          </label>
                          <button
                            className="cw-outline"
                            disabled={
                              saveBusy ||
                              preferenceBusy ||
                              !preference ||
                              !reason.trim()
                            }
                            onClick={() => void savePreference()}
                          >
                            <GitCompareArrows size={15} />
                            保存当前取舍
                          </button>
                        </div>
                        {savedPreference?.id && (
                          <div className="cw-saved-line" role="status">
                            <span>
                              已保存
                              {metricNames[savedPreference.priority_order[0]]}
                              优先的取舍理由。
                            </span>
                            <SavedLinks
                              id={savedPreference.id}
                              label="取舍记录"
                            />
                          </div>
                        )}
                      </>
                    ) : (
                      <div className="cw-empty">
                        <h3>
                          {decision.diagnosis.status === "known_conflict"
                            ? "当前范围内存在已知要求冲突"
                            : "当前没有数值可行方案"}
                        </h3>
                        <p>{decision.diagnosis.message}</p>
                        <p>{decision.scope.evidence_view_note}</p>
                        <div className="cw-next-directions">
                          <button
                            className="cw-outline"
                            onClick={() => setAdjustOpen(true)}
                          >
                            重新确认要求
                          </button>
                          <button
                            className="cw-outline"
                            onClick={() =>
                              candidatesRef.current?.scrollIntoView({
                                block: "start",
                              })
                            }
                          >
                            选择历史材料探索配方
                          </button>
                        </div>
                        <details className="cw-data-gaps">
                          <summary>查看需要核对的资料</summary>
                          <p>
                            当前有 {decision.summary.needs_evidence || 0}{" "}
                            条候选需补证据。可先核对材料身份、原始记录和以下试验条件：
                          </p>
                          <ul>
                            {decision.demand.targets.map((t) => (
                              <li key={t.target_id}>
                                {metricNames[t.metric]}：方法
                                {t.test_method || "待确认"}，条件
                                {Object.keys(t.conditions).length
                                  ? JSON.stringify(t.conditions)
                                  : "待确认"}
                                。
                              </li>
                            ))}
                          </ul>
                        </details>
                      </div>
                    )}
                    {caseId === "C5" && (
                      <div className="cw-diagnostic-switch">
                        <p>
                          完整目录保留缺测项；完整数值子池用于限定范围的冲突诊断。
                        </p>
                        <button
                          className="cw-outline"
                          disabled={busy}
                          onClick={() =>
                            void execute({
                              evidence_view:
                                decision.scope.evidence_view === "all"
                                  ? "complete_numeric_demo"
                                  : "all",
                              target_overrides:
                                run!.run_request.target_overrides,
                              adjustment_reason:
                                run!.run_request.adjustment_reason,
                              based_on_decision_id: decision.id,
                              expected_decision_sha256: decision.sha256,
                            })
                          }
                        >
                          {decision.scope.evidence_view === "all"
                            ? "明确切换完整数值诊断视图"
                            : "返回保留缺测的完整目录"}
                        </button>
                      </div>
                    )}
                    <ConflictPanel diagnosis={decision.diagnosis} />
                    {!!decision.diagnosis.certificates.length && (
                      <p className="cw-caption">
                        删除见证只针对证书中剩余的要求子集；若调整要求，仍需重新计算全套要求。
                      </p>
                    )}
                  </section>
                  <section
                    className="cw-section"
                    ref={candidatesRef}
                    aria-label="材料组成与选材证据"
                  >
                    <div className="cw-step-title">
                      <span>3</span>
                      <div>
                        <h2>看清组成，再决定下一步</h2>
                        <p>查看历史依据，或带着原需求继续探索配方。</p>
                      </div>
                    </div>
                    {!rows.length && (
                      <>
                        <label>
                          选择历史材料作为探索起点
                          <select
                            value={selected[0] || ""}
                            onChange={(e) =>
                              setSelected(
                                e.target.value ? [e.target.value] : [],
                              )
                            }
                          >
                            <option value="">选择目录中的历史记录</option>
                            {decision.results.map((r) => (
                              <option value={r.id} key={r.id}>
                                {candidateName(r)} · {r.failed_targets.length}
                                项已知失败 / {r.unknown_targets.length}项待确认
                              </option>
                            ))}
                          </select>
                        </label>
                        <p className="cw-caption">
                          选为探索起点不表示它满足当前要求。
                        </p>
                      </>
                    )}
                    <div className="cw-schemes">
                      {selected.map((id) => {
                        const row = decision.results.find((r) => r.id === id);
                        return row ? (
                          <article key={id}>
                            <h3>{candidateName(row)}</h3>
                            <details>
                              <summary>材料组成与单元格依据</summary>
                              <MaterialSchemeCard scheme={row.scheme} />
                              <CandidateEvidence
                                candidate={row}
                                datasetId={decision.scope.dataset.id}
                              />
                            </details>
                            <button
                              className="cw-action"
                              onClick={() => explore(id)}
                            >
                              <PencilRuler size={15} />
                              从此方案继续设计
                            </button>
                          </article>
                        ) : null;
                      })}
                    </div>
                  </section>
                  <section className="cw-section" ref={designRef}>
                    {exploreParent && (
                      <DesignExplorer
                        key={decision.id + exploreParent}
                        run={run!}
                        parentId={exploreParent}
                        onClose={() => {
                          setExploreParent(null);
                          candidatesRef.current?.scrollIntoView({
                            block: "start",
                          });
                        }}
                        onSaved={() => void refreshHistory()}
                      />
                    )}
                  </section>
                  <details
                    className="cw-adjustment"
                    ref={adjustmentRef}
                    open={adjustOpen}
                    onToggle={(e) => setAdjustOpen(e.currentTarget.open)}
                  >
                    <summary>调整场景要求，先预览再确认</summary>
                    <p>
                      调整要求会重新筛选全部当前候选。原需求与旧决策保持保存内容。
                    </p>
                    <div className="cw-adjustment-fields">
                      {metricKeys.map((m) => (
                        <label key={m}>
                          {metricNames[m]} &gt;
                          <input
                            type="number"
                            min="0"
                            disabled={busy}
                            value={targetInputs[m] || ""}
                            onChange={(e) => {
                              setTargetInputs((old) => ({
                                ...old,
                                [m]: e.target.value,
                              }));
                              setPreview(null);
                            }}
                          />
                        </label>
                      ))}
                      {caseId === "C4" && (
                        <label>
                          名义RAP最低比例/%
                          <input
                            type="number"
                            min="0"
                            max="100"
                            disabled={busy}
                            value={rapInput}
                            onChange={(e) => {
                              setRapInput(e.target.value);
                              setPreview(null);
                            }}
                          />
                        </label>
                      )}
                    </div>
                    <button
                      className="cw-outline"
                      disabled={busy || !adjustmentValid}
                      onClick={() => void previewAdjustment()}
                    >
                      预览要求变化
                    </button>
                    {preview && (
                      <div className="cw-adjustment-preview" role="status">
                        <p>
                          同一 {preview.pool_size} 条候选中，数值可行{" "}
                          {preview.before_feasible_ids.length} →{" "}
                          {preview.after_feasible_ids.length} 条。
                        </p>
                        {preview.changes.map((c) => (
                          <p key={c.metric}>
                            {metricNames[c.metric]}：{n(c.before)} →{" "}
                            {n(c.after)} {c.unit}
                          </p>
                        ))}
                        <p>{preview.note}</p>
                        <label>
                          确认调整的理由
                          <input
                            value={adjustReason}
                            maxLength={1000}
                            onChange={(e) => setAdjustReason(e.target.value)}
                            placeholder="说明为什么调整这组构造要求"
                          />
                        </label>
                        <button
                          className="cw-action"
                          disabled={
                            busy ||
                            !adjustReason.trim() ||
                            !preview.changes.length
                          }
                          onClick={() =>
                            void execute({
                              ...adjustmentInput(),
                              evidence_view: decision.scope.evidence_view,
                              adjustment_reason: adjustReason,
                              based_on_decision_id: decision.id,
                              expected_decision_sha256: decision.sha256,
                            })
                          }
                        >
                          确认新要求并重新选材
                        </button>
                      </div>
                    )}
                  </details>
                  {difference && (
                    <details className="cw-difference">
                      <summary>比较上次与当前场景判断</summary>
                      <DecisionDiff difference={difference} />
                    </details>
                  )}
                  <footer className="cw-run-footer">
                    <SavedLinks id={run!.id} label="案例卡" />
                    <a href={`?view=design&run=${run!.id}`}>
                      重新打开本次案例记录
                    </a>
                    <small>
                      保存时间：
                      {new Date(run!.created_at).toLocaleString("zh-CN")}
                    </small>
                  </footer>
                </>
              )}
            </>
          )}
        </div>
      </div>
      <section className="cw-history">
        <label>
          回看已保存的设计草案
          <select
            value={openedDraft?.id || ""}
            onChange={(e) => void openDraft(e.target.value)}
          >
            <option value="">选择历史草案</option>
            {history.map((h) => (
              <option value={h.id} key={h.id}>
                {new Date(h.created_at).toLocaleString("zh-CN")} ·{" "}
                {h.design_intent?.slice(0, 38)}
              </option>
            ))}
          </select>
        </label>
        {openedDraft && <DraftView draft={openedDraft} />}
      </section>
    </div>
  );
}
