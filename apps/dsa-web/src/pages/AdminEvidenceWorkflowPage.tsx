import type React from 'react';
import {
  Archive,
  BookOpenCheck,
  CheckCircle2,
  ClipboardCheck,
  Code2,
  FileCheck2,
  Layers3,
  LockKeyhole,
  Route,
  ShieldCheck,
  TerminalSquare,
  TriangleAlert,
} from 'lucide-react';
import { Badge, GlassCard } from '../components/common';
import { cn } from '../utils/cn';

type Tone = 'info' | 'warn' | 'danger' | 'good';
type CommandSnippet = {
  label: string;
  note: string;
  command: string;
};
type RunbookReference = {
  label: string;
  docLabel: string;
  stage: string;
  icon: React.ComponentType<{ className?: string }>;
};

const workflowSteps = [
  { label: '本地工作区', note: '忽略目录' },
  { label: '生成模板', note: '空白模板' },
  { label: '脱敏填写', note: '人工录入' },
  { label: 'preflight', note: '本地预检' },
  { label: 'manifest / bundle / archive', note: '校验归档' },
  { label: '人工复核', note: '外部复核' },
];

const statusCards: Array<{ label: string; value: string; tone: Tone; icon: React.ComponentType<{ className?: string }> }> = [
  { label: '复核入口', value: 'GO-REVIEW-REQUIRED', tone: 'warn', icon: ShieldCheck },
  { label: '缺证据状态', value: 'NO-GO when evidence missing', tone: 'danger', icon: TriangleAlert },
  { label: '人工门禁', value: 'manual review required', tone: 'info', icon: LockKeyhole },
  { label: '发布字段', value: 'releaseApproved=false', tone: 'good', icon: CheckCircle2 },
];

const commandSnippets: CommandSnippet[] = [
  {
    label: '模板生成',
    note: '生成空白脱敏模板，不包含真实目录或凭据。',
    command: 'python3 scripts/operator_evidence_workflow_run.py init --output-dir <templates-dir>',
  },
  {
    label: '证据检查',
    note: '读取已脱敏证据目录，输出校验摘要和复核材料。',
    command: 'python3 scripts/operator_evidence_workflow_run.py check --artifact-dir <sanitized-evidence-dir> --output-dir <review-output-dir>',
  },
  {
    label: '报告渲染',
    note: '从脱敏 bundle 摘要渲染人工复核 Markdown。',
    command: 'python3 scripts/operator_evidence_workflow_run.py report --bundle-summary <review-output-dir>/bundle-summary.json --output <review-output-dir>/release-review-report.md',
  },
];

const localWorkspaceGuards = [
  { label: '本地证据草稿', value: '<local-evidence-draft>' },
  { label: '脱敏输出目录', value: '<sanitized-evidence-output>' },
  { label: '复核归档目录', value: '<review-archive-output>' },
  { label: '本机忽略规则', value: '<gitignored-local-workspace>' },
];

const runbookReferences: RunbookReference[] = [
  {
    label: 'Dry-run 交接',
    docLabel: 'docs/audits/operator-evidence-dry-run-handoff.md',
    stage: '合成演练材料',
    icon: Route,
  },
  {
    label: '脱敏清单',
    docLabel: 'docs/audits/operator-evidence-redaction-checklist.md',
    stage: '交接前检查',
    icon: ClipboardCheck,
  },
  {
    label: 'Schema 参考',
    docLabel: 'docs/audits/operator-evidence-schema-reference-guide.md',
    stage: '本地字段说明',
    icon: BookOpenCheck,
  },
  {
    label: '归档包',
    docLabel: 'docs/audits/operator-evidence-archive-pack-guide.md',
    stage: '复核目录索引',
    icon: Archive,
  },
  {
    label: 'CLI 合约 / 预检',
    docLabel: 'docs/audits/operator-evidence-workflow-runner-guide.md',
    stage: '离线 runner',
    icon: TerminalSquare,
  },
];

const schemaReferenceGroups = [
  {
    label: '数据源 Provider',
    artifact: 'provider_operator_evidence.json',
    validator: 'provider_operator_evidence_check.py',
  },
  {
    label: '恢复 / PITR',
    artifact: 'restore_pitr_operator_evidence.json',
    validator: 'restore_pitr_operator_evidence_check.py',
  },
  {
    label: '安全验收',
    artifact: 'security_operator_acceptance.json',
    validator: 'security_operator_acceptance_check.py',
  },
  {
    label: '配额预算',
    artifact: 'quota_budget_operator_evidence.json',
    validator: 'quota_operator_evidence_check.py',
  },
  {
    label: '预发入口',
    artifact: 'staging_ingress_operator_evidence.json',
    validator: 'staging_ingress_operator_evidence_check.py',
  },
  {
    label: 'WS2 SSE 决策',
    artifact: 'ws2_sse_operator_decision_evidence.json',
    validator: 'ws2_sse_operator_decision_check.py',
  },
  {
    label: '配置快照',
    artifact: 'config_snapshot_evidence.json',
    validator: 'config_snapshot_evidence_check.py',
  },
  {
    label: '人工发布复核',
    artifact: 'manual_release_approval_review_record.json',
    validator: 'manual_release_approval_evidence_check.py',
  },
];

function toneClass(tone: Tone): string {
  return {
    info: 'border-cyan-300/20 bg-cyan-400/8 text-cyan-100',
    warn: 'border-amber-300/25 bg-amber-400/10 text-amber-100',
    danger: 'border-rose-300/28 bg-rose-500/10 text-rose-100',
    good: 'border-emerald-300/22 bg-emerald-400/10 text-emerald-100',
  }[tone];
}

const AdminEvidenceWorkflowPage: React.FC = () => (
  <div
    data-testid="admin-evidence-workflow-page"
    className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar bg-[#050505] px-4 py-5 text-white md:px-6 xl:px-8"
  >
    <div className="mx-auto flex w-full max-w-[1600px] flex-col gap-5">
      <header className="rounded-[24px] border border-white/5 bg-white/[0.02] px-4 py-5 backdrop-blur-md md:px-6">
        <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
          <div className="min-w-0">
            <p className="text-[10px] font-bold uppercase tracking-[0.24em] text-cyan-200/70">ADMIN EVIDENCE REVIEW</p>
            <h1 className="mt-3 text-2xl font-semibold tracking-normal text-white md:text-3xl">证据工作流复核</h1>
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/58">离线证据复核总览，只读、脱敏、人工门禁。</p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info" className="border-cyan-300/20 bg-cyan-400/8 text-cyan-100">只读视图</Badge>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">脱敏状态</Badge>
            <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">人工门禁</Badge>
          </div>
        </div>
        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-3">
          {[
            ['页面用途', '复核脱敏证据路径', '模板、校验、归档、人工复核'],
            ['当前状态', '等待人工复核', '缺证据时保持 NO-GO'],
            ['下一步', '按本地 runbook 生成复核材料', '先确认交接状态；命令、Schema、参考文档默认折叠'],
          ].map(([label, value, note]) => (
            <div key={label} className="min-w-0 rounded-2xl border border-white/5 bg-black/20 px-4 py-3">
              <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">{label}</p>
              <p className="mt-2 text-sm font-semibold text-white">{value}</p>
              <p className="mt-1 text-xs leading-5 text-white/42">{note}</p>
            </div>
          ))}
        </div>
      </header>

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
        <GlassCard as="section" className="p-4 md:p-5 xl:col-span-8">
          <div className="flex items-start gap-3">
            <Layers3 className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">离线序列</p>
              <h2 className="mt-1 text-lg font-semibold text-white">操作员证据路径</h2>
            </div>
          </div>
          <div
            data-testid="admin-evidence-workflow-grid"
            className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-6"
          >
            {workflowSteps.map((step, index) => (
              <article
                key={step.label}
                className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5"
              >
                <p className="font-mono text-[11px] text-white/36">{String(index + 1).padStart(2, '0')}</p>
                <h3 className="mt-2 min-h-10 text-sm font-semibold leading-5 text-white/86">{step.label}</h3>
                <p className="mt-2 text-xs leading-5 text-white/42">{step.note}</p>
              </article>
            ))}
          </div>
        </GlassCard>

        <div className="grid grid-cols-1 gap-4 xl:col-span-4">
          <GlassCard as="section" className="p-4 md:p-5">
            <div className="flex items-start gap-3">
              <FileCheck2 className="mt-1 h-4 w-4 text-emerald-200" aria-hidden="true" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">能力边界</p>
                <h2 className="mt-1 text-lg font-semibold text-white">页面不执行动作</h2>
              </div>
            </div>
            <div className="mt-5 space-y-3 text-sm leading-6 text-white/58">
              <p>不提供上传入口，不调用后端写接口，不变更运行时配置。</p>
              <p>不读取原始 artifact 内容，不展示 provider 载荷、schema 细节或调试字段。</p>
            </div>
          </GlassCard>

          <GlassCard
            as="section"
            data-testid="admin-evidence-local-workspace-guard"
            className="p-4 md:p-5"
          >
            <div className="flex items-start gap-3">
              <LockKeyhole className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
              <div>
                <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">LOCAL GUARD</p>
                <h2 className="mt-1 text-lg font-semibold text-white">本地目录保护</h2>
              </div>
            </div>
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {localWorkspaceGuards.map((guard) => (
                <div
                  key={guard.label}
                  className="min-w-0 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-2"
                >
                  <p className="text-[11px] font-medium text-white/72">{guard.label}</p>
                  <p className="mt-1 break-words font-mono text-[11px] text-cyan-100/66">{guard.value}</p>
                </div>
              ))}
            </div>
          </GlassCard>
        </div>
      </section>

      <section
        data-testid="admin-evidence-status-grid"
        className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        aria-label="静态复核状态"
      >
        {statusCards.map(({ label, value, tone, icon: Icon }) => (
          <GlassCard key={value} as="article" className="p-4" aria-label={`${label}：${value}`}>
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/34">{label}</p>
                <p className="mt-3 break-words font-mono text-sm font-semibold text-white">{value}</p>
              </div>
              <span className={cn('inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border', toneClass(tone))}>
                <Icon className="h-4 w-4" aria-hidden="true" />
              </span>
            </div>
          </GlassCard>
        ))}
      </section>

      <details className="rounded-[20px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/76 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
          <span>二级细节：Runbook 参考</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">默认折叠</span>
        </summary>
      <GlassCard
        as="section"
        data-testid="admin-evidence-runbook-references"
        className="mt-4 p-4 md:p-5"
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <BookOpenCheck className="mt-1 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">本地 Runbook</p>
              <h2 className="mt-1 text-lg font-semibold text-white">操作员工作流参考</h2>
            </div>
          </div>
          <Badge variant="default" className="w-fit border-white/10 bg-white/[0.04] text-white/62">
            静态标签
          </Badge>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-5">
          {runbookReferences.map(({ label, docLabel, stage, icon: Icon }) => (
            <article
              key={docLabel}
              className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5"
              aria-label={`${label}：${docLabel}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">参考卡</p>
                  <h3 className="mt-2 text-sm font-semibold leading-5 text-white/88">{label}</h3>
                </div>
                <span className="inline-flex h-9 w-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/15 bg-cyan-400/8 text-cyan-100">
                  <Icon className="h-4 w-4" aria-hidden="true" />
                </span>
              </div>
              <p className="mt-4 rounded-xl border border-white/[0.04] bg-white/[0.02] px-2.5 py-2 font-mono text-[11px] leading-5 text-cyan-100/78 break-all">
                {docLabel}
              </p>
              <p className="mt-3 text-xs leading-5 text-white/44">{stage}</p>
            </article>
          ))}
        </div>
      </GlassCard>
      </details>

      <details className="rounded-[20px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/76 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
          <span>二级细节：Schema 与字段参考</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">默认折叠</span>
        </summary>
      <GlassCard
        as="section"
        data-testid="admin-evidence-schema-reference"
        className="mt-4 p-4 md:p-5"
      >
        <div className="flex flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
          <div className="flex min-w-0 items-start gap-3">
            <FileCheck2 className="mt-1 h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">本地参考</p>
              <h2 className="mt-1 text-lg font-semibold text-white">离线证据 Schema 参考</h2>
            </div>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">人工复核必需</Badge>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">只读字段</Badge>
          </div>
        </div>

        <div className="mt-5 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-4">
          {schemaReferenceGroups.map((group) => (
            <article
              key={group.artifact}
              className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5"
              aria-label={`${group.label}：${group.artifact}`}
            >
              <div className="flex items-start justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">证据类别</p>
                  <h3 className="mt-2 text-sm font-semibold leading-5 text-white/88">{group.label}</h3>
                </div>
                <span className="shrink-0 rounded-full border border-cyan-300/15 bg-cyan-400/8 px-2 py-1 text-[10px] font-medium text-cyan-100">
                  本地校验
                </span>
              </div>
              <dl className="mt-4 space-y-3 text-xs leading-5">
                <div>
                  <dt className="text-white/34">预期 artifact</dt>
                  <dd className="mt-1 break-all font-mono text-white/74">{group.artifact}</dd>
                </div>
                <div>
                  <dt className="text-white/34">validator / review stage</dt>
                  <dd className="mt-1 break-all font-mono text-cyan-100/78">{group.validator}</dd>
                </div>
                <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-1 2xl:grid-cols-2">
                  <span className="rounded-xl border border-white/[0.04] bg-white/[0.02] px-2.5 py-2 font-mono text-[11px] text-amber-100/86">
                    manual review required
                  </span>
                  <span className="rounded-xl border border-white/[0.04] bg-white/[0.02] px-2.5 py-2 font-mono text-[11px] text-emerald-100/84">
                    releaseApproved=false
                  </span>
                </div>
              </dl>
            </article>
          ))}
        </div>

        <details
          data-testid="admin-evidence-schema-notes"
          className="mt-4 rounded-2xl border border-white/[0.04] bg-white/[0.02] px-3 py-2.5 [&>summary::-webkit-details-marker]:hidden"
        >
          <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/70 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
            <span>字段细节与脱敏规则</span>
            <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">
              默认折叠
            </span>
          </summary>
          <p className="mt-3 text-xs leading-6 text-white/48">
            仅展示类别、文件名、校验脚本和复核姿态；字段清单、原始 schema、provider 载荷和 debug 细节不在页面默认展开。
          </p>
        </details>
      </GlassCard>
      </details>

      <details className="rounded-[20px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden">
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/76 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
          <span>二级细节：离线命令与空状态说明</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">默认折叠</span>
        </summary>
      <section className="mt-4 grid grid-cols-1 gap-4 xl:grid-cols-12">
        <GlassCard as="section" className="p-4 md:p-5 xl:col-span-8">
          <div className="flex items-start gap-3">
            <Code2 className="mt-1 h-4 w-4 text-cyan-200" aria-hidden="true" />
            <div className="min-w-0">
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">离线命令</p>
              <h2 className="mt-1 text-lg font-semibold text-white">可复制的静态片段</h2>
            </div>
          </div>
          <div
            data-testid="admin-evidence-command-snippets"
            className="mt-5 grid grid-cols-1 gap-3 xl:grid-cols-3"
          >
            {commandSnippets.map((snippet) => (
              <article
                key={snippet.label}
                className="min-w-0 rounded-2xl border border-white/5 bg-black/20 p-3.5"
                aria-labelledby={`admin-evidence-command-${snippet.label}`}
              >
                <p id={`admin-evidence-command-${snippet.label}`} className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/34">{snippet.label}</p>
                <pre
                  tabIndex={0}
                  role="group"
                  aria-label={`可复制命令：${snippet.label}`}
                  className="mt-3 max-w-full overflow-x-auto no-scrollbar whitespace-pre-wrap break-all rounded-xl border border-white/[0.04] bg-white/[0.02] p-3 font-mono text-[11px] leading-5 text-cyan-100/86 outline-none transition-colors focus-visible:border-cyan-300/35 focus-visible:ring-2 focus-visible:ring-cyan-300/30"
                >
                  <code>{snippet.command}</code>
                </pre>
                <p className="mt-3 text-xs leading-5 text-white/44">{snippet.note}</p>
              </article>
            ))}
          </div>
        </GlassCard>

        <GlassCard as="aside" className="p-4 md:p-5 xl:col-span-4">
          <div className="flex items-start gap-3">
            <TriangleAlert className="mt-1 h-4 w-4 text-amber-200" aria-hidden="true" />
            <div>
              <p className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/34">空状态</p>
              <h2 className="mt-1 text-lg font-semibold text-white">缺少证据时保持 NO-GO</h2>
            </div>
          </div>
          <div className="mt-5 space-y-3 text-sm leading-6 text-white/58">
            <p>页面不会读取证据目录；没有脱敏摘要时，只展示复核路径和静态命令。</p>
            <p>权限不足时由管理员能力门禁拦截，本页不提供替代入口。</p>
          </div>
        </GlassCard>
      </section>
      </details>

      <details
        data-testid="admin-evidence-raw-disclosure"
        className="rounded-[20px] border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 rounded-xl text-sm font-semibold text-white/76 outline-none transition-colors focus-visible:ring-2 focus-visible:ring-cyan-300/30">
          <span>原始/Schema/Provider/Debug 字段</span>
          <span className="rounded-full border border-white/10 bg-white/[0.03] px-2.5 py-1 text-[11px] font-medium text-white/42">
            默认折叠
          </span>
        </summary>
        <div className="mt-3 rounded-2xl border border-white/[0.04] bg-black/20 p-3 text-xs leading-6 text-white/48">
          原始诊断、provider 载荷、schema 字段和 debug 内容不在本视图展开。复核材料只以脱敏状态码和人工检查结论进入页面。
        </div>
      </details>
    </div>
  </div>
);

export default AdminEvidenceWorkflowPage;
