import type React from 'react';
import { CheckCircle2, Code2, FileCheck2, Layers3, LockKeyhole, ShieldCheck, TriangleAlert } from 'lucide-react';
import { Badge, GlassCard } from '../components/common';
import { cn } from '../utils/cn';

type Tone = 'info' | 'warn' | 'danger' | 'good';
type CommandSnippet = {
  label: string;
  note: string;
  command: string;
};

const workflowSteps = [
  { label: '模板生成', note: '离线模板' },
  { label: '人工填写脱敏证据', note: '人工录入' },
  { label: '分类校验', note: '本地校验' },
  { label: 'manifest 校验', note: '校验和' },
  { label: 'bundle 聚合', note: '脱敏摘要' },
  { label: 'review report 渲染', note: '只读报告' },
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
            <p className="mt-3 max-w-3xl text-sm leading-6 text-white/58">
              仅展示离线操作员证据从模板到复核报告的静态状态，不接收文件、不解析 artifact、不写入后端。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <Badge variant="info" className="border-cyan-300/20 bg-cyan-400/8 text-cyan-100">只读视图</Badge>
            <Badge variant="default" className="border-white/10 bg-white/[0.04] text-white/62">脱敏状态</Badge>
            <Badge variant="warning" className="border-amber-300/25 bg-amber-400/10 text-amber-100">人工门禁</Badge>
          </div>
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
            className="mt-5 grid grid-cols-1 gap-3 lg:grid-cols-7"
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

        <GlassCard as="section" className="p-4 md:p-5 xl:col-span-4">
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
      </section>

      <section
        data-testid="admin-evidence-status-grid"
        className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4"
        aria-label="静态复核状态"
      >
        {statusCards.map(({ label, value, tone, icon: Icon }) => (
          <GlassCard key={value} as="article" className="p-4">
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

      <section className="grid grid-cols-1 gap-4 xl:grid-cols-12">
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
              >
                <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/34">{snippet.label}</p>
                <pre className="mt-3 overflow-x-auto no-scrollbar whitespace-pre-wrap break-all rounded-xl border border-white/[0.04] bg-white/[0.02] p-3 font-mono text-[11px] leading-5 text-cyan-100/86">
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

      <details
        data-testid="admin-evidence-raw-disclosure"
        className="rounded-[20px] border border-white/5 bg-white/[0.02] px-4 py-3 backdrop-blur-md [&>summary::-webkit-details-marker]:hidden"
      >
        <summary className="flex cursor-pointer list-none items-center justify-between gap-3 text-sm font-semibold text-white/76">
          <span>原始/Schema 字段</span>
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
