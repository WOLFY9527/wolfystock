import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import { getConsumerStatusLabel } from '../../utils/consumerStatusLabels';
import type {
  SingleStockEvidencePacket,
  SingleStockEvidencePacketDomainEntry,
  SingleStockEvidencePacketStatus,
} from '../../types/analysis';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';

type EvidencePacketLocale = 'zh' | 'en';

type ConsumerEvidencePacketStripProps = {
  packet: SingleStockEvidencePacket | null | undefined;
  locale?: EvidencePacketLocale;
  title?: string;
  testId?: string;
  className?: string;
};

type EvidenceDomainKey =
  | 'priceHistory'
  | 'technicals'
  | 'fundamentals'
  | 'earnings'
  | 'news'
  | 'catalysts'
  | 'valuation';

const DOMAIN_KEYS: EvidenceDomainKey[] = [
  'priceHistory',
  'technicals',
  'fundamentals',
  'earnings',
  'news',
  'catalysts',
  'valuation',
];

const DOMAIN_LABELS: Record<EvidenceDomainKey, { zh: string; en: string }> = {
  priceHistory: { zh: '价格历史', en: 'Price history' },
  technicals: { zh: '技术面', en: 'Technicals' },
  fundamentals: { zh: '基本面', en: 'Fundamentals' },
  earnings: { zh: '财报', en: 'Earnings' },
  news: { zh: '新闻', en: 'News' },
  catalysts: { zh: '催化', en: 'Catalysts' },
  valuation: { zh: '估值', en: 'Valuation' },
};

const STATUS_LABELS: Record<string, { zh: string; en: string }> = {
  available: { zh: '可用', en: 'Available' },
  degraded: { zh: '降级', en: 'Degraded' },
  missing: { zh: '缺失', en: 'Missing' },
  blocked: { zh: '阻断', en: 'Blocked' },
  pending: { zh: '待补', en: 'Pending' },
  ready: { zh: '就绪', en: 'Ready' },
  insufficient: { zh: '不足', en: 'Insufficient' },
  waiting: { zh: '等待', en: 'Waiting' },
  observe_only: { zh: '仅观察', en: 'Observe only' },
  unknown: { zh: '待确认', en: 'Unconfirmed' },
};

function normalizeStatus(value: SingleStockEvidencePacketStatus | undefined): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_') || 'unknown';
}

function statusVariant(status: string): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (status === 'available' || status === 'ready') return 'success';
  if (status === 'blocked') return 'danger';
  if (status === 'degraded' || status === 'insufficient') return 'caution';
  if (status === 'pending' || status === 'waiting') return 'info';
  return 'neutral';
}

function statusLabel(status: string, locale: EvidencePacketLocale): string {
  if (status === 'blocked' || status === 'pending') {
    return getConsumerStatusLabel(status, locale) || STATUS_LABELS[status]?.[locale] || STATUS_LABELS.unknown[locale];
  }
  return STATUS_LABELS[status]?.[locale] || STATUS_LABELS.unknown[locale];
}

function domainLabel(domain: EvidenceDomainKey, locale: EvidencePacketLocale): string {
  return DOMAIN_LABELS[domain][locale];
}

function countText(count: number, locale: EvidencePacketLocale, singular: string, plural: string): string {
  if (locale === 'en') {
    return `${count} ${count === 1 ? singular : plural}`;
  }
  return `${count} ${plural}`;
}

function compactUnique(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  values.forEach((value) => {
    const text = String(value || '').trim();
    if (!text || seen.has(text)) return;
    seen.add(text);
    result.push(text);
  });
  return result;
}

function safeDomainEntry(entry: SingleStockEvidencePacketDomainEntry | undefined): SingleStockEvidencePacketDomainEntry {
  return entry || { status: 'missing' };
}

function buildFundamentalsSummary(packet: SingleStockEvidencePacket, locale: EvidencePacketLocale): string {
  const evidenceLabels = compactUnique(packet.fundamentalsEarnings?.evidenceLabels || []);
  if (evidenceLabels.length > 0) {
    return locale === 'en'
      ? `Fundamentals/Earnings: ${countText(evidenceLabels.length, locale, 'evidence label', 'evidence labels')}`
      : `基本面/财报：${countText(evidenceLabels.length, locale, '项证据标签', '项证据标签')}`;
  }

  const reasons = compactUnique([
    ...(packet.fundamentalsEarnings?.missingEvidence || []),
    ...(packet.fundamentalsEarnings?.blockingReasons || []),
  ]);
  if (reasons.length > 0 || ['missing', 'blocked', 'pending', 'insufficient'].includes(normalizeStatus(packet.fundamentalsEarnings?.normalizerState))) {
    return locale === 'en'
      ? 'Fundamentals/Earnings: data limited'
      : '基本面/财报：数据不足';
  }

  return locale === 'en'
    ? 'Fundamentals/Earnings: summarized'
    : '基本面/财报：已整理';
}

function buildNewsSummary(packet: SingleStockEvidencePacket, locale: EvidencePacketLocale): string {
  const newsCount = Array.isArray(packet.newsCatalysts?.topNewsItems) ? packet.newsCatalysts?.topNewsItems.length : 0;
  const catalystCount = Array.isArray(packet.newsCatalysts?.topCatalystItems) ? packet.newsCatalysts?.topCatalystItems.length : 0;

  if (locale === 'en') {
    if (newsCount > 0 && catalystCount > 0) {
      return `News/Catalysts: ${countText(newsCount, locale, 'news item', 'news items')}, ${countText(catalystCount, locale, 'catalyst', 'catalysts')}`;
    }
    if (newsCount === 0 && catalystCount > 0) {
      return `News/Catalysts: news pending, ${countText(catalystCount, locale, 'catalyst', 'catalysts')}`;
    }
    if (newsCount > 0 && catalystCount === 0) {
      return `News/Catalysts: ${countText(newsCount, locale, 'news item', 'news items')}, catalysts pending`;
    }
    return 'News/Catalysts: pending';
  }

  if (newsCount > 0 && catalystCount > 0) {
    return `新闻/催化：${countText(newsCount, locale, '条新闻', '条新闻')}，${countText(catalystCount, locale, '条催化', '条催化')}`;
  }
  if (newsCount === 0 && catalystCount > 0) {
    return `新闻/催化：新闻待补，${countText(catalystCount, locale, '条催化', '条催化')}`;
  }
  if (newsCount > 0 && catalystCount === 0) {
    return `新闻/催化：${countText(newsCount, locale, '条新闻', '条新闻')}，催化待补`;
  }
  return '新闻/催化：待补充';
}

function buildReasonLine(packet: SingleStockEvidencePacket, locale: EvidencePacketLocale): string | null {
  const reason = compactUnique([
    ...(packet.fundamentalsEarnings?.blockingReasons || []),
    ...(packet.newsCatalysts?.blockingReasons || []),
  ])[0];
  if (!reason) return null;
  return sanitizeUserFacingDataIssue(reason, locale);
}

const ConsumerEvidencePacketStrip: React.FC<ConsumerEvidencePacketStripProps> = ({
  packet,
  locale = 'zh',
  title,
  testId,
  className,
}) => {
  const isEnglish = locale === 'en';
  const resolvedTitle = title || (isEnglish ? 'Evidence packet' : '证据包摘要');

  if (!packet) return null;

  const packetState = normalizeStatus(packet.packetState);
  const domainEntries = DOMAIN_KEYS.map((domain) => {
    const entry = safeDomainEntry(packet[domain]);
    return {
      domain,
      status: normalizeStatus(entry.status),
    };
  });
  const fundamentalsSummary = buildFundamentalsSummary(packet, locale);
  const newsSummary = buildNewsSummary(packet, locale);
  const reasonLine = buildReasonLine(packet, locale);

  return (
    <section
      data-testid={testId}
      className={cn(
        'research-evidence-surface px-3 py-2.5',
        className,
      )}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="research-evidence-eyebrow text-[10px] font-semibold uppercase tracking-[0.16em]">
          {resolvedTitle}
        </span>
        <span className="research-evidence-muted text-[11px]">
          {isEnglish ? 'Packet state' : '整体状态'}
        </span>
        <TerminalChip variant={statusVariant(packetState)}>
          {statusLabel(packetState, locale)}
        </TerminalChip>
      </div>
      <div className="mt-2 flex min-w-0 flex-wrap gap-2">
        {domainEntries.map(({ domain, status }) => (
          <TerminalChip key={domain} variant={statusVariant(status)}>
            {domainLabel(domain, locale)}
            {' '}
            {statusLabel(status, locale)}
          </TerminalChip>
        ))}
      </div>
      <div className="mt-2 space-y-1.5">
        <p className="research-evidence-copy text-xs leading-5">{fundamentalsSummary}</p>
        <p className="research-evidence-copy text-xs leading-5">{newsSummary}</p>
        {reasonLine ? <p className="research-evidence-muted text-[11px] leading-5">{reasonLine}</p> : null}
        <p className="research-evidence-muted text-[11px] leading-5">
          {isEnglish ? 'Observe only, not investment advice.' : '仅供观察，不构成投资建议。'}
        </p>
      </div>
    </section>
  );
};

export default ConsumerEvidencePacketStrip;
