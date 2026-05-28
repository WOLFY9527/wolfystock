import type React from 'react';
import {
  Archive,
  BookOpenCheck,
  ClipboardCheck,
  Route,
  TerminalSquare,
} from 'lucide-react';
import { AdminEvidenceDiagnosticsConsole } from '../components/evidence/AdminEvidenceDiagnosticsConsole';
import { AdminEvidenceDryRunPreview } from '../components/evidence/AdminEvidenceDryRunPreview';
import {
  TerminalChip,
  TerminalDenseList,
  TerminalDisclosure,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageHeading,
  TerminalPageShell,
  TerminalPanel,
  TerminalSectionHeader,
} from '../components/terminal/TerminalPrimitives';

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

const statusCards: Array<{
  label: string;
  value: string;
  note: string;
}> = [
  { label: '复核入口', value: 'GO-REVIEW-REQUIRED', note: '进入人工复核前不提升结论。' },
  { label: '缺证据状态', value: 'NO-GO when evidence missing', note: '关键脱敏证据缺失即阻塞。' },
  { label: '人工门禁', value: 'manual review required', note: '线下复核决定结论。' },
  { label: '发布字段', value: 'releaseApproved=false', note: '默认保持未放行。' },
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

const AdminEvidenceWorkflowPage: React.FC = () => (
  <div
    data-testid="admin-evidence-workflow-page"
    className="min-h-0 w-full flex-1 overflow-x-hidden overflow-y-auto no-scrollbar text-white"
  >
    <TerminalPageShell className="py-5 md:py-6">
      <TerminalPanel as="section" className="relative overflow-hidden">
        <TerminalPageHeading
          eyebrow="ADMIN EVIDENCE REVIEW"
          title="证据工作流复核"
          action={(
            <div className="flex flex-wrap gap-2">
              <TerminalChip variant="info">只读视图</TerminalChip>
              <TerminalChip variant="caution">人工门禁</TerminalChip>
            </div>
          )}
        />
        <div
          data-testid="admin-evidence-operational-verdict"
          className="mt-4 grid grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1fr)_minmax(320px,0.42fr)]"
        >
          <div className="min-w-0 rounded-lg border border-amber-300/18 bg-amber-300/[0.04] p-4">
            <p className="text-[10px] font-bold uppercase tracking-[0.2em] text-amber-100/62">L0 运维结论</p>
            <h2 className="mt-2 text-lg font-semibold leading-7 text-white">等待人工复核</h2>
            <p className="mt-2 text-sm leading-6 text-white/68">
              缺证据时保持 NO-GO；本页只展示复核路径，不提供审批动作。
            </p>
          </div>
          <TerminalNotice variant="info" className="self-stretch">
            先生成空白模板并脱敏填写，再运行 preflight。
          </TerminalNotice>
        </div>
        <div
          data-testid="admin-evidence-status-grid"
          className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-4"
          aria-label="静态复核状态"
        >
          {statusCards.map(({ label, value, note }) => (
            <article
              key={value}
              data-testid="admin-evidence-module-status"
              aria-label={`${label}：${value}`}
              className="min-w-0 rounded-lg border border-white/[0.06] bg-white/[0.025] px-3 py-2"
            >
              <p className="truncate text-[10px] font-bold uppercase tracking-[0.18em] text-white/36">{label}</p>
              <p className="mt-1 break-words font-mono text-[12px] font-semibold leading-5 text-white/86">{value}</p>
              <p className="mt-1 text-[11px] leading-5 text-white/42">{note}</p>
            </article>
          ))}
        </div>
      </TerminalPanel>

      <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
        <TerminalPanel as="section" className="xl:col-span-8">
          <TerminalSectionHeader
            eyebrow="离线序列"
            title="操作员证据路径"
            action={<TerminalChip variant="info">6 步只读流程</TerminalChip>}
          />
          <TerminalDenseList
            data-testid="admin-evidence-workflow-grid"
            className="mt-5"
          >
            {workflowSteps.map((step, index) => (
              <article key={step.label} className="min-w-0">
                <TerminalNestedBlock className="flex items-start gap-4">
                  <p className="w-8 shrink-0 font-mono text-[11px] text-white/36">{String(index + 1).padStart(2, '0')}</p>
                  <div className="min-w-0 flex-1">
                    <h3 className="text-sm font-semibold leading-5 text-white/86">{step.label}</h3>
                    <p className="mt-1 text-xs leading-5 text-white/42">{step.note}</p>
                  </div>
                </TerminalNestedBlock>
              </article>
            ))}
          </TerminalDenseList>
        </TerminalPanel>

        <div className="grid grid-cols-1 gap-6 xl:col-span-4">
          <TerminalPanel as="section">
            <TerminalSectionHeader
              eyebrow="能力边界"
              title="页面不执行动作"
            />
            <div className="mt-4 space-y-3">
              <TerminalNotice variant="neutral">不提供上传入口，不调用后端写接口，不变更运行时配置。</TerminalNotice>
              <TerminalNotice variant="neutral">不读取原始证据文件内容，不展示数据源载荷、数据结构细节或调试字段。</TerminalNotice>
            </div>
          </TerminalPanel>

          <TerminalPanel
            as="section"
            data-testid="admin-evidence-local-workspace-guard"
          >
            <TerminalSectionHeader
              eyebrow="LOCAL GUARD"
              title="本地目录保护"
            />
            <div className="mt-4 grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1">
              {localWorkspaceGuards.map((guard) => (
                <TerminalNestedBlock key={guard.label} className="min-w-0">
                  <p className="text-[11px] font-medium text-white/72">{guard.label}</p>
                  <p className="mt-1 break-words font-mono text-[11px] text-cyan-100/66">{guard.value}</p>
                </TerminalNestedBlock>
              ))}
            </div>
          </TerminalPanel>
        </div>
      </div>

      <TerminalDisclosure
        data-testid="admin-evidence-diagnostics-disclosure"
        title="二级细节：诊断与 Dry-run 预览"
        summary="默认折叠"
      >
        <div className="space-y-4">
          <AdminEvidenceDiagnosticsConsole />
          <AdminEvidenceDryRunPreview />
        </div>
      </TerminalDisclosure>

      <TerminalDisclosure title="二级细节：Runbook 参考" summary="默认折叠">
        <div data-testid="admin-evidence-runbook-references">
          <TerminalSectionHeader
            eyebrow="本地操作手册"
            title="操作员工作流参考"
            action={<TerminalChip variant="neutral">静态标签</TerminalChip>}
          />
          <TerminalDenseList className="mt-5">
            {runbookReferences.map(({ label, docLabel, stage, icon: Icon }) => (
              <article
                key={docLabel}
                className="min-w-0"
                aria-label={`${label}：${docLabel}`}
              >
                <TerminalNestedBlock className="flex items-start justify-between gap-4">
                  <div className="min-w-0 flex-1">
                    <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">参考卡</p>
                    <h3 className="mt-2 text-sm font-semibold leading-5 text-white/88">{label}</h3>
                    <p className="mt-3 break-all rounded-xl border border-white/[0.04] bg-white/[0.02] px-2.5 py-2 font-mono text-[11px] leading-5 text-cyan-100/78">
                      {docLabel}
                    </p>
                    <p className="mt-3 text-xs leading-5 text-white/44">{stage}</p>
                  </div>
                  <span className="inline-flex size-9 shrink-0 items-center justify-center rounded-full border border-cyan-300/15 bg-cyan-400/8 text-cyan-100">
                    <Icon className="size-4" aria-hidden="true" />
                  </span>
                </TerminalNestedBlock>
              </article>
            ))}
          </TerminalDenseList>
        </div>
      </TerminalDisclosure>

      <TerminalDisclosure title="二级细节：Schema 与字段参考" summary="默认折叠">
        <div data-testid="admin-evidence-schema-reference">
          <TerminalSectionHeader
            eyebrow="本地参考"
            title="离线证据数据结构参考"
            action={(
              <div className="flex flex-wrap gap-2">
                <TerminalChip variant="caution">人工复核必需</TerminalChip>
                <TerminalChip variant="neutral">只读字段</TerminalChip>
              </div>
            )}
          />

          <TerminalDenseList className="mt-5">
            {schemaReferenceGroups.map((group) => (
              <article
                key={group.artifact}
                className="min-w-0"
                aria-label={`${group.label}：${group.artifact}`}
              >
                <TerminalNestedBlock className="min-w-0">
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <p className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/34">证据类别</p>
                      <h3 className="mt-2 text-sm font-semibold leading-5 text-white/88">{group.label}</h3>
                    </div>
                    <TerminalChip variant="info">本地校验</TerminalChip>
                  </div>
                  <dl className="mt-4 grid gap-3 text-xs leading-5 md:grid-cols-[minmax(0,1.3fr)_minmax(0,1fr)_auto] md:items-start">
                    <div>
                      <dt className="text-white/34">预期证据文件</dt>
                      <dd className="mt-1 break-all font-mono text-white/74">{group.artifact}</dd>
                    </div>
                    <div>
                      <dt className="text-white/34">validator / review stage</dt>
                      <dd className="mt-1 break-all font-mono text-cyan-100/78">{group.validator}</dd>
                    </div>
                    <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 md:grid-cols-1">
                      <TerminalNestedBlock className="px-2.5 py-2">
                        <span className="font-mono text-[11px] text-amber-100/86">manual review required</span>
                      </TerminalNestedBlock>
                      <TerminalNestedBlock className="px-2.5 py-2">
                        <span className="font-mono text-[11px] text-emerald-100/84">releaseApproved=false</span>
                      </TerminalNestedBlock>
                    </div>
                  </dl>
                </TerminalNestedBlock>
              </article>
            ))}
          </TerminalDenseList>

          <TerminalDisclosure
            data-testid="admin-evidence-schema-notes"
            title="字段细节与脱敏规则"
            summary="默认折叠"
            className="mt-4"
          >
            <TerminalNotice variant="neutral">
              仅展示类别、文件名、校验脚本和复核姿态；字段清单、原始数据结构、数据源载荷和调试细节不在页面默认展开。
            </TerminalNotice>
          </TerminalDisclosure>
        </div>
      </TerminalDisclosure>

      <TerminalDisclosure title="二级细节：离线命令与空状态说明" summary="默认折叠">
        <div className="grid grid-cols-1 gap-6 xl:grid-cols-12">
          <div className="xl:col-span-8">
            <div data-testid="admin-evidence-command-snippets">
              <TerminalSectionHeader eyebrow="离线命令" title="可复制的静态片段" />
              <TerminalDenseList className="mt-5">
                {commandSnippets.map((snippet) => (
                  <article
                    key={snippet.label}
                    className="min-w-0"
                    aria-labelledby={`admin-evidence-command-${snippet.label}`}
                  >
                    <TerminalNestedBlock className="min-w-0">
                      <p id={`admin-evidence-command-${snippet.label}`} className="text-[10px] font-bold uppercase tracking-[0.2em] text-white/34">
                        {snippet.label}
                      </p>
                      <pre
                        tabIndex={0}
                        role="group"
                        aria-label={`可复制命令：${snippet.label}`}
                        className="mt-3 max-w-full overflow-x-auto no-scrollbar whitespace-pre-wrap break-all rounded-xl border border-white/[0.04] bg-white/[0.02] p-3 font-mono text-[11px] leading-5 text-cyan-100/86 outline-none transition-colors focus-visible:border-cyan-300/35 focus-visible:ring-2 focus-visible:ring-cyan-300/30"
                      >
                        <code>{snippet.command}</code>
                      </pre>
                      <p className="mt-3 text-xs leading-5 text-white/44">{snippet.note}</p>
                    </TerminalNestedBlock>
                  </article>
                ))}
              </TerminalDenseList>
            </div>
          </div>

          <TerminalPanel as="aside" className="xl:col-span-4">
            <TerminalSectionHeader
              eyebrow="空状态"
              title="缺少证据时保持 NO-GO"
              action={<TerminalChip variant="caution">默认保守</TerminalChip>}
            />
            <div className="mt-4 space-y-3">
              <TerminalNotice variant="neutral">页面不会读取证据目录；没有脱敏摘要时，只展示复核路径和静态命令。</TerminalNotice>
              <TerminalNotice variant="neutral">权限不足时由管理员能力门禁拦截，本页不提供替代入口。</TerminalNotice>
            </div>
          </TerminalPanel>
        </div>
      </TerminalDisclosure>

      <TerminalDisclosure
        data-testid="admin-evidence-raw-disclosure"
        title="原始 / 数据结构 / 数据源 / 调试字段"
        summary="默认折叠"
      >
        <TerminalNotice variant="neutral">
          原始诊断、数据源载荷、数据结构字段和调试内容不在本视图展开。复核材料只以脱敏状态码和人工检查结论进入页面。
        </TerminalNotice>
      </TerminalDisclosure>
    </TerminalPageShell>
  </div>
);

export default AdminEvidenceWorkflowPage;
