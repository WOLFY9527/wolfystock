export type PortfolioResearchEvidencePosture =
  | '可用于观察'
  | '仅供观察'
  | '依据需复核'
  | '数据不足'
  | '证据待确认'
  | 'UNAVAILABLE';

export type PortfolioResearchContextView = {
  isHeld: boolean;
  matchedSymbols: string[];
  matchedHoldingsCount: number;
  accountLabels: string[];
  marketLabels: string[];
  currencyLabels: string[];
  concentrationLabel: string;
  freshnessLabel?: string;
  asOf?: string;
  evidencePosture: PortfolioResearchEvidencePosture;
  boundaryCopy: string;
  dataNotes: string[];
};

export type PortfolioResearchContextEvidenceInput = {
  posture?: string | null;
  displayLabel?: string | null;
  freshnessLabel?: string | null;
  limitationLabels?: unknown;
};

type PortfolioResearchContextPositionInput = {
  symbol?: unknown;
  market?: unknown;
  currency?: unknown;
  priceAsOf?: unknown;
  isPriceFallback?: unknown;
};

type PortfolioResearchContextAccountInput = {
  accountName?: unknown;
  name?: unknown;
  market?: unknown;
  baseCurrency?: unknown;
  positions?: unknown;
};

export type PortfolioResearchContextSnapshotInput = {
  asOf?: unknown;
  isStale?: unknown;
  isPartial?: unknown;
  isUnavailable?: unknown;
  fxStale?: unknown;
  fxFreshnessState?: unknown;
  freshnessLabel?: unknown;
  accounts?: unknown;
  analytics?: unknown;
  [key: string]: unknown;
};

export type CreatePortfolioResearchContextViewOptions = {
  snapshot?: PortfolioResearchContextSnapshotInput | null;
  symbols?: string | string[] | null;
  riskEvidence?: PortfolioResearchContextEvidenceInput | null;
};

type MatchedHolding = {
  symbol: string;
  market: string | null;
  currency: string | null;
  accountLabel: string | null;
  priceAsOf: string | null;
  isPriceFallback: boolean;
};

const UNAVAILABLE_VIEW: PortfolioResearchContextView = {
  isHeld: false,
  matchedSymbols: [],
  matchedHoldingsCount: 0,
  accountLabels: [],
  marketLabels: [],
  currencyLabels: [],
  concentrationLabel: '未连接持仓上下文',
  freshnessLabel: '未连接持仓上下文',
  evidencePosture: 'UNAVAILABLE',
  boundaryCopy: '持仓研究上下文暂不可用，仅展示独立研究信息。',
  dataNotes: ['未连接持仓上下文'],
};

const BOUNDARY_COPY = '以下内容仅供观察，用于补充研究上下文，不构成个性化投资建议。';

const INTERNAL_LABEL_PATTERNS = [
  /sourceauthority/i,
  /scorecontribution/i,
  /reasoncode/i,
  /\bprovider\b/i,
  /\bcache\b/i,
  /\bdebug\b/i,
  /\bbackend\b/i,
  /\braw\b/i,
  /\bjson\b/i,
  /\bschema\b/i,
  /\btrace\b/i,
  /\bbroker\b/i,
];

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function asString(value: unknown): string | null {
  if (typeof value !== 'string') return null;
  const trimmed = value.trim();
  return trimmed || null;
}

function asArray(value: unknown): unknown[] {
  return Array.isArray(value) ? value : [];
}

function unique(values: Array<string | null | undefined>): string[] {
  const seen = new Set<string>();
  const result: string[] = [];
  for (const value of values) {
    const trimmed = value?.trim();
    if (!trimmed || seen.has(trimmed)) continue;
    seen.add(trimmed);
    result.push(trimmed);
  }
  return result;
}

function normalizeSymbol(value: unknown): string | null {
  const symbol = asString(value);
  return symbol ? symbol.toUpperCase() : null;
}

function normalizeSymbols(symbols: CreatePortfolioResearchContextViewOptions['symbols']): string[] {
  return unique((Array.isArray(symbols) ? symbols : [symbols]).map(normalizeSymbol));
}

function marketLabel(value: unknown): string | null {
  const token = asString(value)?.toLowerCase();
  if (!token) return null;
  if (token === 'cn' || token === 'a' || token === 'ashare' || token === 'a_share') return 'A股';
  if (token === 'hk' || token === 'hkg') return '港股';
  if (token === 'us' || token === 'usa') return '美股';
  if (token === 'global') return '全球账户';
  return asString(value);
}

function safeAccountLabel(account: PortfolioResearchContextAccountInput): string | null {
  return asString(account.accountName) ?? asString(account.name);
}

function flattenHoldings(snapshot: PortfolioResearchContextSnapshotInput): MatchedHolding[] {
  return asArray(snapshot.accounts).flatMap((accountValue) => {
    if (!isRecord(accountValue)) return [];
    const account = accountValue as PortfolioResearchContextAccountInput;
    const accountLabel = safeAccountLabel(account);
    const accountMarket = asString(account.market);
    const accountCurrency = asString(account.baseCurrency);

    return asArray(account.positions).flatMap((positionValue) => {
      if (!isRecord(positionValue)) return [];
      const position = positionValue as PortfolioResearchContextPositionInput;
      const symbol = normalizeSymbol(position.symbol);
      if (!symbol) return [];

      return [{
        symbol,
        market: asString(position.market) ?? accountMarket,
        currency: asString(position.currency) ?? accountCurrency,
        accountLabel,
        priceAsOf: asString(position.priceAsOf),
        isPriceFallback: position.isPriceFallback === true,
      }];
    });
  });
}

function selectedHoldings(snapshot: PortfolioResearchContextSnapshotInput, symbols: string[]): MatchedHolding[] {
  const holdings = flattenHoldings(snapshot);
  if (!symbols.length) return holdings;
  const target = new Set(symbols);
  return holdings.filter((holding) => target.has(holding.symbol));
}

function concentrationPercent(snapshot: PortfolioResearchContextSnapshotInput): number | null {
  if (!isRecord(snapshot.analytics)) return null;
  const risk = snapshot.analytics.risk;
  if (!isRecord(risk)) return null;
  const largestPosition = risk.largestPosition;
  if (!isRecord(largestPosition)) return null;
  return typeof largestPosition.percent === 'number' && Number.isFinite(largestPosition.percent)
    ? largestPosition.percent
    : null;
}

function concentrationLabel(snapshot: PortfolioResearchContextSnapshotInput, matchedCount: number, targetSymbols: string[]): string {
  if (targetSymbols.length && matchedCount === 0) return '未持有该标的';
  if (matchedCount === 0) return '暂无持仓';

  const percent = concentrationPercent(snapshot);
  if (percent == null) return '持仓分布待确认';
  if (percent < 20) return '分散';
  if (percent < 35) return '适中';
  if (percent < 50) return '集中';
  return '高度集中';
}

function containsInternalVocabulary(value: string): boolean {
  return INTERNAL_LABEL_PATTERNS.some((pattern) => pattern.test(value));
}

function normalizedLabelToken(value: string): string {
  return value.trim().toLowerCase().replace(/[\s/-]+/g, '_');
}

function safeLimitationLabel(value: unknown): string | null {
  const label = asString(value);
  if (!label) return null;
  const normalized = normalizedLabelToken(label);

  if (normalized.includes('fx') && (normalized.includes('stale') || normalized.includes('expired'))) {
    return '已使用最近一次可用数据。';
  }
  if (normalized.includes('fx') && (normalized.includes('missing') || normalized.includes('unavailable'))) {
    return '部分数据暂不可用。';
  }
  if (normalized.includes('holdings') || normalized.includes('lineage') || label.includes('持仓来源')) {
    return '持仓数据待核验';
  }
  if (normalized.includes('stale') || normalized.includes('expired') || label.includes('过期')) {
    return '已使用最近一次可用数据。';
  }
  if (normalized.includes('timeout') || normalized.includes('unavailable') || label.includes('暂不可用')) {
    return '部分数据暂不可用。';
  }
  if (normalized.includes('confidence') || label.includes('置信')) {
    return '当前信号置信度较低，仅供观察。';
  }
  if (normalized.includes('observe') || label.includes('仅供观察')) {
    return '当前信号置信度较低，仅供观察。';
  }
  if (containsInternalVocabulary(label) || /_/.test(normalized)) {
    return null;
  }
  return label;
}

function evidencePosture(evidence?: PortfolioResearchContextEvidenceInput | null): PortfolioResearchEvidencePosture {
  const posture = normalizedLabelToken(asString(evidence?.posture) ?? '');
  const label = asString(evidence?.displayLabel);

  if (posture.includes('blocked') || label?.includes('数据不足')) return '数据不足';
  if (posture.includes('observe') || label?.includes('仅供观察')) return '仅供观察';
  if (posture.includes('review') || posture.includes('allowed_metadata') || label?.includes('复核')) return '依据需复核';
  if (containsInternalVocabulary(label ?? '')) return '证据待确认';
  if (label === '可用于观察') return '可用于观察';
  return '证据待确认';
}

function freshnessLabel(
  snapshot: PortfolioResearchContextSnapshotInput,
  evidence?: PortfolioResearchContextEvidenceInput | null,
): string | undefined {
  if (snapshot.isUnavailable === true) return '暂不可用';
  if (snapshot.isStale === true || snapshot.fxStale === true) return '已使用最近一次可用数据';
  const fxFreshness = normalizedLabelToken(asString(snapshot.fxFreshnessState) ?? '');
  if (fxFreshness.includes('stale') || fxFreshness.includes('expired')) return '已使用最近一次可用数据';
  if (fxFreshness.includes('missing') || fxFreshness.includes('unavailable')) return '暂不可用';

  const evidenceFreshness = asString(evidence?.freshnessLabel) ?? asString(snapshot.freshnessLabel);
  if (!evidenceFreshness || containsInternalVocabulary(evidenceFreshness)) return undefined;
  if (evidenceFreshness.includes('过期') || normalizedLabelToken(evidenceFreshness).includes('stale')) {
    return '已使用最近一次可用数据';
  }
  return evidenceFreshness;
}

function dataNotes(
  snapshot: PortfolioResearchContextSnapshotInput,
  matchedCount: number,
  targetSymbols: string[],
  evidence?: PortfolioResearchContextEvidenceInput | null,
): string[] {
  const notes = [
    targetSymbols.length && matchedCount === 0 ? '未在当前持仓中识别到该研究标的。' : null,
    snapshot.isPartial === true ? '当前信号置信度较低，仅供观察。' : null,
    snapshot.isUnavailable === true ? '部分数据暂不可用。' : null,
    snapshot.isStale === true || snapshot.fxStale === true ? '已使用最近一次可用数据。' : null,
    ...asArray(evidence?.limitationLabels).map(safeLimitationLabel),
  ];
  return unique(notes).slice(0, 4);
}

export function createPortfolioResearchContextView(
  options: CreatePortfolioResearchContextViewOptions,
): PortfolioResearchContextView {
  const snapshot = options.snapshot;
  if (!snapshot) return UNAVAILABLE_VIEW;

  const targetSymbols = normalizeSymbols(options.symbols);
  const holdings = selectedHoldings(snapshot, targetSymbols);
  const matchedSymbols = unique(holdings.map((holding) => holding.symbol));
  const accountLabels = unique(holdings.map((holding) => holding.accountLabel));
  const marketLabels = unique(holdings.map((holding) => marketLabel(holding.market)));
  const currencyLabels = unique(holdings.map((holding) => holding.currency));
  const matchedHoldingsCount = holdings.length;
  const notes = dataNotes(snapshot, matchedHoldingsCount, targetSymbols, options.riskEvidence);

  return {
    isHeld: matchedHoldingsCount > 0,
    matchedSymbols,
    matchedHoldingsCount,
    accountLabels,
    marketLabels,
    currencyLabels,
    concentrationLabel: concentrationLabel(snapshot, matchedHoldingsCount, targetSymbols),
    freshnessLabel: freshnessLabel(snapshot, options.riskEvidence),
    asOf: asString(snapshot.asOf) ?? undefined,
    evidencePosture: evidencePosture(options.riskEvidence),
    boundaryCopy: BOUNDARY_COPY,
    dataNotes: notes,
  };
}
