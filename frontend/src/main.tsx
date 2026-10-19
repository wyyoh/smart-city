import React, { useEffect, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowRight,
  ArrowUpRight,
  Check,
  CheckCircle2,
  ChevronRight,
  ClipboardList,
  Database,
  Download,
  FileText,
  FlaskConical,
  Layers3,
  LoaderCircle,
  Microscope,
  Plus,
  Search,
  ShieldCheck,
  SlidersHorizontal,
  TriangleAlert,
  X,
} from "lucide-react";
import type {
  Case,
  Dataset,
  Evidence,
  Observation,
  Recipe,
  Scenario,
  Snapshot,
} from "./types";
import { core, flags, fmt, metrics } from "./types";
import "./styles.css";
import { DecisionWorkflow } from "./components/DecisionWorkflow";
import { ReviewCenter } from "./components/ReviewCenter";
import type { Highlight } from "./review-types";
import "./decision.css";
import "./review.css";

async function api<T>(path: string, body?: unknown): Promise<T> {
  const response = await fetch(
    "/v1" + path,
    body === undefined
      ? {}
      : {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        },
  );
  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: response.statusText }));
    throw new Error(
      typeof error.detail === "string"
        ? error.detail
        : JSON.stringify(error.detail),
    );
  }
  return response.json() as Promise<T>;
}
const statusText: Record<string, string> = {
  excluded: "未满足目标",
  needs_test: "待补试验",
  needs_review: "建议复核",
};
function Status({ recipe }: { recipe: Recipe }) {
  const status =
    recipe.status || (recipe.kind === "variant" ? "needs_test" : "historical");
  return (
    <span className={"status " + status}>
      {status === "historical" ? "历史记录" : statusText[status]}
    </span>
  );
}
function App() {
  const [route, setRoute] = useState("review");
  const [guidedTour, setGuidedTour] = useState<Highlight | null>(null);
  const [catalog, setCatalog] = useState<Recipe[]>([]),
    [dataset, setDataset] = useState<Dataset | null>(null),
    [cases, setCases] = useState<Case[]>([]);
  const [scenario, setScenario] = useState<Scenario | null>(null),
    [snapshot, setSnapshot] = useState<Snapshot | null>(null);
  const [selected, setSelected] = useState<string | null>(null),
    [detail, setDetail] = useState<Recipe | null>(null),
    [inspectorTab, setInspectorTab] = useState("evidence");
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [dirty, setDirty] = useState(false),
    [refresh, setRefresh] = useState(0);
  const [search, setSearch] = useState("");
  const requestRef = useRef(0);
  const editRevision = useRef(0);
  async function refreshCatalog() {
    const c = await api<{ dataset: Dataset; recipes: Recipe[] }>("/catalog");
    setCatalog(c.recipes);
    setDataset(c.dataset);
  }
  async function calculate(s: Scenario) {
    const serial = ++requestRef.current;
    const inputRevision = editRevision.current;
    setBusy(true);
    setError("");
    try {
      const r = await api<Snapshot>("/recommendations", s);
      if (serial === requestRef.current) {
        setSnapshot(r);
        setSelected(r.results[0]?.id || null);
        // A response must not erase the stale-result notice after a newer edit.
        setDirty(editRevision.current !== inputRevision);
        setRefresh((v) => v + 1);
      }
    } catch (e) {
      if (serial === requestRef.current) setError(String(e));
    } finally {
      if (serial === requestRef.current) setBusy(false);
    }
  }
  useEffect(() => {
    let live = true;
    Promise.all([
      api<Case[]>("/cases"),
      api<{ dataset: Dataset; recipes: Recipe[] }>("/catalog"),
    ])
      .then(([c, d]) => {
        if (live) {
          setCases(c);
          setCatalog(d.recipes);
          setDataset(d.dataset);
          setScenario(c[0].scenario);
        }
      })
      .catch((e) => setError(String(e)));
    return () => {
      live = false;
    };
  }, []);
  useEffect(() => {
    if (!selected) {
      setDetail(null);
      return;
    }
    let live = true;
    setDetail(null);
    api<Recipe>(
      "/recipes/" +
        selected +
        "?context_kind=" +
        (scenario?.context_kind || "project"),
    )
      .then((r) => {
        if (live) setDetail(r);
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
    };
  }, [selected, refresh, scenario?.context_kind]);
  function update(s: Partial<Scenario>) {
    if (scenario) {
      editRevision.current += 1;
      setScenario({ ...scenario, ...s });
      setDirty(true);
    }
  }
  function updateTarget(
    i: number,
    fields: Partial<Scenario["targets"][number]>,
  ) {
    if (!scenario) return;
    update({
      targets: scenario.targets.map((t, j) =>
        j === i
          ? {
              ...t,
              ...fields,
              upper:
                fields.operator === "between" ? (t.upper ?? t.value) : t.upper,
              source_kind: "project_target",
              reference: null,
            }
          : t,
      ),
    });
  }
  async function chooseCase(c: Case) {
    editRevision.current += 1;
    setScenario(structuredClone(c.scenario));
    setDirty(true);
    setNotice("");
    await calculate(c.scenario);
  }
  async function changed(message: string) {
    editRevision.current += 1;
    setNotice(message);
    setDirty(true);
    setRefresh((v) => v + 1);
    await refreshCatalog();
  }
  const visible = catalog
    .filter((r) =>
      `${r.source} ${r.gradation} ${r.product} ${r.display_id}`
        .toLowerCase()
        .includes(search.toLowerCase()),
    )
    .sort(
      (a, b) =>
        (a.payload.fixture_id ? 0 : 1) - (b.payload.fixture_id ? 0 : 1) ||
        a.source.localeCompare(b.source),
    );
  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <span className="brand-symbol">
            <Layers3 size={23} />
          </span>
          <div>
            数智选材<small>MATERIAL WORKBENCH</small>
          </div>
        </div>
        <div className="nav-label">道路养护 · 材料设计</div>
        <nav>
          {[
            { id: "review", label: "成果与验证", icon: ShieldCheck },
            { id: "decision", label: "场景选材", icon: ClipboardList },
            { id: "workbench", label: "历史初筛", icon: SlidersHorizontal },
            { id: "data", label: "数据与依据", icon: Database },
            { id: "observations", label: "试验回流", icon: FlaskConical },
            { id: "models", label: "模型评估", icon: Microscope },
            { id: "reports", label: "方案报告", icon: FileText },
          ].map((n) => (
            <button
              key={n.id}
              aria-current={route === n.id ? "page" : undefined}
              className={route === n.id ? "nav-item active" : "nav-item"}
              onClick={() => {
                setRoute(n.id);
                if (n.id === "workbench" && scenario && !snapshot)
                  void calculate(scenario);
                setNotice("");
              }}
            >
              <n.icon size={18} />
              {n.label}
              {route === n.id && <ChevronRight size={15} />}
            </button>
          ))}
        </nav>
        <div className="sidebar-bottom">
          <div className="connection">
            <i /> 本地工作区 <span>v0.3 研究原型</span>
          </div>
          <p>
            企业提供的实验室记录
            <br />
            历史初筛 → 复核 → 试验验证
          </p>
          <div className="dataset-tag">
            {dataset?.sha256.slice(0, 12) || "正在连接数据"}
            <ShieldCheck size={14} />
          </div>
        </div>
      </aside>
      <div className="main-shell">
        <header className="topbar">
          <div>
            <span>智慧道路养护</span>
            <ChevronRight size={14} />
            <strong>
              {
                (
                  {
                    review: "成果证据与选材复核",
                    decision: "场景驱动材料决策",
                    workbench: "材料方案推荐",
                    data: "数据目录与质量",
                    observations: "试验审核工作区",
                    models: "模型基准与适用域",
                    reports: "可追溯方案报告",
                  } as Record<string, string>
                )[route]
              }
            </strong>
          </div>
          <span className="workspace-tag">单人研发 · 本地原型</span>
        </header>
        <main>
          {error && (
            <div className="message error" role="alert">
              <TriangleAlert size={17} />
              <span>{error}</span>
              <button aria-label="关闭错误" onClick={() => setError("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {notice && (
            <div className="message success" role="status">
              <CheckCircle2 size={17} />
              <span>{notice}</span>
              <button aria-label="关闭提示" onClick={() => setNotice("")}>
                <X size={16} />
              </button>
            </div>
          )}
          {route === "review" && (
            <ReviewCenter
              onStartTour={(tour) => {
                setGuidedTour(tour);
                setRoute("decision");
                window.scrollTo(0, 0);
              }}
            />
          )}
          {route === "decision" && (
            <DecisionWorkflow
              key={guidedTour?.id || "normal"}
              guidedTour={guidedTour}
              onEndTour={() => {
                setGuidedTour(null);
                setRoute("review");
                window.scrollTo(0, 0);
              }}
            />
          )}
          {route === "workbench" && scenario && (
            <>
              <div className="page-heading">
                <div>
                  <h1>养护场景与材料方案</h1>
                  <p>
                    给出养护场景与性能目标，比较历史候选，再决定下一步试验。
                  </p>
                </div>
                <div className="heading-note">
                  <span className="tiny-dot" />
                  历史记录初筛
                  <br />
                  <small>工程适用性待审核</small>
                </div>
              </div>
              <div className="case-bar">
                <span>演示案例</span>
                {cases.map((c) => (
                  <button
                    key={c.id}
                    className={
                      scenario.case_id === c.id ? "case active" : "case"
                    }
                    onClick={() => void chooseCase(c)}
                    disabled={busy}
                  >
                    <b>{c.id}</b>
                    {c.title}
                  </button>
                ))}
              </div>
              <div className="work-grid">
                <section className="scenario-panel panel">
                  <div className="panel-heading">
                    <h2>
                      <ClipboardList size={18} />
                      场景与目标
                    </h2>
                    <span className="mono">INPUT</span>
                  </div>
                  <div className="scenario-body">
                    <label>
                      方案名称
                      <input
                        value={scenario.name}
                        onChange={(e) => update({ name: e.target.value })}
                      />
                    </label>
                    <div className="two-fields">
                      <label>
                        主要病害
                        <select
                          value={scenario.distress_type}
                          onChange={(e) =>
                            update({ distress_type: e.target.value })
                          }
                        >
                          {["高温车辙", "低温开裂", "水损害", "复合需求"].map(
                            (v) => (
                              <option key={v}>{v}</option>
                            ),
                          )}
                        </select>
                      </label>
                      <label>
                        排序优先指标
                        <select
                          value={scenario.priority}
                          onChange={(e) => update({ priority: e.target.value })}
                        >
                          {core.map((m) => (
                            <option value={m} key={m}>
                              {metrics[m].short}
                            </option>
                          ))}
                        </select>
                      </label>
                    </div>
                    <label>
                      已确定的养护方式
                      <input
                        value={scenario.maintenance_method}
                        onChange={(e) =>
                          update({ maintenance_method: e.target.value })
                        }
                      />
                    </label>
                    <label>
                      结构层位
                      <input
                        value={scenario.layer}
                        onChange={(e) => update({ layer: e.target.value })}
                      />
                    </label>
                    <div className="section-label">
                      性能目标 <span>全部约束同时满足</span>
                    </div>
                    <div className="target-list">
                      {scenario.targets.map((t, i) => (
                        <div className="target-row" key={t.metric}>
                          <label htmlFor={"target-" + t.metric}>
                            {metrics[t.metric].short}
                            <small title={t.reference || "项目目标"}>
                              {metrics[t.metric].unit} /{" "}
                              {t.source_kind === "enterprise_reference"
                                ? "企业参考"
                                : t.source_kind === "demo_assumption"
                                  ? "演示目标"
                                  : "项目目标"}
                            </small>
                          </label>
                          <select
                            aria-label={metrics[t.metric].name + "比较符"}
                            value={t.operator}
                            onChange={(e) =>
                              updateTarget(i, {
                                operator: e.target.value as typeof t.operator,
                              })
                            }
                          >
                            {[">", ">=", "<", "<=", "between"].map((o) => (
                              <option key={o} value={o}>
                                {o === "between" ? "区间" : o}
                              </option>
                            ))}
                          </select>
                          <input
                            id={"target-" + t.metric}
                            type="number"
                            min="0"
                            step="any"
                            value={t.value}
                            onChange={(e) =>
                              updateTarget(i, { value: Number(e.target.value) })
                            }
                          />
                          {t.operator === "between" && (
                            <input
                              aria-label={metrics[t.metric].name + "上限"}
                              type="number"
                              value={t.upper ?? t.value}
                              onChange={(e) =>
                                updateTarget(i, {
                                  upper: Number(e.target.value),
                                })
                              }
                            />
                          )}
                        </div>
                      ))}
                    </div>
                    <div className="two-fields">
                      <label>
                        名义 RAP 下限 / %
                        <input
                          type="number"
                          min="0"
                          max="100"
                          value={scenario.rap_min_pct}
                          onChange={(e) =>
                            update({ rap_min_pct: Number(e.target.value) })
                          }
                        />
                      </label>
                      <label>
                        候选范围
                        <select
                          value={scenario.candidate_ids ? "case" : "all"}
                          onChange={(e) =>
                            update({
                              candidate_ids:
                                e.target.value === "all"
                                  ? null
                                  : cases.find((c) => c.id === scenario.case_id)
                                      ?.scenario.candidate_ids || null,
                            })
                          }
                        >
                          <option value="case">当前案例候选</option>
                          <option value="all">全部历史方案</option>
                        </select>
                      </label>
                    </div>
                    <details className="advanced">
                      <summary>气候、交通与项目约束</summary>
                      <label>
                        气候条件
                        <input
                          placeholder="尚未提供"
                          value={scenario.climate_zone || ""}
                          onChange={(e) =>
                            update({ climate_zone: e.target.value || null })
                          }
                        />
                      </label>
                      <label>
                        交通荷载
                        <input
                          placeholder="尚未提供"
                          value={scenario.traffic_level || ""}
                          onChange={(e) =>
                            update({ traffic_level: e.target.value || null })
                          }
                        />
                      </label>
                      <label>
                        可用来源代码（逗号分隔）
                        <input
                          placeholder="全部来源"
                          value={scenario.available_sources?.join(",") || ""}
                          onChange={(e) =>
                            update({
                              available_sources: e.target.value
                                ? e.target.value
                                    .split(/[,，]/)
                                    .map((s) => s.trim())
                                    .filter(Boolean)
                                : null,
                            })
                          }
                        />
                      </label>
                      <label>
                        单位成本上限（缺价格时标记待补充）
                        <input
                          type="number"
                          min="0"
                          value={scenario.budget ?? ""}
                          onChange={(e) =>
                            update({
                              budget: e.target.value
                                ? Number(e.target.value)
                                : null,
                            })
                          }
                        />
                      </label>
                      <label>
                        场景数据范围
                        <select
                          value={scenario.context_kind}
                          onChange={(e) =>
                            update({ context_kind: e.target.value })
                          }
                        >
                          <option value="constructed_demo">
                            构造演示（含已审核演示试验）
                          </option>
                          <option value="project">
                            正式项目（排除演示试验）
                          </option>
                        </select>
                      </label>
                    </details>
                    <p className="input-note">
                      {cases.find((c) => c.id === scenario.case_id)
                        ?.provenance || "请确认项目目标与试验条件。"}
                    </p>
                    <button
                      className="primary wide"
                      disabled={
                        busy ||
                        !scenario.name ||
                        !scenario.maintenance_method ||
                        !scenario.layer
                      }
                      onClick={() => void calculate(scenario)}
                    >
                      {busy ? (
                        <LoaderCircle size={17} className="spin" />
                      ) : (
                        <Search size={17} />
                      )}{" "}
                      {busy ? "正在计算…" : "运行材料初筛"}
                      <ArrowRight size={17} />
                    </button>
                  </div>
                </section>
                <div className="result-stack">
                  <section className="panel result-panel">
                    <div className="panel-heading">
                      <h2>候选方案比较</h2>
                      <div className="panel-tools">
                        {dirty && (
                          <span className="dirty">
                            输入或数据已变化，需重新计算
                          </span>
                        )}
                        {snapshot && (
                          <a
                            className="text-action"
                            href={
                              "/v1/recommendations/" +
                              snapshot.id +
                              "/report.html"
                            }
                            target="_blank"
                            rel="noreferrer"
                          >
                            方案报告
                            <ArrowUpRight size={15} />
                          </a>
                        )}
                      </div>
                    </div>
                    <div className="result-summary">
                      <strong>
                        {snapshot?.summary.needs_review ?? "—"}
                        <small>项建议复核</small>
                      </strong>
                      <span>
                        共 {snapshot?.summary.total ?? 0} 个候选 ·{" "}
                        {snapshot?.summary.excluded ?? 0} 项未满足目标
                      </span>
                      <span className="subtle">所有排序均在硬约束筛选之后</span>
                    </div>
                    {snapshot && (
                      <CandidateTable
                        recipes={snapshot.results}
                        selected={selected}
                        onSelect={setSelected}
                      />
                    )}
                    {snapshot?.empty_reason && (
                      <div className="empty-result">
                        <TriangleAlert size={21} />
                        <div>
                          <strong>当前候选没有同时满足全部目标</strong>
                          <p>{snapshot.empty_reason}</p>
                          <button
                            className="text-action"
                            onClick={() => {
                              setInspectorTab("evidence");
                            }}
                          >
                            查看候选依据与补试验需求
                            <ArrowRight size={14} />
                          </button>
                        </div>
                      </div>
                    )}
                    {snapshot && (
                      <details className="next-tests">
                        <summary>
                          下一步核验与补充试验（{snapshot.next_tests.length}{" "}
                          项建议）
                        </summary>
                        {snapshot.next_tests.map((t, i) => (
                          <button
                            key={i}
                            onClick={() => {
                              setSelected(t.recipe_id);
                              setInspectorTab("evidence");
                            }}
                          >
                            <b>
                              {
                                snapshot.results.find(
                                  (r) => r.id === t.recipe_id,
                                )?.display_id
                              }
                            </b>
                            <span>
                              {metrics[t.metric]?.name ||
                                (t.metric === "unit_cost"
                                  ? "材料价格"
                                  : "RAP计量口径")}
                              ：{t.reason}
                            </span>
                            <ChevronRight size={14} />
                          </button>
                        ))}
                      </details>
                    )}
                    <div className="table-foot">
                      <span>
                        <i className="tiny-dot" />{" "}
                        绿色表示满足当前数值目标，仍需适用性审核
                      </span>
                      <span>历史聚合值 · 非预测区间</span>
                    </div>
                  </section>
                  {selected && (
                    <section className="panel inspector">
                      <div className="panel-heading">
                        <h2>
                          方案依据{" "}
                          <span className="selected-id">
                            {detail?.display_id || "…"}
                          </span>
                        </h2>
                        <div className="tab-group">
                          {[
                            { id: "evidence", label: "试验依据" },
                            { id: "gradation", label: "级配与身份" },
                            { id: "variant", label: "微调版本" },
                            { id: "observations", label: "试验记录" },
                          ].map((t) => (
                            <button
                              key={t.id}
                              className={inspectorTab === t.id ? "active" : ""}
                              onClick={() => setInspectorTab(t.id)}
                            >
                              {t.label}
                            </button>
                          ))}
                        </div>
                      </div>
                      {detail ? (
                        <Inspector
                          recipe={detail}
                          tab={inspectorTab}
                          onError={setError}
                          onVariant={async (r) => {
                            await changed(
                              "已创建微调版本，父方案性能依据已失效。",
                            );
                            setSelected(r.id);
                            const s = {
                              ...scenario,
                              candidate_ids: [r.id],
                              case_id: null,
                            };
                            setScenario(s);
                            await calculate(s);
                          }}
                        />
                      ) : (
                        <div className="loading">
                          <LoaderCircle className="spin" size={18} />
                          正在读取原始依据…
                        </div>
                      )}
                    </section>
                  )}
                </div>
              </div>
            </>
          )}
          {route === "data" && dataset && (
            <>
              <PageTitle
                index="02"
                title="从每条记录，回到原始证据。"
                subtitle="保留工作簿中的身份、单位、缺失值与公式错误，按字段审查。"
              />
              <div className="data-layout">
                <section className="panel">
                  <div className="panel-heading">
                    <h2>历史方案目录</h2>
                    <label className="search-field">
                      <Search size={15} />
                      <input
                        aria-label="搜索数据目录"
                        placeholder="来源 / 级配 / 产品"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                      />
                    </label>
                  </div>
                  <div className="catalog-table">
                    <CandidateTable
                      recipes={visible}
                      selected={selected}
                      onSelect={(id) => {
                        setSelected(id);
                        setRoute("workbench");
                        setInspectorTab("evidence");
                      }}
                    />
                  </div>
                </section>
                <Quality dataset={dataset} />
              </div>
            </>
          )}
          {route === "observations" && (
            <>
              <PageTitle
                index="03"
                title="试验结果，经过审核再回流。"
                subtitle="草稿、审核与修订保留记录；演示数据按范围隔离。"
              />
              <ObservationWorkspace
                recipes={catalog}
                refresh={refresh}
                onChange={changed}
                onError={setError}
              />
            </>
          )}
          {route === "models" && (
            <>
              <PageTitle
                index="04"
                title="先看泛化证据，再使用预测。"
                subtitle="设计前输入、按组拆分与独立折预测；模型结果保留研究属性。"
              />
              <ModelWorkspace onError={setError} />
            </>
          )}
          {route === "reports" && (
            <>
              <PageTitle
                index="05"
                title="每份报告，都保存当时的判断。"
                subtitle="数据、规则、输入与结果一起冻结。后续试验不会覆盖已有报告。"
              />
              <Reports refresh={refresh} onError={setError} />
            </>
          )}
          <footer>
            数智选材 <span>/</span> 道路养护材料方案研究原型 <span>·</span>{" "}
            原始资料只读保留
          </footer>
        </main>
      </div>
    </div>
  );
}

function PageTitle({
  index,
  title,
  subtitle,
}: {
  index: string;
  title: string;
  subtitle: string;
}) {
  return (
    <div className="page-heading">
      <div>
        <h1>{title}</h1>
        <p>{subtitle}</p>
      </div>
    </div>
  );
}
function CandidateTable({
  recipes,
  selected,
  onSelect,
}: {
  recipes: Recipe[];
  selected: string | null;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="table-scroll">
      <table className="candidate-table">
        <thead>
          <tr>
            <th>历史候选 / 材料身份</th>
            <th>
              RAP<small>名义 %</small>
            </th>
            {core.map((m) => (
              <th key={m}>
                {metrics[m].short}
                <small>{metrics[m].unit}</small>
              </th>
            ))}
            <th>当前状态</th>
          </tr>
        </thead>
        <tbody>
          {recipes.map((r) => (
            <tr
              key={r.id}
              className={selected === r.id ? "selected" : ""}
              onClick={() => onSelect(r.id)}
            >
              <td>
                <button
                  className="recipe-select"
                  onClick={(e) => {
                    e.stopPropagation();
                    onSelect(r.id);
                  }}
                >
                  <b>{r.display_id}</b>
                  <span>
                    <strong>
                      {r.source} · {r.gradation}
                    </strong>
                    <small>
                      {r.product}{" "}
                      <span className="oil">
                        油石比 {fmt(r.oil_stone_ratio_pct)}%
                      </span>
                    </small>
                  </span>
                </button>
              </td>
              <td className="numeric">{fmt(r.rap_nominal_pct)}</td>
              {core.map((m) => (
                <td
                  key={m}
                  className={
                    "numeric " + (r.failed_metrics?.includes(m) ? "failed" : "")
                  }
                >
                  {fmt(r.metrics[m])}
                  {r.failed_metrics?.includes(m) && (
                    <span className="cell-mark">↓</span>
                  )}
                </td>
              ))}
              <td>
                <Status recipe={r} />
              </td>
            </tr>
          ))}
        </tbody>
      </table>
      {recipes.length === 0 && (
        <div className="loading">没有匹配的候选记录</div>
      )}
    </div>
  );
}

function Inspector({
  recipe: r,
  tab,
  onVariant,
  onError,
}: {
  recipe: Recipe;
  tab: string;
  onVariant: (r: Recipe) => Promise<void>;
  onError: (s: string) => void;
}) {
  const [raw, setRaw] = useState<{
    title: string;
    cells: Record<
      string,
      { value: unknown; formula: string | null; number_format: string }
    >;
  } | null>(null);
  useEffect(() => {
    setRaw(null);
  }, [r.id]);
  async function showRaw(ev: Evidence, index = 0) {
    const l = ev.raw_labels?.[index];
    if (!l) return;
    try {
      const row = await api<{
        payload: {
          cells: Record<
            string,
            { value: unknown; formula: string | null; number_format: string }
          >;
        };
      }>(
        "/evidence/" +
          r.dataset_id +
          "/" +
          encodeURIComponent(l.sheet) +
          "/" +
          l.row,
      );
      setRaw({
        title: l.sheet + " · 第" + l.row + "行",
        cells: row.payload.cells,
      });
    } catch (e) {
      onError(String(e));
    }
  }
  return (
    <div className="inspector-body">
      <div className="identity-line">
        <strong>
          {r.source} / {r.gradation} / {r.product}
        </strong>
        <span>
          油石比 {fmt(r.oil_stone_ratio_pct)}% → 沥青用量{" "}
          {fmt(r.binder_content_pct, 3)}%
        </span>
        {r.kind === "variant" && (
          <span className="status needs_test">未试验版本</span>
        )}
      </div>
      {tab === "evidence" && (
        <>
          <div className="evidence-grid">
            {core.map((m) => {
              const ev = r.evidence[m];
              return (
                <div className="evidence-item" key={m}>
                  <div>
                    {metrics[m].name}
                    <span>
                      {ev?.source_kind?.includes("observation")
                        ? "审核回流"
                        : "原表记录"}
                    </span>
                  </div>
                  <strong>
                    {fmt(r.metrics[m])}
                    <small>{metrics[m].unit}</small>
                  </strong>
                  {ev ? (
                    <>
                      <p>
                        记录范围 {fmt(ev.range?.[0])} – {fmt(ev.range?.[1])}
                        <br />
                        {ev.n_recorded} 条标签 ·{" "}
                        {ev.n_independent_assumed == null
                          ? "组结果，独立批次未知"
                          : ev.n_independent_assumed + " 条暂按独立记录"}
                      </p>
                      {ev.suspected_derived_mean && (
                        <p className="warning-inline">
                          第 3 条疑为均值，未增加独立数。
                        </p>
                      )}
                      {ev.raw_labels?.length ? (
                        <div className="source-cells">
                          <span>{ev.raw_labels[0].sheet}</span>
                          {ev.raw_labels.map((l, i) => (
                            <button
                              key={l.cell}
                              className="source-link"
                              onClick={() => void showRaw(ev, i)}
                            >
                              {l.cell}
                              <ArrowUpRight size={10} />
                            </button>
                          ))}
                        </div>
                      ) : (
                        <span className="source-link">
                          {ev.observation_id?.slice(-12)}
                        </span>
                      )}
                    </>
                  ) : (
                    <p>
                      缺少该指标的试验记录
                      <br />
                      微调版本需重新试验
                    </p>
                  )}
                </div>
              );
            })}
          </div>
          {raw && (
            <div className="raw-record">
              <div>
                <strong>{raw.title}</strong>
                <button aria-label="关闭原始行" onClick={() => setRaw(null)}>
                  <X size={15} />
                </button>
              </div>
              <div className="raw-scroll">
                <table>
                  <thead>
                    <tr>
                      <th>单元格</th>
                      <th>原始值</th>
                      <th>公式</th>
                      <th>显示格式</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(raw.cells).map(([cell, v]) => (
                      <tr key={cell}>
                        <td>{cell}</td>
                        <td>{String(v.value ?? "缺失")}</td>
                        <td>{v.formula || "—"}</td>
                        <td>{v.number_format}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          )}
          <div className="quality-line">
            <TriangleAlert size={15} />
            {r.payload.flags.map((f) => (
              <span key={f}>{flags[f] || f}</span>
            ))}
          </div>
        </>
      )}
      {tab === "gradation" && (
        <div className="gradation-view">
          <div>
            <h3>合成级配 · 原表存储曲线</h3>
            {r.payload.gradation ? (
              <>
                <Gradation curve={r.payload.gradation.curve} />
                <p className="subtle">
                  {r.payload.gradation.curve_reference} · 通过率 / % · 筛孔 / mm
                </p>
              </>
            ) : (
              <p>级配未关联或因 RAP 微调已失效，需要新的分档比例与筛分试验。</p>
            )}
          </div>
          <div className="field-notes">
            <h3>身份与计算口径</h3>
            <dl>
              <dt>来源代码</dt>
              <dd>{r.source}（匿名代码）</dd>
              <dt>配方身份</dt>
              <dd>{r.id}</dd>
              <dt>父版本</dt>
              <dd>{r.parent_id || "历史原表记录"}</dd>
              <dt>RAP 比例</dt>
              <dd>{fmt(r.rap_nominal_pct)}% · 名义计量基准待确认</dd>
            </dl>
            <p>
              各档权重仅在确认按矿料质量计量后用于合成计算。旧沥青质量记录不等于全部活化。
            </p>
          </div>
        </div>
      )}
      {tab === "variant" && (
        <VariantForm recipe={r} onCreated={onVariant} onError={onError} />
      )}
      {tab === "observations" && (
        <div>
          <p className="subtle">
            此处显示全部草稿与审核记录。使用“试验回流”工作区新增、审核或修订。
          </p>
          {r.observations?.length ? (
            r.observations.map((o) => (
              <div key={o.id} className="observation-line">
                <span>
                  {metrics[o.metric].short}{" "}
                  <b>
                    {fmt(o.value)} {o.unit}
                  </b>
                </span>
                <span>
                  {o.data_scope === "demo" ? "演示" : "正式"} · {o.state}
                </span>
                <small>
                  {o.payload.test_group} · {o.payload.conditions}
                </small>
              </div>
            ))
          ) : (
            <p>尚无回流试验。</p>
          )}
        </div>
      )}
    </div>
  );
}
function Gradation({ curve }: { curve: (number | null)[] }) {
  const xs = [26.5, 19, 16, 13.2, 9.5, 4.75, 2.36, 1.18, 0.6, 0.3, 0.15, 0.075];
  return (
    <svg
      className="gradation-chart"
      role="img"
      aria-label="原表合成级配通过率曲线"
      viewBox="0 0 600 230"
    >
      {[0, 25, 50, 75, 100].map((y) => (
        <g key={y}>
          <line
            x1="36"
            x2="580"
            y1={190 - y * 1.65}
            y2={190 - y * 1.65}
            stroke="#e0e8ec"
          />
          <text x="25" y={194 - y * 1.65} textAnchor="end">
            {y}
          </text>
        </g>
      ))}
      <polyline
        points={curve
          .map((y, i) => (y === null ? "" : `${45 + i * 48},${190 - y * 1.65}`))
          .filter(Boolean)
          .join(" ")}
        fill="none"
        stroke="#007f82"
        strokeWidth="2.6"
      />
      {curve.map(
        (y, i) =>
          y !== null && (
            <circle
              key={i}
              cx={45 + i * 48}
              cy={190 - y * 1.65}
              r="3"
              fill="#007f82"
            />
          ),
      )}
      {xs.map((x, i) => (
        <text key={i} x={45 + i * 48} y="216" textAnchor="middle">
          {x}
        </text>
      ))}
    </svg>
  );
}
function VariantForm({
  recipe,
  onCreated,
  onError,
}: {
  recipe: Recipe;
  onCreated: (r: Recipe) => Promise<void>;
  onError: (s: string) => void;
}) {
  const [oil, setOil] = useState(String(recipe.oil_stone_ratio_pct ?? "")),
    [rap, setRap] = useState(String(recipe.rap_nominal_pct ?? "")),
    [product, setProduct] = useState(recipe.product),
    [note, setNote] = useState(""),
    [busy, setBusy] = useState(false),
    [prediction, setPrediction] = useState<PredictionResult | null>(null),
    [optimization, setOptimization] = useState<string>("");
  useEffect(() => {
    api<{ local_optimization: { reason: string } }>("/features")
      .then((f) => setOptimization(f.local_optimization.reason))
      .catch((e) => onError(String(e)));
  }, []);
  useEffect(() => {
    setOil(String(recipe.oil_stone_ratio_pct ?? ""));
    setRap(String(recipe.rap_nominal_pct ?? ""));
    setProduct(recipe.product);
    setNote("");
    setPrediction(null);
  }, [recipe.id]);
  async function submit(e: React.SubmitEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await onCreated(
        await api<Recipe>("/recipes/" + recipe.id + "/variants", {
          oil_stone_ratio_pct: oil ? Number(oil) : null,
          rap_nominal_pct: rap ? Number(rap) : null,
          product,
          note,
        }),
      );
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <form className="variant-form" onSubmit={(e) => void submit(e)}>
      <div className="message warning">
        <TriangleAlert size={17} />
        <span>
          改变设计输入后，新版本不继承父方案的试验结果。模型预测仅作为研究参考。
        </span>
      </div>
      <p className="input-note">
        自动配方优化暂不可用：{optimization || "正在读取条件状态…"}
      </p>
      <div className="three-fields">
        <label>
          油石比 / %
          <input
            type="number"
            step="0.01"
            min="0.01"
            max="20"
            value={oil}
            onChange={(e) => setOil(e.target.value)}
          />
        </label>
        <label>
          名义 RAP / %
          <input
            type="number"
            min="0"
            max="100"
            value={rap}
            onChange={(e) => setRap(e.target.value)}
          />
        </label>
        <label>
          沥青产品
          <input
            required
            value={product}
            onChange={(e) => setProduct(e.target.value)}
          />
        </label>
      </div>
      <label>
        变更理由
        <input
          required
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="记录为何调整、拟验证的性能与试验安排"
        />
      </label>
      <div className="form-actions">
        <button className="primary" disabled={busy || !note.trim()}>
          <Plus size={16} />
          创建微调版本
        </button>
        <button
          type="button"
          className="secondary"
          onClick={() =>
            void api<PredictionResult>("/predictions/" + recipe.id, {})
              .then(setPrediction)
              .catch((e) => onError(String(e)))
          }
        >
          研究模型预测
        </button>
      </div>
      {prediction && <PredictionPanel result={prediction} />}
    </form>
  );
}
interface PredictionResult {
  status: string;
  reason?: string;
  note?: string;
  predictions: Record<
    string,
    {
      value: number;
      state: string;
      interval: { lower: number; upper: number; center: number } | null;
      historical_identity_seen: boolean;
    }
  >;
}
function PredictionPanel({ result }: { result: PredictionResult }) {
  return (
    <div className="prediction-panel">
      <h3>研究模型参考</h3>
      {result.status === "abstained" ? (
        <p>{result.reason}</p>
      ) : (
        <>
          <div className="table-scroll">
            <table className="model-table">
              <thead>
                <tr>
                  <th>指标</th>
                  <th>点预测</th>
                  <th>另行校准的90%研究区间</th>
                  <th>适用性</th>
                </tr>
              </thead>
              <tbody>
                {Object.entries(result.predictions).map(([m, v]) => (
                  <tr key={m}>
                    <td>{metrics[m].short}</td>
                    <td>
                      {fmt(v.value)} {metrics[m].unit}
                    </td>
                    <td>
                      {v.interval
                        ? `${fmt(v.interval.lower)} – ${fmt(v.interval.upper)}（中心 ${fmt(v.interval.center)}）`
                        : "区间不可用"}
                    </td>
                    <td>
                      {v.state === "research_reference"
                        ? "观察设计范围内"
                        : "超出观察支持"}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p>{result.note}</p>
          <p>
            各指标区间独立校准，需分组可交换性假设；区间中心来自单独拟合的模型。预测与区间均不作为工程验收或硬约束通过依据。
          </p>
        </>
      )}
    </div>
  );
}
function Quality({ dataset: d }: { dataset: Dataset }) {
  return (
    <aside className="panel quality-panel">
      <div className="panel-heading">
        <h2>数据口径与待核验项</h2>
      </div>
      <div className="quality-body">
        <dl>
          <dt>试件记录</dt>
          <dd>{d.summary.specimen_total.toLocaleString()} 行</dd>
          <dt>级配区块</dt>
          <dd>{d.summary.gradation_blocks} 个</dd>
          <dt>来源代码</dt>
          <dd>{d.summary.source_codes} 个</dd>
          <dt>操作配方键</dt>
          <dd>{d.summary.operational_recipes} 个</dd>
        </dl>
        <p>
          试件行数包含重复试验，不能作为独立训练样本数。来源代码尚未确认对应独立料源。
        </p>
        <h3>字段级质量标记</h3>
        <ul>
          <li>
            {d.summary.suspected_mean_DS_groups} 组车辙第三值疑为前两值均值
          </li>
          <li>{d.summary.curve_mismatches.length} 处非零分档曲线关联需复核</li>
          <li>{d.summary.formula_errors.length} 处原料公式错误已隔离</li>
          <li>TSR 原始小数统一 ×100 为百分数</li>
        </ul>
        <h3>待确认别名</h3>
        {d.summary.conditional_aliases.map((s) => (
          <p className="alias" key={s}>
            {s}
          </p>
        ))}
        <h3>来源指纹</h3>
        <p>{d.filename}</p>
        <code>{d.sha256}</code>
        <p className="subtle">原文件 SHA256 · 数据修订 {d.revision}</p>
      </div>
    </aside>
  );
}

function ObservationWorkspace({
  recipes,
  refresh,
  onChange,
  onError,
}: {
  recipes: Recipe[];
  refresh: number;
  onChange: (m: string) => Promise<void>;
  onError: (s: string) => void;
}) {
  const [records, setRecords] = useState<Observation[]>([]),
    [recipe, setRecipe] = useState(
      recipes.find((r) => r.display_id === "R1")?.id || recipes[0]?.id || "",
    ),
    [metric, setMetric] = useState("DS"),
    [value, setValue] = useState(""),
    [method, setMethod] = useState(""),
    [conditions, setConditions] = useState(""),
    [group, setGroup] = useState(""),
    [count, setCount] = useState("2"),
    [scope, setScope] = useState("demo"),
    [sourceReference, setSourceReference] = useState(""),
    [busy, setBusy] = useState(false),
    [supersedes, setSupersedes] = useState<string | null>(null);
  const keyRef = useRef(crypto.randomUUID());
  useEffect(() => {
    api<Observation[]>("/observations")
      .then(setRecords)
      .catch((e) => onError(String(e)));
  }, [refresh]);
  async function submit(e: React.SubmitEvent) {
    e.preventDefault();
    setBusy(true);
    try {
      await api("/observations", {
        recipe_id: recipe,
        metric,
        value: Number(value),
        unit: metrics[metric].unit,
        test_group: group,
        method,
        conditions,
        source_reference: sourceReference,
        sample_count: Number(count),
        idempotency_key: keyRef.current,
        data_scope: scope,
        supersedes_id: supersedes,
        note: "",
      });
      keyRef.current = crypto.randomUUID();
      setValue("");
      setSupersedes(null);
      await onChange("试验草稿已保存，审核前不会参与推荐。");
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="observation-layout">
      <section className="panel">
        <div className="panel-heading">
          <h2>{supersedes ? "新增修订记录" : "录入试验草稿"}</h2>
          <span className="mono">DRAFT</span>
        </div>
        <form className="observation-form" onSubmit={(e) => void submit(e)}>
          <label>
            对应方案
            <select value={recipe} onChange={(e) => setRecipe(e.target.value)}>
              {recipes.map((r) => (
                <option value={r.id} key={r.id}>
                  {r.display_id} · {r.source}/{r.gradation}/{r.product}
                </option>
              ))}
            </select>
          </label>
          <div className="two-fields">
            <label>
              指标
              <select
                value={metric}
                onChange={(e) => setMetric(e.target.value)}
              >
                {Object.entries(metrics).map(([m, d]) => (
                  <option key={m} value={m}>
                    {d.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              组结果 / {metrics[metric].unit}
              <input
                type="number"
                min="0"
                step="any"
                required
                value={value}
                onChange={(e) => setValue(e.target.value)}
              />
            </label>
          </div>
          <label>
            试验组编号
            <input
              required
              value={group}
              onChange={(e) => setGroup(e.target.value)}
              placeholder="批次、日期与试验组标识"
            />
          </label>
          <label>
            试验方法
            <input
              required
              value={method}
              onChange={(e) => setMethod(e.target.value)}
              placeholder="具体试验方法或企业规程"
            />
          </label>
          <label>
            原始记录位置
            <input
              required
              value={sourceReference}
              onChange={(e) => setSourceReference(e.target.value)}
              placeholder="试验报告编号、文件路径或记录页码"
            />
          </label>
          <label>
            试验条件与计算说明
            <textarea
              required
              rows={3}
              value={conditions}
              onChange={(e) => setConditions(e.target.value)}
              placeholder="温度、荷载、养生条件、组结果计算方式与原始记录位置"
            />
          </label>
          <div className="two-fields">
            <label>
              组内试件数
              <input
                required
                type="number"
                min="1"
                max="10000"
                value={count}
                onChange={(e) => setCount(e.target.value)}
              />
            </label>
            <label>
              数据范围
              <select value={scope} onChange={(e) => setScope(e.target.value)}>
                <option value="demo">演示数据</option>
                <option value="official">正式试验</option>
              </select>
            </label>
          </div>
          {supersedes && (
            <p className="subtle">修订 {supersedes}，保留原记录。</p>
          )}
          <p className="input-note">
            TSR 按百分数录入，例如
            88.5。组内试件数为声明值，需原始试验材料核验。
          </p>
          <button className="primary wide" disabled={busy}>
            保存待审核草稿
            <ArrowRight size={16} />
          </button>
        </form>
      </section>
      <section className="panel">
        <div className="panel-heading">
          <h2>审核与版本记录</h2>
          <span>{records.length} 条</span>
        </div>
        <div className="review-list">
          {records.length === 0 && (
            <div className="blank-state">
              <FlaskConical size={32} />
              <h3>第一条回流，从试验开始。</h3>
              <p>
                录入后可审核、驳回或创建修订。演示数据不会进入正式项目和训练集。
              </p>
            </div>
          )}
          {records.map((o) => (
            <ReviewCard
              key={o.id}
              observation={o}
              recipe={recipes.find((r) => r.id === o.recipe_id)}
              onError={onError}
              onChange={onChange}
              onCorrect={() => {
                setRecipe(o.recipe_id);
                setMetric(o.metric);
                setValue(String(o.value));
                setGroup(o.payload.test_group);
                setMethod(o.payload.method);
                setConditions(o.payload.conditions);
                setCount(String(o.payload.sample_count));
                setScope(o.data_scope);
                setSourceReference(o.payload.source_reference || "");
                setSupersedes(o.id);
                keyRef.current = crypto.randomUUID();
              }}
            />
          ))}
        </div>
      </section>
    </div>
  );
}
function ReviewCard({
  observation: o,
  recipe,
  onChange,
  onError,
  onCorrect,
}: {
  observation: Observation;
  recipe?: Recipe;
  onChange: (m: string) => Promise<void>;
  onError: (s: string) => void;
  onCorrect: () => void;
}) {
  const [reviewer, setReviewer] = useState(""),
    [note, setNote] = useState(""),
    [confirmed, setConfirmed] = useState(false),
    [use, setUse] = useState(false),
    [busy, setBusy] = useState(false);
  async function review(state: string) {
    setBusy(true);
    try {
      await api("/observations/" + o.id + "/review", {
        state,
        reviewer,
        note,
        conditions_confirmed: confirmed,
        use_for_recommendation: state === "approved" && use,
      });
      await onChange(
        state === "approved"
          ? "记录已批准，既有报告快照保持不变。"
          : "记录已驳回，原始记录保留。",
      );
    } catch (e) {
      onError(String(e));
    } finally {
      setBusy(false);
    }
  }
  return (
    <article className="review-card">
      <div className="review-heading">
        <div>
          <b>
            {recipe?.display_id || o.recipe_id.slice(-8)} ·{" "}
            {metrics[o.metric].name}
          </b>
          <span>
            {fmt(o.value)} {o.unit}
          </span>
        </div>
        <span
          className={
            "status " +
            (o.state === "approved"
              ? "needs_review"
              : o.state === "rejected"
                ? "excluded"
                : "needs_test")
          }
        >
          {o.data_scope === "demo" ? "演示" : "正式"} ·{" "}
          {o.state === "draft"
            ? "待审核"
            : o.state === "approved"
              ? "已批准"
              : "已驳回"}
        </span>
      </div>
      <p>
        {o.payload.test_group} / {o.payload.method}
      </p>
      <p>{o.payload.conditions}</p>
      <p>原始记录：{o.payload.source_reference}</p>
      {o.payload.supersedes_id && (
        <p className="subtle">修订自 {o.payload.supersedes_id}</p>
      )}
      {o.state === "draft" ? (
        <>
          <div className="two-fields">
            <label>
              审核人
              <input
                required
                value={reviewer}
                onChange={(e) => setReviewer(e.target.value)}
              />
            </label>
            <label>
              审核意见
              <input
                required
                value={note}
                onChange={(e) => setNote(e.target.value)}
              />
            </label>
          </div>
          <label className="check-field">
            <input
              type="checkbox"
              checked={confirmed}
              onChange={(e) => {
                setConfirmed(e.target.checked);
                if (!e.target.checked) setUse(false);
              }}
            />
            已核验原始记录与条件适用性
          </label>
          <label className="check-field">
            <input
              type="checkbox"
              checked={use}
              disabled={!confirmed}
              onChange={(e) => setUse(e.target.checked)}
            />
            用于相同数据范围下的新推荐
          </label>
          <div className="form-actions">
            <button
              className="primary"
              disabled={busy || !reviewer.trim() || !note.trim()}
              onClick={() => void review("approved")}
            >
              <Check size={15} />
              批准记录
            </button>
            <button
              className="secondary"
              disabled={busy || !reviewer.trim() || !note.trim()}
              onClick={() => void review("rejected")}
            >
              驳回并保留
            </button>
          </div>
        </>
      ) : (
        <div className="review-complete">
          <span>
            {o.payload.review?.reviewer} · {o.payload.review?.note}
          </span>
          <button className="text-action" onClick={onCorrect}>
            创建修订
            <Plus size={14} />
          </button>
        </div>
      )}
    </article>
  );
}
interface ModelCard {
  metric: string;
  n: number;
  groups: number;
  selected_family: string;
  outer_selection_beats_dummy_mae: boolean;
  outer_selected: {
    mae: number;
    rmse: number;
    r2: number;
    threshold_errors?: number;
  };
  models: Record<string, { mae: number; rmse: number; r2: number }>;
  caveats: string[];
  calibration?: {
    status: string;
    coverage?: number;
    n_calibration?: number;
    n_test?: number;
    width?: number;
    group_coverage?: number;
    n_calibration_groups?: number;
    n_test_groups?: number;
  };
}
function ModelWorkspace({ onError }: { onError: (s: string) => void }) {
  const [data, setData] = useState<{
    status: string;
    stale?: boolean;
    models: ModelCard[];
    protocol?: string;
    dataset_sha256?: string;
    message?: string;
  } | null>(null);
  useEffect(() => {
    api<typeof data>("/models")
      .then(setData)
      .catch((e) => onError(String(e)));
  }, []);
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>按组验证的设计前性能模型</h2>
        <span className="mono">RESEARCH</span>
      </div>
      {!data ? (
        <div className="loading">正在读取模型卡…</div>
      ) : data.status === "not_trained" ? (
        <div className="blank-state">
          <Microscope size={35} />
          <h3>{data.message}</h3>
          <p>历史记录初筛可独立运行。训练完成后，此处展示真实验证结果。</p>
        </div>
      ) : (
        <div className="model-body">
          {data.stale && (
            <div className="message warning">
              <TriangleAlert size={16} />
              数据已有修订，当前模型需重新训练验证。
            </div>
          )}
          <p>{data.protocol}</p>
          <div className="message warning">
            <TriangleAlert size={17} />
            {
              data.models.filter((m) => !m.outer_selection_beats_dummy_mae)
                .length
            }{" "}
            项选择流程的外层MAE未优于均值基线；单次分组验证仍需独立料源复核。研究预测不参与历史初筛的通过判定。
          </div>
          <div className="model-grid">
            {data.models.map((m) => (
              <article key={m.metric} className="model-card">
                <div className="eyebrow">
                  {metrics[m.metric].short} · {m.selected_family}
                </div>
                <h3>{metrics[m.metric].name}</h3>
                <div className="model-number">
                  {fmt(m.outer_selected.mae)}
                  <small>外层选择流程 MAE / {metrics[m.metric].unit}</small>
                </div>
                <p>
                  {m.n} 个操作配方标签 · {m.groups} 个分组
                </p>
                <table className="model-table">
                  <thead>
                    <tr>
                      <th>基准方法</th>
                      <th>MAE</th>
                      <th>RMSE</th>
                      <th>R²</th>
                    </tr>
                  </thead>
                  <tbody>
                    {Object.entries(m.models).map(([name, score]) => (
                      <tr key={name}>
                        <td>{name}</td>
                        <td>{fmt(score.mae)}</td>
                        <td>{fmt(score.rmse)}</td>
                        <td>{fmt(score.r2, 3)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
                <p className="subtle">
                  {m.calibration?.status || "区间待验证"}
                </p>
                {m.calibration?.coverage != null && (
                  <p className="subtle">
                    校准 {m.calibration.n_calibration} 条 /{" "}
                    {m.calibration.n_calibration_groups} 组；测试{" "}
                    {m.calibration.n_test} 条 / {m.calibration.n_test_groups}{" "}
                    组。行覆盖 {fmt(m.calibration.coverage * 100)}%，组覆盖{" "}
                    {fmt((m.calibration.group_coverage || 0) * 100)}%，区间宽度{" "}
                    {fmt(m.calibration.width)} {metrics[m.metric].unit}。
                  </p>
                )}
                {m.caveats.map((c) => (
                  <p className="model-caveat" key={c}>
                    {c}
                  </p>
                ))}
              </article>
            ))}
          </div>
        </div>
      )}
    </section>
  );
}
function Reports({
  refresh,
  onError,
}: {
  refresh: number;
  onError: (s: string) => void;
}) {
  const [reports, setReports] = useState<
    {
      id: string;
      name: string;
      created_at: string;
      sha256: string;
      summary: Snapshot["summary"];
    }[]
  >([]);
  useEffect(() => {
    api<typeof reports>("/reports")
      .then(setReports)
      .catch((e) => onError(String(e)));
  }, [refresh]);
  return (
    <section className="panel">
      <div className="panel-heading">
        <h2>历史方案快照</h2>
        <span>最近 50 份</span>
      </div>
      {reports.map((r) => (
        <div className="report-row" key={r.id}>
          <FileText size={22} />
          <div>
            <h3>{r.name}</h3>
            <p>
              {new Date(r.created_at).toLocaleString("zh-CN")} ·{" "}
              {r.summary.total} 候选 / {r.summary.needs_review} 项建议复核
            </p>
            <code>{r.sha256.slice(0, 24)}</code>
          </div>
          <a
            className="secondary"
            href={"/v1/recommendations/" + r.id + "/report.html"}
            target="_blank"
            rel="noreferrer"
          >
            查看报告
            <ArrowUpRight size={15} />
          </a>
          <a
            className="text-action"
            href={"/v1/recommendations/" + r.id}
            download={r.id + ".json"}
          >
            JSON
            <Download size={15} />
          </a>
        </div>
      ))}
      {reports.length === 0 && (
        <div className="blank-state">
          <FileText size={32} />
          <h3>运行一次初筛，保存第一份方案报告。</h3>
        </div>
      )}
    </section>
  );
}

createRoot(document.getElementById("root")!).render(<App />);
