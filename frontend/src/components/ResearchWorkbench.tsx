import { useEffect, useRef, useState } from "react";
import { Download, ExternalLink, FlaskConical, LoaderCircle, Plus, Search, X } from "lucide-react";
import { researchApi, researchBase, researchMetrics } from "../research-types";
import type { CandidateDetail, CandidateList, ExperimentRow, MetricKey, ResearchFilters, ResearchOverview, ResearchPlan, SourceAudit, SourceReference } from "../research-types";
import "../research.css";

const metricKeys: MetricKey[] = ["DS", "strain", "TSR", "residual"];
const number = (v: number | null | undefined, places = 2) => v == null ? "未记录" : v.toLocaleString("zh-CN", { maximumFractionDigits: places });
const date = (value: string) => new Date(value).toLocaleString("zh-CN", { timeZone: "Asia/Shanghai", hour12: false });
function Loading() { return <p className="rw-loading" role="status"><LoaderCircle size={17} className="spin" />正在读取研究证据…</p>; }

function ExperimentTable({ rows, repeats }: { rows: ExperimentRow[]; repeats: number }) {
  return <div className="rw-table-scroll"><table className="rw-table"><thead><tr>
    <th>性能指标</th><th>均值基线 MAE</th><th>研究流程 MAE</th><th>相对变化</th><th>改善轮数</th>
  </tr></thead><tbody>{rows.map(row => <tr key={row.metric}>
    <td>{row.label}<small>误差单位：{row.unit === "%" ? "百分点" : row.unit}</small></td>
    <td className="rw-number">{number(row.baseline_mae, 3)}</td><td className="rw-number">{number(row.candidate_mae, 3)}</td>
    <td className={row.relative_improvement > 0 ? "rw-change-positive" : "rw-change-negative"}>
      {row.relative_improvement > 0 ? "下降" : "上升"} {number(Math.abs(row.relative_improvement) * 100)}%
    </td><td>{row.repeats_better_than_mean}/{repeats}</td>
  </tr>)}</tbody></table></div>;
}

function Detail({ value, pinned, toggle }: { value: CandidateDetail; pinned: boolean; toggle: () => void }) {
  return <section className="rw-detail" aria-label="配方明细">
    <div className="rw-detail-heading"><div><h2>{value.summary.source_code} · {value.summary.gradation}</h2><p>{value.summary.product}</p></div>
      <span className="rw-state">待实测</span></div>
    <p className="rw-modification">{value.summary.change_label}</p>
    <dl className="rw-ingredients"><div><dt>油石比</dt><dd>{number(value.parent.oil_stone_ratio_pct)} → <strong>{number(value.summary.oil_stone_ratio_pct)}%</strong></dd></div>
      <div><dt>名义 RAP</dt><dd>{number(value.summary.rap_nominal_pct)}%<small>物理计量口径待确认</small></dd></div></dl>
    <button className="rw-action" onClick={toggle}>{pinned ? <X size={15} /> : <Plus size={15} />}{pinned ? "移出手动计划" : "加入手动计划"}</button>
    <h3>组分份额变化</h3><p className="rw-explanation">名义份额按原表组分核算；称料前需确认 RAP、含水与结合料口径。</p>
    <div className="rw-table-scroll"><table className="rw-table rw-component-table"><thead><tr><th>原表组分</th><th>父配方</th><th>待测配方</th><th>变化</th></tr></thead>
      <tbody>{value.components.filter(c => c.before > 0 || c.after > 0).map(c => <tr key={c.row} className={Math.abs(c.delta_percentage_points) > .001 ? "rw-altered" : ""}>
        <td>{c.type}<small>级配!第{c.row}行 · {c.size === "\\" ? "规格未明确" : c.size}</small></td>
        <td className="rw-number">{number(c.before * 100)}%</td><td className="rw-number">{number(c.after * 100)}%</td>
        <td className="rw-number">{Math.abs(c.delta_percentage_points) < .001 ? "—" : `${c.delta_percentage_points > 0 ? "+" : ""}${number(c.delta_percentage_points)}个百分点`}</td>
      </tr>)}</tbody></table></div>
    <details className="rw-research-values"><summary>查看研究预测与父方案记录</summary>
      <p className="rw-explanation">预测为全量拟合参考。新配方没有实测，父方案历史记录不继承。</p>
      <table className="rw-table"><thead><tr><th>指标</th><th>研究预测</th><th>父方案历史值</th></tr></thead><tbody>{metricKeys.map(m => <tr key={m}>
        <td>{researchMetrics[m].label}<small>{researchMetrics[m].unit}</small></td><td className="rw-number">{number(value.candidate.prediction[m])}</td>
        <td className="rw-number">{number(value.parent.metrics[m]?.value)}</td></tr>)}</tbody></table>
    </details><p className="rw-explanation rw-detail-note">{value.interpretation}</p><small className="rw-id">{value.summary.id}</small>
  </section>;
}

function AuditView({ audit }: { audit: SourceAudit }) {
  const [issueId, setIssueId] = useState(audit.issues[0]?.id || "");
  const [cell, setCell] = useState<SourceReference | null>(null);
  const issue = audit.issues.find(i => i.id === issueId);
  return <div className="rw-audit">
    <div className="rw-section-heading"><div><h2>相同已知输入，需要核对哪些资料</h2><p>{audit.input_alias_groups}组输入别名；{audit.groups_with_observed_conflict}组有已观测标签差异，{audit.masked_curve_alias_groups}组涉及曲线遮蔽。</p></div>
      <a className="rw-outline" href={`${researchBase}/evidence/source_audit`}><Download size={15} />下载复核清单</a></div>
    <label className="rw-issue-select">选择复核组<select value={issueId} onChange={e => { setIssueId(e.target.value); setCell(null); }}>
      {audit.issues.map((i, n) => <option key={i.id} value={i.id}>{n + 1}. {i.entries.map(e => e.source_code).filter((v, ix, all) => all.indexOf(v) === ix).join("、")} · DS跨度 {number(i.label_ranges.DS)}{i.conflicting_metrics.length ? " · 有观测差异" : " · 输入别名"}</option>)}
    </select></label>
    {issue && <><p className="rw-note">{issue.interpretation}</p>
      <div className="rw-table-scroll"><table className="rw-table"><thead><tr><th>操作记录</th><th>级配输入</th>{metricKeys.map(m => <th key={m}>{researchMetrics[m].label}</th>)}</tr></thead>
        <tbody>{issue.entries.map(entry => <tr key={entry.id}><td>{entry.source_code} · {entry.gradation}<small>{entry.product} · {entry.id.slice(-8)}</small></td>
          <td>{entry.curve_input_masked ? "曲线已遮蔽，不能据此认定同配方" : "记录曲线可用；实物身份待核对"}</td>
          {metricKeys.map(m => <td key={m}>{number(entry.labels[m]?.value)}<div className="rw-cell-links">{entry.labels[m]?.references.map((r, i) =>
            <button key={`${r.cell}-${i}`} onClick={() => setCell(r)}>{r.sheet}!{r.cell}</button>)}</div>{entry.labels[m]?.suspected_derived_mean && <small>疑似派生均值，待核对</small>}</td>)}</tr>)}</tbody></table></div>
      {cell && <section className="rw-source-cell" aria-label="原始单元格"><h3>{cell.sheet}!{cell.cell}</h3><dl><div><dt>原表记录值</dt><dd>{number(cell.raw_value, 8)}</dd></div><div><dt>用于聚合的转换值</dt><dd>{number(cell.value, 8)}</dd></div><div><dt>原表公式</dt><dd>{cell.cached_formula || "此单元格未记录公式"}</dd></div></dl><p>位置：{cell.sheet} 第{cell.row}行。记录值与物理试验条件需要一起核对。</p></section>}
      <h3 className="rw-spaced">待补充的确认资料</h3><ol className="rw-questions">{issue.questions.map(q => <li key={q.field}>{q.question}<span>尚未确认</span></li>)}</ol>
    </>}
  </div>;
}

export function ResearchWorkbench() {
  const [overview, setOverview] = useState<ResearchOverview | null>(null);
  const [tab, setTab] = useState("candidates");
  const [filters, setFilters] = useState<ResearchFilters>({ source: "", kind: "all", supported_only: true, q: "" });
  const [offset, setOffset] = useState(0);
  const [list, setList] = useState<CandidateList | null>(null);
  const [selected, setSelected] = useState<string | null>(null);
  const [detail, setDetail] = useState<CandidateDetail | null>(null);
  const [audit, setAudit] = useState<SourceAudit | null>(null);
  const [error, setError] = useState("");
  const [pinned, setPinned] = useState<string[]>([]);
  const [budget, setBudget] = useState(3);
  const [title, setTitle] = useState("待确认配方试验计划");
  const [plan, setPlan] = useState<ResearchPlan | null>(null);
  const [busy, setBusy] = useState(false);
  const pending = useRef<{ intent: string; id: string } | null>(null);
  useEffect(() => {
    const controller = new AbortController();
    researchApi<ResearchOverview>("/overview", undefined, controller.signal).then(setOverview).catch(e => { if (!controller.signal.aborted) setError(String(e.message || e)); });
    return () => controller.abort();
  }, []);
  const query = new URLSearchParams({ ...filters, supported_only: String(filters.supported_only), offset: String(offset), limit: "10" }).toString();
  useEffect(() => {
    const controller = new AbortController(); setList(null); setDetail(null); setSelected(null);
    researchApi<CandidateList>("/candidates?" + query, undefined, controller.signal).then(result => {
      if (controller.signal.aborted) return;
      setList(result); setSelected(result.items[0]?.id || null);
    }).catch(e => { if (!controller.signal.aborted) setError(String(e.message || e)); });
    return () => controller.abort();
  }, [query]);
  useEffect(() => {
    if (!selected) return;
    const controller = new AbortController(); setDetail(null);
    researchApi<CandidateDetail>("/candidates/" + selected, undefined, controller.signal).then(value => {
      if (!controller.signal.aborted) setDetail(value);
    }).catch(e => { if (!controller.signal.aborted) setError(String(e.message || e)); });
    return () => controller.abort();
  }, [selected]);
  useEffect(() => {
    if (tab !== "audit" || audit) return;
    const controller = new AbortController();
    researchApi<SourceAudit>("/audit", undefined, controller.signal).then(value => { if (!controller.signal.aborted) setAudit(value); })
      .catch(e => { if (!controller.signal.aborted) setError(String(e.message || e)); });
    return () => controller.abort();
  }, [tab, audit]);
  function updateFilters(change: Partial<ResearchFilters>) { setFilters(old => ({ ...old, ...change })); setOffset(0); setPinned([]); setList(null); setSelected(null); setDetail(null); setError(""); }
  function togglePin() {
    if (!selected) return;
    if (pinned.includes(selected)) setPinned(old => old.filter(id => id !== selected));
    else if (pinned.length < 8) { setPinned(old => [...old, selected]); if (pinned.length + 1 > budget) setBudget(pinned.length + 1); }
    else setError("每个计划最多安排8种配方，请先移出部分手动配方。");
  }
  async function generate() {
    if (!overview) return;
    setBusy(true); setError("");
    const input = { title, scope_sha256: overview.scope_sha256, filters, budget, pinned_ids: pinned };
    const intent = JSON.stringify(input);
    if (pending.current?.intent !== intent) pending.current = { intent, id: crypto.randomUUID() };
    try {
      const value = await researchApi<ResearchPlan>("/plans", { ...input, request_id: pending.current.id });
      setPlan(value);
    } catch (e) {
      setError(String((e as Error).message || e));
      researchApi<ResearchOverview>("/overview").then(setOverview).catch(() => {});
    } finally { setBusy(false); }
  }
  return <div className="rw-root">
    <div className="rw-heading"><div><h1>配方研究与设计探索</h1><p>比较配方改动与原表依据，展示设计思路；试验安排作为可选拓展。</p></div>
      <div className="rw-downloads"><a className="rw-outline" href={`${researchBase}/evidence/report`}><Download size={15} />计算研究报告</a></div></div>
    {error && <div className="message error" role="alert"><span>{error}</span><button aria-label="关闭研究错误" onClick={() => setError("")}><X size={16} /></button></div>}
    {overview && !overview.compatibility.matches && <p className="rw-note" role="alert">{overview.compatibility.reason}</p>}
    <p className="rw-scope">{overview ? `${overview.counts.hypotheses}个设计假设 · ${overview.counts.within_observed_support}个在当前观测范围内 · 用于创意设计探索` : "正在读取研究范围…"}</p>
    <div className="rw-tabs" role="tablist" aria-label="研究内容">{[{ id: "candidates", label: "候选与方案探索" }, { id: "experiments", label: "计算研究参考" }, { id: "audit", label: "原表复核" }].map(t =>
      <button key={t.id} role="tab" aria-selected={tab === t.id} className={tab === t.id ? "active" : ""} onClick={() => setTab(t.id)}>{t.label}</button>)}</div>
    {tab === "candidates" && <>
      <div className="rw-filters"><label>来源代码<select value={filters.source} onChange={e => updateFilters({ source: e.target.value })}><option value="">全部来源代码</option>{overview?.sources.map(s => <option key={s}>{s}</option>)}</select></label>
        <label>配方改动<select value={filters.kind} onChange={e => updateFilters({ kind: e.target.value as ResearchFilters["kind"] })}><option value="all">全部改动</option><option value="oil_ratio">油石比微调</option><option value="nominal_blend">名义级配微调</option></select></label>
        <label>检索配方<div className="rw-search"><Search size={15} /><input value={filters.q} placeholder="级配、产品或配方编号" onChange={e => updateFilters({ q: e.target.value })} /></div></label>
        <label className="rw-checkbox"><input type="checkbox" checked={filters.supported_only} onChange={e => updateFilters({ supported_only: e.target.checked })} />仅看观测范围内</label></div>
      <div className="rw-candidate-layout"><section className="rw-catalog" aria-label="研究配方目录">
        <div className="rw-list-heading"><h2>候选设计假设</h2><span>{list ? `当前筛选 ${list.total} 个` : "正在筛选…"}</span></div>
        {!list ? <Loading /> : list.items.length === 0 ? <div className="rw-empty"><p>当前范围没有配方。</p><button className="rw-outline" onClick={() => updateFilters({ source: "", kind: "all", supported_only: true, q: "" })}>重置筛选</button></div> : <>
          <div className="rw-table-scroll"><table className="rw-table rw-catalog-table"><thead><tr><th>来源与级配</th><th>改动</th><th>油石比</th><th>查看</th></tr></thead><tbody>
            {list.items.map(row => <tr key={row.id} className={selected === row.id ? "rw-selected" : ""}><td>{row.source_code} · {row.gradation}<small>{row.product}{pinned.includes(row.id) ? " · 已手动加入" : ""}</small></td>
              <td>{row.change_label}<small>{row.within_observed_support ? "观测范围内，性能待测" : "观测范围外，需扩大核验"}</small></td><td className="rw-number">{number(row.oil_stone_ratio_pct)}%</td>
              <td><button className="rw-view" aria-label={`查看配方 ${row.source_code} ${row.id.slice(-6)}`} onClick={() => setSelected(row.id)}>查看</button></td></tr>)}
          </tbody></table></div><div className="rw-pagination"><button disabled={offset === 0} onClick={() => setOffset(Math.max(0, offset - 10))}>上一页</button>
            <span>{offset + 1}–{Math.min(offset + 10, list.total)} / {list.total}</span><button disabled={offset + 10 >= list.total} onClick={() => setOffset(offset + 10)}>下一页</button></div></>}
      </section><div>{detail && detail.summary.id === selected ? <Detail value={detail} pinned={pinned.includes(detail.summary.id)} toggle={togglePin} /> : selected ? <Loading /> : <div className="rw-detail rw-empty">选择配方后查看份额变化和性能依据。</div>}</div></div>
      <details className="rw-plan-section"><summary>后续试验安排（可选）</summary><div className="rw-section-heading"><div><h2><FlaskConical size={18} />保存可选试验计划</h2><p>本次创意交付无需开展实物试验。手动加入{pinned.length}种配方；当前筛选共{list?.total ?? "—"}种。</p></div>
        <a className="rw-outline" href={`${researchBase}/evidence/lab_handoff`}><Download size={15} />五配方送检参考</a></div>
        <div className="rw-plan-inputs"><label>计划名称<input value={title} maxLength={120} onChange={e => setTitle(e.target.value)} /></label><label>待测配方数量<input type="number" min={Math.max(1, pinned.length)} max={8} value={budget} onChange={e => setBudget(Math.max(1, pinned.length, Math.min(8, Number(e.target.value) || 1)))} /></label>
          <button className="rw-action" disabled={busy || !overview?.compatibility.matches || !list?.total || !title.trim()} onClick={() => void generate()}>{busy && <LoaderCircle className="spin" size={16} />}生成并保存计划</button></div>
        <p className="rw-explanation">这里安排的是配方数量。实际称料表、试件数、方法、费用和工期需另行确认；预测不作为达标依据。</p>
        {plan && <article className="rw-saved-plan" aria-label="已保存试验计划"><div className="rw-section-heading"><div><h3>{plan.title}</h3><p>{date(plan.created_at)} · 已保存{plan.selected_formulations}种配方 · 来源筛选：{plan.filters.source || "全部"}</p></div>
          <div className="rw-downloads"><a className="rw-outline" href={`${researchBase}/plans/${plan.id}/export.json`}><Download size={15} />导出保存内容</a>
            <a className="rw-outline" target="_blank" rel="noreferrer" href={`${researchBase}/plans/${plan.id}/print.html`}><ExternalLink size={15} />打印计划</a></div></div>
          <ol className="rw-plan-rows">{plan.formulations.map(f => <li key={f.summary.id}><strong>{f.summary.source_code} · {f.summary.gradation}</strong><span>{f.summary.change_label}</span><span className="rw-state">待确认、待实测</span></li>)}</ol>
          <p>{plan.selection_method}</p><details><summary>试验前需要确认的资料</summary><ol>{plan.required_before_testing.map(t => <li key={t}>{t}</li>)}</ol></details>
          <small className="rw-id">保存内容 SHA256：{plan.sha256}</small><p className="rw-explanation">这份保存内容对应生成时的筛选与研究证据。调整筛选后可生成另一份计划。</p>
        </article>}
      </details>
    </>}
    {tab === "experiments" && (!overview ? <Loading /> : <section className="rw-experiments"><h2>逐指标回退：接受多少预测，实际误差如何</h2>
      <p>{overview.latest_experiment.repeats}次分组、{overview.latest_experiment.outer_folds}个外层折，全部预测{overview.latest_experiment.exact_reproduction ? "逐值复现通过" : "尚未复核"}。MAE越低越好。</p>
      <ExperimentTable rows={overview.latest_experiment.rows} repeats={overview.latest_experiment.repeats} />
      <p className="rw-note">{overview.latest_experiment.note}训练内部证据不足时回退到均值；该规则不保证误差一定降低，也不提供工程放行。</p>
      <details><summary>查看各指标使用模型的比例</summary><ul>{overview.latest_experiment.rows.map(row => <li key={row.metric}>{row.label}：{number((row.head_acceptance_fraction || 0) * 100)}%的离折预测使用模型，其余使用训练标签均值。</li>)}</ul></details>
      <h2 className="rw-spaced">上一轮保守集成</h2><p>{overview.previous_experiment.note}</p><ExperimentTable rows={overview.previous_experiment.rows} repeats={overview.previous_experiment.repeats} />
      <h2 className="rw-spaced">复核资料</h2><div className="rw-evidence-links">{overview.evidence.filter(e => !["lab_print", "lab_handoff"].includes(e.id)).map(e => <a key={e.id} href={e.url}><Download size={14} />{e.title}</a>)}</div>
    </section>)}
    {tab === "audit" && (audit ? <AuditView audit={audit} /> : <Loading />)}
  </div>;
}
