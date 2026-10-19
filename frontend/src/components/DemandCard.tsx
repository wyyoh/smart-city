import { useEffect, useRef, useState } from "react";
import { ArrowRight, CheckCircle2, ClipboardList, LoaderCircle, TriangleAlert } from "lucide-react";
import { decisionApi } from "../decision-types";
import type { Demand, DemandRequest, MetricDefinition, Requirement, SceneProfile } from "../decision-types";

const sourceLabel: Record<string, string> = { enterprise_reference: "企业参考", constructed_demo: "构造演示", project_target: "项目自定", project_approved: "项目批准", normative: "适用规范" };
const choices: Record<string, [string, string][]> = {
  maintenance_method: [["hot_recycling", "热再生（演示）"], ["cold_recycling", "冷再生"], ["other", "其他工法，待建立规则"]],
  layer: [["surface", "表面层"], ["middle", "中面层"], ["base", "基层"]],
  structure_type: [["flexible", "柔性结构"], ["semi_rigid", "半刚性结构"]],
  climate: [["demo_hot", "高温分组（构造）"], ["demo_cold", "低温分组（构造）"], ["demo_wet", "多雨分组（构造）"]],
  traffic: [["demo_general", "一般交通（构造）"], ["demo_heavy", "重载交通（构造）"]],
  distress: [["rutting", "车辙"], ["thermal_cracking", "温缩裂缝"], ["water_damage", "水损害"], ["other_cracking", "其他开裂，机制待判定"]],
  severity: [["mild", "轻度"], ["moderate", "中度"], ["severe", "重度"]],
};

function Choice({ label, field, value, onChange }: { label: string; field: string; value: string | null; onChange: (value: string | null) => void }) {
  return <label>{label}<select value={value || ""} onChange={e => onChange(e.target.value || null)}><option value="">待确认</option>{choices[field].map(([code, text]) => <option key={code} value={code}>{text}</option>)}</select></label>;
}

export function DemandCard({ onConfirmed, onInvalidated }: { onConfirmed?: (demand: Demand) => void; onInvalidated?: () => void }) {
  const [profiles, setProfiles] = useState<SceneProfile[]>([]), [registry, setRegistry] = useState<Record<string, MetricDefinition>>({});
  const [input, setInput] = useState<DemandRequest | null>(null), [profileId, setProfileId] = useState("");
  const [resolution, setResolution] = useState<Demand | null>(null), [confirmed, setConfirmed] = useState<Demand | null>(null);
  const [busy, setBusy] = useState(false), [error, setError] = useState(""), [dirty, setDirty] = useState(false);
  const [engineer, setEngineer] = useState(""), [overrides, setOverrides] = useState<Record<string, { value: string; reason: string }>>({});
  const [projectMetric, setProjectMetric] = useState("DS"), [projectValue, setProjectValue] = useState(""), [projectReference, setProjectReference] = useState("");
  const revision = useRef(0), requestId = useRef(0);
  useEffect(() => {
    let live = true;
    Promise.all([decisionApi<{ profiles: SceneProfile[] }>("/scene-profiles"), decisionApi<{ metrics: Record<string, MetricDefinition> }>("/metric-registry")]).then(([p, r]) => {
      if (live) { setProfiles(p.profiles); setRegistry(r.metrics); setInput(structuredClone(p.profiles[0].example_request)); setProfileId(p.profiles[0].id); }
    }).catch(e => { if (live) setError(String(e)); });
    return () => { live = false; requestId.current++; };
  }, []);
  function edit(next: DemandRequest) { revision.current++; setInput(next); setDirty(true); setConfirmed(null); onInvalidated?.(); }
  function choose(profile: SceneProfile) { edit(structuredClone(profile.example_request)); setProfileId(profile.id); setResolution(null); setOverrides({}); setError(""); }
  async function resolve() {
    if (!input) return;
    const serial = ++requestId.current, startRevision = revision.current;
    setBusy(true); setError(""); setConfirmed(null); onInvalidated?.();
    try {
      const result = await decisionApi<Demand>("/demand-resolutions", input);
      if (serial === requestId.current) { setResolution(result); setDirty(revision.current !== startRevision); setOverrides({}); }
    } catch (e) { if (serial === requestId.current) setError(String(e)); }
    finally { if (serial === requestId.current) setBusy(false); }
  }
  async function confirm() {
    if (!resolution || dirty) return;
    const serial = ++requestId.current, startRevision = revision.current;
    setBusy(true); setError("");
    try {
      const changes = Object.entries(overrides).filter(([, change]) => change.value !== "");
      if (changes.some(([, change]) => !change.reason.trim())) throw new Error("覆盖目标必须填写理由");
      const result = await decisionApi<Demand>(`/demand-resolutions/${resolution.id}/confirm`, {
        expected_sha256: resolution.sha256, confirmed_by: engineer,
        overrides: changes.map(([id, change]) => {
          const target = resolution.targets.find(t => t.target_id === id)!;
          const { target_id: ignoredId, derived_by: ignoredRule, ...requirement } = target;
          void ignoredId; void ignoredRule;
          return { target_id: id, reason: change.reason, requirement: { ...requirement, value: registry[target.metric].value_type === "grade" ? change.value : Number(change.value), source: { kind: "project_target", reference: `工程师 ${engineer}：${change.reason}`, confirmed: false } } };
        }),
      });
      if (serial === requestId.current && startRevision === revision.current) { setConfirmed(result); onConfirmed?.(result); }
    } catch (e) { if (serial === requestId.current) setError(String(e)); }
    finally { if (serial === requestId.current) setBusy(false); }
  }
  function addProjectTarget() {
    if (!input || projectValue === "" || !projectReference.trim()) return;
    const metric = registry[projectMetric];
    const target: Requirement = { metric: projectMetric, value: metric.value_type === "grade" ? projectValue : Number(projectValue), operator: metric.value_type === "grade" ? "grade" : ">", unit: metric.unit, test_method: null, conditions: {}, comparison_basis: null, source: { kind: "project_target", reference: projectReference, confirmed: false } };
    edit({ ...input, project_targets: [...input.project_targets, target] }); setProjectValue("");
  }
  if (!input) return <div role="status" className="panel demand-loading">{error || "正在载入场景规则…"}{error && <button className="secondary" onClick={() => window.location.reload()}>重新加载</button>}</div>;
  const shown = confirmed || resolution;
  return <>
    <div className="page-heading"><div><h1>从养护场景开始选材</h1><p>先确认性能需求与适用口径，再比较材料，保留每一步的判断依据。</p></div><span className="scope-tag">{input.context_kind === "constructed_demo" ? "构造演示 · 工程适用待验证" : "正式项目要求 · 证据逐项核验"}</span></div>
    <div className="scene-profile-bar" aria-label="三类演示场景">{profiles.map((p, i) => <button className={profileId === p.id ? "active" : ""} key={p.id} onClick={() => choose(p)}><span>0{i + 1}</span>{p.title}<ArrowRight size={16} /></button>)}</div>
    <div className="demand-grid">
      <section className="panel demand-input"><div className="panel-heading"><h2><ClipboardList size={18} />01 场景条件</h2><span>输入</span></div><div className="demand-body">
        <label>方案名称<input value={input.name} onChange={e => edit({ ...input, name: e.target.value })} /></label>
        <label>使用范围<select value={input.context_kind} onChange={e => edit({ ...input, context_kind: e.target.value as DemandRequest["context_kind"], project_targets: [] })}><option value="constructed_demo">构造演示：使用有来源的演示规则</option><option value="project">正式项目：需提供项目要求</option></select></label>
        <div className="demand-fields"><Choice label="气候条件" field="climate" value={input.scene.climate.class} onChange={v => edit({ ...input, scene: { ...input.scene, climate: { class: v, source: "界面选择；待核实真实分区映射" } } })} /><Choice label="交通条件" field="traffic" value={input.scene.traffic.class} onChange={v => edit({ ...input, scene: { ...input.scene, traffic: { class: v, source: "界面选择；待核实真实交通映射" } } })} /><Choice label="主要病害" field="distress" value={input.scene.distress.type} onChange={v => edit({ ...input, scene: { ...input.scene, distress: { ...input.scene.distress, type: v } } })} /><Choice label="病害程度" field="severity" value={input.scene.distress.severity} onChange={v => edit({ ...input, scene: { ...input.scene, distress: { ...input.scene.distress, severity: v } } })} /></div>
        <details className="demand-details"><summary>工法、层位与来源</summary><div className="demand-fields"><Choice label="既定工法" field="maintenance_method" value={input.scene.maintenance_method} onChange={v => edit({ ...input, scene: { ...input.scene, maintenance_method: v } })} /><Choice label="层位" field="layer" value={input.scene.layer} onChange={v => edit({ ...input, scene: { ...input.scene, layer: v } })} /><Choice label="路面结构" field="structure_type" value={input.scene.structure_type} onChange={v => edit({ ...input, scene: { ...input.scene, structure_type: v } })} /></div><label>气候来源<input value={input.scene.climate.source || ""} onChange={e => edit({ ...input, scene: { ...input.scene, climate: { ...input.scene.climate, source: e.target.value || null } } })} /></label><label>交通来源<input value={input.scene.traffic.source || ""} onChange={e => edit({ ...input, scene: { ...input.scene, traffic: { ...input.scene.traffic, source: e.target.value || null } } })} /></label></details>
        <details className="demand-details"><summary>其他性能需求与项目自定目标</summary><div className="metric-requests">{Object.entries(registry).map(([m, def]) => <label key={m}><input type="checkbox" checked={input.requested_metrics.includes(m)} onChange={e => edit({ ...input, requested_metrics: e.target.checked ? [...input.requested_metrics, m] : input.requested_metrics.filter(x => x !== m) })} />{def.label}{!def.numeric_demo_supported && <small>能力待补充</small>}</label>)}</div>
          <label>项目目标指标<select value={projectMetric} onChange={e => setProjectMetric(e.target.value)}>{Object.entries(registry).map(([key, m]) => <option value={key} key={key}>{m.label}（{m.unit}）</option>)}</select></label><label>目标值（标量使用严格大于）<input value={projectValue} type={registry[projectMetric]?.value_type === "grade" ? "text" : "number"} onChange={e => setProjectValue(e.target.value)} /></label><label>要求出处<input value={projectReference} onChange={e => setProjectReference(e.target.value)} /></label><button className="secondary" disabled={!projectValue || !projectReference.trim()} onClick={addProjectTarget}>添加项目要求</button>
          {input.project_targets.map((t, i) => <p className="project-target" key={i}>{registry[t.metric]?.label} {t.operator} {t.value} {t.unit}<button aria-label={`删除项目目标${i + 1}`} onClick={() => edit({ ...input, project_targets: input.project_targets.filter((_, j) => j !== i) })}>移除</button></p>)}
        </details>
        <button className="primary demand-action" disabled={busy} onClick={() => void resolve()}>{busy ? <LoaderCircle size={16} className="spin" /> : <ArrowRight size={16} />}生成性能需求</button>
      </div></section>
      <section className="panel demand-output" aria-live="polite"><div className="panel-heading"><h2>02 性能需求卡</h2><span>{confirmed ? "已确认" : "待确认"}</span></div><div className="demand-body">
        {error && <div className="message error" role="alert"><TriangleAlert size={16} />{error}</div>}
        {dirty && resolution && <div className="message warning" role="status">场景已修改，以下是上次需求。请重新生成并确认。</div>}
        {!shown ? <div className="demand-empty"><ClipboardList size={36} /><h3>让场景生成有出处的需求</h3><p>选择左侧条件后生成需求。这里将展示命中规则、目标、来源和待确认项。</p><ol><li>核对气候、交通与病害</li><li>检查量化目标和试验口径</li><li>记录工程师确认与修改理由</li></ol></div> : <>
          {shown.rules.matches.map(rule => <div key={rule.id} className="rule-explanation"><strong>{rule.title}</strong><p>{rule.rationale}</p><small>{rule.id} · {rule.version}</small></div>)}
          <div className="demand-targets">{shown.targets.map(t => <article key={t.target_id} className="demand-target"><div><h3>{registry[t.metric]?.label || t.metric}<small>{sourceLabel[t.source.kind]}</small></h3><strong>{t.operator} {t.value}{t.operator === "between" ? ` 至 ${t.upper}` : ""}<small>{t.unit}</small></strong></div><p>{t.source.reference}</p><small>方法：{t.test_method || "待确认"} · 条件：{Object.keys(t.conditions).length ? JSON.stringify(t.conditions) : "待确认"}</small>
            {!confirmed && <details><summary>工程师覆盖此目标</summary><div className="demand-fields"><label>替代值<input type={registry[t.metric]?.value_type === "grade" ? "text" : "number"} value={overrides[t.target_id]?.value ?? ""} onChange={e => setOverrides({ ...overrides, [t.target_id]: { value: e.target.value, reason: overrides[t.target_id]?.reason || "" } })} placeholder={String(t.value)} /></label><label>修改理由<input value={overrides[t.target_id]?.reason || ""} onChange={e => setOverrides({ ...overrides, [t.target_id]: { value: overrides[t.target_id]?.value || "", reason: e.target.value } })} /></label></div></details>}
          </article>)}</div>
          {shown.open_items.map((item, i) => <p className="demand-open" key={i}>待补充 · {item.message}</p>)}{shown.conflicts.map((item, i) => <p className="demand-open conflict" key={i}>目标冲突 · {item.message}</p>)}{shown.capability_gaps.map(item => <p className="demand-open" key={item.metric}>能力缺口 · {registry[item.metric]?.label}：{item.message}</p>)}
          <details className="demand-details"><summary>适用边界与版本 · {shown.rules.version}</summary>{shown.warnings.map(w => <p key={w}>{w}</p>)}<p className="mono">快照 {shown.sha256.slice(0, 16)}</p></details>
          {confirmed ? <div className="confirmation-receipt"><CheckCircle2 size={19} /><div><strong>{confirmed.confirmed_by} 已记录确认</strong><p>{confirmed.requirements_complete ? "需求已确认，可进入候选检索。" : "仍有未解决项，候选生成等待补齐。"}</p>{confirmed.overrides?.map(change => <p key={change.target_id}>覆盖 {change.before.value} → {change.after.value}：{change.reason}</p>)}</div></div> : <div className="confirm-row"><label>确认人<input value={engineer} onChange={e => setEngineer(e.target.value)} placeholder="填写姓名或自测身份" /></label><button className="primary" disabled={busy || dirty || !engineer.trim()} onClick={() => void confirm()}>确认需求<CheckCircle2 size={16} /></button></div>}
        </>}
      </div></section>
    </div>
  </>;
}
