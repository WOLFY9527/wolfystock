import React, { useEffect, useMemo, useState } from 'react';
import { Activity, Radar, ShieldAlert, Waves, Wallet } from 'lucide-react';
import { backtestApi } from '../../api/backtest';
import { marketRotationApi } from '../../api/marketRotation';
import { optionsLabApi } from '../../api/optionsLab';
import { portfolioApi } from '../../api/portfolio';
import { scannerApi } from '../../api/scanner';
import type { NormalizedEvidenceSummary } from '../../utils/evidenceDisplay';
import {
  normalizeBacktestReadiness,
  normalizeOptionsEvidence,
  normalizePortfolioRiskEvidence,
  normalizeRotationEvidence,
  normalizeScannerEvidence,
} from '../../utils/evidenceDisplay';
import { EvidenceChips } from './EvidenceChips';
import {
  TerminalChip,
  TerminalDisclosure,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPanel,
  TerminalSectionHeader,
} from '../terminal';

type EngineId = 'scanner' | 'rotation' | 'options' | 'backtest' | 'portfolio_risk';
type LoadState = 'loading' | 'ready' | 'empty' | 'error';
type DetailRow = {
  label: string;
  value: string;
};
type EngineSection = {
  id: EngineId;
  title: string;
  eyebrow: string;
  state: LoadState;
  summary: NormalizedEvidenceSummary | null;
  sampleLabel?: string;
  sampleValue?: string;
  note?: string;
  detailRows: DetailRow[];
  operatorReasonCodes: string[];
  sampleSymbol?: string;
};

const ENGINE_META: Record<EngineId, { title: string; eyebrow: string; icon: React.ComponentType<{ className?: string }>; span: string }> = {
  scanner: { title: 'Scanner 候选证据', eyebrow: 'candidate evidence', icon: Activity, span: 'xl:col-span-6' },
  rotation: { title: 'Rotation 状态证据', eyebrow: 'rotation state', icon: Radar, span: 'xl:col-span-6' },
  options: { title: 'Options 门禁证据', eyebrow: 'gate posture', icon: Waves, span: 'xl:col-span-4' },
  backtest: { title: 'Backtest 就绪度', eyebrow: 'readiness', icon: ShieldAlert, span: 'xl:col-span-4' },
  portfolio_risk: { title: 'Portfolio 风险证据', eyebrow: 'risk confidence', icon: Wallet, span: 'xl:col-span-4' },
};

const INITIAL_SECTIONS: Record<EngineId, EngineSection> = {
  scanner: { id: 'scanner', title: ENGINE_META.scanner.title, eyebrow: ENGINE_META.scanner.eyebrow, state: 'loading', summary: null, detailRows: [], operatorReasonCodes: [] },
  rotation: { id: 'rotation', title: ENGINE_META.rotation.title, eyebrow: ENGINE_META.rotation.eyebrow, state: 'loading', summary: null, detailRows: [], operatorReasonCodes: [] },
  options: { id: 'options', title: ENGINE_META.options.title, eyebrow: ENGINE_META.options.eyebrow, state: 'loading', summary: null, detailRows: [], operatorReasonCodes: [] },
  backtest: { id: 'backtest', title: ENGINE_META.backtest.title, eyebrow: ENGINE_META.backtest.eyebrow, state: 'loading', summary: null, detailRows: [], operatorReasonCodes: [] },
  portfolio_risk: { id: 'portfolio_risk', title: ENGINE_META.portfolio_risk.title, eyebrow: ENGINE_META.portfolio_risk.eyebrow, state: 'loading', summary: null, detailRows: [], operatorReasonCodes: [] },
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function toCompactText(value: unknown, fallback = '--'): string {
  if (value === null || value === undefined) return fallback;
  const text = String(value).trim();
  return text ? text.slice(0, 96) : fallback;
}

function stageLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    early_watch: '早期观察',
    confirmed_rotation: '确认轮动',
    extended_watch: '延展观察',
    cooling_watch: '降温观察',
    weak_or_no_signal: '信号较弱',
  };
  return labels[String(value || '')] || toCompactText(value, '待确认');
}

function backtestStatusLabel(value?: string | null): string {
  const labels: Record<string, string> = {
    completed: '完成',
    running: '运行中',
    failed: '失败',
    cancelled: '已取消',
  };
  return labels[String(value || '').toLowerCase()] || toCompactText(value, '待确认');
}

function candidateEvidenceContainer(candidate: unknown): Record<string, unknown> | null {
  if (!isRecord(candidate)) return null;
  const containers = [
    isRecord(candidate.diagnostics) ? candidate.diagnostics : null,
    isRecord(candidate.metadata) ? candidate.metadata : null,
  ].filter((value): value is Record<string, unknown> => Boolean(value));

  for (const container of containers) {
    if (isRecord(container.evidence_packet) || isRecord(container.evidencePacket)) {
      return container;
    }
  }

  return null;
}

function pickScannerCandidate(detail: Record<string, unknown>): Record<string, unknown> | null {
  const candidateGroups = [
    Array.isArray(detail.selected) ? detail.selected : [],
    Array.isArray(detail.shortlist) ? detail.shortlist : [],
    Array.isArray(detail.candidates) ? detail.candidates : [],
  ];

  for (const group of candidateGroups) {
    const match = group.find((candidate) => Boolean(candidateEvidenceContainer(candidate)));
    if (isRecord(match)) return match;
  }
  return null;
}

function chooseOptionsSymbol(sections: Record<EngineId, EngineSection>): string | null {
  return sections.scanner.sampleSymbol
    || sections.portfolio_risk.sampleSymbol
    || sections.backtest.sampleSymbol
    || sections.rotation.sampleSymbol
    || null;
}

async function loadScannerSection(): Promise<EngineSection> {
  try {
    const recent = await scannerApi.getRecentWatchlists({ limitDays: 7 });
    const runId = recent.items?.[0]?.id;
    if (!runId) {
      return {
        ...INITIAL_SECTIONS.scanner,
        state: 'empty',
        note: '最近 watchlist 暂无候选证据包。',
      };
    }

    const detail = await scannerApi.getRun(runId);
    const candidate = pickScannerCandidate(detail as unknown as Record<string, unknown>);
    const payload = candidate ? candidateEvidenceContainer(candidate) : null;
    if (!candidate || !payload) {
      return {
        ...INITIAL_SECTIONS.scanner,
        state: 'empty',
        sampleLabel: '最近样本',
        sampleValue: `run #${runId}`,
        note: '最近样本未附带可显示的 evidence packet。',
      };
    }

    const summary = normalizeScannerEvidence(payload, { audience: 'admin' });
    return {
      ...INITIAL_SECTIONS.scanner,
      state: 'ready',
      summary,
      sampleLabel: '最近候选',
      sampleValue: `${toCompactText(candidate.symbol)} · run #${runId}`,
      sampleSymbol: toCompactText(candidate.symbol, ''),
      operatorReasonCodes: summary.adminReasonCodes,
      detailRows: [
        { label: '市场 / 策略', value: `${toCompactText(detail.market)} / ${toCompactText(detail.profile)}` },
        { label: '状态', value: toCompactText(detail.status, '待确认') },
        { label: '入选数量', value: String(Array.isArray(detail.shortlist) ? detail.shortlist.length : 0) },
      ],
    };
  } catch {
    return {
      ...INITIAL_SECTIONS.scanner,
      state: 'error',
      note: 'Scanner 样本暂不可用。',
    };
  }
}

async function loadRotationSection(): Promise<EngineSection> {
  try {
    const payload = await marketRotationApi.getRotationRadar();
    const theme = (payload.themes || []).find((item) => item.rotationStateEvidence) || payload.themes?.[0];
    if (!theme?.rotationStateEvidence) {
      return {
        ...INITIAL_SECTIONS.rotation,
        state: 'empty',
        note: '当前 rotation radar 未返回可用证据包。',
      };
    }

    const summary = normalizeRotationEvidence({ rotationStateEvidence: theme.rotationStateEvidence }, { audience: 'admin' });
    const representativeSymbol = Array.isArray(theme.representativeSymbols) ? theme.representativeSymbols[0] : undefined;
    return {
      ...INITIAL_SECTIONS.rotation,
      state: 'ready',
      summary,
      sampleLabel: '主题样本',
      sampleValue: toCompactText(theme.name),
      sampleSymbol: representativeSymbol ? toCompactText(representativeSymbol, '') : undefined,
      operatorReasonCodes: summary.adminReasonCodes,
      detailRows: [
        { label: '阶段', value: stageLabel(theme.stage) },
        { label: '代表标的', value: representativeSymbol ? toCompactText(representativeSymbol) : '未提供' },
        { label: '分数 / 置信', value: `${theme.rotationScore} / ${Math.round((theme.confidence || 0) * 100)}%` },
      ],
    };
  } catch {
    return {
      ...INITIAL_SECTIONS.rotation,
      state: 'error',
      note: 'Rotation 样本暂不可用。',
    };
  }
}

async function loadBacktestSection(): Promise<EngineSection> {
  try {
    const history = await backtestApi.getRuleBacktestRuns({ limit: 5 });
    const runId = history.items?.[0]?.id;
    if (!runId) {
      return {
        ...INITIAL_SECTIONS.backtest,
        state: 'empty',
        note: '最近没有可用的规则回测样本。',
      };
    }

    const run = await backtestApi.getRuleBacktestRun(runId);
    const summary = normalizeBacktestReadiness(run, { audience: 'admin' });
    return {
      ...INITIAL_SECTIONS.backtest,
      state: 'ready',
      summary,
      sampleLabel: '最近回测',
      sampleValue: `${toCompactText(run.code)} · #${runId}`,
      sampleSymbol: toCompactText(run.code, ''),
      operatorReasonCodes: summary.adminReasonCodes,
      detailRows: [
        { label: '状态', value: backtestStatusLabel(run.status) },
        { label: '时间框架', value: toCompactText(run.timeframe) },
        { label: '观察窗口', value: `${toCompactText(run.lookbackBars)} bars` },
      ],
    };
  } catch {
    return {
      ...INITIAL_SECTIONS.backtest,
      state: 'error',
      note: 'Backtest 样本暂不可用。',
    };
  }
}

async function loadPortfolioSection(): Promise<EngineSection> {
  try {
    const snapshot = await portfolioApi.getSnapshot();
    const summary = normalizePortfolioRiskEvidence(snapshot, { audience: 'admin' });
    const firstSymbol = snapshot.accounts?.flatMap((account) => account.positions || []).find((position) => position.symbol)?.symbol;
    return {
      ...INITIAL_SECTIONS.portfolio_risk,
      state: 'ready',
      summary,
      sampleLabel: '账户样本',
      sampleValue: `${snapshot.accountCount} 个账户`,
      sampleSymbol: firstSymbol ? toCompactText(firstSymbol, '') : undefined,
      operatorReasonCodes: summary.adminReasonCodes,
      detailRows: [
        { label: '账户数', value: String(snapshot.accountCount || 0) },
        { label: 'FX 状态', value: snapshot.fxStale ? '存在过期汇率' : '未见过期汇率' },
        { label: '参考标的', value: firstSymbol ? toCompactText(firstSymbol) : '暂无持仓' },
      ],
    };
  } catch {
    return {
      ...INITIAL_SECTIONS.portfolio_risk,
      state: 'error',
      note: 'Portfolio 风险样本暂不可用。',
    };
  }
}

async function loadOptionsSection(symbol: string | null): Promise<EngineSection> {
  if (!symbol) {
    return {
      ...INITIAL_SECTIONS.options,
      state: 'empty',
      note: '没有可复用的样本标的，未触发 options gate 读取。',
    };
  }

  try {
    const decision = await optionsLabApi.evaluateDecision({
      symbol,
      strategy: 'bull_call_spread',
    });
    const summary = normalizeOptionsEvidence(decision, { audience: 'admin' });
    return {
      ...INITIAL_SECTIONS.options,
      state: 'ready',
      summary,
      sampleLabel: '样本标的',
      sampleValue: toCompactText(symbol),
      sampleSymbol: toCompactText(symbol, ''),
      operatorReasonCodes: summary.adminReasonCodes,
      detailRows: [
        { label: '策略', value: toCompactText(decision.strategy) },
        { label: '决策', value: toCompactText(decision.decisionLabel) },
        { label: '新鲜度', value: toCompactText(decision.freshness?.freshness, '待确认') },
      ],
    };
  } catch {
    return {
      ...INITIAL_SECTIONS.options,
      state: 'error',
      sampleLabel: '样本标的',
      sampleValue: toCompactText(symbol),
      note: 'Options gate 样本暂不可用。',
    };
  }
}

function metricSubvalue(section: EngineSection): string {
  if (section.state === 'loading') return '正在汇总';
  if (section.state === 'error') return '读取失败';
  if (section.state === 'empty') return '暂无样本';
  const limitationCount = section.summary?.limitationLabels.length || 0;
  const reasonCount = section.operatorReasonCodes.length;
  if (!limitationCount && !reasonCount) return '证据正常可读';
  return [
    limitationCount ? `${limitationCount} 个限制` : null,
    reasonCount ? `${reasonCount} 个原因码` : null,
  ].filter(Boolean).join(' · ');
}

function metricValue(section: EngineSection): string {
  if (section.state === 'loading') return '读取中';
  if (section.state === 'error') return '暂不可用';
  if (section.state === 'empty') return '暂无样本';
  return section.summary?.displayLabel || '证据待确认';
}

function metricTone(section: EngineSection): string {
  if (section.state === 'error') return 'text-rose-200';
  if (section.state === 'empty') return 'text-white/45';
  if (section.summary?.tone === 'danger') return 'text-rose-200';
  if (section.summary?.tone === 'warning') return 'text-amber-200';
  if (section.summary?.tone === 'info') return 'text-cyan-200';
  if (section.summary?.tone === 'success') return 'text-emerald-200';
  return 'text-white';
}

function renderSectionBody(section: EngineSection) {
  if (section.state === 'loading') {
    return <TerminalEmptyState title="正在汇总">{`读取 ${section.title}…`}</TerminalEmptyState>;
  }

  if (section.state === 'error') {
    return <TerminalNotice variant="caution">{section.note || '只读诊断暂不可用。'}</TerminalNotice>;
  }

  if (section.state === 'empty' || !section.summary) {
    return <TerminalEmptyState title="暂无样本">{section.note || '当前没有可复用的只读证据样本。'}</TerminalEmptyState>;
  }

  const summary = section.summary;
  const limitationExtras = summary.limitationLabels.filter((label) => label !== summary.displayLabel && label !== summary.freshnessLabel);

  return (
    <div className="mt-4 flex min-w-0 flex-col gap-3">
      <EvidenceChips
        summary={summary}
        audience="user"
        maxLabels={section.id === 'portfolio_risk' ? 5 : 3}
        data-testid={`admin-evidence-diagnostic-chips-${section.id}`}
      />

      {section.sampleLabel && section.sampleValue ? (
        <TerminalNestedBlock>
          <p className="text-[10px] uppercase tracking-widest text-white/35">{section.sampleLabel}</p>
          <p className="mt-1 font-mono text-sm text-white/82">{section.sampleValue}</p>
        </TerminalNestedBlock>
      ) : null}

      <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
        {section.detailRows.map((row) => (
          <TerminalNestedBlock key={`${section.id}-${row.label}`}>
            <p className="text-[10px] uppercase tracking-widest text-white/35">{row.label}</p>
            <p className="mt-1 break-words font-mono text-[12px] text-white/80">{row.value}</p>
          </TerminalNestedBlock>
        ))}
      </div>

      {(section.operatorReasonCodes.length > 0 || limitationExtras.length > 0 || section.note) ? (
        <TerminalDisclosure
          data-testid={`admin-evidence-operator-details-${section.id}`}
          title="操作员细节"
          summary={[
            section.operatorReasonCodes.length ? `${section.operatorReasonCodes.length} 个原因码` : null,
            limitationExtras.length ? `${limitationExtras.length} 个限制标签` : null,
          ].filter(Boolean).join(' · ') || '展开查看'}
        >
          <div className="flex min-w-0 flex-col gap-3">
            {section.operatorReasonCodes.length ? (
              <div className="flex min-w-0 flex-wrap gap-1.5">
                {section.operatorReasonCodes.map((code) => (
                  <TerminalChip key={`${section.id}-${code}`} variant="neutral">
                    {code}
                  </TerminalChip>
                ))}
              </div>
            ) : null}
            {limitationExtras.length ? (
              <div className="flex min-w-0 flex-wrap gap-1.5">
                {limitationExtras.map((label) => (
                  <TerminalChip key={`${section.id}-${label}`} variant="info">
                    {label}
                  </TerminalChip>
                ))}
              </div>
            ) : null}
            {section.note ? <TerminalNotice>{section.note}</TerminalNotice> : null}
          </div>
        </TerminalDisclosure>
      ) : null}
    </div>
  );
}

export function AdminEvidenceDiagnosticsConsole() {
  const [sections, setSections] = useState<Record<EngineId, EngineSection>>(INITIAL_SECTIONS);

  useEffect(() => {
    let cancelled = false;

    async function load() {
      const [scanner, rotation, backtest, portfolio] = await Promise.all([
        loadScannerSection(),
        loadRotationSection(),
        loadBacktestSection(),
        loadPortfolioSection(),
      ]);

      const nextSections = {
        scanner,
        rotation,
        backtest,
        portfolio_risk: portfolio,
        options: INITIAL_SECTIONS.options,
      } satisfies Record<EngineId, EngineSection>;
      const options = await loadOptionsSection(chooseOptionsSymbol(nextSections));

      if (!cancelled) {
        setSections({
          ...nextSections,
          options,
        });
      }
    }

    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  const orderedSections = useMemo(
    () => (['scanner', 'rotation', 'options', 'backtest', 'portfolio_risk'] as EngineId[]).map((id) => sections[id]),
    [sections],
  );

  const unavailableCount = orderedSections.filter((section) => section.state === 'error' || section.state === 'empty').length;

  return (
    <div data-testid="admin-evidence-diagnostics-console" className="flex flex-col gap-4">
      <TerminalPanel as="section" dense>
        <TerminalSectionHeader
          eyebrow="cross-engine evidence"
          title="证据诊断台"
          action={
            <div className="flex flex-wrap gap-1.5">
              <TerminalChip variant="info">只读聚合</TerminalChip>
              <TerminalChip variant="neutral">普通页面仍隐藏内部词</TerminalChip>
            </div>
          }
        />
        <p className="mt-3 max-w-4xl text-sm leading-6 text-white/55">
          从现有前端可读 surface 抽取代表性样本，压缩展示 Scanner、Rotation、Options、Backtest、Portfolio 的证据姿态；内部原因码仅保留在折叠的操作员细节里。
        </p>
        {unavailableCount > 0 ? (
          <TerminalNotice className="mt-3">
            {`${unavailableCount} 个引擎当前没有可复用样本或读取失败，页面会保持只读空状态而不会补造后端 contract。`}
          </TerminalNotice>
        ) : null}
        <div
          data-testid="admin-evidence-diagnostics-summary-strip"
          className="mt-4 grid grid-cols-1 gap-2 md:grid-cols-2 xl:grid-cols-5"
        >
          {orderedSections.map((section) => (
            <TerminalMetric
              key={section.id}
              data-testid={`admin-evidence-diagnostic-summary-${section.id}`}
              label={section.title}
              value={metricValue(section)}
              subvalue={metricSubvalue(section)}
              valueClassName={metricTone(section)}
            />
          ))}
        </div>
      </TerminalPanel>

      <TerminalGrid>
        {orderedSections.map((section) => {
          const meta = ENGINE_META[section.id];
          const Icon = meta.icon;
          const summary = section.summary;
          return (
            <TerminalPanel
              key={section.id}
              as="section"
              dense
              className={meta.span}
              data-testid={`admin-evidence-diagnostic-engine-${section.id}`}
            >
              <TerminalSectionHeader
                eyebrow={section.eyebrow}
                title={
                  <span className="inline-flex min-w-0 items-center gap-2">
                    <Icon className="h-4 w-4 shrink-0 text-cyan-200" aria-hidden="true" />
                    <span className="truncate">{section.title}</span>
                  </span>
                }
                action={section.state === 'ready' && summary ? (
                  <TerminalChip variant={summary.tone === 'danger' ? 'danger' : summary.tone === 'warning' ? 'caution' : summary.tone === 'info' ? 'info' : summary.tone === 'success' ? 'success' : 'neutral'}>
                    {summary.displayLabel}
                  </TerminalChip>
                ) : null}
              />
              {renderSectionBody(section)}
            </TerminalPanel>
          );
        })}
      </TerminalGrid>

      <TerminalNotice>
        AI evidence packet metadata adapter / schema readiness 只在前端已有 surface 暴露时才纳入；当前页面未额外发明新的 adapter contract。
      </TerminalNotice>
    </div>
  );
}
