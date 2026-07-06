import type { ProductReadModel } from './productReadModel';

export interface StockEvidenceFundamentalsSummary {
  marketCap?: number;
  peTtm?: number;
  pb?: number;
  beta?: number;
  revenueTtm?: number;
  netIncomeTtm?: number;
  fcfTtm?: number;
  grossMargin?: number;
  operatingMargin?: number;
  roe?: number;
  roa?: number;
  period?: string;
  source?: string;
  freshness?: string;
  missingFields: string[];
  notInvestmentAdvice: boolean;
  observationOnly: boolean;
  scoreContributionAllowed: boolean;
  sourceAuthorityAllowed: boolean;
}

export type StockEvidencePacket = Record<string, unknown> & {
  fundamentalsSummary?: StockEvidenceFundamentalsSummary;
};

export type SymbolEvidenceReadinessTier = 'sufficient' | 'partial' | 'insufficient';

export interface SymbolEvidenceReadiness {
  symbolEvidenceReadiness: true;
  symbol: string;
  readinessTier: SymbolEvidenceReadinessTier;
  evidenceUsed: string[];
  evidenceMissing: string[];
  staleInputs: string[];
  conflictingEvidence: string[];
  dataQualityNotes: string[];
  suggestedResearchPath: string[];
  observationOnly: true;
  noAdviceDisclosure: string;
}

export interface StockEvidenceItem {
  symbol: string;
  market?: string | null;
  productReadModel?: ProductReadModel | null;
  quote?: Record<string, unknown> | null;
  technical?: Record<string, unknown> | null;
  fundamental?: Record<string, unknown> | null;
  news?: Record<string, unknown> | null;
  secFilingEvidence?: Record<string, unknown> | null;
  stockEvidencePacket?: StockEvidencePacket;
  symbolEvidenceReadiness?: SymbolEvidenceReadiness;
}

export interface StockEvidenceMeta {
  generatedAt?: string | null;
  source?: string | null;
}

export interface StockEvidenceResponse {
  symbols: string[];
  items: StockEvidenceItem[];
  meta?: StockEvidenceMeta;
}
