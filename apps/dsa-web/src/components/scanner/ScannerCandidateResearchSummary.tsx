import { TerminalChip } from '../terminal/TerminalPrimitives';
import { FieldChip } from './ScannerDisplayAtoms';

export type ScannerCandidateResearchSummaryTopDownRef = {
  key?: string | null;
  state?: string | null;
  label?: string | null;
};

export type ScannerCandidateResearchSummaryFrame = {
  contractVersion?: string | null;
  frameState?: string | null;
  symbol?: string | null;
  rank?: number | null;
  primaryResearchReason?: string | null;
  evidenceHighlights?: string[] | null;
  missingEvidence?: string[] | null;
  blockingReasons?: string[] | null;
  topDownContextRefs?: ScannerCandidateResearchSummaryTopDownRef[] | null;
  sourceAuthority?: string | null;
  freshness?: string | null;
  nextResearchStep?: string | null;
  noAdviceBoundary?: boolean | null;
};

type SummaryVariant = 'row' | 'detail';

const DOMAIN_LABELS: Record<string, { zh: string; en: string }> = {
  technicals: { zh: '技术面', en: 'Technicals' },
  pricehistory: { zh: '价格历史', en: 'Price history' },
  liquidity: { zh: '流动性', en: 'Liquidity' },
  volume: { zh: '成交量', en: 'Volume' },
  gapmomentum: { zh: '动量', en: 'Momentum' },
  trend: { zh: '趋势', en: 'Trend' },
  theme: { zh: '主题', en: 'Theme' },
  fundamentals: { zh: '基本面', en: 'Fundamentals' },
  newscatalyst: { zh: '新闻催化', en: 'News catalyst' },
  news: { zh: '新闻催化', en: 'News catalyst' },
  catalyst: { zh: '新闻催化', en: 'News catalyst' },
  macro: { zh: '宏观', en: 'Macro' },
  scanner_context: { zh: '扫描上下文', en: 'Scanner context' },
  freshness: { zh: '时效', en: 'Freshness' },
  source_authority: { zh: '来源确认', en: 'Source confirmation' },
};

const HIGHLIGHT_LABELS: Record<string, { zh: string; en: string }> = {
  'technicals available': { zh: '技术面可用', en: 'Technicals available' },
  'price history available': { zh: '价格历史可用', en: 'Price history available' },
  'liquidity available': { zh: '流动性可用', en: 'Liquidity available' },
  'volume evidence available': { zh: '成交量线索可用', en: 'Volume evidence available' },
  'momentum evidence available': { zh: '动量线索可用', en: 'Momentum evidence available' },
  'momentum evidence partial': { zh: '动量线索部分可用', en: 'Momentum evidence partial' },
  'trend structure available': { zh: '趋势结构可用', en: 'Trend structure available' },
  'theme context available': { zh: '主题线索可用', en: 'Theme context available' },
  'theme context partial': { zh: '主题线索部分可用', en: 'Theme context partial' },
  'fundamentals available': { zh: '基本面可用', en: 'Fundamentals available' },
  'news and catalyst context available': { zh: '新闻催化线索可用', en: 'News catalyst available' },
};

const BLOCKING_REASON_LABELS: Record<string, { zh: string; en: string }> = {
  source_authority_router_rejected: { zh: '来源确认待补齐', en: 'Source confirmation pending' },
  source_authority_missing: { zh: '来源确认待补齐', en: 'Source confirmation pending' },
  observation_only: { zh: '当前线索仅供观察', en: 'Current signals are observation only' },
  missing_required_evidence: { zh: '关键信息仍待补齐', en: 'Core evidence is still missing' },
  stale_evidence: { zh: '部分线索已过期', en: 'Some signals are stale' },
  fallback_evidence: { zh: '当前仅保留最近一次可用线索', en: 'Using the latest available signals only' },
};

const TOP_DOWN_LABELS: Record<string, { zh: string; en: string }> = {
  marketreadiness: { zh: '市场', en: 'Market' },
  macroregime: { zh: '宏观', en: 'Macro' },
  liquidityframe: { zh: '流动性', en: 'Liquidity' },
  assetclassbias: { zh: '资产', en: 'Asset' },
  themeframe: { zh: '主题', en: 'Theme' },
};

function normalizeKey(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_').replace(/[^a-z0-9_]/g, '');
}

function hasChineseText(value?: string | null): boolean {
  return /[\u3400-\u9fff]/.test(String(value || ''));
}

function localizeDomain(value: string, language: 'zh' | 'en'): string {
  const normalized = normalizeKey(value).replace(/_/g, '');
  return DOMAIN_LABELS[normalized]?.[language] || value;
}

function localizeHighlight(value: string, language: 'zh' | 'en'): string {
  const normalized = String(value || '').trim().toLowerCase();
  return HIGHLIGHT_LABELS[normalized]?.[language] || value;
}

function localizeBlockingReason(value: string, language: 'zh' | 'en'): string {
  const normalized = normalizeKey(value);
  return BLOCKING_REASON_LABELS[normalized]?.[language]
    || (language === 'en' ? 'Research boundary remains limited' : '研究边界仍受限');
}

function localizeState(value: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = normalizeKey(value);
  const labels: Record<string, { zh: string; en: string }> = {
    supportive: { zh: '支持', en: 'Supportive' },
    ready: { zh: '支持', en: 'Supportive' },
    available: { zh: '可用', en: 'Available' },
    observe_only: { zh: '仅观察', en: 'Observe only' },
    insufficient: { zh: '证据不足', en: 'Research evidence pending' },
    blocked: { zh: '阻断', en: 'Blocked' },
    mixed: { zh: '混合', en: 'Mixed' },
    waiting: { zh: '等待更新', en: 'Waiting' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Pending' : '待确认');
}

function localizeSourceAuthority(value: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = normalizeKey(value);
  const labels: Record<string, { zh: string; en: string }> = {
    scoregradeallowed: { zh: '研究证据可用', en: 'Research evidence usable' },
    observationonly: { zh: '仅研究观察线索', en: 'Research-only signals' },
    unavailable: { zh: '来源待确认', en: 'Source confirmation pending' },
    blocked: { zh: '来源待确认', en: 'Source confirmation pending' },
    unknown: { zh: '来源待确认', en: 'Source confirmation pending' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Source confirmation pending' : '来源待确认');
}

function localizeFreshness(value: string | null | undefined, language: 'zh' | 'en'): string {
  const normalized = normalizeKey(value);
  const labels: Record<string, { zh: string; en: string }> = {
    live: { zh: '实时更新', en: 'Live update' },
    cached: { zh: '缓存更新', en: 'Cached update' },
    delayed: { zh: '延迟更新', en: 'Delayed update' },
    fallback: { zh: '最近一次可用更新', en: 'Latest available update' },
    stale: { zh: '较早更新', en: 'Older update' },
    unknown: { zh: '时效待确认', en: 'Freshness pending' },
    unavailable: { zh: '时效待确认', en: 'Freshness pending' },
  };
  return labels[normalized]?.[language] || (language === 'en' ? 'Freshness pending' : '时效待确认');
}

function topDownChipLabel(ref: ScannerCandidateResearchSummaryTopDownRef, language: 'zh' | 'en'): string {
  const key = normalizeKey(ref.key).replace(/_/g, '');
  const label = TOP_DOWN_LABELS[key]?.[language] || (language === 'en' ? 'Context' : '上下文');
  return `${label}：${localizeState(ref.state, language)}`;
}

function localizedPrimaryReason(
  frame: ScannerCandidateResearchSummaryFrame,
  language: 'zh' | 'en',
): string {
  const raw = String(frame.primaryResearchReason || '').trim();
  if (raw && ((language === 'zh' && hasChineseText(raw)) || language === 'en')) {
    return raw;
  }

  const missing = (frame.missingEvidence || []).map((item) => localizeDomain(item, language));
  const highlights = (frame.evidenceHighlights || []).map((item) => localizeHighlight(item, language));
  const sourceAuthority = normalizeKey(frame.sourceAuthority);
  const frameState = normalizeKey(frame.frameState);

  if (language === 'zh') {
    if (frameState === 'blocked') {
      return '核心证据仍有缺口，当前候选仅保留研究观察。';
    }
    if (sourceAuthority !== 'scoregradeallowed' && sourceAuthority) {
      return '当前候选进入研究列表，现有线索仅用于研究观察。';
    }
    if (missing.length) {
      return `当前候选进入研究列表，但${missing[0]}仍待补齐。`;
    }
    if (highlights.length) {
      return `当前候选进入研究列表，已具备${highlights[0]}。`;
    }
    return '当前候选进入研究列表，可继续围绕现有证据做研究观察。';
  }

  if (missing.length) {
    return `The candidate remains on the research list, but ${missing[0]} is still missing.`;
  }
  if (sourceAuthority !== 'scoregradeallowed' && sourceAuthority) {
    return 'Current signals are observation only, so this candidate stays research-only.';
  }
  if (highlights.length) {
    return `The candidate remains on the research list with ${highlights[0].toLowerCase()}.`;
  }
  return 'The candidate remains on the research list for bounded follow-up review.';
}

function localizedNextStep(
  frame: ScannerCandidateResearchSummaryFrame,
  language: 'zh' | 'en',
): string {
  const raw = String(frame.nextResearchStep || '').trim();
  if (raw && ((language === 'zh' && hasChineseText(raw)) || language === 'en')) {
    return raw;
  }

  const missing = (frame.missingEvidence || []).map((item) => localizeDomain(item, language));
  const freshness = normalizeKey(frame.freshness);

  if (language === 'zh') {
    if (missing.length >= 2) {
      return `先补充${missing[0]}与${missing[1]}，再复核当前候选。`;
    }
    if (missing.length === 1) {
      return `优先补充${missing[0]}，再复核当前候选。`;
    }
    if (freshness === 'delayed' || freshness === 'stale' || freshness === 'fallback') {
      return '等待下一次数据更新后，再复核当前候选。';
    }
    return '先补充更完整证据，再复核当前候选。';
  }

  if (missing.length) {
    return `Refresh ${missing.join(' and ')} before reviewing this candidate again.`;
  }
  if (freshness === 'delayed' || freshness === 'stale' || freshness === 'fallback') {
    return 'Wait for the next data refresh before reviewing this candidate again.';
  }
  return 'Review the candidate again after more complete evidence arrives.';
}

export function ScannerCandidateResearchSummary({
  frame,
  language,
  variant = 'detail',
  testId,
}: {
  frame?: ScannerCandidateResearchSummaryFrame | null;
  language: 'zh' | 'en';
  variant?: SummaryVariant;
  testId?: string;
}) {
  if (!frame) return null;

  const evidenceHighlights = Array.from(new Set((frame.evidenceHighlights || []).flatMap((item) => {
    const label = localizeHighlight(item, language);
    return label ? [label] : [];
  })));
  const missingEvidence = Array.from(new Set((frame.missingEvidence || []).flatMap((item) => {
    const label = localizeDomain(item, language);
    return label ? [label] : [];
  })));
  const blockingReasons = Array.from(new Set((frame.blockingReasons || []).flatMap((item) => {
    const label = localizeBlockingReason(item, language);
    return label ? [label] : [];
  })));
  const topDownRefs = Array.from(new Set((frame.topDownContextRefs || []).flatMap((item) => {
    const label = topDownChipLabel(item, language);
    return label ? [label] : [];
  })));
  const primaryReason = localizedPrimaryReason(frame, language);
  const nextStep = localizedNextStep(frame, language);
  const sourceAuthority = localizeSourceAuthority(frame.sourceAuthority, language);
  const freshness = localizeFreshness(frame.freshness, language);
  const missingSummary = missingEvidence.length
    ? `${language === 'en' ? 'Missing' : '待补'} ${missingEvidence.slice(0, 2).join(' / ')}`
    : null;

  if (variant === 'row') {
    return (
      <div data-testid={testId} className="mt-1.5 space-y-1.5">
        <p className="line-clamp-2 text-[11px] leading-relaxed text-white/58">
          {primaryReason}
        </p>
        <div className="flex min-w-0 flex-wrap items-center gap-1.5 text-[10px] text-white/46">
          {missingSummary ? <span className="truncate">{missingSummary}</span> : null}
          <span className="truncate">{sourceAuthority}</span>
          <span className="truncate">{freshness}</span>
          {frame.noAdviceBoundary ? (
            <TerminalChip variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {language === 'en' ? 'Research only' : '仅研究观察'}
            </TerminalChip>
          ) : null}
        </div>
      </div>
    );
  }

  return (
    <section data-testid={testId} className="grid gap-2 rounded-xl border border-white/8 bg-white/[0.015] p-3">
      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/40">
        {language === 'en' ? 'Research summary' : '研究摘要'}
      </p>
      <p className="text-xs leading-relaxed text-white/72">
        {primaryReason}
      </p>
      {evidenceHighlights.length ? (
        <div className="flex min-w-0 flex-wrap gap-1.5">
          {evidenceHighlights.slice(0, 3).map((item) => (
            <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
              {item}
            </TerminalChip>
          ))}
        </div>
      ) : null}
      <div className="flex min-w-0 flex-wrap gap-1.5">
        {missingEvidence.length ? (
          <FieldChip
            label={language === 'en' ? 'Missing' : '待补'}
            value={missingEvidence.slice(0, 3).join(' / ')}
          />
        ) : null}
        {blockingReasons.slice(0, 2).map((item) => (
          <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
            {item}
          </TerminalChip>
        ))}
      </div>
      {topDownRefs.length ? (
        <div className="space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/36">
            {language === 'en' ? 'Market drivers' : '市场驱动因素'}
          </p>
          <div className="flex min-w-0 flex-wrap gap-1.5">
            {topDownRefs.slice(0, 4).map((item) => (
              <TerminalChip key={item} variant="neutral" className="px-1.5 py-0.5 text-[10px] font-sans text-white/72">
                {item}
              </TerminalChip>
            ))}
          </div>
        </div>
      ) : null}
      <div className="flex min-w-0 flex-wrap gap-1.5">
        <FieldChip label={language === 'en' ? 'Source' : '来源'} value={sourceAuthority} />
        <FieldChip label={language === 'en' ? 'Freshness' : '时效'} value={freshness} />
        {frame.noAdviceBoundary ? (
          <FieldChip label={language === 'en' ? 'Boundary' : '边界'} value={language === 'en' ? 'Research only' : '仅研究观察'} />
        ) : null}
      </div>
      <p className="text-xs leading-relaxed text-white/62">
        <span className="text-white/42">{language === 'en' ? 'Next:' : '下一步：'}</span>
        {nextStep}
      </p>
    </section>
  );
}

export default ScannerCandidateResearchSummary;
