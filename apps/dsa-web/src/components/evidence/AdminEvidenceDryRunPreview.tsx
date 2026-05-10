import {
  TerminalChip,
  TerminalDisclosure,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPanel,
  TerminalSectionHeader,
} from '../terminal';
import {
  ADMIN_EVIDENCE_DRY_RUN_PREVIEWS,
  type AdminEvidenceDryRunPreviewItem,
} from './adminEvidenceDryRunPreviewData';

const postureMeta: Record<
AdminEvidenceDryRunPreviewItem['posture'],
{ label: string; variant: 'danger' | 'caution' | 'info' | 'neutral' }
> = {
  blocked: { label: '禁止判断', variant: 'danger' },
  observe_only: { label: '仅供观察', variant: 'caution' },
  allowed_metadata_only: { label: '元数据观察', variant: 'info' },
  review_required: { label: '需人工复核', variant: 'neutral' },
};

const validationMeta: Record<
AdminEvidenceDryRunPreviewItem['validationState'],
{ label: string; variant: 'success' | 'danger' | 'neutral' }
> = {
  valid: { label: '已校验', variant: 'success' },
  invalid: { label: '校验失败', variant: 'danger' },
  not_evaluated: { label: '待校验', variant: 'neutral' },
};

const disabledClaimLabels: Record<string, string> = {
  options_recommendation: '策略推荐已禁用',
  options_tradeability: '可交易性判断已禁用',
  professional_backtest_claim: '专业量化结论已禁用',
  strong_risk_conclusion: '强风险结论已禁用',
  real_fund_flow_claim: '真实资金流表述已禁用',
};

function formatGeneratedAt(value: string): string {
  if (!value) return '--';
  return value.replace('T', ' ').replace('Z', ' UTC');
}

function disabledClaimText(claim: string): string {
  return disabledClaimLabels[claim] || claim.replace(/_/g, ' ');
}

export function AdminEvidenceDryRunPreview() {
  return (
    <TerminalPanel
      as="section"
      dense
      data-testid="admin-evidence-dry-run-preview"
      className="flex flex-col gap-4"
    >
      <TerminalSectionHeader
        eyebrow="deterministic dry-run"
        title="AI 证据解释预览"
        action={(
          <div className="flex flex-wrap justify-end gap-2">
            <TerminalChip variant="info">display-only</TerminalChip>
            <TerminalChip variant="neutral">no live influence</TerminalChip>
          </div>
        )}
      />

      <TerminalNotice variant="info">
        该区块展示确定性 dry-run 解释预览，仅供管理员观察；不影响实时 AI 决策、提示词、权重或引擎判断。
      </TerminalNotice>

      <TerminalGrid
        data-testid="admin-evidence-dry-run-preview-grid"
        className="gap-3 md:grid-cols-2 xl:grid-cols-5"
      >
        {ADMIN_EVIDENCE_DRY_RUN_PREVIEWS.map((item) => {
          const posture = postureMeta[item.posture];
          const validation = validationMeta[item.validationState];
          return (
            <TerminalPanel
              key={item.engine}
              as="article"
              dense
              data-testid={`admin-evidence-dry-run-card-${item.engine}`}
              className="flex h-full flex-col gap-3 xl:col-span-1"
            >
              <TerminalSectionHeader
                eyebrow={item.engineLabel}
                title={item.representativePacket}
                action={<TerminalChip variant={posture.variant}>{posture.label}</TerminalChip>}
              />

              <div className="grid grid-cols-2 gap-2">
                <TerminalMetric
                  data-testid={`admin-evidence-dry-run-cap-${item.engine}`}
                  label="置信上限"
                  value={`≤${item.confidenceCap}`}
                  subvalue={item.explanationMode}
                  className="min-w-0"
                />
                <TerminalMetric
                  data-testid={`admin-evidence-dry-run-validation-${item.engine}`}
                  label="校验状态"
                  value={validation.label}
                  className="min-w-0"
                />
              </div>

              <TerminalNestedBlock className="min-w-0">
                <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">安全摘要</p>
                <p className="mt-1 text-sm leading-6 text-white/78">{item.safeSummary}</p>
              </TerminalNestedBlock>

              <div className="flex flex-wrap gap-2">
                {item.limitationLabels.map((label) => (
                  <TerminalChip key={`${item.engine}-${label}`} variant="neutral">
                    {label}
                  </TerminalChip>
                ))}
              </div>

              <div className="flex flex-wrap gap-2 text-[11px] text-white/42">
                <span>原因码 {item.adminReasonCodeCount}</span>
                <span>生成于 {formatGeneratedAt(item.generatedAt)}</span>
              </div>

              <TerminalDisclosure
                data-testid={`admin-evidence-dry-run-disclosure-${item.engine}`}
                title="代表样本诊断"
                summary={item.disabledClaims.length ? `已禁用 ${item.disabledClaims.length} 项结论` : '当前无额外禁用结论'}
              >
                <div className="grid grid-cols-1 gap-2">
                  <TerminalNestedBlock>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">禁用结论</p>
                    {item.disabledClaims.length ? (
                      <div className="mt-2 flex flex-wrap gap-2">
                        {item.disabledClaims.map((claim) => (
                          <TerminalChip key={`${item.engine}-${claim}`} variant="danger">
                            {disabledClaimText(claim)}
                          </TerminalChip>
                        ))}
                      </div>
                    ) : (
                      <p className="mt-1 text-xs text-white/48">当前样本没有额外禁用结论。</p>
                    )}
                  </TerminalNestedBlock>

                  <TerminalNestedBlock>
                    <p className="text-[10px] font-bold uppercase tracking-widest text-white/35">管理员元信息</p>
                    <div className="mt-2 grid grid-cols-1 gap-2 text-xs text-white/58">
                      <div className="flex items-center justify-between gap-3">
                        <span>engine</span>
                        <span className="font-mono text-white/72">{item.engine}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span>packet version</span>
                        <span className="font-mono text-white/72">{item.sourcePacketVersion}</span>
                      </div>
                      <div className="flex items-center justify-between gap-3">
                        <span>validation</span>
                        <span className="font-mono text-white/72">{item.validationState}</span>
                      </div>
                    </div>
                  </TerminalNestedBlock>
                </div>
              </TerminalDisclosure>
            </TerminalPanel>
          );
        })}
      </TerminalGrid>
    </TerminalPanel>
  );
}
