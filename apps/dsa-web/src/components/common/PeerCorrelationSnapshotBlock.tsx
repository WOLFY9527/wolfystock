import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import type {
  StockPeerCorrelationEvidence,
  StockPeerCorrelationSnapshot,
  StockPeerCorrelationState,
} from '../../api/stocks';
import { sanitizeUserFacingDataIssue } from '../../utils/userFacingDataIssues';

type PeerCorrelationSnapshotBlockProps = {
  snapshot?: StockPeerCorrelationSnapshot | null;
  locale?: 'zh' | 'en';
  className?: string;
  title?: string;
  testId?: string;
};

const PEER_COPY_UNSAFE_PATTERN =
  /\b(provider|debug|trace|raw|sourceRef|reasonCode|requestId|cache|schema|buy|sell|hold|recommend(?:ation)?|target price|stop loss|position sizing|observation-only|insufficient_evidence|freshness\s*=\s*unavailable|peer group metadata|daily ohlcv|verified peers?|peer correlation|latency boundary)\b|\b[a-z]+(?:_[a-z0-9]+)+\b|买入|卖出|持有|推荐|目标价|止损|仓位建议/i;

function stateVariant(state: StockPeerCorrelationState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'aligned') return 'success';
  if (state === 'diverging') return 'caution';
  return 'neutral';
}

function peerStateLabel(state: StockPeerCorrelationState, locale: 'zh' | 'en'): string {
  const labels: Record<StockPeerCorrelationState, { zh: string; en: string }> = {
    aligned: { zh: '同业走势同步', en: 'Peer aligned' },
    diverging: { zh: '同业走势分化', en: 'Peer diverging' },
    insufficient_evidence: { zh: '同业证据不足', en: 'Peer evidence insufficient' },
  };
  return labels[state]?.[locale] ?? (locale === 'en' ? 'Peer evidence under review' : '同业证据待确认');
}

function confidenceCapLabel(value: string | number | null | undefined, locale: 'zh' | 'en'): string {
  if (value == null || value === '') return '--';
  if (typeof value === 'number' && Number.isFinite(value)) return String(value);
  const normalized = String(value).trim().toLowerCase();
  if (normalized === 'high') return locale === 'en' ? 'High' : '高';
  if (normalized === 'medium') return locale === 'en' ? 'Medium' : '中';
  if (normalized === 'low') return locale === 'en' ? 'Low' : '低';
  return String(value);
}

function mapKnownPeerCopy(locale: 'zh' | 'en', value: string): string | null {
  const text = value.trim();
  if (!text) return null;
  const normalized = text.toLowerCase().replace(/\s+/g, ' ').replace(/[.。!?]+$/g, '');

  if (/freshness\s*=\s*unavailable/i.test(text) || normalized === 'freshness unavailable') {
    return locale === 'en' ? 'Freshness currently unavailable' : '数据新鲜度暂不可确认';
  }
  if (/\binsufficient_evidence\b/i.test(text) || normalized === 'insufficient evidence') {
    return locale === 'en' ? 'Peer evidence insufficient' : '同业证据不足';
  }

  if (locale === 'zh') {
    const peerHistory = text.match(/^([A-Z0-9._-]+) peer history is unavailable\.?$/i);
    if (peerHistory?.[1]) {
      return `${peerHistory[1].toUpperCase()} 同业历史数据暂缺。`;
    }
    const movedWith = text.match(/^([A-Z0-9._-]+) moved with ([A-Z0-9._-]+) across the comparison window\.?$/i);
    if (movedWith?.[1] && movedWith[2]) {
      return `${movedWith[1].toUpperCase()} 与 ${movedWith[2].toUpperCase()} 在当前对比窗口内走势同步。`;
    }
    const labels: Record<string, string> = {
      'observation-only peer movement context; no personalized action instruction': '仅供同业走势观察，不构成个性化行动指令。',
      'review whether peer alignment persists after the next close': '下一个收盘后复核同业同步是否延续。',
      'peer movement remains bounded by the available comparison window': '同业走势仅按当前可用对比窗口观察。',
      'peer behavior remains bounded by current evidence': '同业行为仍受当前证据窗口约束。',
      'need broader peer evidence': '需要补充更广泛的同业证据。',
      'review the next close': '复核下一次收盘后的结构变化。',
      'no verified local peer group metadata is available for aapl': '同业对比信息待确认',
      'add verified local peer group metadata before interpreting peer movement': '补齐本地同业分组后再复核同业走势。',
      'load recent local daily ohlcv for the symbol and at least two verified peers': '历史行情待补',
      'peer correlation was not evaluated because structure evidence exceeded the latency boundary': '因结构证据超过时效边界，未评估同业相关性。',
      'peer correlation was not evaluated because structure computation exceeded the latency boundary': '因结构计算超过时效边界，未评估同业相关性。',
    };
    return labels[normalized] ?? null;
  }

  if (normalized === 'observation-only peer movement context; no personalized action instruction') {
    return 'Peer movement context only; no personalized action instruction.';
  }

  return null;
}

function safeCopy(locale: 'zh' | 'en', value: string | undefined, fallback: string): string {
  const text = String(value || '').trim();
  if (!text) return fallback;
  const knownCopy = mapKnownPeerCopy(locale, text);
  if (knownCopy) return knownCopy;
  const sanitized = PEER_COPY_UNSAFE_PATTERN.test(text)
    ? sanitizeUserFacingDataIssue(text, locale)
    : text;
  const mappedSanitized = mapKnownPeerCopy(locale, sanitized);
  if (mappedSanitized) return mappedSanitized;
  return PEER_COPY_UNSAFE_PATTERN.test(sanitized) ? fallback : sanitized;
}

function evidenceSummary(
  locale: 'zh' | 'en',
  evidence: StockPeerCorrelationEvidence,
): string {
  const fallback = locale === 'en'
    ? 'Peer movement remains bounded by the available comparison window.'
    : '同业走势仅按当前可用对比窗口观察。';
  return safeCopy(locale, evidence.summary, fallback);
}

function boundedList(values: string[], locale: 'zh' | 'en', fallback: string): string[] {
  return values
    .map((value) => safeCopy(locale, value, fallback))
    .filter((value, index, list) => value && list.indexOf(value) === index)
    .slice(0, 3);
}

const PeerCorrelationSnapshotBlock: React.FC<PeerCorrelationSnapshotBlockProps> = ({
  snapshot,
  locale = 'zh',
  className,
  title,
  testId = 'peer-correlation-snapshot',
}) => {
  if (!snapshot) {
    return null;
  }

  const isEnglish = locale === 'en';
  const resolvedTitle = title || (isEnglish ? 'Peer correlation' : '同业相关性');
  const peerGroupLabel = safeCopy(
    locale,
    snapshot.peerGroup.label || undefined,
    isEnglish ? 'Peer group' : '同业组',
  );
  const peerSymbols = snapshot.peerGroup.symbols.slice(0, 6);
  const staleInputs = boundedList(
    snapshot.staleInputs,
    locale,
    isEnglish ? 'Some peer inputs need a fresher comparison window.' : '部分同业输入需要更新对比窗口。',
  );
  const missingInputs = boundedList(
    snapshot.missingInputs,
    locale,
    isEnglish ? 'Some peer inputs are unavailable for this comparison.' : '部分同业输入暂不可用于本次对比。',
  );
  const nextSteps = boundedList(
    snapshot.researchNextSteps,
    locale,
    isEnglish ? 'Review the peer comparison again after fresh evidence arrives.' : '补齐新的同业证据后再复核该结构观察。',
  );
  const boundary = safeCopy(
    locale,
    snapshot.observationBoundary,
    isEnglish ? 'Observation-only peer context; no personalized action instruction.' : '仅供同业走势观察，不构成个性化行动指令。',
  );
  const peerEvidence = snapshot.peerEvidence.slice(0, 3);
  const divergenceEvidence = snapshot.divergenceEvidence.slice(0, 3);
  const emptyEvidence = isEnglish ? 'No peer evidence listed.' : '暂无同业证据条目。';
  const emptyDivergence = isEnglish ? 'No divergence evidence listed.' : '暂无背离证据条目。';
  const emptyInput = isEnglish ? 'No explicit limitation listed.' : '暂无明确限制。';

  return (
    <section
      className={cn(
        'min-w-0 rounded-[10px] border border-white/[0.08] bg-white/[0.024] px-3 py-3',
        className,
      )}
      data-testid={testId}
    >
      <div className="flex min-w-0 flex-wrap items-center gap-2">
        <span className="text-[10px] font-semibold uppercase tracking-[0.16em] text-white/42">
          {resolvedTitle}
        </span>
        <TerminalChip variant={stateVariant(snapshot.correlationState)}>
          {peerStateLabel(snapshot.correlationState, locale)}
        </TerminalChip>
        <TerminalChip variant="neutral">
          {isEnglish ? `Confidence cap ${confidenceCapLabel(snapshot.confidenceCap, locale)}` : `置信上限 ${confidenceCapLabel(snapshot.confidenceCap, locale)}`}
        </TerminalChip>
      </div>

      <p className="mt-2 min-w-0 break-words text-xs leading-5 text-white/62">
        {peerGroupLabel}
        {peerSymbols.length ? ` / ${peerSymbols.join(', ')}` : ''}
      </p>

      <div className="mt-3 grid min-w-0 gap-2 sm:grid-cols-2">
        <div className="min-w-0 rounded-[8px] border border-white/[0.06] bg-white/[0.018] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/36">
            {isEnglish ? 'Peer evidence' : '同业证据'}
          </p>
          <div className="mt-2 space-y-1.5">
            {peerEvidence.length ? peerEvidence.map((item) => (
              <p key={`${item.symbol}-${item.state}-${item.overlapDays}`} className="text-xs leading-5 text-white/66">
                <span className="font-semibold text-white/78">{item.symbol}</span>
                {' / '}
                <span>{peerStateLabel(item.state, locale)}</span>
                {' - '}
                <span>{evidenceSummary(locale, item)}</span>
              </p>
            )) : (
              <p className="text-xs leading-5 text-white/50">{emptyEvidence}</p>
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-[8px] border border-white/[0.06] bg-white/[0.018] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/36">
            {isEnglish ? 'Divergence evidence' : '背离证据'}
          </p>
          <div className="mt-2 space-y-1.5">
            {divergenceEvidence.length ? divergenceEvidence.map((item) => (
              <p key={`${item.symbol}-${item.state}-${item.overlapDays}`} className="text-xs leading-5 text-white/66">
                <span className="font-semibold text-white/78">{item.symbol}</span>
                {' / '}
                <span>{peerStateLabel(item.state, locale)}</span>
                {' - '}
                <span>{evidenceSummary(locale, item)}</span>
              </p>
            )) : (
              <p className="text-xs leading-5 text-white/50">{emptyDivergence}</p>
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-[8px] border border-white/[0.06] bg-white/[0.018] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/36">
            {isEnglish ? 'Input limits' : '输入限制'}
          </p>
          <p className="mt-2 text-xs leading-5 text-white/62">
            {isEnglish ? 'Stale: ' : '过期输入：'}
            {staleInputs.length ? staleInputs.join(isEnglish ? ' / ' : '；') : emptyInput}
          </p>
          <p className="mt-1 text-xs leading-5 text-white/62">
            {isEnglish ? 'Missing: ' : '缺失输入：'}
            {missingInputs.length ? missingInputs.join(isEnglish ? ' / ' : '；') : emptyInput}
          </p>
        </div>

        <div className="min-w-0 rounded-[8px] border border-white/[0.06] bg-white/[0.018] px-3 py-2.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.12em] text-white/36">
            {isEnglish ? 'Research boundary' : '研究边界'}
          </p>
          <p className="mt-2 text-xs leading-5 text-white/62">{boundary}</p>
          <p className="mt-1 text-xs leading-5 text-white/62">
            {isEnglish ? 'Next: ' : '下一步：'}
            {nextSteps.length ? nextSteps.join(isEnglish ? ' / ' : '；') : (isEnglish ? 'Continue peer review after fresh evidence arrives.' : '等待新的同业证据后继续复核。')}
          </p>
        </div>
      </div>
    </section>
  );
};

export default PeerCorrelationSnapshotBlock;
