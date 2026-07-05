import apiClient from './index';
import { toCamelCase } from './utils';
import type { ProductReadModel } from '../types/productReadModel';

export type DashboardOverviewStatus = 'ready' | 'partial' | 'no_evidence' | 'unavailable' | string;
export type DashboardPublicState = 'ready' | 'delayed' | 'cached' | 'partial' | 'no_evidence' | 'unavailable' | string;

export type DashboardMetric = {
  label: string;
  value: string;
  change: string;
  status: DashboardPublicState;
};

export type DashboardSummaryItem = {
  summary: string;
  status: DashboardPublicState;
};

export type DashboardMarketIntelligenceOverview = {
  status: DashboardOverviewStatus;
  asOf: string;
  marketPulse: {
    sp500: DashboardMetric;
    nasdaq: DashboardMetric;
    russell2000: DashboardMetric;
    vix: DashboardMetric;
    tenYearYield: DashboardMetric;
    dollarIndex: DashboardMetric;
    marketBreadth: DashboardSummaryItem;
    liquidityState: string;
  };
  marketBrief: {
    headline: string;
    summary: string;
    status: DashboardOverviewStatus;
  };
  moneyFlow: {
    topInflows: string[];
    topOutflows: string[];
    styleBias: string;
    offensiveDefensiveBias: string;
    sourceStatus: DashboardPublicState;
    status: DashboardOverviewStatus;
  };
  liquidityRisk: {
    summary: string;
    volatilityTone: string;
    fundingStress: string;
    dollarRatePressure: string;
    status: DashboardOverviewStatus;
  };
  sectorThemeRotation: {
    leadingThemes: string[];
    laggingThemes: string[];
    diffusion: string;
    summary: string;
    status: DashboardOverviewStatus;
  };
  researchQueue: {
    status: DashboardOverviewStatus;
    items: Array<{
      title: string;
      summary: string;
      action: string;
      priority: string;
    }>;
  };
  dataQuality: {
    state: DashboardPublicState;
    label: string;
    summary: string;
    sections: Record<string, DashboardPublicState>;
  };
  productReadModel?: ProductReadModel | null;
  noAdviceDisclosure: string;
};

export const dashboardOverviewApi = {
  getMarketIntelligenceOverview: async (): Promise<DashboardMarketIntelligenceOverview> => {
    const response = await apiClient.get<Record<string, unknown>>(
      '/api/v1/dashboard/market-intelligence-overview',
      { timeoutTier: 'quick' },
    );
    return toCamelCase<DashboardMarketIntelligenceOverview>(response.data);
  },
};
