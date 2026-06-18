import type { MarketDecisionCockpitDriverScore, MarketDecisionCockpitResponse } from '../api/marketDecisionCockpit';

type Locale = 'zh' | 'en';

type DriverState = 'available' | 'partial' | 'missing';

type DriverDescriptor = {
  key: string;
  label: string;
  score: number | null;
  state: DriverState;
};

export type MarketDecisionCockpitNarrative = {
  sentences: string[];
};

const DRIVER_LABELS: Record<string, { zh: string; en: string }> = {
  dealerGamma: { zh: 'Gamma 观察', en: 'gamma observation' },
  breadthParticipation: { zh: '广度参与', en: 'breadth participation' },
  volatilityStructure: { zh: '波动结构', en: 'volatility structure' },
  ratesDollar: { zh: '利率与美元', en: 'rates and USD' },
  liquidityCredit: { zh: '流动性与信用', en: 'liquidity and credit' },
  crossAssetRisk: { zh: '跨资产风险', en: 'cross-asset risk' },
  sectorThemeRotation: { zh: '主题轮动', en: 'theme rotation' },
  eventCatalyst: { zh: '事件催化', en: 'event catalyst' },
};

const REGIME_LABELS: Record<string, { zh: string; en: string }> = {
  riskon: { zh: '风险偏好观察', en: 'Risk-on observation' },
  risk_on: { zh: '风险偏好观察', en: 'Risk-on observation' },
  riskoff: { zh: '风险规避观察', en: 'Risk-off observation' },
  risk_off: { zh: '风险规避观察', en: 'Risk-off observation' },
  neutral: { zh: '中性观察', en: 'Neutral observation' },
  mixed: { zh: '混合状态观察', en: 'Mixed-regime observation' },
  lowconfidence: { zh: '低置信观察区间', en: 'low-confidence observation zone' },
  low_confidence: { zh: '低置信观察区间', en: 'low-confidence observation zone' },
};

const EVIDENCE_STATE_LABELS: Record<string, { zh: string; en: string; state: DriverState }> = {
  score_grade: { zh: '可评分证据', en: 'score-grade evidence', state: 'available' },
  available: { zh: '证据可用', en: 'evidence available', state: 'available' },
  ready: { zh: '证据可用', en: 'evidence available', state: 'available' },
  partial: { zh: '部分证据', en: 'partial evidence', state: 'partial' },
  mixed: { zh: '部分证据', en: 'partial evidence', state: 'partial' },
  thin: { zh: '证据偏薄', en: 'thin evidence', state: 'partial' },
  unavailable: { zh: '证据暂不可用', en: 'evidence unavailable', state: 'missing' },
  blocked: { zh: '证据暂不可用', en: 'evidence unavailable', state: 'missing' },
  degraded: { zh: '证据暂不可用', en: 'evidence unavailable', state: 'missing' },
};

function normalizeToken(value: string | null | undefined): string {
  return String(value || '')
    .trim()
    .replace(/([a-z0-9])([A-Z])/g, '$1_$2')
    .toLowerCase()
    .replace(/[-\s]+/g, '_');
}

function driverLabel(key: string, locale: Locale): string {
  const mapped = DRIVER_LABELS[key];
  if (mapped) {
    return mapped[locale];
  }
  return locale === 'en' ? 'additional driver' : '其他驱动';
}

function regimeLabel(value: string | null | undefined, locale: Locale): string {
  const mapped = REGIME_LABELS[normalizeToken(value)];
  if (mapped) {
    return mapped[locale];
  }
  return locale === 'en' ? 'market observation' : '市场观察';
}

function classifyEvidenceState(value: string | null | undefined): DriverState {
  const normalized = normalizeToken(value);
  const mapped = EVIDENCE_STATE_LABELS[normalized];
  if (mapped) {
    return mapped.state;
  }
  if (!normalized) {
    return 'missing';
  }
  if (/(provider|runtime|schema|debug|trace|raw|reason|timeout|missing|unavailable|blocked|error|failed)/i.test(normalized)) {
    return 'missing';
  }
  return 'partial';
}

export function getDriverEvidenceStateLabel(value: string | null | undefined, locale: Locale): string {
  const normalized = normalizeToken(value);
  const mapped = EVIDENCE_STATE_LABELS[normalized];
  if (mapped) {
    return mapped[locale];
  }
  return classifyEvidenceState(value) === 'missing'
    ? (locale === 'en' ? 'evidence unavailable' : '证据暂不可用')
    : (locale === 'en' ? 'partial evidence' : '部分证据');
}

function scoreValue(score: MarketDecisionCockpitDriverScore | undefined): number | null {
  return typeof score?.score === 'number' && Number.isFinite(score.score) ? score.score : null;
}

function describeDrivers(
  driverScores: MarketDecisionCockpitResponse['marketRegimeDecision']['driverScores'],
  locale: Locale,
): DriverDescriptor[] {
  return Object.entries(driverScores ?? {}).map(([key, score]) => {
    const value = scoreValue(score);
    const state = classifyEvidenceState(score?.evidenceState);
    return {
      key,
      label: driverLabel(key, locale),
      score: value,
      state: value != null && value > 0 && state === 'missing' ? 'partial' : state,
    };
  });
}

function sortedAvailableDrivers(drivers: DriverDescriptor[]): DriverDescriptor[] {
  return drivers
    .filter((driver) => driver.state !== 'missing' && (driver.score ?? 0) > 0)
    .sort((left, right) => (right.score ?? 0) - (left.score ?? 0));
}

function sortedMissingDrivers(drivers: DriverDescriptor[]): DriverDescriptor[] {
  return drivers
    .filter((driver) => driver.state === 'missing' || (driver.score ?? 0) <= 0)
    .sort((left, right) => (right.score ?? 0) - (left.score ?? 0));
}

function joinLabels(labels: string[], locale: Locale): string {
  const limited = labels.filter(Boolean).slice(0, 3);
  if (!limited.length) {
    return locale === 'en' ? 'available market evidence' : '可用市场证据';
  }
  if (locale === 'zh') {
    return limited.join('、');
  }
  const formatted = limited.map((label, index) => (index === 0 ? label.replace(/^./, (char) => char.toUpperCase()) : label));
  if (formatted.length === 1) {
    return formatted[0];
  }
  if (formatted.length === 2) {
    return `${formatted[0]} and ${formatted[1]}`;
  }
  return `${formatted.slice(0, -1).join(', ')}, and ${formatted[formatted.length - 1]}`;
}

function isLowConfidence(payload: MarketDecisionCockpitResponse): boolean {
  const confidence = normalizeToken(payload.marketRegimeDecision.confidence);
  const regime = normalizeToken(payload.marketRegimeDecision.regime);
  const score = payload.marketRegimeDecision.confidenceScore;
  return confidence === 'low'
    || regime === 'lowconfidence'
    || regime === 'low_confidence'
    || (typeof score === 'number' && score < 0.4);
}

export function buildMarketDecisionCockpitNarrative(
  payload: MarketDecisionCockpitResponse,
  locale: Locale,
): MarketDecisionCockpitNarrative {
  const drivers = describeDrivers(payload.marketRegimeDecision.driverScores, locale);
  const availableDrivers = sortedAvailableDrivers(drivers);
  const missingDrivers = sortedMissingDrivers(drivers);
  const missingMostDrivers = drivers.length > 0 && missingDrivers.length >= Math.ceil(drivers.length / 2);
  const lowConfidence = isLowConfidence(payload);
  const regime = regimeLabel(payload.marketRegimeDecision.regime, locale);
  const support = joinLabels(availableDrivers.map((driver) => driver.label), locale);
  const missing = joinLabels(missingDrivers.map((driver) => driver.label), locale);

  if (locale === 'en') {
    const opening = lowConfidence || missingMostDrivers
      ? `The current market state remains in a ${regime} because most drivers lack score-grade evidence.`
      : `The current market state reads as a ${regime} based on the available driver evidence.`;
    const supportSentence = availableDrivers.length
      ? `Available evidence mainly comes from ${support}.`
      : 'Available evidence is still too thin to name a dominant driver.';
    const missingSentence = missingDrivers.length
      ? `Key missing or degraded drivers include ${missing}.`
      : 'No major driver is marked as missing in this snapshot.';
    const confidenceSentence = lowConfidence || missingDrivers.length
      ? 'Use this result as a research priority signal, not a decision-grade conclusion.'
      : 'Use this result as a research priority signal while monitoring whether the driver evidence remains aligned.';
    return { sentences: [opening, supportSentence, missingSentence, confidenceSentence] };
  }

  const opening = lowConfidence || missingMostDrivers
    ? `当前市场状态仍处于${regime}，因为多数驱动项缺少可评分证据。`
    : `当前市场状态呈现为${regime}，主要基于已可用的驱动证据。`;
  const supportSentence = availableDrivers.length
    ? `可用证据主要来自${support}。`
    : '当前可用证据仍偏薄，暂难归因到单一主导驱动。';
  const missingSentence = missingDrivers.length
    ? `关键缺失或降级驱动包括${missing}。`
    : '当前快照没有标记主要缺失驱动。';
  const confidenceSentence = lowConfidence || missingDrivers.length
    ? '因此该结果适合作为研究优先级线索，而不是决策级结论。'
    : '因此该结果适合作为研究优先级线索，并继续观察驱动证据是否保持一致。';
  return { sentences: [opening, supportSentence, missingSentence, confidenceSentence] };
}
