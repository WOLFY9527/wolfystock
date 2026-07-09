/**
 * Shared Research Anatomy Foundation (Wave C0)
 *
 * Editorial Density Workbench primitives for page-family migrations:
 * conclusion → evidence → data quality → risk limits → next research action
 *
 * Consumer pages are paper-first. Admin/operator surfaces remain separate.
 * Do not introduce recommendation language or parallel design systems.
 */

export type {
  NextResearchActionItem,
  NextResearchActionKind,
  ResearchDensityMode,
  ResearchFrameRole,
  ResearchLocale,
  ResearchObservationFact,
  ResearchQualityFacet,
  ResearchQualityFacetKind,
  ResearchRiskLimitItem,
  ResearchRiskLimitsPlacement,
} from './types';

export {
  RESEARCH_DENSITY_MODES,
  RESEARCH_DENSITY_PAGE_DEFAULTS,
  densityDataAttributes,
  isResearchDensityMode,
  normalizeResearchDensityMode,
} from './researchDensity';

export {
  RESEARCH_FRAME_ATTR,
  RESEARCH_FRAME_DEPTH_ATTR,
  RESEARCH_NESTING_MAX_VISIBLE_FRAMES,
  RESEARCH_SURFACE_SCOPE_ATTR,
  computeFrameDepth,
  countContributingFrames,
  frameRoleContributesToBudget,
  isResearchFrameRole,
  isWithinNestingBudget,
  nestingBudgetViolation,
  researchFrameDataAttributes,
  type ResearchSurfaceScope,
} from './researchNesting';

export {
  LeadText,
  MetaLabel,
  MetricValue,
  ObservationTitle,
  SectionTitle,
} from './ResearchTypography';

export { ResearchFrame } from './ResearchFrame';
export { ObservationHead, type ObservationHeadProps } from './ObservationHead';
export {
  ResearchDataQualityComposition,
  type ResearchDataQualityCompositionProps,
} from './ResearchDataQualityComposition';
export {
  ResearchRiskLimits,
  type ResearchRiskLimitsProps,
} from './ResearchRiskLimits';
export {
  NextResearchAction,
  type NextResearchActionProps,
} from './NextResearchAction';
