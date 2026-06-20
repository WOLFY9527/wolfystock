import { useCallback, useEffect, useMemo, useState, type ReactNode } from 'react';
import { Link, useLocation } from 'react-router-dom';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { ConsumerOnboardingCtaPanel } from '../components/common/ConsumerOnboardingCtaPanel';
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
  buildMarketDecisionCockpitNarrative,
  getCockpitConsumerStatusLabel,
  getDriverEvidenceStateLabel,
} from '../utils/marketDecisionCockpitNarrative';
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

const FORBIDDEN_CONSUMER_WORDING = /建议(买入|卖出|加仓|减仓|持有)|买入|卖出|下单|立即交易|立即买入|交易建议|投资建议|止损|止盈|目标价|目标位|目标区间|仓位建议|必买|稳赚|保证收益|\b(buy now|sell now|buy|sell|hold|place order|submit order|trade recommendation|trading advice|investment advice|recommended trade|strategy recommendation|ai recommends you buy|best contract|guaranteed return|guaranteed|take profit|stop loss|target price|target|stop|position sizing|live trading|execution ready)\b/i;

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
    return language === 'en' ? 'Structured research context' : '结构化研究语境';
  }
  return language === 'en' ? 'Research context only' : '仅作研究语境';
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
      return sanitizeCockpitStatusOrIssue(value, language) || '--';
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
      return sanitizeCockpitStatusOrIssue(value, language) || '--';
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

function sanitizeCockpitDisplayItems(
  items: Array<string | null | undefined>,
  language: 'zh' | 'en',
): string[] {
  const seen = new Set<string>();
  const labels: string[] = [];
  items.forEach((item) => {
    const raw = String(item || '').trim();
    if (!raw) {
      return;
    }
    const label = FORBIDDEN_CONSUMER_WORDING.test(raw)
      ? (language === 'en' ? 'Review after evidence is refreshed.' : '等待证据刷新后再复核。')
      : sanitizeCockpitStatusOrIssue(raw, language);
    if (!label || seen.has(label)) {
      return;
    }
    seen.add(label);
    labels.push(label);
  });
  return labels;
}

function pushUniqueLabel(target: string[], label: string | null | undefined, limit = Number.POSITIVE_INFINITY) {
  const normalized = String(label || '').trim();
  if (!normalized || target.includes(normalized) || target.length >= limit) {
    return;
  }
  target.push(normalized);
}

function pushSanitizedLabels(
  target: string[],
  items: Array<string | null | undefined> | null | undefined,
  language: 'zh' | 'en',
  limit = Number.POSITIVE_INFINITY,
) {
  sanitizeCockpitDisplayItems(items ?? [], language).forEach((item) => pushUniqueLabel(target, item, limit));
}

function pushDailyReasonLabels(
  target: string[],
  items: Array<string | null | undefined> | null | undefined,
  language: 'zh' | 'en',
  limit = Number.POSITIVE_INFINITY,
) {
  (items ?? []).forEach((item) => pushUniqueLabel(target, dailyReasonLabel(item, language), limit));
}

function normalizeCockpitStatusToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[:=./\\\s-]+/g, '_')
    .replace(/_+/g, '_')
    .replace(/^_+|_+$/g, '');
}

function isCockpitStatusToken(value: string | null | undefined): boolean {
  const raw = String(value || '').trim();
  if (!raw || /\s/.test(raw)) {
    return false;
  }
  const normalized = normalizeCockpitStatusToken(raw);
  return [
    'unavailable',
    'stale',
    'proxy',
    'proxy_only',
    'pending',
    'pending_heavy',
    'blocked',
    'low_confidence',
    'score_grade',
    'freshness_unavailable',
    'degraded',
  ].includes(normalized);
}

function sanitizeCockpitStatusOrIssue(value: string | null | undefined, language: 'zh' | 'en'): string {
  return isCockpitStatusToken(value)
    ? getCockpitConsumerStatusLabel(value, language)
    : sanitizeUserFacingDataIssue(value, language);
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

function CockpitFirstViewportSummary({
  data,
  briefing,
  loading,
  dailyLoading,
  narrativeSentences,
}: {
  data: MarketDecisionCockpitResponse | null;
  briefing: DailyIntelligenceResponse | null;
  loading: boolean;
  dailyLoading: boolean;
  narrativeSentences: string[];
}) {
  const { language } = useI18n();
  const locale = language === 'en' ? 'en' : 'zh';

  const summary = useMemo(() => {
    const whatHappened: string[] = [];
    const whatMatters: string[] = [];
    const nextChecks: string[] = [];
    const missingData: string[] = [];

    pushSanitizedLabels(whatHappened, briefing?.whatChanged, locale, 3);
    pushSanitizedLabels(whatHappened, data?.cockpitSummary?.whatChanged, locale, 3);
    pushSanitizedLabels(whatHappened, narrativeSentences.slice(0, 1), locale, 3);

    pushSanitizedLabels(whatMatters, briefing?.marketRegimeSummary?.supportingObservations, locale, 3);
    pushSanitizedLabels(whatMatters, data?.cockpitSummary?.whyItMatters, locale, 3);
    pushSanitizedLabels(whatMatters, data?.marketRegimeDecision?.explanation?.whyThisRegime, locale, 3);
    (briefing?.topResearchPriorities ?? []).forEach((item) => {
      const subject = item.ticker || item.label || '';
      const observation = sanitizeCockpitDisplayItems(item.observations ?? [], locale)[0]
        || sanitizeCockpitDisplayItems(item.whatToVerify ?? [], locale)[0];
      if (subject && observation) {
        pushUniqueLabel(whatMatters, `${subject}: ${observation}`, 3);
      }
    });

    (briefing?.topResearchPriorities ?? []).forEach((item) => pushSanitizedLabels(nextChecks, item.whatToVerify, locale, 3));
    pushSanitizedLabels(nextChecks, data?.marketRegimeDecision?.researchPriorities?.watchToday, locale, 3);
    pushSanitizedLabels(nextChecks, data?.marketRegimeDecision?.researchPriorities?.investigateNext, locale, 3);
    (data?.researchQueuePreview?.topCandidates ?? []).forEach((candidate) => pushSanitizedLabels(nextChecks, candidate.whatToVerify, locale, 3));
    pushSanitizedLabels(nextChecks, briefing?.firstRunChecklist, locale, 3);
    pushSanitizedLabels(nextChecks, briefing?.starterResearchWorkflow, locale, 3);

    pushDailyReasonLabels(missingData, briefing?.degradedInputs.map((item) => item.reason), locale, 3);
    pushDailyReasonLabels(missingData, briefing?.evidenceGaps, locale, 3);
    (briefing?.topResearchPriorities ?? []).forEach((item) => pushDailyReasonLabels(missingData, item.evidenceGaps, locale, 3));
    (briefing?.scannerHighlights ?? []).forEach((item) => pushDailyReasonLabels(missingData, item.evidenceGaps, locale, 3));
    (briefing?.watchlistHighlights ?? []).forEach((item) => pushDailyReasonLabels(missingData, item.evidenceGaps, locale, 3));
    (briefing?.portfolioStructureHighlights ?? []).forEach((item) => pushDailyReasonLabels(missingData, item.missingEvidence, locale, 3));
    pushSanitizedLabels(missingData, data?.dataQuality?.reasonCodes, locale, 3);
    pushSanitizedLabels(missingData, data?.researchQueuePreview?.degradedState?.reasonCodes, locale, 3);
    pushSanitizedLabels(missingData, data?.researchQueuePreview?.evidenceGaps, locale, 3);
    consumerMissingEvidenceLabels(data?.optionsStructureStatus?.missingEvidence, locale)
      .forEach((item) => pushUniqueLabel(missingData, item, 3));
    pushSanitizedLabels(missingData, data?.optionsStructureStatus?.blockedReasonCodes, locale, 3);

    const headline = briefing?.marketRegimeSummary?.summary
      || data?.cockpitSummary?.whatChanged?.[0]
      || narrativeSentences[0]
      || (locale === 'en'
        ? 'The research packet is still assembling market context.'
        : '研究包正在整理当前市场语境。');

    return {
      headline: sanitizeCockpitDisplayItems([headline], locale)[0] || headline,
      whatHappened,
      whatMatters,
      nextChecks,
      missingData,
    };
  }, [briefing, data, locale, narrativeSentences]);

  if (loading && dailyLoading && !data && !briefing) {
    return (
      <div className="border-b border-[color:var(--wolfy-divider)] p-3">
        <RoughSectionCard
          eyebrow={locale === 'en' ? 'Research state' : '研究状态'}
          title={locale === 'en' ? 'Preparing market context' : '正在整理市场语境'}
          data-testid="decision-cockpit-first-viewport-summary"
        >
          <TerminalEmptyState title={locale === 'en' ? 'Loading research packet' : '正在载入研究包'}>
            {locale === 'en'
              ? 'The page is collecting the latest market frame and next research checks.'
              : '页面正在收集最新市场框架与下一步研究检查。'}
          </TerminalEmptyState>
        </RoughSectionCard>
      </div>
    );
  }

  return (
    <div className="border-b border-[color:var(--wolfy-divider)] p-3">
      <RoughSectionCard
        eyebrow={locale === 'en' ? 'Research state' : '研究状态'}
        title={locale === 'en' ? 'What happened, what matters, what to check next' : '发生了什么、为什么重要、下一步查什么'}
        data-testid="decision-cockpit-first-viewport-summary"
      >
        <div className="space-y-4">
          <p className="text-base leading-7 text-[color:var(--wolfy-text-primary)]">{summary.headline}</p>
          <div className="grid gap-3 xl:grid-cols-3">
            <BriefingBlock
              eyebrow={locale === 'en' ? 'What happened' : '发生了什么'}
              title={locale === 'en' ? 'Latest readout' : '最新读数'}
            >
              <RoughBulletList
                items={summary.whatHappened}
                emptyText={locale === 'en' ? 'No market change has been summarized yet.' : '暂未整理出市场变化摘要。'}
              />
            </BriefingBlock>
            <BriefingBlock
              eyebrow={locale === 'en' ? 'What matters' : '为什么重要'}
              title={locale === 'en' ? 'Useful context already available' : '已有可用语境'}
            >
              <RoughBulletList
                items={summary.whatMatters}
                emptyText={locale === 'en' ? 'Useful market context is still thin.' : '当前可用市场语境仍偏薄。'}
              />
            </BriefingBlock>
            <BriefingBlock
              eyebrow={locale === 'en' ? 'Check next' : '下一步检查'}
              title={locale === 'en' ? 'Research checks' : '研究检查'}
            >
              <RoughBulletList
                items={summary.nextChecks}
                emptyText={locale === 'en' ? 'No specific next check is ready yet.' : '暂未形成明确下一步检查。'}
              />
            </BriefingBlock>
          </div>
          {summary.missingData.length ? (
            <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-black/10 p-3" data-testid="decision-cockpit-missing-summary">
              <div className="text-xs font-medium text-[color:var(--wolfy-text-primary)]">
                {locale === 'en' ? 'What is still missing' : '仍需补齐的部分'}
              </div>
              <p className="mt-1 text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                {summary.missingData.join(locale === 'en' ? ' · ' : '；')}
              </p>
            </div>
          ) : null}
          <p className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
            {locale === 'en'
              ? 'Research context only; not an action instruction.'
              : '仅作研究语境，不构成操作指令。'}
          </p>
        </div>
      </RoughSectionCard>
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
        ? (locale === 'en' ? 'Research context only' : '仅作研究语境')
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
      evidenceLinks?: DailyIntelligenceEvidenceLink[];
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
      <details className="rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-black/5 p-3">
        <summary className="cursor-pointer text-sm font-medium text-[color:var(--wolfy-text-secondary)]">
          {locale === 'en' ? 'Daily briefing details and availability notes' : '日度简报明细与可用性说明'}
        </summary>
        <div className="mt-3">
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
              ? 'Retry after the briefing data is available again.'
              : '请在简报数据恢复后重试。')}
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
                        ? (locale === 'en' ? 'Research-context briefing' : '研究语境简报')
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
            <ConsumerOnboardingCtaPanel
              data-testid="daily-intelligence-onboarding-cta"
              language={locale}
              title={locale === 'en' ? 'Start with context, then choose one research path' : '先建立市场语境，再选择一个研究入口'}
              guidance={briefing.onboardingGuidance}
              actions={briefing.emptyStateActions}
              starterResearchWorkflow={briefing.starterResearchWorkflow}
              firstRunChecklist={briefing.firstRunChecklist}
              suggestedResearchEntrypoints={briefing.suggestedResearchEntrypoints}
              radarLabel={locale === 'en' ? 'Review Research Radar' : '查看研究雷达'}
            />
            <div className="grid gap-3 xl:grid-cols-2">
              <BriefingBlock
                eyebrow={dailySectionLabel('marketRegimeSummary', locale)}
                title={locale === 'en' ? 'Regime evidence and invalidation' : '状态证据与失效观察'}
              >
                <RoughKeyValueRows
                  emptyText={locale === 'en' ? 'No briefing summary available yet.' : '暂无简报摘要。'}
                  rows={summaryRows}
                />
                <div className="mt-3 grid gap-3 md:grid-cols-2">
                  <div>
                    <div className="text-xs text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Supporting observations' : '支持观察'}</div>
                    <RoughBulletList
                      items={sanitizeCockpitDisplayItems(briefing.marketRegimeSummary.supportingObservations ?? [], locale)}
                      emptyText={locale === 'en' ? 'No supporting observations yet.' : '暂未补充支持观察。'}
                      className="mt-2"
                    />
                  </div>
                  <div>
                    <div className="text-xs text-[color:var(--wolfy-text-secondary)]">{locale === 'en' ? 'Invalidation observations' : '失效观察'}</div>
                    <RoughBulletList
                      items={sanitizeCockpitDisplayItems(briefing.marketRegimeSummary.invalidationObservations ?? [], locale)}
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
                  items={sanitizeCockpitDisplayItems(briefing.whatChanged ?? [], locale)}
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
                title={locale === 'en' ? 'Scenario risks' : '情景风险'}
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
      </details>
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
        en: 'Please retry after the data becomes available.',
        zh: '请在数据恢复后重试。',
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
    () => sortDriverScores(data?.marketRegimeDecision.driverScores).map(([key, value]) => {
      const evidenceLabel = value?.evidenceState ? getDriverEvidenceStateLabel(value.evidenceState, locale) : null;
      const reasonLabels = sanitizeCockpitDisplayItems(value?.reasons ?? [], locale);
      return {
        key,
        label: labelFromKey(key, locale),
        value: value?.score ?? '--',
        meta: [evidenceLabel, ...reasonLabels].filter(Boolean).join(locale === 'en' ? ' · ' : '；')
          || (locale === 'en' ? 'Observation signal' : '观察信号'),
        badge: evidenceLabel
          ? {
            label: evidenceLabel,
            variant: value?.evidenceState === 'unavailable' ? ('caution' as const) : ('info' as const),
          }
          : undefined,
      };
    }),
    [data?.marketRegimeDecision.driverScores, locale],
  );

  const previewCandidates = data?.researchQueuePreview.topCandidates ?? [];
  const cockpitSummary = data?.cockpitSummary;
  const priorities = data?.marketRegimeDecision.researchPriorities;
  const optionsStatus = data?.optionsStructureStatus;
  const cockpitNarrative = useMemo(
    () => (data ? buildMarketDecisionCockpitNarrative(data, locale) : null),
    [data, locale],
  );
  const railChangeItems = useMemo(() => {
    const items = sanitizeCockpitDisplayItems(cockpitSummary?.whatChanged ?? [], locale);
    return items.length ? items : cockpitNarrative?.sentences.slice(0, 2) ?? [];
  }, [cockpitNarrative?.sentences, cockpitSummary?.whatChanged, locale]);
  const nextEvidenceItems = (priorities?.needsMoreEvidence?.length
    ? priorities.needsMoreEvidence
    : data?.researchQueuePreview.evidenceGaps) ?? [];

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
                {locale === 'en' ? 'Primary market-structure entry for the current backdrop, research queue, and next checks.' : '市场结构主入口，集中呈现当前背景、研究队列与下一步检查。'}
              </div>
            </WolfyCommandBar>
          )}
          rail={(
            <ConsoleContextRail className="flex flex-col gap-3 p-3">
              <RoughSectionCard eyebrow={locale === 'en' ? 'Summary' : '摘要'} title={locale === 'en' ? 'What changed' : '发生了什么'}>
                <RoughBulletList
                  items={railChangeItems}
                  emptyText={locale === 'en' ? 'No change summary yet.' : '暂未整理变化摘要。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Research focus' : '研究焦点'} title={locale === 'en' ? 'What to check next' : '下一步查什么'}>
                <RoughBulletList
                  items={sanitizeCockpitDisplayItems(priorities?.investigateNext ?? nextEvidenceItems, locale).slice(0, 3)}
                  emptyText={locale === 'en' ? 'No explicit next check yet.' : '暂未整理明确下一步检查。'}
                />
              </RoughSectionCard>
              <RoughSectionCard eyebrow={locale === 'en' ? 'Disclosure' : '披露'} title={locale === 'en' ? 'Research boundary' : '研究边界'}>
                <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                  {locale === 'en' ? 'Research context only; not an action instruction.' : '仅作研究语境，不构成操作指令。'}
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
                ? 'Use this first to read the current market backdrop, the facts already available, and the next research checks worth opening.'
                : '先用这里阅读当前市场背景、已可用事实，以及值得打开的下一步研究检查。'}
            />
            <CockpitFirstViewportSummary
              data={data}
              briefing={dailyIntelligence}
              loading={loading}
              dailyLoading={dailyIntelligenceLoading}
              narrativeSentences={cockpitNarrative?.sentences ?? []}
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
              <details className="m-3 rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-black/5 p-3">
                <summary className="cursor-pointer text-sm font-medium text-[color:var(--wolfy-text-secondary)]">
                  {locale === 'en' ? 'Market structure details and data-quality notes' : '市场结构明细与数据质量说明'}
                </summary>
                <div className="mt-3">
                <ConsoleStatusStrip
                  items={[
                    {
                      label: locale === 'en' ? 'Updated' : '更新时间',
                      value: formatDateTime(data.generatedAt, { locale: locale === 'en' ? 'en-US' : 'zh-CN' }),
                    },
                    {
                      label: locale === 'en' ? 'Data quality' : '数据质量',
                      value: <StatusBadge status={statusTone(data.dataQuality?.status)} label={getCockpitConsumerStatusLabel(data.dataQuality?.status, locale)} size="sm" />,
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
                      value: getCockpitConsumerStatusLabel(data.researchQueuePreview.queueQuality, locale),
                    },
                  ]}
                />
                {cockpitNarrative ? (
                  <div className="border-b border-[color:var(--wolfy-divider)] p-3">
                    <RoughSectionCard
                      eyebrow={locale === 'en' ? 'Narrative' : '叙事'}
                      title={locale === 'en' ? 'Why this market state looks this way' : '为什么形成当前市场状态'}
                      data-testid="market-cockpit-narrative"
                    >
                      <RoughBulletList
                        items={cockpitNarrative.sentences}
                        emptyText={locale === 'en' ? 'Narrative is not available yet.' : '暂未形成市场状态叙事。'}
                      />
                    </RoughSectionCard>
                  </div>
                ) : null}
                <div className="grid gap-3 p-3 md:grid-cols-2">
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Drivers' : '驱动'} title={locale === 'en' ? 'Driver scores' : '驱动评分'}>
                    <RoughScoreRows
                      items={driverRows}
                      emptyText={locale === 'en' ? 'No driver scores yet.' : '暂无驱动评分。'}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Regime logic' : '状态逻辑'} title={locale === 'en' ? 'Why this regime' : '为什么形成当前状态'}>
                    <RoughKeyValueRows
                      emptyText={locale === 'en' ? 'No regime explanation available yet.' : '暂无状态解释。'}
                      rows={[
                        {
                          key: 'why',
                          label: locale === 'en' ? 'Why this regime' : '形成原因',
                          value: sanitizeCockpitDisplayItems(data.marketRegimeDecision.explanation?.whyThisRegime ?? [], locale).join('；') || '--',
                        },
                        {
                          key: 'confirm',
                          label: locale === 'en' ? 'What confirms it' : '确认信号',
                          value: sanitizeCockpitDisplayItems(data.marketRegimeDecision.explanation?.whatConfirmsIt ?? [], locale).join('；') || '--',
                        },
                        {
                          key: 'invalidate',
                          label: locale === 'en' ? 'What invalidates it' : '失效观察',
                          value: sanitizeCockpitDisplayItems(data.marketRegimeDecision.invalidationConditions ?? [], locale).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Next steps' : '下一步'} title={locale === 'en' ? 'What to watch and verify' : '关注点与验证项'}>
                    <RoughKeyValueRows
                      emptyText={locale === 'en' ? 'No next steps available yet.' : '暂无下一步关注点。'}
                      rows={[
                        {
                          key: 'watch',
                          label: locale === 'en' ? 'What to watch' : '今日关注',
                          value: sanitizeCockpitDisplayItems(cockpitSummary?.whatToWatch ?? priorities?.watchToday ?? [], locale).join('；') || '--',
                        },
                        {
                          key: 'evidence',
                          label: locale === 'en' ? 'Needs more evidence' : '待补证据',
                          value: sanitizeCockpitDisplayItems(nextEvidenceItems, locale)
                            .join('；') || '--',
                        },
                        {
                          key: 'next',
                          label: locale === 'en' ? 'Investigate next' : '下一步研究',
                          value: sanitizeCockpitDisplayItems(priorities?.investigateNext ?? [], locale).join('；') || '--',
                        },
                      ]}
                    />
                  </RoughSectionCard>
                  <RoughSectionCard eyebrow={locale === 'en' ? 'Options / gamma' : '期权 / Gamma'} title={locale === 'en' ? 'Research context status' : '研究语境状态'}>
                    {(() => {
                      const blockedReasonLabels = sanitizeCockpitDisplayItems(optionsStatus?.blockedReasonCodes ?? [], locale);
                      const missingEvidenceLabels = consumerMissingEvidenceLabels(optionsStatus?.missingEvidence, locale);
                      return (
                        <>
                          <RoughKeyValueRows
                            emptyText={locale === 'en' ? 'No options observation data yet.' : '暂无期权观察数据。'}
                            rows={[
                              {
                                key: 'gamma',
                                label: locale === 'en' ? 'Gamma evidence' : 'Gamma 证据',
                                value: optionsStatus?.gammaEvidenceStatus
                                  ? sanitizeCockpitStatusOrIssue(optionsStatus.gammaEvidenceStatus, locale)
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
                                  {sanitizeCockpitDisplayItems(candidate.whyOnRadar ?? [], locale).join('；') || (locale === 'en' ? 'Research queue preview item.' : '研究队列预览条目。')}
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
                        {locale === 'en' ? 'Top candidates and next checks will appear here when the queue is ready.' : '队列就绪后，这里会展示重点候选与下一步检查。'}
                      </TerminalEmptyState>
                    )}
                  </RoughSectionCard>
                </div>
                </div>
              </details>
            ) : null}
          </ConsoleBoard>
        </ResearchConsoleShell>
      </ConsumerWorkspacePageShell>
    </ConsumerWorkspaceScope>
  );
}
