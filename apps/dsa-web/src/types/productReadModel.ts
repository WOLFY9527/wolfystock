export type ProductReadModelState =
  | 'available'
  | 'partial'
  | 'stale'
  | 'unavailable'
  | 'insufficient'
  | 'no_evidence'
  | 'degraded'
  | 'rejected'
  | 'pending'
  | string;

export type ProductReadModelChild = {
  name?: string | null;
  state?: ProductReadModelState | null;
  critical?: boolean | null;
};

export type ProductReadModelFreshness = {
  state?: ProductReadModelState | null;
  asOf?: string | null;
  coveredDateRange?: Record<string, unknown> | null;
};

export type ProductReadModelProvenance = {
  sourceClass?: string | null;
  asOf?: string | null;
  freshness?: ProductReadModelState | null;
  quality?: ProductReadModelState | string | null;
};

export type ProductReadModelClassification = {
  observedState?: string | null;
  displayState?: string | null;
  strongConclusionAllowed?: boolean | null;
};

export type ProductReadModelConfidence = {
  label?: string | null;
  state?: string | null;
  strongConclusionAllowed?: boolean | null;
  reasons?: string[] | null;
};

export type ProductReadModelCoverage = {
  state?: ProductReadModelState | null;
  start?: string | null;
  end?: string | null;
  barCount?: number | null;
  requiredBars?: number | null;
  availableBars?: number | null;
};

export type ProductReadModelQuality = {
  state?: ProductReadModelState | null;
  missingDataClasses?: string[] | null;
  sourceQualityState?: string | null;
};

export type ProductReadModelEvidence = {
  missingEvidenceCount?: number | null;
  readinessState?: ProductReadModelState | null;
  dataQualityState?: ProductReadModelState | null;
};

export type ProductReadModel = {
  contractVersion?: string | null;
  surface?: string | null;
  state?: ProductReadModelState | null;
  ready?: boolean | null;
  children?: ProductReadModelChild[] | null;
  criticalChildStates?: Record<string, ProductReadModelState | string | null> | null;
  blockingChildren?: string[] | null;
  freshness?: ProductReadModelFreshness | null;
  provenance?: ProductReadModelProvenance | null;
  classification?: ProductReadModelClassification | null;
  confidence?: ProductReadModelConfidence | null;
  coverage?: ProductReadModelCoverage | null;
  quality?: ProductReadModelQuality | null;
  evidence?: ProductReadModelEvidence | null;
  observationOnly?: boolean | null;
  decisionGrade?: boolean | null;
  readOnly?: boolean | null;
  backtestExecuted?: boolean | null;
};
