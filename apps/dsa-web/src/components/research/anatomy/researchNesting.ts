import type { ResearchFrameRole } from './types';

/**
 * Visual nesting budget for consumer research composition:
 * maximum two visible frame layers before inner content uses dividers/rows.
 *
 * Encouraged:
 *   board → section → rows
 *
 * Discouraged:
 *   board → card → card → mini-card
 *
 * Admin/operator surfaces are intentionally out of scope.
 */
export const RESEARCH_NESTING_MAX_VISIBLE_FRAMES = 2;

export const RESEARCH_FRAME_ATTR = 'data-research-frame';
export const RESEARCH_FRAME_DEPTH_ATTR = 'data-research-frame-depth';
export const RESEARCH_SURFACE_SCOPE_ATTR = 'data-research-surface-scope';

export type ResearchSurfaceScope = 'consumer' | 'admin';

export function frameRoleContributesToBudget(role: ResearchFrameRole): boolean {
  // Content layer uses dividers/rows and does not count as a chrome frame.
  return role === 'board' || role === 'section';
}

export function computeFrameDepth(
  parentDepth: number | null | undefined,
  role: ResearchFrameRole,
): number {
  const base = typeof parentDepth === 'number' && Number.isFinite(parentDepth) ? Math.max(0, parentDepth) : 0;
  if (!frameRoleContributesToBudget(role)) {
    return base;
  }
  return base + 1;
}

export function isWithinNestingBudget(depth: number): boolean {
  return depth <= RESEARCH_NESTING_MAX_VISIBLE_FRAMES;
}

/**
 * Counts contributing frame layers from a composed depth chain.
 * Used by tests and lightweight composition helpers — not a repo-wide linter.
 */
export function countContributingFrames(roles: ResearchFrameRole[]): number {
  return roles.filter(frameRoleContributesToBudget).length;
}

export function nestingBudgetViolation(
  roles: ResearchFrameRole[],
): { ok: true } | { ok: false; depth: number; max: number } {
  const depth = countContributingFrames(roles);
  if (isWithinNestingBudget(depth)) {
    return { ok: true };
  }
  return {
    ok: false,
    depth,
    max: RESEARCH_NESTING_MAX_VISIBLE_FRAMES,
  };
}

export function researchFrameDataAttributes(
  role: ResearchFrameRole,
  depth: number,
  scope: ResearchSurfaceScope = 'consumer',
): Record<string, string | number> {
  return {
    [RESEARCH_FRAME_ATTR]: role,
    [RESEARCH_FRAME_DEPTH_ATTR]: depth,
    [RESEARCH_SURFACE_SCOPE_ATTR]: scope,
  };
}
