import type { ResearchDensityMode } from './types';

export const RESEARCH_DENSITY_MODES = ['editorial', 'research', 'workbench'] as const satisfies ReadonlyArray<ResearchDensityMode>;

export function isResearchDensityMode(value: unknown): value is ResearchDensityMode {
  return value === 'editorial' || value === 'research' || value === 'workbench';
}

export function normalizeResearchDensityMode(
  value: unknown,
  fallback: ResearchDensityMode = 'research',
): ResearchDensityMode {
  return isResearchDensityMode(value) ? value : fallback;
}

/**
 * Page-family defaults for shared density adoption.
 * Pages may override; this is guidance for future migrations, not routing logic.
 */
export const RESEARCH_DENSITY_PAGE_DEFAULTS: Record<string, ResearchDensityMode> = {
  home: 'editorial',
  'decision-cockpit': 'editorial',
  structure: 'research',
  'market-overview': 'research',
  scenario: 'research',
  backtest: 'research',
  radar: 'research',
  watchlist: 'workbench',
  scanner: 'workbench',
  portfolio: 'workbench',
};

export function densityDataAttributes(density: ResearchDensityMode): {
  'data-research-density': ResearchDensityMode;
} {
  return { 'data-research-density': density };
}
