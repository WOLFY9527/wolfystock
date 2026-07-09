import type React from 'react';

/**
 * Shared research-page density modes for the Editorial Density Workbench.
 * Exactly three modes — spacing/composition only, not separate design systems.
 */
export type ResearchDensityMode = 'editorial' | 'research' | 'workbench';

/**
 * Visible frame roles for nesting budget:
 * board → section → rows/content (max two visible frame layers before dividers).
 */
export type ResearchFrameRole = 'board' | 'section' | 'content';

export type ResearchLocale = 'zh' | 'en';

export type ResearchQualityFacetKind =
  | 'freshness'
  | 'coverage'
  | 'authority'
  | 'lineage'
  | 'partial'
  | 'degraded'
  | 'delayed'
  | 'cached'
  | 'stale'
  | 'unavailable'
  | 'blocked'
  | 'observation-only';

export type ResearchQualityFacet = {
  kind: ResearchQualityFacetKind;
  label: React.ReactNode;
  value?: React.ReactNode;
  detail?: React.ReactNode;
  tone?: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  key?: React.Key;
};

export type ResearchObservationFact = {
  key?: React.Key;
  label?: React.ReactNode;
  body: React.ReactNode;
};

export type NextResearchActionKind =
  | 'inspect'
  | 'compare'
  | 'validate'
  | 'handoff'
  | 'continue'
  | 'gap';

export type NextResearchActionItem = {
  key?: React.Key;
  kind?: NextResearchActionKind;
  label: React.ReactNode;
  description?: React.ReactNode;
  href?: string;
  onClick?: () => void;
  external?: boolean;
};

export type ResearchRiskLimitItem = {
  key?: React.Key;
  body: React.ReactNode;
};

export type ResearchRiskLimitsPlacement = 'rail' | 'disclosure' | 'summary';
