import { describe, expect, it } from 'vitest';

import { presentConsumerSymbolIdentity } from '../consumerSymbolIdentityPresentation';

describe('presentConsumerSymbolIdentity', () => {
  it('presents explicitly resolved names for US, CN, and HK canonical identities', () => {
    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'AAPL',
      displayName: 'Apple Inc.',
      displayNameState: 'resolved',
      market: 'us',
      provenance: 'authoritative',
    })).toMatchObject({
      primarySymbol: 'AAPL',
      displayName: 'Apple Inc.',
      combinedLabel: 'AAPL · Apple Inc.',
      contextLabel: 'Apple Inc. · us',
      isAuthoritative: true,
    });

    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: '600519',
      displayName: '贵州茅台',
      displayNameState: 'resolved',
      market: 'cn',
    }).combinedLabel).toBe('600519 · 贵州茅台');

    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'HK00700',
      displayName: '腾讯控股',
      displayNameState: 'resolved',
      market: 'hk',
    }).combinedLabel).toBe('HK00700 · 腾讯控股');
  });

  it('does not promote fallback, missing, or unproven legacy names into display identity', () => {
    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'AAPL',
      displayName: 'AAPL',
      displayNameState: 'symbol_fallback',
      market: 'us',
    })).toMatchObject({
      combinedLabel: 'AAPL',
      displayName: null,
      contextLabel: 'us',
    });

    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'aapl',
      market: 'us',
    })).toMatchObject({
      primarySymbol: 'AAPL',
      combinedLabel: 'AAPL',
      displayName: null,
      contextLabel: 'us',
    });

    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'AAPL',
      displayName: 'Apple Inc.',
      market: 'us',
    })).toMatchObject({
      combinedLabel: 'AAPL',
      displayName: null,
      displayNameState: 'unknown',
      contextLabel: 'us',
    });
  });

  it('retains resolved truth when a pathological resolved name matches the symbol while suppressing visual repetition', () => {
    const identity = presentConsumerSymbolIdentity({
      canonicalSymbol: 'AAPL',
      displayName: 'AAPL',
      displayNameState: 'resolved',
      market: 'us',
      provenance: 'authoritative',
    });

    expect(identity.displayNameState).toBe('resolved');
    expect(identity.displayName).toBe('AAPL');
    expect(identity.combinedLabel).toBe('AAPL');
    expect(identity.contextLabel).toBe('us');

    expect(presentConsumerSymbolIdentity({
      canonicalSymbol: 'AAPL',
      displayName: 'aapl',
      displayNameState: 'resolved',
      market: 'us',
    }).combinedLabel).toBe('AAPL');
  });

  it('retains fixture and demo provenance without turning those identities into authoritative claims', () => {
    const fixtureIdentity = presentConsumerSymbolIdentity({
      canonicalSymbol: 'TEM',
      displayName: 'Tempus AI',
      displayNameState: 'resolved',
      provenance: 'fixture',
    });

    expect(fixtureIdentity.combinedLabel).toBe('TEM · Tempus AI');
    expect(fixtureIdentity.provenance).toBe('fixture');
    expect(fixtureIdentity.isAuthoritative).toBe(false);

    const demoIdentity = presentConsumerSymbolIdentity({
      canonicalSymbol: 'DEMO',
      displayName: 'Demo Co.',
      displayNameState: 'resolved',
      provenance: 'demo',
    });
    expect(demoIdentity.provenance).toBe('demo');
    expect(demoIdentity.isAuthoritative).toBe(false);
  });
});
