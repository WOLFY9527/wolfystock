export type MarketOverviewDataStateStripView = {
  availableCount: number;
  fallbackCount: number;
  staleCount: number;
  hasUnavailable: boolean;
  unavailableCount: number;
  hasFallback: boolean;
  needsRefresh: boolean;
  isRefreshing: boolean;
  updatedAtLabel: string;
  variant: 'neutral' | 'info' | 'caution';
};

export type MarketOverviewTemperatureSummaryView = {
  reliable: boolean;
  valueText: string;
  toneClass: string;
  label: string;
  confidenceLabel: string;
  reliableInputCount: number;
  fallbackInputCount: number;
  excludedInputCount: number;
};

export type MarketOverviewBriefingSummaryView = {
  confidenceLabel: string;
  toneClass: string;
  leadMessage: string;
  warning?: string;
};

export type MarketOverviewDecisionSemanticsLineView = {
  key: string;
  label: string;
  meta?: string;
};

export type MarketOverviewDecisionSemanticsBoundaryView = {
  key: string;
  label: string;
  allowed: boolean;
  reasonCode?: string;
};

export type MarketOverviewDirectionReadinessPillarView = {
  key: string;
  label: string;
  reasonCode?: string;
};

export type MarketOverviewDirectionReadinessView = {
  status: 'direction_ready' | 'partial_context_only' | 'data_insufficient' | string;
  statusLabel: string;
  statusVariant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  confidenceLabel: string;
  scoreGradeCount: number;
  observationOnlyCount: number;
  missingCount: number;
  scoreGradePillars: MarketOverviewDirectionReadinessPillarView[];
  observationOnlyPillars: MarketOverviewDirectionReadinessPillarView[];
  missingPillars: MarketOverviewDirectionReadinessPillarView[];
  blockingReasons: string[];
  notInvestmentAdvice: boolean;
};

export type MarketOverviewDecisionSemanticsView = {
  postureLabel: string;
  confidenceLabel: string;
  confidenceValueText: string;
  exposureBiasLabel: string;
  insufficient: boolean;
  capReasons: string[];
  styleTilts: MarketOverviewDecisionSemanticsLineView[];
  confirmationSignals: MarketOverviewDecisionSemanticsLineView[];
  invalidationTriggers: MarketOverviewDecisionSemanticsLineView[];
  counterEvidence: MarketOverviewDecisionSemanticsLineView[];
  dataGaps: MarketOverviewDecisionSemanticsLineView[];
  directionReadiness?: MarketOverviewDirectionReadinessView;
  claimBoundaries: MarketOverviewDecisionSemanticsBoundaryView[];
  notInvestmentAdvice: boolean;
};
