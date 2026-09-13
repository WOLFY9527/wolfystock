/**
 * Presentation-safe consumer identity projection.
 *
 * A symbol is always an instrument identifier. A display name becomes a
 * second identity component only when the producer explicitly marks it as
 * resolved. This keeps legacy name fields from becoming company-name truth.
 */

export type ConsumerDisplayNameState =
  | 'resolved'
  | 'symbol_fallback'
  | 'unresolved'
  | 'unavailable'
  | 'unknown';

export type ConsumerIdentityProvenance =
  | 'authoritative'
  | 'fixture'
  | 'demo'
  | 'unknown';

export type ConsumerSymbolIdentityInput = {
  canonicalSymbol?: string | null;
  displaySymbol?: string | null;
  displayName?: string | null;
  displayNameState?: string | null;
  market?: string | null;
  exchange?: string | null;
  provenance?: string | null;
};

export type ConsumerSymbolIdentityPresentation = {
  primarySymbol: string;
  displayName: string | null;
  displayNameState: ConsumerDisplayNameState;
  marketContext: string | null;
  provenance: ConsumerIdentityProvenance;
  /** Symbol plus a genuinely resolved, presentation-safe name when present. */
  combinedLabel: string;
  /** Name and market context only; useful beside a separately rendered symbol. */
  contextLabel: string | null;
  /** Fixture/demo names never become live or verified identity claims. */
  isAuthoritative: boolean;
};

const DISPLAY_NAME_STATES = new Set<ConsumerDisplayNameState>([
  'resolved',
  'symbol_fallback',
  'unresolved',
  'unavailable',
  'unknown',
]);

const IDENTITY_PROVENANCE = new Set<ConsumerIdentityProvenance>([
  'authoritative',
  'fixture',
  'demo',
  'unknown',
]);

function text(value: string | null | undefined): string | null {
  const normalized = String(value || '').trim();
  return normalized || null;
}

function displayNameState(value: string | null | undefined): ConsumerDisplayNameState {
  const normalized = text(value)?.toLowerCase().replace(/[\s-]+/g, '_');
  return normalized && DISPLAY_NAME_STATES.has(normalized as ConsumerDisplayNameState)
    ? normalized as ConsumerDisplayNameState
    : 'unknown';
}

function provenance(value: string | null | undefined): ConsumerIdentityProvenance {
  const normalized = text(value)?.toLowerCase().replace(/[\s-]+/g, '_');
  return normalized && IDENTITY_PROVENANCE.has(normalized as ConsumerIdentityProvenance)
    ? normalized as ConsumerIdentityProvenance
    : 'unknown';
}

/**
 * Projects typed identity facts without deriving semantic state from display
 * text. Equality is used only to avoid a visually repeated label after a
 * producer has explicitly classified the name as resolved.
 */
export function presentConsumerSymbolIdentity(
  input: ConsumerSymbolIdentityInput,
): ConsumerSymbolIdentityPresentation {
  const primarySymbol = (text(input.displaySymbol) || text(input.canonicalSymbol) || '--').toUpperCase();
  const state = displayNameState(input.displayNameState);
  const identityProvenance = provenance(input.provenance);
  const rawDisplayName = text(input.displayName);
  const resolvedDisplayName = state === 'resolved' ? rawDisplayName : null;
  const visuallyDistinctName = resolvedDisplayName && resolvedDisplayName.toUpperCase() !== primarySymbol
    ? resolvedDisplayName
    : null;
  const marketContext = text(input.exchange) || text(input.market);
  const contextLabel = [visuallyDistinctName, marketContext].filter((value): value is string => Boolean(value)).join(' · ') || null;

  return {
    primarySymbol,
    displayName: resolvedDisplayName,
    displayNameState: state,
    marketContext,
    provenance: identityProvenance,
    combinedLabel: visuallyDistinctName ? `${primarySymbol} · ${visuallyDistinctName}` : primarySymbol,
    contextLabel,
    isAuthoritative: identityProvenance === 'authoritative',
  };
}
