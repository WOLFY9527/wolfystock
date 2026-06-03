export type ResearchReadinessState =
  | 'ready'
  | 'observe_only'
  | 'insufficient'
  | 'blocked'
  | 'waiting'
  | string;

export type ResearchSourceAuthority =
  | 'scoreGradeAllowed'
  | 'observationOnly'
  | 'unavailable'
  | string;

export type ResearchFreshnessFloor =
  | 'live'
  | 'fresh'
  | 'delayed'
  | 'cached'
  | 'stale'
  | 'fallback'
  | 'synthetic'
  | 'unknown'
  | string;

export interface ResearchEvidenceCoverage {
  scoreGradeCount?: number;
  observationOnlyCount?: number;
  missingCount?: number;
  totalCount?: number;
}

export interface ResearchReadinessV1 {
  contractVersion?: string;
  researchReady?: boolean;
  readinessState: ResearchReadinessState;
  verdictLabel?: string;
  blockingReasons?: string[];
  missingEvidence?: string[];
  evidenceCoverage?: ResearchEvidenceCoverage | null;
  sourceAuthority?: ResearchSourceAuthority;
  freshnessFloor?: ResearchFreshnessFloor;
  consumerActionBoundary?: string;
  nextEvidenceNeeded?: string[];
  debugRef?: string;
}

export interface ScannerContextSignalFrame {
  state?: string | null;
  label?: string | null;
  source?: string | null;
  freshness?: string | null;
  blockers?: string[] | null;
  observationOnly?: boolean | null;
  sourceAuthorityAllowed?: boolean | null;
  scoreContributionAllowed?: boolean | null;
  proxyOnly?: boolean | null;
}

export interface ScannerContextThemeItem {
  id?: string | null;
  label?: string | null;
  observationOnly?: boolean | null;
  proxyOnly?: boolean | null;
}

export interface ScannerContextThemeFrame extends ScannerContextSignalFrame {
  themes?: ScannerContextThemeItem[] | null;
}

export interface ScannerContextFrame {
  marketReadiness?: ResearchReadinessV1 | null;
  macroRegime?: ScannerContextSignalFrame | null;
  liquidityFrame?: ScannerContextSignalFrame | null;
  assetClassBias?: ScannerContextSignalFrame | null;
  themeFrame?: ScannerContextThemeFrame | null;
  universePolicy?: {
    type?: string | null;
    label?: string | null;
    blockers?: string[] | null;
  } | null;
  noAdviceBoundary?: boolean | null;
}

export interface OptionsNoTradingBoundary {
  analyticalOnly?: boolean;
  noBrokerExecution?: boolean;
  noOrderPlacement?: boolean;
  noPortfolioMutation?: boolean;
  noTradingRecommendation?: boolean;
}

export interface OptionsResearchReadiness {
  optionsResearchReady?: boolean;
  readinessState?: string;
  dataQualityTier?: string;
  decisionGrade?: boolean;
  providerAuthority?: ResearchSourceAuthority;
  liquidityGate?: string;
  ivGreeksGate?: string;
  spreadGate?: string;
  scenarioCoverage?: string;
  noTradingBoundary?: OptionsNoTradingBoundary | null;
  blockingReasons?: string[];
  nextEvidenceNeeded?: string[];
}

export type ConsumerReadinessTone = 'success' | 'info' | 'caution' | 'danger' | 'neutral';

export interface ConsumerReadinessChip {
  key: string;
  label: string;
}

export interface ConsumerResearchReadinessView {
  state: ResearchReadinessState;
  verdictLabel: string;
  tone: ConsumerReadinessTone;
  summaryLine: string;
  chips: ConsumerReadinessChip[];
}
