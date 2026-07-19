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

export function densityDataAttributes(density: ResearchDensityMode): {
  'data-research-density': ResearchDensityMode;
} {
  return { 'data-research-density': density };
}
