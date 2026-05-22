export type PortfolioCostMethod = 'fifo' | 'avg' | 'futu_diluted' | 'ths_pnl';
export type PortfolioSide = 'buy' | 'sell';
export type PortfolioCashDirection = 'in' | 'out';
export type PortfolioCorporateActionType = 'cash_dividend' | 'split_adjustment';

export interface PortfolioAccountItem {
  id: number;
  ownerId?: string | null;
  name: string;
  broker?: string | null;
  market: 'cn' | 'hk' | 'us' | 'global';
  baseCurrency: string;
  isActive: boolean;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PortfolioAccountListResponse {
  accounts: PortfolioAccountItem[];
}

export interface PortfolioAccountDeleteResponse {
  ok: boolean;
  deletedAccountId: number;
  deleteMode: 'soft' | 'hard';
  nextAccountId?: number | null;
}

export interface PortfolioAccountCreateRequest {
  name: string;
  broker?: string;
  market: 'cn' | 'hk' | 'us' | 'global';
  baseCurrency: string;
  ownerId?: string;
}

export interface PortfolioBrokerConnectionItem {
  id: number;
  ownerId?: string | null;
  portfolioAccountId: number;
  portfolioAccountName?: string | null;
  brokerType: string;
  brokerName?: string | null;
  connectionName: string;
  brokerAccountRef?: string | null;
  importMode: string;
  status: string;
  lastImportedAt?: string | null;
  lastImportSource?: string | null;
  lastImportFingerprint?: string | null;
  syncMetadata: Record<string, unknown>;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PortfolioBrokerConnectionListResponse {
  connections: PortfolioBrokerConnectionItem[];
}

export interface PortfolioIbkrSyncRequest {
  accountId: number;
  brokerConnectionId?: number;
  brokerAccountRef?: string;
  sessionToken: string;
  apiBaseUrl?: string;
  verifySsl?: boolean;
}

export interface PortfolioIbkrSyncResponse {
  accountId: number;
  brokerConnectionId: number;
  brokerAccountRef: string;
  connectionName: string;
  snapshotDate: string;
  syncedAt: string;
  baseCurrency: string;
  totalCash: number;
  totalMarketValue: number;
  totalEquity: number;
  realizedPnl: number;
  unrealizedPnl: number;
  positionCount: number;
  cashBalanceCount: number;
  fxStale: boolean;
  snapshotOverlayActive: boolean;
  usedExistingConnection: boolean;
  apiBaseUrl: string;
  verifySsl: boolean;
  warnings: string[];
}

export interface PortfolioPositionItem {
  symbol: string;
  market: string;
  currency: string;
  quantity: number;
  avgCost: number;
  totalCost: number;
  lastPrice: number;
  marketValueBase: number;
  unrealizedPnlBase: number;
  valuationCurrency: string;
  costBasisNative?: number | null;
  marketValueNative?: number | null;
  unrealizedPnlNative?: number | null;
  unrealizedPnlPct?: number | null;
  displayMarketValue?: number | null;
  displayUnrealizedPnl?: number | null;
  displayCurrency?: string | null;
  displayFxStatus?: PortfolioFxStatus | null;
}

export interface PortfolioAccountSnapshot {
  accountId: number;
  accountName: string;
  ownerId?: string | null;
  broker?: string | null;
  market: string;
  baseCurrency: string;
  asOf: string;
  costMethod: PortfolioCostMethod;
  totalCash: number;
  totalMarketValue: number;
  totalEquity: number;
  realizedPnl: number;
  unrealizedPnl: number;
  feeTotal: number;
  taxTotal: number;
  fxStale: boolean;
  positions: PortfolioPositionItem[];
}

export interface PortfolioFxRateItem {
  fromCurrency: string;
  toCurrency: string;
  rate?: number | null;
  rateDate?: string | null;
  source: string;
  isStale: boolean;
  updatedAt?: string | null;
  sourceDirection: string;
}

export interface PortfolioLiveFxRateResponse {
  baseCurrency: string;
  quoteCurrency: string;
  rate: number;
  provider: string;
  fetchedAt: string;
  cacheHit: boolean;
  stale: boolean;
  error?: string | null;
}

export type PortfolioFxStatus = 'live' | 'stale' | 'unavailable';

export interface PortfolioPnlMetric {
  amount: number;
  amountDisplay?: string | null;
  percent?: number | null;
  currency: string;
  fxStatus: PortfolioFxStatus;
}

export interface PortfolioPnlSummary {
  displayCurrency: string;
  realized: PortfolioPnlMetric;
  unrealized: PortfolioPnlMetric;
  total: PortfolioPnlMetric;
}

export interface PortfolioExposureItem {
  key: string;
  label: string;
  marketValue: number;
  displayValue: number;
  displayCurrency: string;
  percent: number;
  fxStatus: PortfolioFxStatus;
  nativeValue?: number | null;
  nativeCurrency?: string | null;
  accountId?: number | null;
  accountName?: string | null;
  baseCurrency?: string | null;
  currency?: string | null;
  market?: string | null;
  symbol?: string | null;
  sector?: string | null;
  holdingCount?: number | null;
  unrealizedPnl?: number | null;
  unrealizedPnlPct?: number | null;
}

export interface PortfolioExposureSummary {
  byAccount: PortfolioExposureItem[];
  byCurrency: PortfolioExposureItem[];
  byMarket: PortfolioExposureItem[];
  bySymbol: PortfolioExposureItem[];
  bySector: PortfolioExposureItem[];
  sectorStatus: 'available' | 'unavailable';
}

export interface PortfolioAnalyticsRiskSummary {
  largestPosition?: PortfolioExposureItem | null;
  largestCurrency?: PortfolioExposureItem | null;
  largestMarket?: PortfolioExposureItem | null;
  holdingCount: number;
  accountCount: number;
  cashPercent?: number | null;
  fxUnavailable: boolean;
  warnings: string[];
}

export interface PortfolioAnalyticsSummary {
  pnl: PortfolioPnlSummary;
  exposure: PortfolioExposureSummary;
  risk: PortfolioAnalyticsRiskSummary;
}

export interface PortfolioEvidenceMetadata {
  source?: string | null;
  sourceLabel?: string | null;
  freshness?: string | null;
  freshnessLabel?: string | null;
  asOf?: string | null;
  isFallback?: boolean | null;
  isStale?: boolean | null;
  isPartial?: boolean | null;
  isUnavailable?: boolean | null;
  coverage?: Record<string, unknown> | null;
  confidenceWeight?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
  state?: string | null;
  status?: string | null;
}

export interface PortfolioRiskDiagnosticIssue extends PortfolioEvidenceMetadata {
  code?: string | null;
  label?: string | null;
  detail?: string | null;
  accountIds?: number[];
  severity?: string | null;
  [key: string]: unknown;
}

export interface PortfolioRiskEvidenceSection extends PortfolioEvidenceMetadata {
  summary?: string | null;
  issues?: PortfolioRiskDiagnosticIssue[];
  details?: Record<string, unknown>;
  [key: string]: unknown;
}

export interface PortfolioRiskConfidenceCap extends PortfolioEvidenceMetadata {
  value?: number | null;
  decisionStatus?: string | null;
  reasonCodes?: string[];
  limitationLabels?: string[];
  disabledClaims?: string[];
  policyVersion?: string | null;
  [key: string]: unknown;
}

export interface PortfolioRiskEvidenceEntity {
  type?: string | null;
  id?: string | null;
  symbol?: string | null;
  market?: string | null;
  displayName?: string | null;
  [key: string]: unknown;
}

export interface PortfolioRiskEvidenceItem extends PortfolioEvidenceMetadata {
  key?: string | null;
  criticality?: string | null;
  valueClass?: string | null;
  sourceRefIds?: string[];
  freshnessClass?: string | null;
  reasonCodes?: string[];
  [key: string]: unknown;
}

export interface PortfolioRiskEvidenceSourceRef extends PortfolioEvidenceMetadata {
  sourceRefId?: string | null;
  provider?: string | null;
  category?: string | null;
  sourceClass?: string | null;
  cacheHit?: boolean | null;
  providerUsageEventIds?: string[];
  sanitizedReasonCode?: string | null;
  rawPayloadStored?: boolean | null;
  [key: string]: unknown;
}

export interface PortfolioRiskExplainableFact {
  factId?: string | null;
  statement?: string | null;
  sourceRefIds?: string[];
  criticality?: string | null;
  confidenceClass?: string | null;
  userVisible?: boolean | null;
  [key: string]: unknown;
}

export interface PortfolioRiskEvidenceFreshness extends PortfolioEvidenceMetadata {
  [key: string]: unknown;
}

export interface PortfolioRiskEvidencePacket {
  source?: string | null;
  sourceLabel?: string | null;
  freshnessLabel?: string | null;
  asOf?: string | null;
  isFallback?: boolean | null;
  isStale?: boolean | null;
  isPartial?: boolean | null;
  isUnavailable?: boolean | null;
  coverage?: Record<string, unknown> | null;
  confidenceWeight?: number | null;
  degradationReason?: string | null;
  capReason?: string | null;
  state?: string | null;
  status?: string | null;
  engine?: string | null;
  entity?: PortfolioRiskEvidenceEntity | null;
  runId?: string | null;
  evidenceVersion?: string | null;
  requiredEvidence?: PortfolioRiskEvidenceItem[];
  optionalEvidence?: PortfolioRiskEvidenceItem[];
  freshness?: PortfolioRiskEvidenceFreshness | null;
  qualityFlags?: string[];
  decisionStatus?: string | null;
  confidenceCap?: PortfolioRiskConfidenceCap | null;
  sourceRefs?: PortfolioRiskEvidenceSourceRef[];
  explainableFacts?: PortfolioRiskExplainableFact[];
  adminDiagnostics?: Record<string, unknown>;
  limitationLabels?: string[];
  [key: string]: unknown;
}

export interface PortfolioRiskDiagnostics extends PortfolioEvidenceMetadata {
  holdingsLineage?: PortfolioRiskEvidenceSection | null;
  cashLedgerCompleteness?: PortfolioRiskEvidenceSection | null;
  transactionLineage?: PortfolioRiskEvidenceSection | null;
  fxFreshness?: PortfolioRiskEvidenceSection | null;
  costBasisCoverage?: PortfolioRiskEvidenceSection | null;
  sourceAuthority?: PortfolioRiskEvidenceSection | null;
  benchmarkFactorMapping?: PortfolioRiskEvidenceSection | null;
  confidenceCap?: PortfolioRiskConfidenceCap | null;
  evidencePacket?: PortfolioRiskEvidencePacket | null;
  [key: string]: unknown;
}

export interface PortfolioRiskDiagnosticsStateFields {
  sourceAuthorityState?: string | null;
  fxFreshnessState?: string | null;
  holdingsLineageState?: string | null;
  cashLedgerCompletenessState?: string | null;
  benchmarkMappingState?: string | null;
  factorMappingState?: string | null;
}

export interface PortfolioRiskDiagnosticsResponseFields extends PortfolioRiskDiagnosticsStateFields {
  riskDiagnostics?: PortfolioRiskDiagnostics | null;
  portfolioRiskEvidence?: PortfolioRiskEvidencePacket | null;
  confidenceCap?: PortfolioRiskConfidenceCap | null;
}

export interface PortfolioSnapshotResponse extends PortfolioEvidenceMetadata, PortfolioRiskDiagnosticsResponseFields {
  asOf: string;
  costMethod: PortfolioCostMethod;
  currency: string;
  accountCount: number;
  totalCash: number;
  totalMarketValue: number;
  totalEquity: number;
  realizedPnl: number;
  unrealizedPnl: number;
  feeTotal: number;
  taxTotal: number;
  fxStale: boolean;
  fxRates?: PortfolioFxRateItem[];
  portfolioAttribution?: Record<string, unknown>;
  analytics?: PortfolioAnalyticsSummary | null;
  accounts: PortfolioAccountSnapshot[];
}

export interface PortfolioConcentrationItem {
  symbol: string;
  marketValueBase: number;
  weightPct: number;
  isAlert: boolean;
}

export interface PortfolioSectorConcentrationItem {
  sector: string;
  marketValueBase: number;
  weightPct: number;
  symbolCount: number;
  isAlert: boolean;
}

export interface PortfolioDrawdownBlock {
  seriesPoints: number;
  maxDrawdownPct: number;
  currentDrawdownPct: number;
  alert: boolean;
  fxStale: boolean;
}

export interface PortfolioStopLossItem {
  accountId: number;
  symbol: string;
  avgCost: number;
  lastPrice: number;
  lossPct: number;
  nearThresholdPct: number;
  isTriggered: boolean;
}

export interface PortfolioRiskResponse extends PortfolioEvidenceMetadata, PortfolioRiskDiagnosticsResponseFields {
  asOf: string;
  accountId?: number | null;
  costMethod: PortfolioCostMethod;
  currency: string;
  thresholds: Record<string, number>;
  concentration: {
    totalMarketValue: number;
    topWeightPct: number;
    alert: boolean;
    topPositions: PortfolioConcentrationItem[];
  };
  sectorConcentration: {
    totalMarketValue: number;
    topWeightPct: number;
    alert: boolean;
    topSectors: PortfolioSectorConcentrationItem[];
    coverage: Record<string, number>;
    errors: string[];
  };
  drawdown: PortfolioDrawdownBlock;
  industryAttribution?: Record<string, unknown>;
  accountAttribution?: Record<string, unknown>;
  stopLoss: {
    nearAlert: boolean;
    triggeredCount: number;
    nearCount: number;
    items: PortfolioStopLossItem[];
  };
}

export interface PortfolioTradeCreateRequest {
  accountId: number;
  symbol: string;
  tradeDate: string;
  side: PortfolioSide;
  quantity: number;
  price: number;
  fee?: number;
  tax?: number;
  market?: 'cn' | 'hk' | 'us';
  currency?: string;
  tradeUid?: string;
  note?: string;
}

export interface PortfolioTradeUpdateRequest {
  accountId?: number;
  symbol?: string;
  tradeDate?: string;
  side?: PortfolioSide;
  quantity?: number;
  price?: number;
  fee?: number;
  tax?: number;
  market?: 'cn' | 'hk' | 'us';
  currency?: string;
  note?: string;
}

export interface PortfolioCashLedgerCreateRequest {
  accountId: number;
  eventDate: string;
  direction: PortfolioCashDirection;
  amount: number;
  currency?: string;
  note?: string;
}

export interface PortfolioCorporateActionCreateRequest {
  accountId: number;
  symbol: string;
  effectiveDate: string;
  actionType: PortfolioCorporateActionType;
  market?: 'cn' | 'hk' | 'us';
  currency?: string;
  cashDividendPerShare?: number;
  splitRatio?: number;
  note?: string;
}

export interface PortfolioEventCreatedResponse {
  id: number;
}

export interface PortfolioDeleteResponse {
  deleted: number;
  deleteMode?: 'soft' | 'hard' | null;
}

export interface PortfolioTradeListItem {
  id: number;
  accountId: number;
  tradeUid?: string | null;
  symbol: string;
  market: string;
  currency: string;
  tradeDate: string;
  side: PortfolioSide;
  quantity: number;
  price: number;
  fee: number;
  tax: number;
  note?: string | null;
  isActive?: boolean;
  voidedAt?: string | null;
  createdAt?: string | null;
  updatedAt?: string | null;
}

export interface PortfolioTradeListResponse {
  items: PortfolioTradeListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PortfolioCashLedgerListItem {
  id: number;
  accountId: number;
  eventDate: string;
  direction: PortfolioCashDirection;
  amount: number;
  currency: string;
  note?: string | null;
  createdAt?: string | null;
}

export interface PortfolioCashLedgerListResponse {
  items: PortfolioCashLedgerListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PortfolioCorporateActionListItem {
  id: number;
  accountId: number;
  symbol: string;
  market: string;
  currency: string;
  effectiveDate: string;
  actionType: PortfolioCorporateActionType;
  cashDividendPerShare?: number | null;
  splitRatio?: number | null;
  note?: string | null;
  createdAt?: string | null;
}

export interface PortfolioCorporateActionListResponse {
  items: PortfolioCorporateActionListItem[];
  total: number;
  page: number;
  pageSize: number;
}

export interface PortfolioImportTradeItem {
  tradeDate: string;
  symbol: string;
  side: PortfolioSide;
  quantity: number;
  price: number;
  fee: number;
  tax: number;
  tradeUid?: string | null;
  dedupHash: string;
  market?: string | null;
  currency?: string | null;
  note?: string | null;
}

export interface PortfolioImportCashEntryItem {
  eventDate: string;
  direction: PortfolioCashDirection;
  amount: number;
  currency: string;
  note?: string | null;
}

export interface PortfolioImportCorporateActionItem {
  effectiveDate: string;
  symbol: string;
  market: string;
  currency: string;
  actionType: PortfolioCorporateActionType;
  cashDividendPerShare?: number | null;
  splitRatio?: number | null;
  note?: string | null;
}

export interface PortfolioImportParseResponse {
  broker: string;
  recordCount: number;
  skippedCount: number;
  errorCount: number;
  records: PortfolioImportTradeItem[];
  cashRecordCount: number;
  cashEntries: PortfolioImportCashEntryItem[];
  corporateActionCount: number;
  corporateActions: PortfolioImportCorporateActionItem[];
  warnings: string[];
  metadata: Record<string, unknown>;
  errors: string[];
}

export interface PortfolioImportCommitResponse {
  accountId: number;
  recordCount: number;
  insertedCount: number;
  duplicateCount: number;
  failedCount: number;
  cashRecordCount: number;
  cashInsertedCount: number;
  cashFailedCount: number;
  corporateActionCount: number;
  corporateActionInsertedCount: number;
  corporateActionFailedCount: number;
  dryRun: boolean;
  duplicateImport: boolean;
  brokerConnectionId?: number | null;
  warnings: string[];
  metadata: Record<string, unknown>;
  errors: string[];
}

export interface PortfolioImportBrokerItem {
  broker: string;
  aliases: string[];
  displayName?: string;
  fileExtensions?: string[];
}

export interface PortfolioImportBrokerListResponse {
  brokers: PortfolioImportBrokerItem[];
}

export interface PortfolioFxRefreshResponse {
  asOf: string;
  accountCount: number;
  refreshEnabled?: boolean;
  disabledReason?: string | null;
  pairCount: number;
  updatedCount: number;
  staleCount: number;
  errorCount: number;
}
