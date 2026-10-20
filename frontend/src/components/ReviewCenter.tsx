import { useEffect, useRef, useState } from "react";
import {
  ArrowRight,
  BookOpen,
  Check,
  Download,
  ExternalLink,
  FileCheck2,
  LoaderCircle,
  Route,
  ShieldCheck,
} from "lucide-react";
import { decisionApi } from "../decision-types";
import type {
  Highlight,
  ReviewOverview,
  ReviewRequirement,
} from "../review-types";
import { saveJson } from "../review-types";
import { DecisionReviewPanel } from "./DecisionReviewPanel";

function CoverageTable({
  items,
  overview,
}: {
  items: ReviewRequirement[];
  overview: ReviewOverview;
}) {
  return (
    <div className="table-scroll">
      <table className="coverage-table">
        <thead>
          <tr>
            <th>赛题要求</th>
            <th>当前完成范围</th>
            <th>可复查证据</th>
          </tr>
        </thead>
        <tbody>
          {items.map((r) => (
            <tr key={r.id}>
              <td>
                <strong>{r.title}</strong>
                <small>赛题PDF第{r.source_page}页</small>
              </td>
              <td>
                <span className={`coverage-state ${r.status}`}>
                  {r.status_label}
                </span>
                <p>{r.delivered_scope}</p>
              </td>
              <td>
                {r.evidence_ids.map((id) => {
                  const ev = overview.evidence[id];
                  return (
                    <div key={id} className="coverage-evidence">
                      {ev.download_url ? (
                        <a href={ev.download_url} download>
                          {ev.label}
                          <Download size={12} />
                        </a>
                      ) : (
                        <span>{ev.label}</span>
                      )}
                      <small
                        className={
                          ev.integrity === "verified"
                            ? "evidence-ok"
                            : "evidence-changed"
                        }
                      >
                        {ev.integrity === "verified"
                          ? "指纹相符"
                          : ev.integrity === "changed"
                            ? "文件已变，需重建索引"
                            : "文件缺失"}
                      </small>
                    </div>
                  );
                })}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

export function ReviewCenter({
  onStartTour,
}: {
  onStartTour: (tour: Highlight) => void;
}) {
  const [overview, setOverview] = useState<ReviewOverview | null>(null);
  const [error, setError] = useState("");
  const [retry, setRetry] = useState(0);
  const [tab, setTab] = useState("coverage");
  const [history, setHistory] = useState<
    { id: string; name: string; created_at: string }[]
  >([]);
  const [decisionId, setDecisionId] = useState("");
  const [reviewId, setReviewId] = useState("");
  const [templateText, setTemplateText] = useState("");
  const [validation, setValidation] = useState<{
    schema_valid: boolean;
    collection_complete: boolean;
    authenticity_verified: boolean;
    human_participants: number | null;
    issues: { field: string; message: string }[];
    note: string;
  } | null>(null);
  const [checking, setChecking] = useState(false);
  const validationSerial = useRef(0);
  useEffect(() => {
    let live = true;
    setError("");
    Promise.all([
      decisionApi<ReviewOverview>("/review/overview"),
      decisionApi<typeof history>("/decisions"),
    ])
      .then(([o, h]) => {
        if (live) {
          setOverview(o);
          setHistory(h);
          setDecisionId(h[0]?.id || "");
        }
      })
      .catch((e) => {
        if (live) setError(String(e));
      });
    return () => {
      live = false;
      validationSerial.current++;
    };
  }, [retry]);
  async function downloadTemplate() {
    try {
      saveJson(
        await decisionApi("/review/validation-template"),
        "数智选材_外部核验空白模板.json",
      );
    } catch (e) {
      setError(String(e));
    }
  }
  async function validate() {
    const serial = ++validationSerial.current;
    setChecking(true);
    setValidation(null);
    setError("");
    try {
      const data = JSON.parse(templateText);
      if (!data || typeof data !== "object" || Array.isArray(data))
        throw new Error("请输入一个JSON对象");
      const result = await decisionApi<NonNullable<typeof validation>>(
        "/review/validate-input",
        data,
      );
      if (serial === validationSerial.current) setValidation(result);
    } catch (e) {
      if (serial === validationSerial.current)
        setError(e instanceof SyntaxError ? "JSON格式有误，请检查引号、逗号和括号后重试。" : String(e));
    } finally {
      if (serial === validationSerial.current) setChecking(false);
    }
  }
  if (!overview)
    return (
      <div className="panel review-loading" role="status">
        {error || (
          <>
            <LoaderCircle size={22} className="spin" />
            正在核对成果与证据…
          </>
        )}
        {error && (
          <button className="secondary" onClick={() => setRetry((r) => r + 1)}>
            重新加载
          </button>
        )}
      </div>
    );
  return (
    <div className="review-center">
      <section className="review-intro">
        <div className="review-intro-copy">
          <div className="review-topic">
            <ShieldCheck size={17} />
            企业课题一
          </div>
          <h1>成果与验证</h1>
          <p>从养护需求生成可解释的材料设计方案，支持多目标权衡与人工微调。</p>
          <small>
            {overview.submission_scope?.summary || "v0.4 本地研究原型。软件验证、计算研究与工程实证分别登记。"}
          </small>
          <a
            className="secondary"
            href="/v2/review/handbook.html"
            target="_blank"
            rel="noreferrer"
          >
            <BookOpen size={16} />
            打开评审手册
          </a>
        </div>
        <div className="review-chain" aria-label="选材证据链">
          {["养护场景", "性能要求", "材料方案", "证据复核", "验证行动"].map(
            (name, i) => (
              <div key={name}>
                <span>{name}</span>
                {i < 4 && <ArrowRight size={16} />}
              </div>
            ),
          )}
          <p>未知条件保留，工程适用逐项核验。</p>
        </div>
      </section>
      <div className="review-data-strip">
        <span>
          <strong>{overview.current_data.historical_keys}</strong> 历史操作键
        </span>
        <span>
          <strong>{overview.current_data.ac13_keys}</strong> AC-13历史目录
        </span>
        <span>
          <strong>
            {overview.current_data.complete_four_metric_ac13_keys}
          </strong>{" "}
          四指标完整记录
        </span>
        <small>
          {overview.current_data.identity_note}
          {overview.current_data.variants > 0 &&
            ` 另有${overview.current_data.variants}条待试验微调版本。`}
        </small>
      </div>
      {error && (
        <div className="message error" role="alert">
          {error}
          <button className="secondary" onClick={() => setError("")}>
            关闭
          </button>
        </div>
      )}
      <section className="review-highlight-section">
        <div className="review-section-title">
          <h2>三项创意机制，交互演示</h2>
          <span>载入构造案例后，逐步操作真实流程</span>
        </div>
        <div className="review-highlights">
          {overview.highlights.map((h) => (
            <article key={h.id} className={`review-highlight ${h.id}`}>
              <Route size={22} />
              <h3>{h.title}</h3>
              <p>{h.question}</p>
              <small>{h.mechanism}</small>
              <button
                className="review-tour-button"
                onClick={() => onStartTour(h)}
              >
                开始{h.case_id}演示
                <ArrowRight size={16} />
              </button>
            </article>
          ))}
        </div>
      </section>
      <section className="panel review-coverage">
        <div className="review-tabs" role="tablist" aria-label="成果核验分类">
          {[
            ["coverage", "赛题成果"],
            ["sources", "依据与阈值"],
            ["external", "工程化拓展"],
          ].map(([id, label]) => (
            <button
              key={id}
              id={`review-tab-${id}`}
              role="tab"
              aria-selected={tab === id}
              aria-controls={`review-panel-${id}`}
              onClick={() => setTab(id)}
            >
              {label}
            </button>
          ))}
        </div>
        <div
          role="tabpanel"
          id={`review-panel-${tab}`}
          aria-labelledby={`review-tab-${tab}`}
        >
          {tab === "coverage" && (
            <>
              <div className="review-section-title">
                <h2>五项基本成果</h2>
                <small>状态为团队证据登记，不代表官方验收</small>
              </div>
              <CoverageTable
                items={overview.requirements.filter((r) => r.kind === "basic")}
                overview={overview}
              />
              <details className="review-more">
                <summary>展开十项技术要求及当前范围</summary>
                <CoverageTable
                  items={overview.requirements.filter(
                    (r) => r.kind === "technical_detail",
                  )}
                  overview={overview}
                />
              </details>
              <details className="review-more">
                <summary>展开七项可选加分方向</summary>
                <CoverageTable
                  items={overview.requirements.filter(
                    (r) => r.kind === "bonus",
                  )}
                  overview={overview}
                />
              </details>
            </>
          )}
          {tab === "sources" && (
            <div className="review-source-section">
              <h2>依据版本与量化阈值分别核验</h2>
              <p>
                企业参考值与团队强化阈值已明确标注。正式项目需提供采用文件、条款、方法、条件及批准依据。
              </p>
              {overview.sources.map((s) => (
                <article key={s.id}>
                  <div>
                    <h3>{s.standard}</h3>
                    <span>{s.type}</span>
                  </div>
                  <p>
                    公告落款 {s.notice_date}；页面公开 {s.page_publication_date}
                    ；施行 {s.effective_date}。
                  </p>
                  <p>{s.verification_scope}</p>
                  <a href={s.url} target="_blank" rel="noreferrer">
                    查看交通运输部公告
                    <ExternalLink size={13} />
                  </a>
                </article>
              ))}
              <div className="review-reference-note">
                版本信息于2026年10月19日核对。公告登记不把历史数据转换为新规程试验，也不授权构造阈值用于正式项目。
              </div>
            </div>
          )}
          {tab === "external" && (
            <div className="review-external">
              <div>
                <h2>后续工程化拓展（可选）</h2>
                <p>
                  {overview.submission_scope?.engineering_extension_note || "后续工程使用可通过统一模板采集真实记录，再审核适用性。"}
                </p>
                <ul>
                  {overview.external_pending.map((item) => (
                    <li key={item}>
                      <Check size={15} />
                      {item}
                    </li>
                  ))}
                </ul>
                <button
                  className="secondary"
                  onClick={() => void downloadTemplate()}
                >
                  <Download size={16} />
                  下载空白核验模板
                </button>
              </div>
              <div>
                <label htmlFor="external-validation-json">
                  粘贴填写后的JSON，检查字段与时间逻辑
                </label>
                <textarea
                  id="external-validation-json"
                  rows={7}
                  spellCheck={false}
                  value={templateText}
                  onChange={(event) => {
                    validationSerial.current++;
                    setChecking(false);
                    setValidation(null);
                    setTemplateText(event.target.value);
                  }}
                  placeholder="下载模板后填写真实记录，再粘贴到这里"
                />
                <button
                  className="secondary"
                  disabled={!templateText.trim() || checking}
                  onClick={() => void validate()}
                >
                  {checking ? (
                    <LoaderCircle size={15} className="spin" />
                  ) : (
                    <FileCheck2 size={15} />
                  )}
                  检查核验记录
                </button>
                {validation && (
                  <div className="review-validation-result" role="status">
                    <strong>
                      {validation.schema_valid
                        ? "字段结构通过"
                        : "字段结构未通过"}
                      ；
                      {validation.collection_complete
                        ? "采集字段完整，真实性待审核"
                        : "采集记录待补齐"}
                    </strong>
                    <p>
                      输入记录中的真人参与数：
                      {validation.human_participants ?? "无法计算"}
                    </p>
                    <ul>
                      {validation.issues.slice(0, 8).map((issue, i) => (
                        <li key={i}>
                          {issue.message}
                          <small>{issue.field}</small>
                        </li>
                      ))}
                    </ul>
                    {validation.issues.length > 8 && (
                      <small>
                        共{validation.issues.length}个待补字段，显示前8项。
                      </small>
                    )}
                    <p>{validation.note}</p>
                  </div>
                )}
              </div>
            </div>
          )}
        </div>
      </section>
      <section className="panel review-existing">
        <div>
          <h2>复核已有决策</h2>
          <p>保存一份绑定原决策的复核单，再导出相同内容。</p>
        </div>
        <label>
          已保存决策
          <select
            value={decisionId}
            onChange={(event) => setDecisionId(event.target.value)}
          >
            <option value="">尚无可选决策</option>
            {history.map((h) => (
              <option key={h.id} value={h.id}>
                {h.name} · {new Date(h.created_at).toLocaleString("zh-CN")}
              </option>
            ))}
          </select>
        </label>
        <button
          className="primary"
          disabled={!decisionId}
          onClick={() => setReviewId(decisionId)}
        >
          <FileCheck2 size={16} />
          生成选材复核单
        </button>
      </section>
      {reviewId && (
        <DecisionReviewPanel
          key={reviewId}
          decisionId={reviewId}
          onClose={() => setReviewId("")}
        />
      )}
      <details className="panel review-questions">
        <summary>答辩常见问题与回答依据</summary>
        {overview.questions.map((q) => (
          <article key={q.question}>
            <h3>{q.question}</h3>
            <p>{q.answer}</p>
          </article>
        ))}
      </details>
    </div>
  );
}
