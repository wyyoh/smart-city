
  (() => {
    const root = document.getElementById('asphalt-scenario-explorer');
    const data = JSON.parse(root.querySelector('#asphalt-inline-data').textContent);
    const select = root.querySelector('#asphalt-case');
    const rows = root.querySelector('#asphalt-candidates');
    const targets = root.querySelector('#asphalt-targets');
    const result = root.querySelector('#asphalt-result');
    const evidence = root.querySelector('#asphalt-evidence');
    const assumption = root.querySelector('#asphalt-assumption');
    const labels = {DS:'动稳定度',strain:'最大弯拉应变',TSR:'冻融劈裂强度比',residual:'残留稳定度比',RAP:'名义 RAP 比例'};
    const units = {DS:'次/mm',strain:'με',TSR:'%',residual:'%'};
    const candidates = Object.fromEntries(data.candidates.map(c => [c.id,c]));
    const escape = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
    const fmt = (value,digits=1) => value == null ? '缺测' : Number(value).toLocaleString('zh-CN',{maximumFractionDigits:digits});
    let caseId = 'C1';
    let candidateId = 'R1';
    for (const c of data.cases) {
      const option = document.createElement('option'); option.value=c.id; option.textContent=c.title; select.append(option);
    }
    function restore(state) {
      if (state && data.cases.some(c => c.id===state.caseId)) caseId=state.caseId;
      const current=data.cases.find(c => c.id===caseId);
      candidateId = state && current.candidate_ids.includes(state.candidateId) ? state.candidateId : current.candidate_ids[0];
    }
    function persist() {
      if (window.openai?.setWidgetState) window.openai.setWidgetState({modelContent:{caseId,candidateId},privateContent:null}).catch(()=>{});
    }
    function evaluate(candidate, scene) {
      const failed=Object.entries(scene.targets).filter(([metric,target])=>candidate.metrics[metric]!=null && candidate.metrics[metric]<=target).map(([metric])=>metric);
      const missing=Object.keys(scene.targets).filter(metric=>candidate.metrics[metric]==null);
      if(candidate.rap_nominal_pct<scene.rap_min_pct) failed.push('RAP');
      return {failed,missing,pass:failed.length===0&&missing.length===0};
    }
    function render() {
      const scene=data.cases.find(c=>c.id===caseId); select.value=caseId;
      const evaluated=scene.candidate_ids.map(id=>({c:candidates[id],e:evaluate(candidates[id],scene)}));
      const passing=evaluated.filter(x=>x.e.pass);
      result.textContent=passing.length ? `${passing.length} 个历史候选满足演示目标，待试验核验` : '当前候选均未满足全部演示目标';
      targets.textContent=Object.entries(scene.targets).map(([metric,target])=>`${labels[metric]} > ${fmt(target)} ${units[metric]}`).join('　');
      if(scene.rap_min_pct) targets.textContent+=`　名义 RAP ≥ ${scene.rap_min_pct}%`;
      rows.innerHTML=evaluated.map(({c,e})=>`<tr class="${c.id===candidateId?'asphalt-selected':''}"><td><button type="button" class="btn btn-ghost" data-candidate="${c.id}" aria-pressed="${c.id===candidateId}">${escape(c.source+' · '+c.product)}</button><div class="text-small">${escape(c.gradation)}</div></td>${Object.keys(scene.targets).map(metric=>`<td class="text-end ${e.failed.includes(metric)?'text-destructive':''}">${fmt(c.metrics[metric],metric==='DS'||metric==='strain'?0:2)}</td>`).join('')}<td class="text-end ${e.failed.includes('RAP')?'text-destructive':''}">${fmt(c.rap_nominal_pct)}</td><td>${e.pass?'待核验':e.failed.length?'未满足':'待补测'}</td></tr>`).join('');
      for(const button of rows.querySelectorAll('button')) button.addEventListener('click',()=>{candidateId=button.dataset.candidate;render();persist();});
      const c=candidates[candidateId], status=evaluate(c,scene);
      const keyMetrics=Object.keys(scene.targets);
      evidence.innerHTML=`<div class="asphalt-detail"><span>${escape(c.source+' · '+c.gradation+' · '+c.product)}</span><span class="tabular-nums">油石比 ${fmt(c.oil_stone_ratio_pct)}%</span></div><div class="asphalt-evidence-grid">${keyMetrics.map(metric=>{const range=c.metric_ranges[metric],ref=c.references[metric];return `<div><span>${labels[metric]}　<span class="tabular-nums">${fmt(c.metrics[metric],2)} ${units[metric]}</span></span><div class="text-small text-muted asphalt-range">记录极差 ${range?fmt(range[0],2)+'–'+fmt(range[1],2):'缺测'} · ${ref?ref.n_recorded:0} 条记录</div></div>`;}).join('')}</div><div class="text-small" style="margin-top:12px">${status.failed.length?'未满足：'+status.failed.map(x=>labels[x]).join('、'):keyMetrics.some(metric=>c.metric_ranges[metric]?.[0]<=scene.targets[metric])?'部分试件记录低于目标，建议复核相关试验。':'按历史聚合值进入候选复核。'}</div><details style="margin-top:12px"><summary class="cursor-interaction">原表依据与核验事项</summary><div class="text-small asphalt-reference">${keyMetrics.map(metric=>{const r=c.references[metric];return `<div>${labels[metric]}：${r?escape(r.sheet)+' 第 '+r.rows.join('、')+' 行':'无对应记录'}</div>`;}).join('')}<div style="margin-top:8px">${c.notes.map(escape).join(' ')}</div><div>极差描述现有记录，不是预测区间。记录条数不等于独立批次数。</div></div></details>`;
      assumption.textContent=scene.provenance;
      root.dataset.caseId=caseId;
      root.dataset.passingIds=passing.map(x=>x.c.id).join(',');
    }
    restore(window.openai?.widgetState?.modelContent);
    render();
    select.addEventListener('change',()=>{caseId=select.value;candidateId=data.cases.find(c=>c.id===caseId).candidate_ids[0];render();persist();});
    window.addEventListener('openai:set_globals',event=>{if(event.detail?.globals?.widgetState){restore(event.detail.globals.widgetState.modelContent);render();}});
  })();
  