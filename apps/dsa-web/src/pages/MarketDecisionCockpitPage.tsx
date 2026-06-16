import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import {
  ConsoleBoard,
  ConsoleContextRail,
  ConsoleStatusStrip,
  MetricStrip,
  ResearchConsoleShell,
  WolfyCommandBar,
} from '../components/linear/LinearPrimitives';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import { StatusBadge } from '../components/ui/StatusBadge';
import { TerminalButton, TerminalChip, TerminalEmptyState } from '../components/terminal/TerminalPrimitives';
import {
  dailyIntelligenceApi,
  type DailyIntelligenceEvidenceLink,
  type DailyIntelligenceResponse,
} from '../api/dailyIntelligence';
import { createParsedApiError, getParsedApiError, type ParsedApiError } from '../api/error';
import { marketDecisionCockpitApi, type MarketDecisionCockpitResponse } from '../api/marketDecisionCockpit';
import { useI18n } from '../contexts/UiLanguageContext';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { formatDateTime } from '../utils/format';
import { sanitizeUserFacingDataIssue, sanitizeUserFacingDataIssues } from '../utils/userFacingDataIssues';
import {
  RoughBulletList,
  RoughKeyValueRows,
  RoughScoreRows,
  RoughSectionCard,
  RoughSurfaceIntro,
} from './roughShellShared';

const DRIVER_LABELS = {
  dealerGamma: { zh: 'Gamma 观察', en: 'Gamma observation' },
  breadthParticipation: { zh: '广度参与', en: 'Breadth participation' },
  volatilityStructure: { zh: '波动结构', en: 'Volatility structure' },
  ratesDollar: { zh: '利率与美元', en: 'Rates and USD' },
  liquidityCredit: { zh: '流动性与信用', en: 'Liquidity and credit' },
  crossAssetRisk: { zh: '跨资产风险', en: 'Cross-asset risk' },
  sectorThemeRotation: { zh: '主题轮动', en: 'Theme rotation' },
  eventCatalyst: { zh: '事件催化', en: 'Event catalyst' },
} as const;

const DAILY_SECTION_LABELS = {
  marketRegimeSummary: { zh: '市场状态摘要', en: 'Market regime summary' },
  whatChanged: { zh: '发生了什么', en: 'What changed' },
  topResearchPriorities: { zh: '研究优先级', en: 'Research priorities' },
  scannerHighlights: { zh: '扫描重点', en: 'Scanner highlights' },
  watchlistHighlights: { zh: '观察列表重点', en: 'Watchlist highlights' },
  portfolioStructureHighlights: { zh: '持仓结构重点', en: 'Portfolio structure highlights' },
  scenarioRisks: { zh: '情景风险', en: 'Scenario risks' },
  evidenceGaps: { zh: '证据缺口', en: 'Evidence gaps' },
  degradedInputs: { zh: '可用性提醒', en: 'Availability notes' },
} as const;

const DAILY_REASON_LABELS = {
  owner_context_missing: {
    zh: '登录后可附加个人研究队列、观察列表和持仓语境。',
    en: 'Sign in to attach personal queue, watchlist, and portfolio context.',
  },
  research_radar_unavailable: {
    zh: '研究队列暂不可用，稍后再补读。',
    en: 'The research queue is temporarily unavailable for this briefing.',
  },
  watchlist_unavailable: {
    zh: '观察列表研究视图暂不可用。',
    en: 'The watchlist research view is temporarily unavailable.',
  },
  portfolio_structure_review_unavailable: {
    zh: '持仓结构复核暂不可用。',
    en: 'Portfolio structure review is temporarily unavailable.',
  },
  scannerCandidates: {
    zh: '扫描候选尚未形成可读条目。',
    en: 'Scanner candidates are not ready for a readable briefing yet.',
  },
  watchlist_research_context: {
    zh: '观察列表暂未形成研究上下文。',
    en: 'Watchlist research context is not ready yet.',
  },
  cached_portfolio_holdings: {
    zh: '持仓上下文暂未形成结构复核条目。',
    en: 'Portfolio holdings context is not ready for structure review yet.',
  },
  scenario_risk_read_model_unavailable: {
    zh: '情景风险读模型暂未接入本次日度简报。',
    en: 'Scenario-risk readouts are not yet attached to this daily briefing.',
  },
} as const;

const DAILY_EVIDENCE_LINK_LABELS = {
  'Research Radar': { zh: '研究雷达', en: 'Research Radar' },
  Scanner: { zh: '扫描器', en: 'Scanner' },
  Watchlist: { zh: '观察列表', en: 'Watchlist' },
  Portfolio: { zh: '组合', en: 'Portfolio' },
  'Stock Structure': { zh: '结构详情', en: 'Stock structure' },
  'Scenario Lab': { zh: '情景实验室', en: 'Scenario Lab' },
} as const;

function labelFromKey(
  key: string,
  language: 'zh' | 'en',
): string {
  const mapped = DRIVER_LABELS[key as keyof typeof DRIVER_LABELS];
  if (mapped) {
    return mapped[language];
  }
  return key.replace(/([a-z])([A-Z])/g, '$1 $2');
}

function confidenceLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  switch (String(value || '').toLowerCase()) {
    case 'high':
      return language === 'en' ? 'High' : '高';
    case 'medium':
      return language === 'en' ? 'Medium' : '中';
    case 'low':
      return language === 'en' ? 'Low' : '低';
    default:
      return value || '--';
  }
}

function consumerOptionsBoundaryLabel(observationOnly: boolean | null | undefined, language: 'zh' | 'en'): string {
  if (observationOnly === false) {
    return language === 'en' ? 'Structured observation' : '可继续观察';
  }
  return language === 'en' ? 'Observe only' : '仅供观察';
}

function consumerDecisionGradeLabel(decisionGrade: boolean | null | undefined, language: 'zh' | 'en'): string {
  if (decisionGrade === true) {
    return language === 'en' ? 'Decision-grade reached' : '达到可判断等级';
  }
  return language === 'en' ? 'Not decision-grade yet' : '未达到可判断等级';
}

function consumerMissingEvidenceLabels(
  items: Array<{ code?: string | null; kind?: string | null; field?: string | null; message?: string | null }> | null | undefined,
  language: 'zh' | 'en',
): string[] {
  return sanitizeUserFacingDataIssues(
    (items ?? []).map((item) => item.message || item.code || item.kind || item.field || ''),
    language,
  );
}

function regimeLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  switch (String(value || '').toLowerCase()) {
    case 'riskon':
    case 'risk_on':
      return language === 'en' ? 'Risk-on observation' : '风险偏好观察';
    case 'riskoff':
    case 'risk_off':
      return language === 'en' ? 'Risk-off observation' : '风险规避观察';
    case 'neutral':
      return language === 'en' ? 'Neutral observation' : '中性观察';
    case 'lowconfidence':
    case 'low_confidence':
      return language === 'en' ? 'Low-confidence observation' : '低置信观察';
    default:
      return value || '--';
  }
}

function sessionLabel(value: string | null | undefined, language: 'zh' | 'en'): string {
  switch (String(value || '').toLowerCase()) {
    case 'pre-market':
    case 'pre_market':
      return language === 'en' ? 'Pre-market' : '盘前';
    case 'intraday':
      return language === 'en' ? 'Intraday' : '盘中';
    case 'after-hours':
    case 'after_hours':
      return language === 'en' ? 'After-hours' : '盘后';
    default:
      return value || '--';
  }
}

function statusTone(value: string | null | undefined): string {
  const normalized = String(value || '').toLowerCase();
  if (['ready', 'high', 'strong', 'available', 'complete', 'success', 'riskon', 'supportive'].includes(normalized)) {
    return 'success';
  }
  if (['medium', 'mixed', 'partial', 'thin', 'warning', 'neutral', 'preview'].includes(normalized)) {
    return 'warning';
  }
  if (['blocked', 'degraded', 'unavailable', 'low', 'empty', 'low_evidence'].includes(normalized)) {
    return 'error';
  }
  return 'info';
}

function humanizeEnum(value: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = String(value || '').trim();
  if (!normalized) {
    return '--';
  }
  switch (normalized.toLowerCase()) {
    case 'high':
    case 'medium':
    case 'low':
      return confidenceLabel(normalized, language);
    case 'structure_changed':
      return language === 'en' ? 'Structure changed' : '结构变化';
    case 'mixed':
      return language === 'en' ? 'Mixed' : '混合';
    case 'partial':
      return language === 'en' ? 'Partly available' : '部分可用';
    case 'degraded':
      return language === 'en' ? 'Partial context' : '部分缺口';
    case 'blocked':
      return language === 'en' ? 'Blocked' : '已阻断';
    case 'unavailable':
      return language === 'en' ? 'Unavailable' : '暂不可用';
    case 'available':
      return language === 'en' ? 'Available' : '可用';
    case 'ready':
      return language === 'en' ? 'Ready' : '就绪';
    case 'preview':
      return language === 'en' ? 'Preview' : '预览';
    default:
      return normalized.replace(/[_-]+/g, ' ').replace(/([a-z])([A-Z])/g, '$1 $2');
  }
}

function dailySectionLabel(section: string | null | undefined, language: 'zh' | 'en'): string {
  if (!section) {
    return language === 'en' ? 'Availability note' : '可用性提醒';
  }
  const mapped = DAILY_SECTION_LABELS[section as keyof typeof DAILY_SECTION_LABELS];
  return mapped ? mapped[language] : humanizeEnum(section, language);
}

function dailyReasonLabel(reason: string | null | undefined, language: 'zh' | 'en'): string {
  if (!reason) {
    return language === 'en' ? 'Some evidence is still unavailable.' : '部分证据仍暂不可用。';
  }
  const mapped = DAILY_REASON_LABELS[reason as keyof typeof DAILY_REASON_LABELS];
  if (mapped) {
    return mapped[language];
  }
  const safeLabel = sanitizeUserFacingDataIssue(reason, language);
  if (safeLabel !== String(reason).trim()) {
    return safeLabel;
  }
  return language === 'en' ? 'Some evidence still needs verification.' : '该部分证据仍待补充验证。';
}

function dailyEvidenceLinkLabel(label: string | null | undefined, language: 'zh' | 'en'): string {
  if (!label) {
    return language === 'en' ? 'Evidence' : '证据';
  }
  const mapped = DAILY_EVIDENCE_LINK_LABELS[label as keyof typeof DAILY_EVIDENCE_LINK_LABELS];
  return mapped ? mapped[language] : label;
}

function createLocalizedApiError(
  language: 'zh' | 'en',
  title: { zh: string; en: string },
  message: { zh: string; en: string },
): ParsedApiError {
  return createParsedApiError({
    title: language === 'en' ? title.en : title.zh,
    message: language === 'en' ? message.en : message.zh,
  });
}

function BriefingBlock({
  eyebrow,
  title,
  children,
  footer,
}: {
  eyebrow: string;
  title: string;
  children: ReactNode;
  footer?: ReactNode;
}) {
  return (
    <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
      <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{eyebrow}</div>
      <div className="mt-1 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{title}</div>
      <div className="mt-3 min-w-0">{children}</div>
      {footer ? <div className="mt-3 min-w-0">{footer}</div> : null}
    </div>
  );
}

function EvidenceLinkStrip({
  links,
  language,
  localizePath,
}: {
  links: DailyIntelligenceEvidenceLink[];
  language: 'zh' | 'en';
  localizePath: (path: string) => string;
}) {
  if (!links.length) {
    return null;
  }

  return (
    <div className="flex flex-wrap gap-2">
      {links.map((link, index) => {
        const route = String(link.route || '').trim();
        if (!route) {
          return null;
        }
        const label = dailyEvidenceLinkLabel(link.label, language);
        const prefix = language === 'en' ? 'Inspect evidence:' : '查看证据：';
        return (
          <Link
            key={`${route}-${label}-${index}`}
            to={localizePath(route)}
            className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-2.5 py-1 text-[11px] text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
          >
            {`${prefix}${label}`}
          </Link>
        );
      })}
    </div>
  );
}

function DailyIntelligenceBriefingSection({
  briefing,
  loading,
  error,
  language,
  localizePath,
}: {
  briefing: DailyIntelligenceResponse | null;
  loading: boolean;
  error: ParsedApiError | null;
  language: 'zh' | 'en';
  localizePath: (path: string) => string;
}) {
  const locale = language === 'en' ? 'en' : 'zh';

  const degradedBySection = briefing?.degradedInputs.reduce<Record<string, DailyIntelligenceResponse['degradedInputs']>>((acc, item) => {
    const key = item.section || 'unknown';
    acc[key] = acc[key] || [];
    acc[key].push(item);
    return acc;
  }, {}) ?? {};

  const emptyTextForSection = (section: keyof typeof DAILY_SECTION_LABELS) => {
    const degradedItems = degradedBySection[section] ?? [];
    if (degradedItems.length) {
      return degradedItems.map((item) => dailyReasonLabel(item.reason, locale)).join(locale === 'en' ? ' ' : '；');
    }
    return locale === 'en'
      ? `No ${dailySectionLabel(section, locale).toLowerCase()} in today's briefing.`
      : `今日简报暂无${dailySectionLabel(section, locale)}。`;
  };

  const summaryRows = briefing ? [
    {
      key: 'updated',
      label: locale === 'en' ? 'Updated' : '更新时间',
      value: formatDateTime(briefing.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
    },
    {
      key: 'session',
      label: locale === 'en' ? 'Session' : '时段',
      value: sessionLabel(briefing.sessionLabel, locale),
    },
    {
      key: 'regime',
      label: locale === 'en' ? 'Regime' : '市场状态',
      value: regimeLabel(briefing.marketRegimeSummary.regime, locale),
      detail: briefing.marketRegimeSummary.summary || '--',
    },
    {
      key: 'boundary',
      label: locale === 'en' ? 'Boundary' : '边界',
      value: briefing.observationOnly
        ? (locale === 'en' ? 'Observation-only' : '仅观察')
        : '--',
      detail: briefing.decisionGrade
        ? (locale === 'en' ? 'Decision-grade enabled.' : '允许决策级判断。')
        : (locale === 'en' ? 'Not decision-grade.' : '不构成决策级结论。'),
    },
  ] : [];

  const sectionLinksFor = (section: string) => (
    briefing?.sectionLinks.filter((link) => link.section === section && link.route) ?? []
  );

  const renderPriorityItems = () => {
    if (!briefing?.topResearchPriorities.length) {
      return (
        <TerminalEmptyState title={locale === 'en' ? 'Research priorities not ready' : '研究优先级暂未形成'}>
          {emptyTextForSection('topResearchPriorities')}
        </TerminalEmptyState>
      );
    }

    return (
      <div className="space-y-3">
        {briefing.topResearchPriorities.map((item, index) => (
          <div key={`${item.ticker || item.label || 'priority'}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                  {item.ticker || item.label || (locale === 'en' ? 'Research queue item' : '研究队列条目')}
                </div>
                <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  {(item.observations ?? []).join(locale === 'en' ? ' · ' : '；') || item.label || '--'}
                </div>
              </div>
              {item.priority ? <StatusBadge status={statusTone(item.priority)} label={humanizeEnum(item.priority, locale)} size="sm" /> : null}
            </div>
            <div className="mt-3 space-y-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
              <div>
                <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Verify next: ' : '下一步验证：'}</span>
                {(item.whatToVerify ?? []).join(locale === 'en' ? ' · ' : '；') || '--'}
              </div>
              <div>
                <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Evidence gap: ' : '证据缺口：'}</span>
                {(item.evidenceGaps ?? []).map((gap) => dailyReasonLabel(gap, locale)).join(locale === 'en' ? ' · ' : '；') || '--'}
              </div>
            </div>
            <div className="mt-3">
              <EvidenceLinkStrip
                links={item.evidenceLinks ?? []}
                language={locale}
                localizePath={localizePath}
              />
            </div>
          </div>
        ))}
      </div>
    );
  };

  const renderHighlightItems = (
    items: Array<{
      ticker?: string | null;
      title?: string | null;
      priority?: string | null;
      structureState?: string | null;
      confidence?: string | null;
      whyWatching?: string | null;
      observations?: string[];
      whatToVerify?: string[];
      evidenceGaps?: string[];
      riskFlags?: string[];
      watchNext?: string[];
      missingEvidence?: string[];
    }>,
    section: 'scannerHighlights' | 'watchlistHighlights' | 'portfolioStructureHighlights',
  ) => {
    if (!items.length) {
      return (
        <TerminalEmptyState title={locale === 'en' ? 'Section pending' : '该部分暂未形成'}>
          {emptyTextForSection(section)}
        </TerminalEmptyState>
      );
    }

    return (
      <div className="space-y-3">
        {items.map((item, index) => (
          <div key={`${item.ticker || item.title || section}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
            <div className="flex flex-wrap items-center justify-between gap-3">
              <div className="min-w-0">
                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                  {item.ticker || item.title || '--'}
                </div>
                <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                  {item.whyWatching
                    || (item.observations ?? []).join(locale === 'en' ? ' · ' : '；')
                    || (item.watchNext ?? []).join(locale === 'en' ? ' · ' : '；')
                    || '--'}
                </div>
              </div>
              <div className="flex flex-wrap gap-2">
                {item.priority ? <StatusBadge status={statusTone(item.priority)} label={humanizeEnum(item.priority, locale)} size="sm" /> : null}
                {item.structureState ? <TerminalChip variant="info">{humanizeEnum(item.structureState, locale)}</TerminalChip> : null}
                {item.confidence ? <TerminalChip variant="neutral">{confidenceLabel(item.confidence, locale)}</TerminalChip> : null}
              </div>
            </div>
            <div className="mt-3 space-y-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
              {item.whatToVerify?.length ? (
                <div>
                  <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Verify next: ' : '下一步验证：'}</span>
                  {item.whatToVerify.join(locale === 'en' ? ' · ' : '；')}
                </div>
              ) : null}
              {item.watchNext?.length ? (
                <div>
                  <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Watch next: ' : '下一步观察：'}</span>
                  {item.watchNext.join(locale === 'en' ? ' · ' : '；')}
                </div>
              ) : null}
              {item.riskFlags?.length ? (
                <div>
                  <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Risk flags: ' : '风险标记：'}</span>
                  {item.riskFlags.map((flag) => dailyReasonLabel(flag, locale)).join(locale === 'en' ? ' · ' : '；')}
                </div>
              ) : null}
              {(item.evidenceGaps?.length || item.missingEvidence?.length) ? (
                <div>
                  <span className="text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Evidence gaps: ' : '证据缺口：'}</span>
                  {[...(item.evidenceGaps ?? []), ...(item.missingEvidence ?? [])]
                    .map((gap) => dailyReasonLabel(gap, locale))
                    .join(locale === 'en' ? ' · ' : '；')}
                </div>
              ) : null}
            </div>
            <div className="mt-3">
              <EvidenceLinkStrip
                links={item.evidenceLinks ?? []}
                language={locale}
                localizePath={localizePath}
              />
            </div>
          </div>
        ))}
      </div>
    );
  };

  return (
    <div className="border-b border-[color:var(--wolfy-divider)] p-3">
      <RoughSectionCard
        eyebrow={locale === 'en' ? 'Daily intelligence' : '日度情报'}
        title={locale === 'en' ? 'Daily research briefing' : '每日研究简报'}
        data-testid="daily-intelligence-briefing"
      >
        {loading && !briefing ? (
          <TerminalEmptyState title={locale === 'en' ? 'Preparing daily briefing' : '正在整理日度简报'}>
            {locale === 'en'
              ? 'The rest of the cockpit can load first; this section will attach the daily research readout when ready.'
              : '其他驾驶舱区块可以先显示；本区会在简报就绪后自动补齐。'}
          </TerminalEmptyState>
        ) : null}
        {!loading && error && !briefing ? (
          <TerminalEmptyState title={error.title || (locale === 'en' ? 'Daily briefing unavailable' : '日度简报暂不可用')}>
            {error.message || (locale === 'en'
              ? 'Retry after the briefing endpoint responds again.'
              : '请在简报接口恢复后重试。')}
          </TerminalEmptyState>
        ) : null}
        {briefing ? (
          <div className="space-y-3">
            {error ? (
              <TerminalEmptyState title={locale === 'en' ? 'Briefing refresh delayed' : '简报刷新稍有延迟'}>
                {error.message || (locale === 'en'
                  ? 'Showing the last successful daily briefing while refresh catches up.'
                  : '当前先展示上一次成功的简报，刷新完成后会自动更新。')}
              </TerminalEmptyState>
            ) : null}
            <div className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div className="min-w-0">
                  <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                    {briefing.marketRegimeSummary.summary || (locale === 'en' ? 'Daily market regime readout.' : '今日日度市场状态摘要。')}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-2">
                    <StatusBadge
                      status={statusTone(briefing.marketRegimeSummary.confidence)}
                      label={`${locale === 'en' ? 'Confidence' : '置信度'} · ${confidenceLabel(briefing.marketRegimeSummary.confidence, locale)}`}
                      size="sm"
                    />
                    <TerminalChip variant="info">
                      {briefing.observationOnly
                        ? (locale === 'en' ? 'Observation-only briefing' : '仅观察简报')
                        : '--'}
                    </TerminalChip>
                    <TerminalChip variant={briefing.decisionGrade ? 'success' : 'caution'}>
                      {briefing.decisionGrade
                        ? (locale === 'en' ? 'Decision-grade enabled' : '允许决策级判断')
                        : (locale === 'en' ? 'Not decision-grade' : '非决策级')}
                    </TerminalChip>
                    {briefing.sessionLabel ? <TerminalChip variant="neutral">{sessionLabel(briefing.sessionLabel, locale)}</TerminalChip> : null}
                  </div>
                </div>
              </div>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              <BriefingBlock
                eyebrow={dailySectionLabel('marketRegimeSummary', locale)}
                title={locale === 'en' ? 'Regime evidence and invalidation' : '状态证据与失效观察'}
              >
                <RoughKeyValueRows rows={summaryRows} />
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div>
                    <div className="text-xs text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Supporting observations' : '支持观察'}</div>
                    <RoughBulletList
                      items={(briefing.marketRegimeSummary.supportingObservations ?? []).map((item) => item)}
                      emptyText={locale === 'en' ? 'No supporting observations yet.' : '暂未补充支持观察。'}
                      className="mt-2"
                    />
                  </div>
                  <div>
                    <div className="text-xs text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Invalidation observations' : '失效观察'}</div>
                    <RoughBulletList
                      items={(briefing.marketRegimeSummary.invalidationObservations ?? []).map((item) => item)}
                      emptyText={locale === 'en' ? 'No invalidation observations yet.' : '暂未补充失效观察。'}
                      className="mt-2"
                    />
                  </div>
                </div>
              </BriefingBlock>
              <BriefingBlock
                eyebrow={dailySectionLabel('whatChanged', locale)}
                title={locale === 'en' ? 'What changed and why it is on today’s queue' : '今日变化与当日研究线索'}
              >
                <RoughBulletList
                  items={(briefing.whatChanged ?? []).map((item) => item)}
                  emptyText={emptyTextForSection('whatChanged')}
                />
              </BriefingBlock>
            </div>
            <div className="grid gap-3 xl:grid-cols-2">
              <BriefingBlock
                eyebrow={dailySectionLabel('topResearchPriorities', locale)}
                title={locale === 'en' ? 'Top research priorities' : '研究优先级'}
                footer={(
                  <EvidenceLinkStrip
                    links={sectionLinksFor('topResearchPriorities')}
                    language={locale}
                    localizePath={localizePath}
                  />
                )}
              >
                {renderPriorityItems()}
              </BriefingBlock>
              <BriefingBlock
                eyebrow={dailySectionLabel('scenarioRisks', locale)}
                title={locale === 'en' ? 'Scenario risks and evidence gaps' : '情景风险与证据缺口'}
              >
                <RoughBulletList
                  items={(briefing.scenarioRisks ?? []).map((item, index) => (
                    <span key={`${item.label || 'scenario'}-${index}`}>
                      <span className="text-[color:var(--wolfy-text-primary)]">
                        {item.label && item.label.toLowerCase() === 'scenario risk section unavailable'
                          ? (locale === 'en' ? 'Scenario risk section unavailable' : '情景风险区块暂不可用')
                          : (item.label || (locale === 'en' ? 'Scenario risk observation' : '情景风险观察'))}
                      </span>
                      {(item.observations ?? []).length
                        ? `: ${(item.observations ?? []).join(locale === 'en' ? ' · ' : '；')}`
                        : ''}
                    </span>
                  ))}
                  emptyText={emptyTextForSection('scenarioRisks')}
                />
                <div className="mt-3 flex flex-wrap gap-2">
                  {(briefing.evidenceGaps ?? []).length
                    ? (briefing.evidenceGaps ?? []).map((gap, index) => (
                      <TerminalChip key={`${gap}-${index}`} variant="caution">
                        {dailyReasonLabel(gap, locale)}
                      </TerminalChip>
                    ))
                    : <TerminalChip variant="success">{locale === 'en' ? 'No aggregate evidence gap' : '暂无汇总证据缺口'}</TerminalChip>}
                </div>
              </BriefingBlock>
            </div>
            <div className="grid gap-3 xl:grid-cols-3">
              <BriefingBlock
                eyebrow={dailySectionLabel('scannerHighlights', locale)}
                title={locale === 'en' ? 'Scanner highlights' : '扫描重点'}
                footer={(
                  <EvidenceLinkStrip
                    links={sectionLinksFor('scannerHighlights')}
                    language={locale}
                    localizePath={localizePath}
                  />
                )}
              >
                {renderHighlightItems(briefing.scannerHighlights, 'scannerHighlights')}
              </BriefingBlock>
              <BriefingBlock
                eyebrow={dailySectionLabel('watchlistHighlights', locale)}
                title={locale === 'en' ? 'Watchlist highlights' : '观察列表重点'}
                footer={(
                  <EvidenceLinkStrip
                    links={sectionLinksFor('watchlistHighlights')}
                    language={locale}
                    localizePath={localizePath}
                  />
                )}
              >
                {renderHighlightItems(briefing.watchlistHighlights, 'watchlistHighlights')}
              </BriefingBlock>
              <BriefingBlock
                eyebrow={dailySectionLabel('portfolioStructureHighlights', locale)}
                title={locale === 'en' ? 'Portfolio structure highlights' : '持仓结构重点'}
                footer={(
                  <EvidenceLinkStrip
                    links={sectionLinksFor('portfolioStructureHighlights')}
                    language={locale}
                    localizePath={localizePath}
                  />
                )}
              >
                {renderHighlightItems(briefing.portfolioStructureHighlights, 'portfolioStructureHighlights')}
              </BriefingBlock>
            </div>
            <BriefingBlock
              eyebrow={dailySectionLabel('degradedInputs', locale)}
              title={locale === 'en' ? 'Availability notes' : '可用性提醒'}
            >
              <RoughBulletList
                items={(briefing.degradedInputs ?? []).map((item, index) => (
                  <span key={`${item.section || 'degraded'}-${index}`}>
                    <span className="text-[color:var(--wolfy-text-primary)]">
                      {dailySectionLabel(item.section, locale)}
                    </span>
                    {`: ${humanizeEnum(item.status, locale)} · ${dailyReasonLabel(item.reason, locale)}`}
                  </span>
                ))}
                emptyText={locale === 'en' ? 'All daily briefing sections are available.' : '今日简报各部分均可用。'}
              />
            </BriefingBlock>
          </div>
        ) : null}
      </RoughSectionCard>
    </div>
  );
}

function sortDriverScores(payload: MarketDecisionCockpitResponse['marketRegimeDecision']['driverScores']) {
  return Object.entries(payload || {})
    .sort(([, left], [, right]) => (right?.score ?? 0) - (left?.score ?? 0));
}

export default function MarketDecisionCockpitPage() {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';
  const location = useLocation();
  const routeLocale = parseLocaleFromPathname(location.pathname);
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const [data, setData] = useState<MarketDecisionCockpitResponse | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [dailyIntelligence, setDailyIntelligence] = useState<DailyIntelligenceResponse | null>(null);
  const [dailyIntelligenceLoading, setDailyIntelligenceLoading] = useState(true);
  const [dailyIntelligenceError, setDailyIntelligenceError] = useState<ParsedApiError | null>(null);

  const loadCockpit = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await marketDecisionCockpitApi.getDecisionCockpit();
      setData(response);
    } catch (err) {
      setError(getParsedApiError(err) || createLocalizedApiError(locale, {
        en: 'Market decision cockpit unavailable',
        zh: '市场决策驾驶舱暂不可用',
      }, {
        en: 'Please retry after the API becomes available.',
        zh: '请在接口恢复后重试。',
      }));
    } finally {
      setLoading(false);
    }
  }, [locale]);

  const loadDailyIntelligence = useCallback(async () => {
    setDailyIntelligenceLoading(true);
    setDailyIntelligenceError(null);
    try {
      const response = await dailyIntelligenceApi.getDailyIntelligence();
      setDailyIntelligence(response);
    } catch (err) {
      setDailyIntelligenceError(getParsedApiError(err) || createLocalizedApiError(locale, {
        en: 'Daily briefing unavailable',
        zh: '日度简报暂不可用',
      }, {
        en: 'The rest of the cockpit remains available while the daily briefing catches up.',
        zh: '其余驾驶舱内容仍可使用，日度简报恢复后会自动补齐。',
      }));
    } finally {
      setDailyIntelligenceLoading(false);
    }
  }, [locale]);

  const load = useCallback(() => {
    void loadCockpit();
    void loadDailyIntelligence();
  }, [loadCockpit, loadDailyIntelligence]);

  useEffect(() => {
    load();
  }, [load]);

  const driverRows = useMemo(
    () => sortDriverScores(data?.marketRegimeDecision.driverScores).map(([key, value]) => ({
      key,
      label: labelFromKey(key, locale),
      value: value?.score ?? '--',
      meta: value?.reasons?.join(' · ')
        || (value?.evidenceState ? dailyReasonLabel(value.evidenceState, locale) : null)
        || (locale === 'en' ? 'Observation signal' : '观察信号'),
      badge: value?.evidenceState
        ? {
          label: humanizeEnum(value.evidenceState, locale),
          variant: value.evidenceState === 'unavailable' ? ('caution' as const) : ('info' as const),
        }
        : undefined,
    })),
    [data?.marketRegimeDecision.driverScores, locale],
  );

  const previewCandidates = data?.researchQueuePreview.topCandidates ?? [];
  const cockpitSummary = data?.cockpitSummary;
  const priorities = data?.marketRegimeDecision.researchPriorities;
  const optionsStatus = data?.optionsStructureStatus;

  return (
    <ConsumerWorkspaceScope className="flex min-h-0 flex-1">
      <ConsumerWorkspacePageShell className="flex min-h-0 flex-1 flex-col gap-4 md:gap-6">
        <ResearchConsoleShell
          className="flex-1"
          command={(
            <WolfyCommandBar
              leading={<span className="text-xs text-[color:var(--wolfy-text-muted)]">{locale === 'en' ? 'Market Structure / Cockpit' : '市场结构 / 驾驶舱'}</span>}
              trailing={(
                <div className="flex flex-wrap items-center gap-2">
                  <Link
                    to={localize('/research/radar')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Research radar' : '研究雷达'}
                  </Link>
                  <Link
                    to={localize('/scenario-lab')}
                    className="rounded-md border border-[color:var(--wolfy-border-subtle)] px-3 py-1.5 text-xs text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                  >
                    {locale === 'en' ? 'Scenario lab' : '情景实验室'}
                  </Link>
                  <TerminalButton variant="compact" onClick={() => void load()}>
                    {locale === 'en' ? 'Refresh' : '刷新'}
                  </TerminalButton>
                </div>
              )}
            >
              <div className="text-xs text-[color:var(--wolfy-text-secondary)]">
                {locale === 'en' ? 'Primary market-structure entry for regime, queue, confidence limits, and observation-only gamma context.' : '市场结构主入口，集中呈现状态、队列、置信边界与仅观察 Gamma 语境。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Summary' : '摘要'} title={locale === 'en' ? 'What changed' : '发生了什么'}>
                <RoughBulletList
                  items={(cockpitSummary?.whatChanged ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No change summary yet.' : '暂未整理变化摘要。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Boundary' : '边界'} title={locale === 'en' ? 'Confidence limits' : '置信边界'}>
                <RoughBulletList
                  items={(cockpitSummary?.confidenceLimits ?? []).map((item) => item)}
                  emptyText={locale === 'en' ? 'No explicit confidence limit yet.' : '暂未整理明确的置信边界。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Observation-only note' : '观察型说明'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {data?.noAdviceDisclosure || (locale === 'en'
                    ? 'Research context only.'
                    : '仅供研究语境参考。')}
                </p>
              </RoughSectionCard>
            </ConsoleContextRail>
          )}
        >
          <ConsoleBoard className="min-h-0" data-testid="market-decision-cockpit-page">
            <RoughSurfaceIntro
              eyebrow={locale === 'en' ? 'Market decision cockpit' : '市场决策驾驶舱'}
              title={locale === 'en' ? 'Market structure, positioning context, and research queue' : '市场结构、定位语境与研究队列'}
              description={locale === 'en'
                ? 'This surface is the first-stop cockpit for reading the current market backdrop, evidence quality, and what deserves research attention next.'
                : '这个页面是新版研究工作流的第一站，用于阅读当前市场背景、证据质量和下一步研究关注点。'}
            />
            <DailyIntelligenceBriefingSection
              briefing={dailyIntelligence}
              loading={dailyIntelligenceLoading}
              error={dailyIntelligenceError}
              language={locale}
              localizePath={localize}
            />
            {error ? (
              <div className="p-4 md:p-5">
                <ApiErrorAlert
                  error={error}
                  actionLabel={locale === 'en' ? 'Retry' : '重试'}
                  onAction={() => void load()}
                />
              </div>
            ) : null}
            {loading && !data ? (
              <div className="p-4 md:p-5">
                <TerminalEmptyState title={locale === 'en' ? 'Loading market frame' : '正在整理市场框架'}>
                  {locale === 'en' ? 'The page is waiting for market regime, queue preview, and options observation status.' : '正在等待市场状态、研究队列预览与期权观察状态。'}
                </TerminalEmptyState>
              </div>
            ) : null}
            {data ? (
              <>
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Updated' : '更新时间',
                      value: formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
                    },
                    {
                      label: locale === 'en' ? 'Data quality' : '数据质量',
                      value: <StatusBadge status={statusTone(data.dataQuality?.status)} label={humanizeEnum(data.dataQuality?.status, locale)} size="sm" />,
                    },
                    {
                      label: locale === 'en' ? 'Preview mode' : '预览模式',
                      value: data.researchQueuePreview.previewOnly ? (locale === 'en' ? 'Preview only' : '仅预览') : '--',
                    },
                  ]}
                />
                <MetricStrip
                  items={[
                    {
                      key: 'regime',
                      label: locale === 'en' ? 'Regime' : '市场状态',
                      value: regimeLabel(data.marketRegimeDecision.regime, locale),
                    },
                    {
                      key: 'confidence',
                      label: locale === 'en' ? 'Confidence' : '置信度',
                      value: confidenceLabel(data.marketRegimeDecision.confidence, locale),
                    },
                    {
                      key: 'queue',
                      label: locale === 'en' ? 'Queue quality' : '队列质量',
                      value: humanizeEnum(data.researchQueuePreview.queueQuality, locale),
                    },
                  ]}
                />
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Drivers' : '驱动'} title={locale === 'en' ? 'Driver scores' : '驱动评分'}>
                    <RoughScoreRows
                      items={driverRows}
                      emptyText={locale === 'en' ? 'No driver scores yet.' : '暂无驱动评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Regime logic' : '状态逻辑'} title={locale === 'en' ? 'Why this regime' : '为什么形成当前状态'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'why',
                          label: locale === 'en' ? 'Why this regime' : '形成原因',
                          value: (data.marketRegimeDecision.explanation?.whyThisRegime ?? []).join('；') || '--',
                        },
                        {
                          key: 'confirm',
                          label: locale === 'en' ? 'What confirms it' : '确认信号',
                          value: (data.marketRegimeDecision.explanation?.whatConfirmsIt ?? []).join('；') || '--',
                        },
                        {
                          key: 'invalidate',
                          label: locale === 'en' ? 'What invalidates it' : '失效观察',
                          value: (data.marketRegimeDecision.invalidationConditions ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Next steps' : '下一步'} title={locale === 'en' ? 'What to watch and verify' : '关注点与验证项'}>
                    <RoughKeyValueRows
                      rows={[
                        {
                          key: 'watch',
                          label: locale === 'en' ? 'What to watch' : '今日关注',
                          value: (cockpitSummary?.whatToWatch ?? priorities?.watchToday ?? []).join('；') || '--',
                        },
                        {
                          key: 'evidence',
                          label: locale === 'en' ? 'Needs more evidence' : '待补证据',
                          value: (priorities?.needsMoreEvidence ?? data.researchQueuePreview.evidenceGaps ?? [])
                            .map((item) => dailyReasonLabel(item, locale))
                            .join('；') || '--',
                        },
                        {
                          key: 'next',
                          label: locale === 'en' ? 'Investigate next' : '下一步研究',
                          value: (priorities?.investigateNext ?? []).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Options / gamma' : '期权 / Gamma'} title={locale === 'en' ? 'Observation-only status' : '仅观察状态'}>
                    {(() => {
                      const blockedReasonLabels = sanitizeUserFacingDataIssues(optionsStatus?.blockedReasonCodes ?? [], locale);
                      const missingEvidenceLabels = consumerMissingEvidenceLabels(optionsStatus?.missingEvidence, locale);
                      return (
                        <>
                          <RoughKeyValueRows
                            rows={[
                              {
                                key: 'gamma',
                                label: locale === 'en' ? 'Gamma evidence' : 'Gamma 证据',
                                value: optionsStatus?.gammaEvidenceStatus
                                  ? sanitizeUserFacingDataIssue(optionsStatus.gammaEvidenceStatus, locale)
                                  : '--',
                              },
                              {
                                key: 'observation',
                                label: locale === 'en' ? 'Research boundary' : '研究边界',
                                value: consumerOptionsBoundaryLabel(optionsStatus?.observationOnly, locale),
                              },
                              {
                                key: 'decision-grade',
                                label: locale === 'en' ? 'Decision grade' : '判断等级',
                                value: consumerDecisionGradeLabel(optionsStatus?.decisionGrade, locale),
                              },
                              {
                                key: 'blocked',
                                label: locale === 'en' ? 'Blocked reasons' : '阻塞原因',
                                value: blockedReasonLabels.join(locale === 'en' ? ' ; ' : '；') || '--',
                              },
                            ]}
                          />
                          <div className="mt-3 flex flex-wrap gap-2">
                            {missingEvidenceLabels.map((label, index) => (
                              <TerminalChip key={`${label}-${index}`} variant="caution">
                                {label || (locale === 'en' ? 'Missing evidence' : '缺失证据')}
                              </TerminalChip>
                            ))}
                          </div>
                        </>
                      );
                    })()}
                  </RoughSectionCard>
                </div>
                <div className="border-t border-[color:var(--wolfy-divider)] p-3">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Research queue' : '研究队列'} title={locale === 'en' ? 'Queue preview' : '队列预览'}>
                    {previewCandidates.length ? (
                      <div className="space-y-3">
                        {previewCandidates.map((candidate, index) => (
                          <div key={`${candidate.ticker || candidate.symbol || 'candidate'}-${index}`} className="rounded-xl border border-[color:var(--wolfy-divider)] bg-black/10 p-3">
                            <div className="flex flex-wrap items-center justify-between gap-3">
                              <div>
                                <div className="text-sm font-medium text-[color:var(--wolfy-text-primary)]">
                                  {candidate.ticker || candidate.symbol || '--'}
                                </div>
                                <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                                  {(candidate.whyOnRadar ?? []).join('；') || (locale === 'en' ? 'Research queue preview item.' : '研究队列预览条目。')}
                                </div>
                              </div>
                              <div className="flex flex-wrap items-center gap-2">
                                {candidate.priority ? <StatusBadge status={statusTone(candidate.priority)} label={humanizeEnum(candidate.priority, locale)} size="sm" /> : null}
                                {candidate.researchBias ? <TerminalChip variant="info">{humanizeEnum(candidate.researchBias, locale)}</TerminalChip> : null}
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : (
                      <TerminalEmptyState title={locale === 'en' ? 'Queue preview unavailable' : '队列预览暂不可用'}>
                        {locale === 'en' ? 'Use this area for top candidates, evidence gaps, and degraded queue notes.' : '这里用于展示重点候选、证据缺口与降级说明。'}
                      </TerminalEmptyState>
                    )}
                  </RoughSectionCard>
                </div>
              </>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
