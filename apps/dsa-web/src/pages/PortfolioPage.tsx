import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { ArrowRightLeft, Copy, Download, MoreHorizontal, PenSquare, RefreshCw, Trash2 } from 'lucide-react';
import { portfolioApi, type PortfolioFxLineage, type PortfolioLineageStatusSummary, type PortfolioLineageSummary, type PortfolioPriceLineage, type PortfolioSnapshotWithLineage, type PortfolioValuationSnapshotLineage } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { Button } from '../components/common/Button';
import { Checkbox } from '../components/common/Checkbox';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
import { ConsumerOnboardingCtaPanel } from '../components/common/ConsumerOnboardingCtaPanel';
import { Drawer } from '../components/common/Drawer';
import { Input } from '../components/common/Input';
import { PillBadge } from '../components/common/PillBadge';
import { SectionShell } from '../components/common/SectionShell';
import { SegmentedControl } from '../components/common/SegmentedControl';
import { Select } from '../components/common/Select';
import { ConsumerWorkspacePageShell, ConsumerWorkspaceScope } from '../components/layout/ConsumerWorkspaceShell';
import {
  PortfolioScenarioRiskPanel,
  type PortfolioScenarioRiskVisiblePosition,
} from '../components/portfolio/PortfolioScenarioRiskPanel';
import {
  PortfolioExposureResearchContextPanel,
  PortfolioRiskExposureReadinessPanel,
} from '../components/portfolio/PortfolioExposureResearchContextPanel';
import { PortfolioTrustStrip, type PortfolioTrustChipItem } from '../components/portfolio/PortfolioTrustStrip';
import {
  TerminalButton,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalDisclosure,
  TerminalChip,
  TerminalEmptyState,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPanel,
} from '../components/terminal/TerminalPrimitives';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
} from '../hooks/useSafariInteractionReady';
import { useProductSurface } from '../hooks/useProductSurface';
import { translate } from '../i18n/core';
import { normalizePortfolioRiskEvidence } from '../utils/evidenceDisplay';
import { toDateInputValue } from '../utils/format';
import { buildLocalizedPath, parseLocaleFromPathname } from '../utils/localeRouting';
import { buildResearchWorkspacePath } from '../utils/researchWorkspaceRoute';
import {
  inferSettlementCurrency,
  LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY,
  normalizePortfolioDisplayCurrency,
  PORTFOLIO_DISPLAY_CURRENCY_CHANGED_EVENT,
  PORTFOLIO_DISPLAY_CURRENCY_OPTIONS,
  PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY,
  readPortfolioDisplayCurrency,
  savePortfolioDisplayCurrency,
  type PortfolioDisplayCurrency,
} from '../utils/portfolioPreferences';
import type {
  PortfolioAccountItem,
  PortfolioBrokerConnectionItem,
  PortfolioCashDirection,
  PortfolioCashLedgerListItem,
  PortfolioCorporateActionListItem,
  PortfolioCorporateActionType,
  PortfolioCostMethod,
  PortfolioExposureItem,
  PortfolioFxRateItem,
  PortfolioImportBrokerItem,
  PortfolioImportCommitResponse,
  PortfolioImportParseResponse,
  PortfolioIbkrSyncResponse,
  PortfolioLiveFxRateResponse,
  PortfolioPositionItem,
  PortfolioSide,
  PortfolioStructureReviewResponse,
  PortfolioTradeListItem,
  PortfolioTradeUpdateRequest,
} from '../types/portfolio';

const PORTFOLIO_FIELD_LABEL_CLASS = '!mb-1 text-[11px] font-medium tracking-normal text-[color:var(--wolfy-text-muted)]';
const PORTFOLIO_FIELD_WRAPPER_CLASS = 'flex flex-col gap-1.5';
const PORTFOLIO_FORM_GRID_CLASS = 'mt-4 grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2';
const PORTFOLIO_INPUT_CLASS = 'h-10 rounded-lg border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2.5 text-sm text-[color:var(--wolfy-text-primary)] placeholder:text-[color:var(--wolfy-text-muted)] outline-none focus:border-[color:var(--wolfy-accent)]';
const PORTFOLIO_SELECT_CLASS = 'min-w-0';
const PORTFOLIO_PRIMARY_BUTTON_CLASS = 'border border-[color:var(--theme-button-primary-border)] bg-[var(--theme-button-primary-bg)] text-[color:var(--theme-button-primary-text)] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[var(--sage-deep)] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SUBMIT_BUTTON_CLASS = 'mt-5 w-full border border-[color:var(--theme-button-primary-border)] bg-[var(--theme-button-primary-bg)] text-[color:var(--theme-button-primary-text)] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[var(--sage-deep)] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SECONDARY_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-divider)] px-4 py-2.5 rounded-md transition-colors';
const PORTFOLIO_TEXT_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-transparent text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] px-3 py-1.5 rounded-md text-xs transition-colors disabled:text-[color:var(--wolfy-text-muted)] disabled:opacity-50';
const PORTFOLIO_ICON_BUTTON_CLASS = 'size-9 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-0 text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]';
const PORTFOLIO_DANGER_GHOST_CLASS = 'size-8 rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-transparent p-0 text-[color:var(--wolfy-market-down)] hover:bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)]';
const CASH_CURRENCY_OPTIONS = ['CNY', 'HKD', 'USD'] as const;
const FX_CURRENCY_OPTIONS = ['USD', 'CNY', 'HKD', 'EUR', 'JPY', 'GBP'] as const;
const LEGACY_RECOVERY_TOKEN = ['fall', 'back'].join('');
const LEGACY_PRICE_RECOVERY_TOKEN = ['price', LEGACY_RECOVERY_TOKEN].join('_');
const LEGACY_FX_RECOVERY_TOKEN = ['fx', LEGACY_RECOVERY_TOKEN, '1', 'to', '1'].join('_');
const PORTFOLIO_VALUATION_EVIDENCE_PACK_SCHEMA = 'portfolio_valuation_evidence_pack_v1';
const UNKNOWN_EVIDENCE_VALUE = 'unknown/待补证';

const DEFAULT_PAGE_SIZE = 20;

function subscribeNarrowViewport(onStoreChange: () => void): () => void {
  if (typeof window === 'undefined') {
    return () => {};
  }

  window.addEventListener('resize', onStoreChange);
  return () => window.removeEventListener('resize', onStoreChange);
}

function getNarrowViewportSnapshot(): boolean {
  return typeof window !== 'undefined' ? window.innerWidth <= 390 : false;
}

type AccountOption = 'all' | number;
type EventType = 'trade' | 'cash' | 'corporate';
type TradeFormType = 'stock' | 'fund' | 'corporate';
type ExposureTab = 'account' | 'currency' | 'market' | 'symbol' | 'sector';

type FlatPosition = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

type PortfolioSegmentOption = {
  value: string;
  label: React.ReactNode;
};

type DisplayFxRate = {
  rate: number;
  timestamp?: string;
  provider?: string;
  cacheHit?: boolean;
  isStale?: boolean;
};

type DisplayCurrency = PortfolioDisplayCurrency;

type ConvertedMoney = {
  value: number;
  currency: DisplayCurrency;
  rate: number;
  stale: boolean;
} | null;

type PendingDelete =
  | { eventType: 'trade'; id: number; title: string; message: string; confirmText: string }
  | { eventType: 'cash'; id: number; message: string }
  | { eventType: 'corporate'; id: number; message: string };

type EditingTrade = {
  id: number;
  accountId: number;
  symbol: string;
  side: PortfolioSide;
  quantity: string;
  price: string;
  tradeDate: string;
  currency: string;
  currencyManuallyEdited: boolean;
  fee: string;
  tax: string;
  note: string;
};

type FxRefreshFeedback = {
  tone: 'neutral' | 'success' | 'warning';
  text: string;
};

type FxRefreshContext = {
  viewKey: string;
  requestId: number;
};

type PortfolioLanguage = 'zh' | 'en';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

type TradeFormState = {
  symbol: string;
  tradeDate: string;
  side: PortfolioSide;
  currency: DisplayCurrency;
  quantity: string;
  price: string;
  fee: string;
  tax: string;
  tradeUid: string;
  note: string;
};

type CashFormState = {
  eventDate: string;
  direction: PortfolioCashDirection;
  amount: string;
  currency: string;
  note: string;
};

type CorporateActionFormState = {
  symbol: string;
  effectiveDate: string;
  actionType: PortfolioCorporateActionType;
  cashDividendPerShare: string;
  splitRatio: string;
  note: string;
};

type AccountFormState = {
  name: string;
  broker: string;
  market: 'cn' | 'hk' | 'us' | 'global';
  baseCurrency: string;
};

type PortfolioValuationEvidencePack = {
  schemaVersion: string;
  generatedAt: string;
  appSurface: string;
  account: {
    scope: 'all_accounts' | 'selected_account';
    label: string;
  };
  holdingsCount: number;
  valuationAsOf: string;
  priceLineage: {
    label: string;
    freshness: string;
    priceSourceLabels: string[];
    missingQuoteCount: number | string;
    staleQuoteCount: number | string;
    totalQuoteCount: number | string;
    affectedSymbols: string[];
    lastUpdatedAt: string;
  };
  fxLineage: {
    label: string;
    affectedCurrencies: string[];
    affectedPairs: string[];
    lastUpdatedAt: string;
  };
  valuationLineage: {
    label: string;
    positionCount: number | string;
    completePositionCount: number | string;
    partialPositionCount: number | string;
    blockedPositionCount: number | string;
    blockedBy: {
      priceSymbols: string[];
      fxPairs: string[];
      fxCurrencies: string[];
    };
    lastUpdatedAt: string;
  };
  valuationSummary: {
    totalMarketValue: string;
    totalEquity: string;
    totalCash: string;
    unrealizedPnl: string;
    currency: string;
  };
  warnings: string[];
  consumerBoundary: string;
};

function hasLimitedValuationConfidence(position: Pick<PortfolioPositionItem, 'valuationConfidence'>): boolean {
  return typeof position.valuationConfidence === 'number' && position.valuationConfidence < 1;
}

function positionPriceFreshnessLabel(position: Pick<PortfolioPositionItem, 'isPriceFallback' | 'priceAsOf'>, language: PortfolioLanguage): string {
  if (position.isPriceFallback) {
    return language === 'zh' ? '价格可能延迟' : 'Pricing may be delayed';
  }
  if (position.priceAsOf) {
    return language === 'zh' ? '价格快照' : 'Price snapshot';
  }
  return language === 'zh' ? '价格更新中' : 'Pricing updating';
}

function positionPriceFreshnessExplanation(position: Pick<PortfolioPositionItem, 'isPriceFallback' | 'priceAsOf'>, language: PortfolioLanguage): string {
  if (position.isPriceFallback) {
    return language === 'zh'
      ? '部分价格数据暂不可用，已使用最近一次可用数据。'
      : 'Some price data is temporarily unavailable; the latest available data is shown.';
  }
  if (!position.priceAsOf) {
    return language === 'zh'
      ? '价格数据更新中，稍后将自动刷新。'
      : 'Price data is updating and will refresh automatically.';
  }
  return positionPriceFreshnessLabel(position, language);
}

function limitedConfidenceLabel(language: PortfolioLanguage): string {
  return language === 'zh' ? '置信度有限' : 'Limited confidence';
}

function consumerFxLabel(state: 'fresh' | 'stale' | 'missing' | 'pending', language: PortfolioLanguage): string {
  if (language === 'zh') {
    switch (state) {
      case 'fresh':
        return '汇率已更新';
      case 'stale':
        return '汇率可能延迟';
      case 'missing':
        return '汇率暂不可用';
      default:
        return '汇率待确认';
    }
  }
  switch (state) {
    case 'fresh':
      return 'Exchange rates current';
    case 'stale':
      return 'Exchange rates delayed';
    case 'missing':
      return 'Exchange rates unavailable';
    default:
      return 'Exchange rates pending';
  }
}

function consumerPortfolioDataNotice(
  options: {
    valuationLineageNotice?: string | null;
    hasDataLineage?: boolean;
    hasPriceFallback: boolean;
    hasUpdatingPrice: boolean;
    hasLimitedConfidence: boolean;
    hasFxUnavailable: boolean;
    hasFxStale?: boolean;
  },
  language: PortfolioLanguage,
): string | null {
  if (options.hasFxUnavailable) {
    return language === 'zh'
      ? '部分汇率数据暂不可用，估值已暂停更新。'
      : 'Some exchange-rate data is temporarily unavailable; valuation updates are paused.';
  }
  if (options.valuationLineageNotice) {
    return options.valuationLineageNotice;
  }
  if (options.hasFxStale) {
    return language === 'zh'
      ? '当前估值可能存在延迟，仅供参考。'
      : 'Current valuation may be delayed and is for reference only.';
  }
  if (options.hasPriceFallback) {
    return language === 'zh'
      ? '部分价格数据暂不可用，已使用最近一次可用数据。'
      : 'Some price data is temporarily unavailable; the latest available data is shown.';
  }
  if (options.hasUpdatingPrice) {
    return language === 'zh'
      ? '价格数据更新中，稍后将自动刷新。'
      : 'Price data is updating and will refresh automatically.';
  }
  if (options.hasLimitedConfidence) {
    return language === 'zh'
      ? '当前估值可能存在延迟，仅供参考。'
      : 'Current valuation may be delayed and is for reference only.';
  }
  if (options.hasDataLineage === false) {
    return language === 'zh'
      ? '价格、汇率与估值状态待确认。'
      : 'Price, FX, and valuation state are still pending.';
  }
  return null;
}

function sanitizePortfolioConsumerLabel(label: string | null | undefined, language: PortfolioLanguage): string | null {
  const normalized = String(label || '').trim().toLowerCase();
  if (!normalized) return null;
  if (
    normalized.includes('sourceauthority')
    || normalized.includes('syncimportstatus')
    || normalized.includes('reasoncode')
    || normalized.includes('manual_replay')
    || normalized.includes('provider')
    || normalized.includes('cache')
    || normalized.includes('raw')
    || normalized.includes('debug')
    || normalized.includes('json')
  ) {
    return null;
  }
  if (normalized.includes('fx') || normalized.includes('汇率')) {
    if (normalized.includes('missing') || normalized.includes('缺失') || normalized.includes('unavailable') || normalized.includes('暂不可用')) {
      return consumerFxLabel('missing', language);
    }
    if (normalized.includes('stale') || normalized.includes('过期') || normalized.includes('expired') || normalized.includes('延迟')) {
      return consumerFxLabel('stale', language);
    }
    return consumerFxLabel('pending', language);
  }
  if (normalized.includes('benchmark') || normalized.includes('factor') || normalized.includes('mapping') || normalized.includes('基准') || normalized.includes('因子') || normalized.includes('映射')) {
    return language === 'zh' ? '部分风险参考暂不可用' : 'Some risk references are unavailable';
  }
  if (normalized.includes('holdings') || normalized.includes('lineage') || normalized.includes('持仓来源')) {
    return language === 'zh' ? '持仓数据待核验' : 'Holdings data pending';
  }
  if (normalized.includes(LEGACY_RECOVERY_TOKEN) || normalized.includes('备用') || normalized.includes('回退')) {
    return language === 'zh' ? '当前估值可能存在延迟' : 'Current valuation may be delayed';
  }
  if (normalized.includes('confidence') || normalized.includes('置信')) {
    return limitedConfidenceLabel(language);
  }
  if (
    normalized.includes('数据不足，禁止判断')
    || normalized.includes('禁止判断')
    || normalized.includes('blocked')
    || normalized.includes('forbid')
  ) {
    return language === 'zh' ? '数据暂不完整，待补充后评估' : 'Data is still incomplete and will be reviewed after more inputs arrive.';
  }
  if (normalized.includes('stale') || normalized.includes('过期') || normalized.includes('expired')) {
    return language === 'zh' ? '数据可能延迟' : 'Data may be delayed';
  }
  return label || null;
}

function portfolioEvidenceVariant(
  summary: ReturnType<typeof normalizePortfolioRiskEvidence> | null | undefined,
): PortfolioTrustChipItem['variant'] {
  if (summary?.posture === 'blocked') return 'caution';
  if (summary?.tone === 'danger') return 'danger';
  if (summary?.tone === 'warning') return 'caution';
  if (summary?.tone === 'info') return 'info';
  if (summary?.tone === 'success') return 'success';
  return 'neutral';
}

function consumerTrustItemFromLabel(label: string | null | undefined, language: PortfolioLanguage, keyPrefix: string): PortfolioTrustChipItem | null {
  const safeLabel = sanitizePortfolioConsumerLabel(label, language);
  if (!safeLabel) return null;
  return { key: `${keyPrefix}-${safeLabel}`, label: safeLabel, variant: 'neutral' };
}

function consumerFxRefreshFeedback(stale: boolean, language: PortfolioLanguage): string {
  if (stale) {
    return language === 'zh'
      ? '部分汇率数据暂不可用，估值已暂停更新。'
      : 'Some exchange-rate data is temporarily unavailable; valuation updates are paused.';
  }
  return language === 'zh' ? '汇率数据已更新。' : 'Exchange-rate data updated.';
}

function normalizeTrustToken(value?: string | null): string {
  return String(value || '').trim().toLowerCase().replace(/[\s-]+/g, '_');
}

function mapValuationLineageState(
  rawValue: string | null | undefined,
  language: PortfolioLanguage,
): { notice: string | null; trustItem: PortfolioTrustChipItem | null } {
  const token = normalizeTrustToken(rawValue);
  if (!token) {
    return { notice: null, trustItem: null };
  }

  if (token === 'current') {
    return {
      notice: null,
      trustItem: {
        key: `valuation-lineage-${token}`,
        label: language === 'zh' ? '估值完整' : 'Valuation complete',
        variant: 'success',
      },
    };
  }

  if (token === LEGACY_PRICE_RECOVERY_TOKEN || token === 'fx_stale') {
    return {
      notice: language === 'zh'
        ? '当前估值可能存在延迟，仅供参考。'
        : 'Current valuation may be delayed and is for reference only.',
      trustItem: {
        key: `valuation-lineage-${token}`,
        label: language === 'zh' ? '估值可能延迟' : 'Valuation may be delayed',
        variant: 'caution',
      },
    };
  }

  if (
    token === LEGACY_FX_RECOVERY_TOKEN
    || token === 'unavailable'
    || token === 'missing_authority'
    || token === 'authority_missing'
    || token === 'missing_source_authority'
    || token.includes('missing_authority')
    || token.includes('authority_missing')
  ) {
    return {
      notice: language === 'zh'
        ? '部分汇率数据暂不可用，估值已暂停更新。'
        : 'Some exchange-rate data is temporarily unavailable; valuation updates are paused.',
      trustItem: {
        key: `valuation-lineage-${token}`,
        label: language === 'zh' ? '估值已暂停' : 'Valuation paused',
        variant: 'danger',
      },
    };
  }

  if (token === 'partial_cash' || token === 'cash_missing') {
    return {
      notice: language === 'zh'
        ? '现金流水不完整，估值仅供参考。'
        : 'Cash ledger is incomplete; valuation is for reference only.',
      trustItem: {
        key: `valuation-lineage-${token}`,
        label: language === 'zh' ? '现金流水不完整' : 'Cash ledger incomplete',
        variant: 'caution',
      },
    };
  }

  return {
    notice: language === 'zh'
      ? '估值状态待确认，仅供参考。'
      : 'Valuation status pending and is for reference only.',
    trustItem: {
      key: `valuation-lineage-${token}`,
      label: language === 'zh' ? '估值待确认' : 'Valuation pending',
      variant: 'neutral',
    },
  };
}

function isReadyTrustToken(token: string): boolean {
  return Boolean(token) && (
    token.includes('ready')
    || token.includes('authoritative')
    || token.includes('complete')
    || token.includes('fresh')
    || token.includes('current')
    || token.includes('verified')
    || token.includes('confirmed')
    || token.includes('ok')
    || token.includes('mapped')
    || token.includes('available')
  );
}

function uniqueTrustItems(items: Array<PortfolioTrustChipItem | null | undefined | false>): PortfolioTrustChipItem[] {
  const seen = new Set<string>();
  const result: PortfolioTrustChipItem[] = [];
  for (const item of items) {
    if (!item) continue;
    const signature = `${item.label}::${item.variant ?? 'neutral'}`;
    if (seen.has(signature)) continue;
    seen.add(signature);
    result.push(item);
  }
  return result;
}

function buildTrustStateItem(
  kind: 'fxFreshness' | 'holdingsLineage' | 'cashLedgerCompleteness' | 'benchmarkMapping' | 'factorMapping',
  rawValue: string | null | undefined,
  language: PortfolioLanguage,
): PortfolioTrustChipItem | null {
  const token = normalizeTrustToken(rawValue);
  if (!token) return null;

  if (kind === 'fxFreshness') {
    if (token.includes('stale') || token.includes('expired')) {
      return { key: `fx-${token}`, label: consumerFxLabel('stale', language), variant: 'caution' };
    }
    if (token.includes('missing') || token.includes('unavailable')) {
      return { key: `fx-${token}`, label: consumerFxLabel('missing', language), variant: 'danger' };
    }
    if (isReadyTrustToken(token)) {
      return { key: `fx-${token}`, label: consumerFxLabel('fresh', language), variant: 'success' };
    }
    return { key: `fx-${token}`, label: consumerFxLabel('pending', language), variant: 'neutral' };
  }

  if (kind === 'holdingsLineage') {
    if (token.includes('missing') || token.includes('partial') || token.includes('incomplete')) {
      return { key: `holdings-${token}`, label: language === 'zh' ? '持仓数据待核验' : 'Holdings data pending', variant: 'caution' };
    }
    if (isReadyTrustToken(token)) {
      return { key: `holdings-${token}`, label: language === 'zh' ? '持仓数据已核验' : 'Holdings data verified', variant: 'success' };
    }
    return { key: `holdings-${token}`, label: language === 'zh' ? '持仓数据待确认' : 'Holdings data pending', variant: 'neutral' };
  }

  if (kind === 'cashLedgerCompleteness') {
    if (token.includes('missing') || token.includes('partial') || token.includes('incomplete')) {
      return { key: `cash-${token}`, label: language === 'zh' ? '现金流水不完整' : 'Cash ledger incomplete', variant: 'caution' };
    }
    if (isReadyTrustToken(token)) {
      return { key: `cash-${token}`, label: language === 'zh' ? '现金流水完整' : 'Cash ledger complete', variant: 'success' };
    }
    return { key: `cash-${token}`, label: language === 'zh' ? '现金流水待确认' : 'Cash ledger pending', variant: 'neutral' };
  }

  if (kind === 'benchmarkMapping') {
    if (token.includes('missing') || token.includes('partial') || token.includes('limited') || token.includes('unmapped')) {
      return { key: `benchmark-${token}`, label: language === 'zh' ? '部分风险参考暂不可用' : 'Some risk references are unavailable', variant: 'caution' };
    }
    if (isReadyTrustToken(token)) {
      return { key: `benchmark-${token}`, label: language === 'zh' ? '风险参考已更新' : 'Risk references current', variant: 'success' };
    }
    return { key: `benchmark-${token}`, label: language === 'zh' ? '风险参考待确认' : 'Risk references pending', variant: 'neutral' };
  }

  if (token.includes('missing') || token.includes('partial') || token.includes('limited') || token.includes('unmapped')) {
    return { key: `factor-${token}`, label: language === 'zh' ? '部分风险参考暂不可用' : 'Some risk references are unavailable', variant: 'caution' };
  }
  if (isReadyTrustToken(token)) {
    return { key: `factor-${token}`, label: language === 'zh' ? '风险参考已更新' : 'Risk references current', variant: 'success' };
  }
  return { key: `factor-${token}`, label: language === 'zh' ? '风险参考待确认' : 'Risk references pending', variant: 'neutral' };
}

function summarizePortfolioPriceFreshness(
  positions: PortfolioPositionItem[],
  language: PortfolioLanguage,
): PortfolioTrustChipItem | null {
  if (!positions.length) return null;
  if (positions.some((position) => position.isPriceFallback)) {
    return { key: 'price-freshness-delayed', label: positionPriceFreshnessLabel({ isPriceFallback: true }, language), variant: 'caution' };
  }
  if (positions.some((position) => !position.priceAsOf)) {
    return { key: 'price-freshness-updating', label: positionPriceFreshnessLabel({ isPriceFallback: false }, language), variant: 'neutral' };
  }
  return {
    key: 'price-freshness-snapshot',
    label: positionPriceFreshnessLabel({ isPriceFallback: false, priceAsOf: positions[0].priceAsOf }, language),
    variant: 'success',
  };
}

function summarizePortfolioPriceAsOf(
  positions: PortfolioPositionItem[],
  language: PortfolioLanguage,
): PortfolioTrustChipItem | null {
  const values = Array.from(new Set(
    positions
      .map((position) => position.priceAsOf)
      .filter((value): value is string => Boolean(value)),
  ));
  if (!values.length) return null;
  if (values.length === 1) {
    return {
      key: `price-asof-${values[0]}`,
      label: language === 'zh' ? `截至 ${values[0]}` : `As of ${values[0]}`,
      variant: 'neutral',
    };
  }
  return {
    key: 'price-asof-mixed',
    label: language === 'zh' ? '多时点快照' : 'Mixed snapshot times',
    variant: 'neutral',
  };
}

function lineagePreviewDetail(
  item: PortfolioLineageStatusSummary | null | undefined,
  replacement: string,
): string {
  if (!item) return replacement;
  return item.total > 0 || item.count > 0 ? item.detail : replacement;
}

function lineageTrustItem(
  key: string,
  item: PortfolioLineageStatusSummary | null | undefined,
): PortfolioTrustChipItem | null {
  if (!item) return null;
  return {
    key: `portfolio-lineage-${key}`,
    label: item.label,
    variant: item.variant,
  };
}

function hasPortfolioLineage(summary: PortfolioLineageSummary | null | undefined): summary is PortfolioLineageSummary {
  return Boolean(summary?.hasLineage);
}

function safeEvidenceString(value: string | null | undefined): string {
  return value && value.trim() ? value : UNKNOWN_EVIDENCE_VALUE;
}

function safeEvidenceNumber(value: number | null | undefined): number | string {
  return typeof value === 'number' && Number.isFinite(value) ? value : UNKNOWN_EVIDENCE_VALUE;
}

function uniqueSafeEvidenceList(values: Array<string | null | undefined>): string[] {
  return Array.from(new Set(values.map((value) => String(value || '').trim()).filter(Boolean))).sort();
}

function hasBlockedValuationEvidence(
  summary: PortfolioLineageSummary | null | undefined,
  valuationLineage: PortfolioValuationSnapshotLineage | undefined,
  hasFxUnavailable: boolean,
): boolean {
  const status = normalizeTrustToken(valuationLineage?.status || valuationLineage?.snapshotState);
  if (hasFxUnavailable) {
    return true;
  }
  if (status.includes('blocked') || status.includes('unavailable')) {
    return true;
  }
  return summary?.snapshot?.label === '估值不可用';
}

function buildPortfolioValuationEvidencePack(options: {
  snapshot: PortfolioSnapshotWithLineage;
  language: PortfolioLanguage;
  accountScope: 'all_accounts' | 'selected_account';
  accountLabel: string;
  positions: PortfolioPositionItem[];
  summary: PortfolioLineageSummary | null;
  priceLineage?: PortfolioPriceLineage;
  fxLineage?: PortfolioFxLineage;
  valuationLineage?: PortfolioValuationSnapshotLineage;
  totalMarketValue: number;
  totalEquity: number;
  totalCash: number;
  unrealizedPnl: number;
  currency: string;
  warnings: string[];
}): PortfolioValuationEvidencePack {
  const priceLabels = uniqueSafeEvidenceList(options.positions.map((position) => (
    sanitizePortfolioConsumerLabel(position.priceSourceLabel, options.language)
    || positionPriceFreshnessLabel(position, options.language)
  )));
  const priceAsOfSummary = summarizePortfolioPriceAsOf(options.positions, options.language);
  const priceFreshnessSummary = summarizePortfolioPriceFreshness(options.positions, options.language);
  const priceSummary = options.summary?.price;
  const fxSummary = options.summary?.fx;
  const valuationSummary = options.summary?.snapshot;
  const valuationLineage = options.valuationLineage;
  const priceLineage = options.priceLineage;
  const fxLineage = options.fxLineage;
  const safeWarnings = uniqueSafeEvidenceList(options.warnings);

  return {
    schemaVersion: PORTFOLIO_VALUATION_EVIDENCE_PACK_SCHEMA,
    generatedAt: new Date().toISOString(),
    appSurface: 'Portfolio valuation',
    account: {
      scope: options.accountScope,
      label: safeEvidenceString(options.accountLabel),
    },
    holdingsCount: options.positions.length,
    valuationAsOf: safeEvidenceString(options.snapshot.asOf),
    priceLineage: {
      label: safeEvidenceString(priceSummary?.label || priceFreshnessSummary?.label),
      freshness: safeEvidenceString(priceAsOfSummary?.label || priceFreshnessSummary?.label),
      priceSourceLabels: priceLabels.length ? priceLabels : [UNKNOWN_EVIDENCE_VALUE],
      missingQuoteCount: safeEvidenceNumber(priceLineage?.counts.missing),
      staleQuoteCount: safeEvidenceNumber(priceLineage?.counts.stale),
      totalQuoteCount: safeEvidenceNumber(priceLineage?.counts.total ?? priceSummary?.total),
      affectedSymbols: uniqueSafeEvidenceList([
        ...(priceSummary?.affectedSymbols ?? []),
        ...(priceLineage?.affectedSymbols.missing ?? []),
        ...(priceLineage?.affectedSymbols.stale ?? []),
      ]),
      lastUpdatedAt: safeEvidenceString(priceLineage?.lastUpdatedAt ?? priceSummary?.lastUpdatedAt),
    },
    fxLineage: {
      label: safeEvidenceString(fxSummary?.label),
      affectedCurrencies: uniqueSafeEvidenceList([
        ...(fxSummary?.affectedCurrencies ?? []),
        ...(fxLineage?.affectedCurrencies.missing ?? []),
        ...(fxLineage?.affectedCurrencies.stale ?? []),
      ]),
      affectedPairs: uniqueSafeEvidenceList([
        ...(fxSummary?.affectedPairs ?? []),
        ...(fxLineage?.affectedPairs.missing ?? []),
        ...(fxLineage?.affectedPairs.stale ?? []),
      ]),
      lastUpdatedAt: safeEvidenceString(fxLineage?.lastUpdatedAt ?? fxSummary?.lastUpdatedAt),
    },
    valuationLineage: {
      label: safeEvidenceString(valuationSummary?.label),
      positionCount: safeEvidenceNumber(valuationLineage?.positionCount ?? valuationSummary?.total),
      completePositionCount: safeEvidenceNumber(valuationLineage?.completePositionCount),
      partialPositionCount: safeEvidenceNumber(valuationLineage?.partialPositionCount),
      blockedPositionCount: safeEvidenceNumber(valuationLineage?.blockedPositionCount),
      blockedBy: {
        priceSymbols: uniqueSafeEvidenceList(valuationLineage?.blockedBy.priceSymbols ?? []),
        fxPairs: uniqueSafeEvidenceList(valuationLineage?.blockedBy.fxPairs ?? []),
        fxCurrencies: uniqueSafeEvidenceList(valuationLineage?.blockedBy.fxCurrencies ?? []),
      },
      lastUpdatedAt: safeEvidenceString(valuationLineage?.lastUpdatedAt ?? valuationSummary?.lastUpdatedAt),
    },
    valuationSummary: {
      totalMarketValue: formatMoney(options.totalMarketValue, options.currency),
      totalEquity: formatMoney(options.totalEquity, options.currency),
      totalCash: formatMoney(options.totalCash, options.currency),
      unrealizedPnl: formatMoney(options.unrealizedPnl, options.currency),
      currency: options.currency,
    },
    warnings: safeWarnings.length ? safeWarnings : [UNKNOWN_EVIDENCE_VALUE],
    consumerBoundary: options.language === 'zh'
      ? '仅导出估值证据，不包含交易指令。'
      : 'Exports valuation evidence only; no trade instruction is included.',
  };
}

function PortfolioSegmentedControl({
  value,
  options,
  onChange,
  className = '',
  itemClassName = '',
  dataTestId,
}: {
  value: string;
  options: PortfolioSegmentOption[];
  onChange: (value: string) => void;
  className?: string;
  itemClassName?: string;
  dataTestId?: string;
}) {
  return (
    <TerminalNestedBlock data-testid={dataTestId} className={`min-w-0 w-full max-w-full p-0 ${className}`}>
      <SegmentedControl
        value={value}
        options={options}
        onChange={onChange}
        className="space-y-0"
        listClassName="ui-scroll-x-quiet w-full rounded-xl border-0 bg-[var(--wolfy-surface-input)] p-1"
        buttonClassName={`rounded-lg border-0 text-center text-sm font-medium ${itemClassName}`}
        activeButtonClassName="bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-primary)] shadow-sm"
        inactiveButtonClassName="bg-transparent text-[color:var(--wolfy-text-muted)] hover:bg-transparent hover:text-[color:var(--wolfy-text-secondary)]"
        size="sm"
      />
    </TerminalNestedBlock>
  );
}

function getPortfolioCopy(
  t: TranslateFn,
  language: PortfolioLanguage,
){
  const copy = {
    documentTitle: t('portfolio.documentTitle'),
    eyebrow: t('portfolio.eyebrow'),
    title: t('portfolio.title'),
    description: t('portfolio.description'),
    createAccount: t('portfolio.createAccount'),
    collapseCreate: t('portfolio.collapseCreate'),
    refreshData: t('portfolio.refreshData'),
    refreshingData: t('portfolio.refreshingData'),
    noAccounts: t('portfolio.noAccounts'),
    accountView: t('portfolio.accountView'),
    allAccounts: t('portfolio.allAccounts'),
    costMethod: t('portfolio.costMethod'),
    costFifo: t('portfolio.costFifo'),
    costAvg: t('portfolio.costAvg'),
    costFutuDiluted: t('portfolio.costFutuDiluted'),
    costThsPnl: t('portfolio.costThsPnl'),
    scopeHint: t('portfolio.scopeHint'),
    fxState: t('portfolio.fxState'),
    refreshFx: t('portfolio.refreshFx'),
    refreshingFx: t('portfolio.refreshingFx'),
    emptyConcentration: t('portfolio.emptyConcentration'),
    noBrokerConnections: t('portfolio.noBrokerConnections'),
    emptyEventsTitle: t('portfolio.emptyEventsTitle'),
    emptyEventsBody: t('portfolio.emptyEventsBody'),
    prevPage: t('portfolio.prevPage'),
    nextPage: t('portfolio.nextPage'),
    pageLabel: t('portfolio.pageLabel'),
    deleteTitle: t('portfolio.deleteTitle'),
    deleteMessage: t('portfolio.deleteMessage'),
    deleteConfirm: t('portfolio.deleteConfirm'),
    deleteInProgress: t('portfolio.deleteInProgress'),
    cancel: t('portfolio.cancel'),
    accountNameRequired: t('portfolio.accountNameRequired'),
    accountCreated: t('portfolio.accountCreated'),
    accountArchived: t('portfolio.accountArchived'),
    accountDeleteTitle: t('portfolio.accountDeleteTitle'),
    accountDeleteMessage: t('portfolio.accountDeleteMessage'),
    accountCreateFailed: t('portfolio.accountCreateFailed'),
    riskFallback: t('portfolio.riskFallback'),
    writeRequiresAccount: t('portfolio.writeRequiresAccount'),
    syncRequiresAccount: t('portfolio.syncRequiresAccount'),
    syncRequiresToken: t('portfolio.syncRequiresToken'),
    deleteRequiresAccount: t('portfolio.deleteRequiresAccount'),
    riskDegraded: t('portfolio.riskDegraded'),
    actionHint: t('portfolio.actionHint'),
    createAccountTitle: t('portfolio.createAccountTitle'),
    createAccountHelp: t('portfolio.createAccountHelp'),
    accountNamePlaceholder: t('portfolio.accountNamePlaceholder'),
    brokerPlaceholder: t('portfolio.brokerPlaceholder'),
    baseCurrencyPlaceholder: t('portfolio.baseCurrencyPlaceholder'),
    marketCn: t('portfolio.marketCn'),
    marketHk: t('portfolio.marketHk'),
    marketUs: t('portfolio.marketUs'),
    marketGlobal: t('portfolio.marketGlobal'),
    creatingAccount: t('portfolio.creatingAccount'),
    totalEquity: t('portfolio.totalEquity'),
    totalMarketValue: t('portfolio.totalMarketValue'),
    totalCash: t('portfolio.totalCash'),
    fxFresh: t('portfolio.fxFresh'),
    fxStale: t('portfolio.fxStale'),
    drawdownTitle: t('portfolio.drawdownTitle'),
    maxDrawdown: t('portfolio.maxDrawdown'),
    currentDrawdown: t('portfolio.currentDrawdown'),
    alert: t('portfolio.alert'),
    yes: t('portfolio.yes'),
    no: t('portfolio.no'),
    stopLossTitle: t('portfolio.stopLossTitle'),
    triggeredCount: t('portfolio.triggeredCount'),
    nearCount: t('portfolio.nearCount'),
    snapshotBasisTitle: t('portfolio.snapshotBasisTitle'),
    accountCount: t('portfolio.accountCount'),
    reportingCurrency: t('portfolio.reportingCurrency'),
    costMethodLabel: t('portfolio.costMethodLabel'),
    allAccountsWarning: t('portfolio.allAccountsWarning'),
    positionsTitle: t('portfolio.positionsTitle'),
    positionsCount: (count: number) => t('portfolio.positionsCount', { count }),
    noPositions: t('portfolio.noPositions'),
    positionAccount: t('portfolio.positionAccount'),
    positionCode: t('portfolio.positionCode'),
    positionMarketCurrency: t('portfolio.positionMarketCurrency'),
    positionQuantity: t('portfolio.positionQuantity'),
    positionAvgCost: t('portfolio.positionAvgCost'),
    positionLastPrice: t('portfolio.positionLastPrice'),
    positionMarketValue: t('portfolio.positionMarketValue'),
    positionUnrealized: t('portfolio.positionUnrealized'),
    sectorConcentration: t('portfolio.sectorConcentration'),
    singleNameConcentration: t('portfolio.singleNameConcentration'),
    concentrationHint: t('portfolio.concentrationHint'),
    concentrationScope: t('portfolio.concentrationScope'),
    concentrationScopeSector: t('portfolio.concentrationScopeSector'),
    concentrationScopeFallback: t('portfolio.concentrationScopeFallback'),
    sectorAlert: t('portfolio.sectorAlert'),
    topWeight: t('portfolio.topWeight'),
    dataSyncTitle: t('portfolio.dataSyncTitle'),
    brokerImport: t('portfolio.brokerImport'),
    currentImportAccount: t('portfolio.currentImportAccount'),
    brokerFallbackEmpty: t('portfolio.brokerFallbackEmpty'),
    brokerFallbackUnavailable: t('portfolio.brokerFallbackUnavailable'),
    selectBrokerExport: t('portfolio.selectBrokerExport'),
    selectIbkrExport: t('portfolio.selectIbkrExport'),
    dryRun: t('portfolio.dryRun'),
    parsing: t('portfolio.parsing'),
    parseFile: t('portfolio.parseFile'),
    committing: t('portfolio.committing'),
    commitImport: t('portfolio.commitImport'),
    brokerImportHint: t('portfolio.brokerImportHint'),
    ibkrImportHint: t('portfolio.ibkrImportHint'),
    ibkrReadOnlyTitle: t('portfolio.ibkrReadOnlyTitle'),
    ibkrReadOnlyBody: t('portfolio.ibkrReadOnlyBody'),
    readOnlyBadge: t('portfolio.readOnlyBadge'),
    ibkrApiBasePlaceholder: t('portfolio.ibkrApiBasePlaceholder'),
    ibkrAccountRefPlaceholder: t('portfolio.ibkrAccountRefPlaceholder'),
    ibkrSessionTokenPlaceholder: t('portfolio.ibkrSessionTokenPlaceholder'),
    verifyIbkrSsl: t('portfolio.verifyIbkrSsl'),
    syncing: t('portfolio.syncing'),
    syncIbkr: t('portfolio.syncIbkr'),
    syncResult: t('portfolio.syncResult'),
    positionsCountLabel: t('portfolio.positionsCountLabel'),
    cashCurrenciesLabel: t('portfolio.cashCurrenciesLabel'),
    accountRef: t('portfolio.accountRef'),
    syncedAt: t('portfolio.syncedAt'),
    syncOverlay: t('portfolio.syncOverlay'),
    syncSaved: t('portfolio.syncSaved'),
    parseResult: t('portfolio.parseResult'),
    valid: t('portfolio.valid'),
    cash: t('portfolio.cash'),
    corporateActions: t('portfolio.corporateActions'),
    skipped: t('portfolio.skipped'),
    errors: t('portfolio.errors'),
    accountMapping: t('portfolio.accountMapping'),
    commitResult: t('portfolio.commitResult'),
    inserted: t('portfolio.inserted'),
    duplicates: t('portfolio.duplicates'),
    failed: t('portfolio.failed'),
    duplicateFingerprintHint: t('portfolio.duplicateFingerprintHint'),
    manualAdjustments: t('portfolio.manualAdjustments'),
    manualTrade: t('portfolio.manualTrade'),
    symbolPlaceholder: t('portfolio.symbolPlaceholder'),
    tradeDate: t('portfolio.tradeDate'),
    sideLabel: t('portfolio.sideLabel'),
    buy: t('portfolio.buy'),
    sell: t('portfolio.sell'),
    quantity: t('portfolio.quantity'),
    price: t('portfolio.price'),
    feeOptional: t('portfolio.feeOptional'),
    taxOptional: t('portfolio.taxOptional'),
    optional: t('portfolio.optional'),
    reference: t('portfolio.reference'),
    note: t('portfolio.note'),
    submitTrade: t('portfolio.submitTrade'),
    manualCash: t('portfolio.manualCash'),
    eventDate: t('portfolio.eventDate'),
    direction: t('portfolio.direction'),
    cashIn: t('portfolio.cashIn'),
    cashOut: t('portfolio.cashOut'),
    amount: t('portfolio.amount'),
    currencyOptional: (currency: string) => t('portfolio.currencyOptional', {
      currency: currency || t('portfolio.accountBaseCurrencyFallback'),
    }),
    currency: t('portfolio.currency'),
    submitCash: t('portfolio.submitCash'),
    manualCorporate: t('portfolio.manualCorporate'),
    stockCode: t('portfolio.stockCode'),
    effectiveDate: t('portfolio.effectiveDate'),
    actionType: t('portfolio.actionType'),
    cashDividend: t('portfolio.cashDividend'),
    splitAdjustment: t('portfolio.splitAdjustment'),
    dividendPerShare: t('portfolio.dividendPerShare'),
    splitRatio: t('portfolio.splitRatio'),
    submitCorporate: t('portfolio.submitCorporate'),
    ledgerAudit: t('portfolio.ledgerAudit'),
    tradeLedger: t('portfolio.tradeLedger'),
    cashLedger: t('portfolio.cashLedger'),
    corporateLedger: t('portfolio.corporateLedger'),
    loading: t('portfolio.loading'),
    refreshLedger: t('portfolio.refreshLedger'),
    filterBySymbol: t('portfolio.filterBySymbol'),
    allSides: t('portfolio.allSides'),
    allDirections: t('portfolio.allDirections'),
    allActions: t('portfolio.allActions'),
    deleteHintBlocked: t('portfolio.deleteHintBlocked'),
    deleteHintReady: t('portfolio.deleteHintReady'),
    tradeDeleteMessage: (item: PortfolioTradeListItem) => t('portfolio.tradeDeleteMessage', {
      tradeDate: item.tradeDate,
      sideLabel: formatSideLabel(item.side, language),
      symbol: item.symbol,
      quantity: item.quantity,
      price: item.price,
    }),
    cashDeleteMessage: (item: PortfolioCashLedgerListItem) => t('portfolio.cashDeleteMessage', {
      eventDate: item.eventDate,
      directionLabel: formatCashDirectionLabel(item.direction, language),
      amount: item.amount,
      currency: item.currency,
    }),
    corporateDeleteMessage: (item: PortfolioCorporateActionListItem) => t('portfolio.corporateDeleteMessage', {
      effectiveDate: item.effectiveDate,
      actionLabel: formatCorporateActionLabel(item.actionType, language),
      symbol: item.symbol,
    }),
    tradeUidPlaceholder: language === 'en' ? 'Record reference (optional)' : '流水引用（可选）',
    notePlaceholder: language === 'en' ? 'Note (optional)' : '备注（可选）',
  };

  return copy;
}

function getTodayIso(): string {
  return toDateInputValue(new Date());
}

function formatMoney(value: number | undefined | null, currency = 'CNY'): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${currency} ${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

function formatFxRate(rate: number | undefined | null): string {
  if (rate == null || Number.isNaN(rate)) return '--';
  return Number(rate).toLocaleString(undefined, {
    minimumFractionDigits: 4,
    maximumFractionDigits: 4,
  });
}

function formatFxTimestamp(value: string | undefined | null): string {
  if (!value) return '--';
  return value.replace('T', ' ').replace(/\.\d+$/, '');
}

function formatSideLabel(value: PortfolioSide, language: PortfolioLanguage): string {
  return translate(language, `portfolio.side.${value}`);
}

function formatCashDirectionLabel(value: PortfolioCashDirection, language: PortfolioLanguage): string {
  return translate(language, `portfolio.cashDirection.${value}`);
}

function formatCorporateActionLabel(value: PortfolioCorporateActionType, language: PortfolioLanguage): string {
  return translate(language, `portfolio.corporateAction.${value}`);
}

function formatBrokerLabel(value: string, displayName: string | undefined, language: PortfolioLanguage): string {
  const knownName = translate(language, `portfolio.brokerName.${value}`);
  if (knownName !== `portfolio.brokerName.${value}`) {
    return translate(language, 'portfolio.labelWithKnownName', { value, name: knownName });
  }
  if (displayName && displayName.trim()) {
    return translate(language, 'portfolio.labelWithKnownName', { value, name: displayName.trim() });
  }
  return value;
}

function formatAccountMarketLabel(value: string, language: PortfolioLanguage): string {
  const normalized = value === 'global' || value === 'hk' || value === 'us' ? value : 'cn';
  return translate(language, `portfolio.marketLabel.${normalized}`);
}

function formatConsumerAccountLabel(value: string | null | undefined, language: PortfolioLanguage): string {
  const text = String(value || '').trim();
  if (!text) {
    return language === 'zh' ? '组合账户' : 'Portfolio account';
  }
  if (/audit[-_\s]?trace[-_\s]?acct|internal|debug|trace|local_db|fixture/i.test(text)) {
    return language === 'zh' ? '组合账户' : 'Portfolio account';
  }
  return text;
}

function isMissingMarketValue(value: string | undefined | null): boolean {
  const normalized = String(value || '').trim().toLowerCase();
  return !normalized || normalized === 'unknown' || normalized === 'unclassified' || normalized === '--' || normalized === 'n/a';
}

function formatExposureMarketLabel(row: PortfolioExposureItem | undefined | null, language: PortfolioLanguage): string {
  if (!row || isMissingMarketValue(row.market || row.key || row.label)) {
    return language === 'zh' ? '暂无市场分类' : 'No market category';
  }
  const marketValue = String(row.market || row.key || '').toLowerCase();
  if (marketValue === 'cn' || marketValue === 'hk' || marketValue === 'us' || marketValue === 'global') {
    return formatAccountMarketLabel(marketValue, language);
  }
  return row.label || marketValue.toUpperCase();
}

function formatSignedMoney(value: number, currency: string): string {
  const formatted = formatMoney(Math.abs(value), currency);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

function formatPercent(value: number | undefined | null): string {
  if (value == null || Number.isNaN(value)) return '--';
  return `${Number(value).toLocaleString(undefined, {
    minimumFractionDigits: 1,
    maximumFractionDigits: 1,
  })}%`;
}

function normalizeStructureReviewToken(value: string | null | undefined): string {
  return String(value || '').trim().toLowerCase();
}

function structureReviewChipVariant(value: string | null | undefined): 'neutral' | 'success' | 'caution' | 'danger' {
  const token = normalizeStructureReviewToken(value);
  if (!token) return 'neutral';
  if (['available', 'high', 'strong', 'breakout', 'trend', 'confirmed'].includes(token)) return 'success';
  if (['partial', 'mixed', 'medium'].includes(token)) return 'caution';
  if (['unavailable', 'low', 'blocked', 'degraded', 'lowconfidence'].includes(token)) return 'danger';
  return 'neutral';
}

function structureReviewDataStatusLabel(value: string | null | undefined, language: PortfolioLanguage): string {
  const token = normalizeStructureReviewToken(value);
  if (token === 'available') {
    return language === 'zh' ? '结构已覆盖' : 'Structure coverage ready';
  }
  if (token === 'partial' || token === 'mixed') {
    return language === 'zh' ? '需补证据' : 'Evidence gaps pending';
  }
  if (token === 'unavailable') {
    return language === 'zh' ? '结构暂不可用' : 'Structure coverage unavailable';
  }
  return language === 'zh' ? '结构待确认' : 'Structure review pending';
}

function structureReviewEvidenceStatusLabel(value: string | null | undefined, language: PortfolioLanguage): string {
  const token = normalizeStructureReviewToken(value);
  if (token === 'available') {
    return language === 'zh' ? '证据覆盖可用' : 'Evidence coverage ready';
  }
  if (token === 'partial' || token === 'mixed') {
    return language === 'zh' ? '证据仍然偏薄' : 'Evidence still thin';
  }
  if (token === 'unavailable') {
    return language === 'zh' ? '证据暂不可用' : 'Evidence unavailable';
  }
  return language === 'zh' ? '证据待确认' : 'Evidence pending';
}

function sanitizeStructureReviewMessage(value: string | null | undefined, language: PortfolioLanguage): string | null {
  const trimmed = String(value || '').trim();
  if (!trimmed) {
    return null;
  }

  const normalized = trimmed.toLowerCase();
  if (normalized.includes('cached holdings are partially available')) {
    return language === 'zh'
      ? '当前持仓覆盖不完整，结构审查仅展示可用部分。'
      : 'Holding coverage is partial for structure review.';
  }
  if (normalized.includes('security metadata is unavailable for this cached holding')) {
    return language === 'zh'
      ? '该持仓的证券元数据暂不可用。'
      : 'Security metadata is unavailable for this holding.';
  }
  if (normalized.includes('ticker, market, or currency metadata is missing for this cached holding')) {
    return language === 'zh'
      ? '该持仓缺少代码、市场或币种元数据。'
      : 'Ticker, market, or currency metadata is missing for this holding.';
  }

  return trimmed.replace(/\bcached\s+/gi, '');
}

function structureReviewDetailRoute(
  review: PortfolioStructureReviewResponse | null,
  ticker: string | null | undefined,
): string | null {
  const token = String(ticker || '').trim();
  const researchLinkage = review?.researchLinkage;
  if (!token || !researchLinkage || researchLinkage.status === 'unavailable') {
    return null;
  }
  const drilldown = researchLinkage.holdingDrilldowns.find(
    (entry) => entry.ticker === token && entry.evidenceLinkage !== 'unavailable',
  );
  const route = drilldown?.structureLinks[0]?.route;
  return route?.startsWith('/') ? route : null;
}

function getFxRateForDisplay(
  fxRows: PortfolioFxRateItem[],
  fromCurrency: string | undefined | null,
  toCurrency: DisplayCurrency,
): { rate: number; stale: boolean } | null {
  const from = (fromCurrency || '').toUpperCase();
  const to = toCurrency.toUpperCase();
  if (!from || from === to) {
    return { rate: 1, stale: false };
  }

  const direct = fxRows.find((item) => item.fromCurrency === from && item.toCurrency === to);
  if (direct && typeof direct.rate === 'number' && direct.rate > 0) {
    return { rate: direct.rate, stale: direct.isStale };
  }

  const inverse = fxRows.find((item) => item.fromCurrency === to && item.toCurrency === from);
  if (inverse && typeof inverse.rate === 'number' && inverse.rate > 0) {
    return { rate: 1 / inverse.rate, stale: inverse.isStale };
  }

  return null;
}

function extractIbkrSyncConfig(connection?: PortfolioBrokerConnectionItem | null): {
  apiBaseUrl?: string;
  verifySsl?: boolean;
  brokerAccountRef?: string;
  lastSyncAt?: string;
} {
  const metadata = connection?.syncMetadata;
  if (!metadata || typeof metadata !== 'object') {
    return {};
  }
  const nested = (metadata as Record<string, unknown>).ibkrApi;
  if (!nested || typeof nested !== 'object') {
    return {};
  }
  const record = nested as Record<string, unknown>;
  return {
    apiBaseUrl: typeof record.apiBaseUrl === 'string' ? record.apiBaseUrl : undefined,
    verifySsl: typeof record.verifySsl === 'boolean' ? record.verifySsl : undefined,
    brokerAccountRef: typeof record.brokerAccountRef === 'string' ? record.brokerAccountRef : undefined,
    lastSyncAt: typeof (metadata as Record<string, unknown>).lastSyncAt === 'string'
      ? ((metadata as Record<string, unknown>).lastSyncAt as string)
      : undefined,
  };
}

function buildPortfolioRefreshViewKey(
  selectedAccount: AccountOption,
  costMethod: PortfolioCostMethod,
): string {
  return `${selectedAccount === 'all' ? 'all' : `account:${selectedAccount}`}:cost:${costMethod}`;
}

type PortfolioCopy = ReturnType<typeof getPortfolioCopy>;

function PortfolioTradeActions({
  item,
  context,
  isNarrowViewport,
  openTradeActionMenuId,
  voidedTradeLabel,
  moreTradeActionsLabel,
  editTradeActionLabel,
  deleteTradeActionLabel,
  onToggleMenu,
  onEdit,
  onVoid,
}: {
  item: PortfolioTradeListItem;
  context: 'history' | 'recent';
  isNarrowViewport: boolean;
  openTradeActionMenuId: number | null;
  voidedTradeLabel: string;
  moreTradeActionsLabel: string;
  editTradeActionLabel: string;
  deleteTradeActionLabel: string;
  onToggleMenu: (id: number) => void;
  onEdit: (item: PortfolioTradeListItem) => void;
  onVoid: (item: PortfolioTradeListItem) => void;
}) {
  if (item.isActive === false) {
    return (
      <TerminalChip variant="neutral" className="shrink-0">
        {voidedTradeLabel}
      </TerminalChip>
    );
  }

  if (isNarrowViewport) {
    const menuKey = `${context}-trade-${item.id}`;
    const isOpen = openTradeActionMenuId === item.id;
    return (
      <div className="relative shrink-0">
        <Button
          type="button"
          variant="ghost"
          className={PORTFOLIO_TEXT_BUTTON_CLASS}
          onClick={() => onToggleMenu(item.id)}
        >
          <MoreHorizontal className="size-3.5" aria-hidden="true" />
          {moreTradeActionsLabel}
        </Button>
        {isOpen ? (
          <TerminalNestedBlock
            data-testid={`${menuKey}-menu`}
            className="absolute right-0 z-20 mt-2 flex min-w-[132px] flex-col gap-1 bg-[var(--wolfy-surface-input)] p-2 shadow-[var(--shadow-tight)]"
          >
            <Button type="button" variant="ghost" className="justify-start rounded-lg px-2 text-xs text-[color:var(--wolfy-text-secondary)]" onClick={() => onEdit(item)}>
              <PenSquare className="size-3.5" aria-hidden="true" />
              {editTradeActionLabel}
            </Button>
            <Button type="button" variant="ghost" className="justify-start rounded-lg px-2 text-xs text-red-300 hover:text-red-200" onClick={() => onVoid(item)}>
              <Trash2 className="size-3.5" aria-hidden="true" />
              {deleteTradeActionLabel}
            </Button>
          </TerminalNestedBlock>
        ) : null}
      </div>
    );
  }

  return (
    <div className="flex shrink-0 items-center gap-1">
      <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} onClick={() => onEdit(item)}>
        <PenSquare className="size-3.5" aria-hidden="true" />
        {editTradeActionLabel}
      </Button>
      <Button type="button" variant="ghost" className={`${PORTFOLIO_TEXT_BUTTON_CLASS} text-red-300 hover:text-red-200`} onClick={() => onVoid(item)}>
        <Trash2 className="size-3.5" aria-hidden="true" />
        {deleteTradeActionLabel}
      </Button>
    </div>
  );
}

function ManualTradeForm({
  copy,
  language,
  tradeForm,
  tradeCurrencyValue,
  writableAccountId,
  tradeSubmitting,
  tradeCurrencyHint,
  tradeCurrencyWarning,
  setTradeForm,
  setTradeCurrencyManuallyEdited,
  onSubmit,
}: {
  copy: PortfolioCopy;
  language: PortfolioLanguage;
  tradeForm: TradeFormState;
  tradeCurrencyValue: DisplayCurrency;
  writableAccountId?: number;
  tradeSubmitting: boolean;
  tradeCurrencyHint: string;
  tradeCurrencyWarning: string | null;
  setTradeForm: React.Dispatch<React.SetStateAction<TradeFormState>>;
  setTradeCurrencyManuallyEdited: React.Dispatch<React.SetStateAction<boolean>>;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
}) {
  return (
    <div>
      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualTrade}</p>
      <form onSubmit={onSubmit}>
        <div className={PORTFOLIO_FORM_GRID_CLASS}>
          <Input
            label={copy.stockCode}
            labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
            containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS}
            className={PORTFOLIO_INPUT_CLASS}
            placeholder={copy.symbolPlaceholder}
            value={tradeForm.symbol}
            onChange={(e) => {
              const symbol = e.target.value;
              setTradeForm((prev) => ({
                ...prev,
                symbol,
              }));
            }}
            required
          />
          <Input label={copy.tradeDate} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={tradeForm.tradeDate} onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
          <Select label={copy.sideLabel} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={tradeForm.side} onChange={(value) => setTradeForm((prev) => ({ ...prev, side: value as PortfolioSide }))} options={[{ value: 'buy', label: copy.buy }, { value: 'sell', label: copy.sell }]} />
          <Select
            label={copy.currency}
            labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
            className={PORTFOLIO_SELECT_CLASS}
            value={tradeCurrencyValue}
            onChange={(value) => {
              setTradeCurrencyManuallyEdited(true);
              setTradeForm((prev) => ({ ...prev, currency: normalizePortfolioDisplayCurrency(value) }));
            }}
            options={PORTFOLIO_DISPLAY_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
          />
          <Input label={copy.quantity} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={tradeForm.quantity} onChange={(e) => setTradeForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
          <Input label={copy.price} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={tradeForm.price} onChange={(e) => setTradeForm((prev) => ({ ...prev, price: e.target.value }))} required />
          <Input label={copy.feeOptional} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder={copy.optional} value={tradeForm.fee} onChange={(e) => setTradeForm((prev) => ({ ...prev, fee: e.target.value }))} />
          <Input label={copy.taxOptional} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder={copy.optional} value={tradeForm.tax} onChange={(e) => setTradeForm((prev) => ({ ...prev, tax: e.target.value }))} />
          <Input label={copy.reference} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="text" placeholder={copy.optional} value={tradeForm.tradeUid} onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeUid: e.target.value }))} />
        </div>
        <div className="mt-3 rounded-lg bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
          {tradeCurrencyHint}
          {tradeCurrencyWarning ? (
            <span className="mt-1 block text-amber-200">{tradeCurrencyWarning}</span>
          ) : null}
        </div>
        <Input label={copy.note} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.optional} value={tradeForm.note} onChange={(e) => setTradeForm((prev) => ({ ...prev, note: e.target.value }))} />
        {!writableAccountId ? (
          <div className="mt-3 rounded-lg border border-amber-300/15 bg-amber-300/10 px-3 py-2 text-xs text-amber-200">
            {language === 'zh' ? '请选择具体账户后保存持仓流水' : 'Select a specific account before saving holding records'}
          </div>
        ) : null}
        <Button
          type="submit"
          variant="primary"
          className={PORTFOLIO_SUBMIT_BUTTON_CLASS}
          disabled={!writableAccountId || tradeSubmitting}
          isLoading={tradeSubmitting}
          loadingText={copy.refreshingData}
        >
          {copy.submitTrade}
        </Button>
      </form>
    </div>
  );
}

function ManualCashForm({
  copy,
  cashForm,
  snapshotCurrency,
  writableAccountId,
  setCashForm,
  onSubmit,
}: {
  copy: PortfolioCopy;
  cashForm: CashFormState;
  snapshotCurrency: string;
  writableAccountId?: number;
  setCashForm: React.Dispatch<React.SetStateAction<CashFormState>>;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
}) {
  return (
    <SectionShell className="rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4" contentClassName="">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCash}</p>
      <form onSubmit={onSubmit}>
        <div data-testid="portfolio-cash-amount-currency-grid" className={PORTFOLIO_FORM_GRID_CLASS}>
          <Input label={copy.eventDate} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={cashForm.eventDate} onChange={(e) => setCashForm((prev) => ({ ...prev, eventDate: e.target.value }))} required />
          <Select label={copy.direction} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={cashForm.direction} onChange={(value) => setCashForm((prev) => ({ ...prev, direction: value as PortfolioCashDirection }))} options={[{ value: 'in', label: copy.cashIn }, { value: 'out', label: copy.cashOut }]} />
          <Input label={copy.amount} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.01" placeholder="0.00" value={cashForm.amount} onChange={(e) => setCashForm((prev) => ({ ...prev, amount: e.target.value }))} required />
          <Select
            data-testid="portfolio-cash-currency-select"
            label={copy.currency}
            labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
            className={PORTFOLIO_SELECT_CLASS}
            value={cashForm.currency}
            onChange={(value) => setCashForm((prev) => ({ ...prev, currency: value }))}
            options={CASH_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
            placeholder={copy.currencyOptional(snapshotCurrency)}
          />
        </div>
        <Input label={copy.note} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.optional} value={cashForm.note} onChange={(e) => setCashForm((prev) => ({ ...prev, note: e.target.value }))} />
        <Button type="submit" variant="primary" className={PORTFOLIO_SUBMIT_BUTTON_CLASS} disabled={!writableAccountId}>{copy.submitCash}</Button>
      </form>
    </SectionShell>
  );
}

function ManualCorporateActionForm({
  copy,
  corpForm,
  writableAccountId,
  setCorpForm,
  onSubmit,
}: {
  copy: PortfolioCopy;
  corpForm: CorporateActionFormState;
  writableAccountId?: number;
  setCorpForm: React.Dispatch<React.SetStateAction<CorporateActionFormState>>;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
}) {
  return (
    <SectionShell className="rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4" contentClassName="">
      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCorporate}</p>
      <form onSubmit={onSubmit}>
        <div className={PORTFOLIO_FORM_GRID_CLASS}>
          <Input label={copy.stockCode} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.symbolPlaceholder} value={corpForm.symbol} onChange={(e) => setCorpForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
          <Input label={copy.effectiveDate} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={corpForm.effectiveDate} onChange={(e) => setCorpForm((prev) => ({ ...prev, effectiveDate: e.target.value }))} required />
          <Select label={copy.actionType} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={corpForm.actionType} onChange={(value) => setCorpForm((prev) => ({ ...prev, actionType: value as PortfolioCorporateActionType }))} options={[{ value: 'cash_dividend', label: copy.cashDividend }, { value: 'split_adjustment', label: copy.splitAdjustment }]} />
          <Input label={copy.dividendPerShare} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={corpForm.cashDividendPerShare} onChange={(e) => setCorpForm((prev) => ({ ...prev, cashDividendPerShare: e.target.value }))} />
          <Input label={copy.splitRatio} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="1.0000" value={corpForm.splitRatio} onChange={(e) => setCorpForm((prev) => ({ ...prev, splitRatio: e.target.value }))} />
        </div>
        <Input label={copy.note} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.optional} value={corpForm.note} onChange={(e) => setCorpForm((prev) => ({ ...prev, note: e.target.value }))} />
        <Button type="submit" variant="primary" className={PORTFOLIO_SUBMIT_BUTTON_CLASS} disabled={!writableAccountId}>{copy.submitCorporate}</Button>
      </form>
    </SectionShell>
  );
}

function AccountManagementPanel({
  copy,
  language,
  accounts,
  showCreateAccount,
  hasAccounts,
  accountForm,
  accountCreating,
  accountCreateError,
  accountCreateSuccess,
  isLoading,
  setAccountForm,
  onToggleCreate,
  onRefresh,
  onSubmit,
  onDeleteAccount,
}: {
  copy: PortfolioCopy;
  language: PortfolioLanguage;
  accounts: PortfolioAccountItem[];
  showCreateAccount: boolean;
  hasAccounts: boolean;
  accountForm: AccountFormState;
  accountCreating: boolean;
  accountCreateError: string | null;
  accountCreateSuccess: string | null;
  isLoading: boolean;
  setAccountForm: React.Dispatch<React.SetStateAction<AccountFormState>>;
  onToggleCreate: () => void;
  onRefresh: () => void;
  onSubmit: React.FormEventHandler<HTMLFormElement>;
  onDeleteAccount: (account: PortfolioAccountItem) => void;
}) {
  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between gap-3">
        <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.createAccountTitle}</p>
        <div className="flex gap-2">
          <Button
            type="button"
            variant="secondary"
            className={PORTFOLIO_SECONDARY_BUTTON_CLASS}
            onClick={onToggleCreate}
          >
            {showCreateAccount ? copy.collapseCreate : copy.createAccount}
          </Button>
          <Button type="button" variant="ghost" className={PORTFOLIO_ICON_BUTTON_CLASS} onClick={onRefresh} disabled={isLoading} aria-label={isLoading ? copy.refreshingData : copy.refreshData} title={isLoading ? copy.refreshingData : copy.refreshData}>
            <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
          </Button>
        </div>
      </div>
      {accountCreateError ? <div className="text-xs text-danger">{accountCreateError}</div> : null}
      {accountCreateSuccess ? <div className="text-xs text-success">{accountCreateSuccess}</div> : null}
      <div className="space-y-2">
        {accounts.map((account) => (
          <div key={account.id} className="theme-panel-subtle rounded-[16px] px-4 py-3 text-sm text-secondary-text">
            <div className="flex items-center justify-between gap-3">
              <span className="min-w-0 truncate text-foreground">{formatConsumerAccountLabel(account.name, language)}</span>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-muted-text">#{account.id}</span>
                <Button
                  type="button"
                  variant="ghost"
                  className={PORTFOLIO_DANGER_GHOST_CLASS}
                  onClick={() => onDeleteAccount(account)}
                  aria-label={language === 'en' ? `Delete ${formatConsumerAccountLabel(account.name, language)}` : `删除 ${formatConsumerAccountLabel(account.name, language)}`}
                  title={copy.accountDeleteTitle}
                >
                  <Trash2 className="size-4" aria-hidden="true" />
                </Button>
              </div>
            </div>
            <div className="mt-1 text-xs text-muted-text">{formatAccountMarketLabel(account.market, language)} · {account.baseCurrency} · {account.broker || '--'}</div>
          </div>
        ))}
      </div>
      {(showCreateAccount || !hasAccounts) ? (
        <form className="space-y-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3" onSubmit={onSubmit}>
          <Input label={language === 'zh' ? '账户名称' : 'Account name'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.accountNamePlaceholder} value={accountForm.name} onChange={(e) => setAccountForm((prev) => ({ ...prev, name: e.target.value }))} />
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-2">
            <Input label={language === 'zh' ? '券商' : 'Broker'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.brokerPlaceholder} value={accountForm.broker} onChange={(e) => setAccountForm((prev) => ({ ...prev, broker: e.target.value }))} />
            <Input label={language === 'zh' ? '基准币种' : 'Base currency'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.baseCurrencyPlaceholder} value={accountForm.baseCurrency} onChange={(e) => setAccountForm((prev) => ({ ...prev, baseCurrency: e.target.value.toUpperCase() }))} />
          </div>
          <Select label={language === 'zh' ? '市场范围' : 'Market'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={accountForm.market} onChange={(value) => setAccountForm((prev) => ({ ...prev, market: value as AccountFormState['market'] }))} options={[{ value: 'cn', label: copy.marketCn }, { value: 'hk', label: copy.marketHk }, { value: 'us', label: copy.marketUs }, { value: 'global', label: copy.marketGlobal }]} />
          <Button type="submit" variant="primary" className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`} disabled={accountCreating}>{accountCreating ? copy.creatingAccount : copy.createAccount}</Button>
        </form>
      ) : null}
    </div>
  );
}

function PortfolioIbkrImportHeader({ copy }: { copy: PortfolioCopy }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <div className="space-y-1 text-xs text-secondary-text">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{copy.ibkrReadOnlyTitle}</p>
        <p>{copy.ibkrReadOnlyBody}</p>
      </div>
      <PillBadge variant="info">{copy.readOnlyBadge}</PillBadge>
    </div>
  );
}

function PortfolioIbkrSyncResultCard({
  copy,
  result,
}: {
  copy: PortfolioCopy;
  result: PortfolioIbkrSyncResponse;
}) {
  return (
    <div className="theme-panel-subtle rounded-[16px] px-4 py-3 text-xs text-secondary-text space-y-1">
      <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{copy.syncResult}</p>
      <div>{copy.positionsCountLabel} <span className="text-foreground">{result.positionCount ?? '--'}</span></div>
      <div>{copy.cashCurrenciesLabel} <span className="text-foreground">{result.cashBalanceCount ?? 0}</span></div>
      <div>{copy.syncedAt}: <span className="text-foreground">{result.syncedAt ? result.syncedAt.replace('T', ' ') : '--'}</span></div>
      <div>{copy.totalEquity} <span className="text-foreground">{formatMoney(result.totalEquity, result.baseCurrency)}</span></div>
    </div>
  );
}

function PortfolioImportPreviewCard({
  title,
  boundary,
  acceptedLabel,
  rejectedLabel,
  duplicateLabel,
  currencyLabel,
  unknownLabel,
  recoveryLabel,
  parseResult,
  result,
}: {
  title: string;
  boundary: string;
  acceptedLabel: string;
  rejectedLabel: string;
  duplicateLabel: string;
  currencyLabel: string;
  unknownLabel: string;
  recoveryLabel: string;
  parseResult: PortfolioImportParseResponse | null;
  result: PortfolioImportCommitResponse;
}) {
  const accepted = result.acceptedCount ?? result.insertedCount ?? 0;
  const rejected = result.rejectedCount ?? result.failedCount ?? 0;
  const duplicateCandidates = result.duplicateCandidates?.length ?? (result.duplicateCount > 0 ? 1 : 0);
  const currencyIssues = result.currencyIssues?.length ?? 0;
  const unknownSymbols = result.unknownSymbols?.length ?? 0;
  const recoveryActions = result.recoveryActions ?? [];

  return (
    <div data-testid="portfolio-import-preview-card" className="theme-panel-subtle rounded-[16px] px-4 py-3 text-xs text-secondary-text space-y-3">
      <div className="space-y-1">
        <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{title}</p>
        <p className="leading-5 text-[color:var(--wolfy-text-secondary)]">{boundary}</p>
      </div>
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <TerminalNestedBlock className="px-3 py-2">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{acceptedLabel}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">{accepted}</div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="px-3 py-2">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{rejectedLabel}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">{rejected}</div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="px-3 py-2">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{duplicateLabel}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">{duplicateCandidates || result.duplicateCount || 0}</div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="px-3 py-2">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{currencyLabel}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">{currencyIssues}</div>
        </TerminalNestedBlock>
        <TerminalNestedBlock className="px-3 py-2">
          <div className="text-[11px] text-[color:var(--wolfy-text-muted)]">{unknownLabel}</div>
          <div className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-primary)]">{unknownSymbols}</div>
        </TerminalNestedBlock>
      </div>
      {parseResult ? (
        <div className="text-[11px] leading-5 text-[color:var(--wolfy-text-muted)]">
          {parseResult.broker.toUpperCase()} · records {parseResult.recordCount} · cash {parseResult.cashRecordCount} · actions {parseResult.corporateActionCount}
        </div>
      ) : null}
      {recoveryActions.length > 0 ? (
        <div className="rounded-xl border border-amber-300/15 bg-amber-300/[0.05] px-3 py-2 text-amber-100/80">
          <p className="font-medium">{recoveryLabel}</p>
          <ul className="mt-1 list-disc space-y-1 pl-4">
            {recoveryActions.map((action) => <li key={action}>{action}</li>)}
          </ul>
        </div>
      ) : null}
    </div>
  );
}

function sortExposureRowsByPercent(rows: PortfolioExposureItem[] | undefined): PortfolioExposureItem[] {
  const sorted = [...(rows || [])];
  sorted.sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0));
  return sorted;
}

const PortfolioPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { language, t } = useI18n();
  const productSurface = useProductSurface();
  const canManagePortfolioOperations = Boolean(productSurface.isAdminMode && productSurface.canReadProviders);
  const routeLocale = typeof window !== 'undefined' ? parseLocaleFromPathname(window.location.pathname) : null;
  const localize = useCallback((path: string) => (routeLocale ? buildLocalizedPath(path, routeLocale) : path), [routeLocale]);
  const copy = getPortfolioCopy(t, language);
  const riskFallbackMessage = copy.riskFallback;

  useEffect(() => {
    document.title = copy.documentTitle;
  }, [copy.documentTitle]);

  const [accounts, setAccounts] = useState<PortfolioAccountItem[]>([]);
  const [selectedAccount, setSelectedAccount] = useState<AccountOption>('all');
  const [selectedTradeAccount, setSelectedTradeAccount] = useState<AccountOption>('all');
  const [showCreateAccount, setShowCreateAccount] = useState(false);
  const [accountCreating, setAccountCreating] = useState(false);
  const [accountCreateError, setAccountCreateError] = useState<string | null>(null);
  const [accountCreateSuccess, setAccountCreateSuccess] = useState<string | null>(null);
  const [accountForm, setAccountForm] = useState<AccountFormState>({
    name: '',
    broker: '',
    market: 'cn' as 'cn' | 'hk' | 'us' | 'global',
    baseCurrency: 'CNY',
  });
  const [costMethod, setCostMethod] = useState<PortfolioCostMethod>('fifo');
  const [displayCurrency, setDisplayCurrency] = useState<DisplayCurrency>(() => readPortfolioDisplayCurrency());
  const [snapshot, setSnapshot] = useState<PortfolioSnapshotWithLineage | null>(null);
  const [structureReview, setStructureReview] = useState<PortfolioStructureReviewResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fxRefreshing, setFxRefreshing] = useState(false);
  const [fxRefreshFeedback, setFxRefreshFeedback] = useState<FxRefreshFeedback | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [riskWarning, setRiskWarning] = useState<string | null>(null);
  const [writeWarning, setWriteWarning] = useState<string | null>(null);
  const [tradeSubmitting, setTradeSubmitting] = useState(false);
  const [tradeFeedback, setTradeFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);
  const [valuationEvidenceFeedback, setValuationEvidenceFeedback] = useState<string | null>(null);

  const [brokers, setBrokers] = useState<PortfolioImportBrokerItem[]>([]);
  const [brokerListUnavailable, setBrokerListUnavailable] = useState(false);
  const [brokerConnections, setBrokerConnections] = useState<PortfolioBrokerConnectionItem[]>([]);
  const [selectedBroker, setSelectedBroker] = useState('');
  const [ibkrApiBaseUrlDraft, setIbkrApiBaseUrlDraft] = useState<string | null>(null);
  const [ibkrVerifySslDraft, setIbkrVerifySslDraft] = useState<boolean | null>(null);
  const [ibkrSessionToken, setIbkrSessionToken] = useState('');
  const [ibkrBrokerAccountRefDraft, setIbkrBrokerAccountRefDraft] = useState<string | null>(null);
  const [ibkrSyncing, setIbkrSyncing] = useState(false);
  const [ibkrSyncResult, setIbkrSyncResult] = useState<PortfolioIbkrSyncResponse | null>(null);
  const [importFile, setImportFile] = useState<File | null>(null);
  const [importParsing, setImportParsing] = useState(false);
  const [importCommitting, setImportCommitting] = useState(false);
  const [importParseResult, setImportParseResult] = useState<PortfolioImportParseResponse | null>(null);
  const [importPreview, setImportPreview] = useState<PortfolioImportCommitResponse | null>(null);
  const [importCommitResult, setImportCommitResult] = useState<PortfolioImportCommitResponse | null>(null);

  const [leftTab, setLeftTab] = useState<'trade' | 'account' | 'sync' | 'fx'>('trade');
  const [exposureTab, setExposureTab] = useState<ExposureTab>('account');
  const [eventType, setEventType] = useState<EventType>('trade');
  const [eventDateFrom] = useState('');
  const [eventDateTo] = useState('');
  const [eventSymbol] = useState('');
  const [eventSide] = useState<'' | PortfolioSide>('');
  const [eventDirection] = useState<'' | PortfolioCashDirection>('');
  const [eventActionType] = useState<'' | PortfolioCorporateActionType>('');
  const [eventPage, setEventPage] = useState(1);
  const [tradeEvents, setTradeEvents] = useState<PortfolioTradeListItem[]>([]);
  const [cashEvents, setCashEvents] = useState<PortfolioCashLedgerListItem[]>([]);
  const [corporateEvents, setCorporateEvents] = useState<PortfolioCorporateActionListItem[]>([]);
  const [showEmptyFullHistory, setShowEmptyFullHistory] = useState(false);
  const [manualLedgerOpen, setManualLedgerOpen] = useState(false);
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);
  const [editingTrade, setEditingTrade] = useState<EditingTrade | null>(null);
  const [tradeEditSubmitting, setTradeEditSubmitting] = useState(false);
  const [openTradeActionMenuId, setOpenTradeActionMenuId] = useState<number | null>(null);
  const isNarrowViewport = useSyncExternalStore(subscribeNarrowViewport, getNarrowViewportSnapshot, () => false);

  const [tradeForm, setTradeForm] = useState<TradeFormState>({
    symbol: '',
    tradeDate: getTodayIso(),
    side: 'buy' as PortfolioSide,
    currency: 'CNY' as DisplayCurrency,
    quantity: '',
    price: '',
    fee: '',
    tax: '',
    tradeUid: '',
    note: '',
  });
  const [tradeCurrencyManuallyEdited, setTradeCurrencyManuallyEdited] = useState(false);
  const [cashForm, setCashForm] = useState<CashFormState>({
    eventDate: getTodayIso(),
    direction: 'in' as PortfolioCashDirection,
    amount: '',
    currency: '',
    note: '',
  });
  const [corpForm, setCorpForm] = useState<CorporateActionFormState>({
    symbol: '',
    effectiveDate: getTodayIso(),
    actionType: 'cash_dividend' as PortfolioCorporateActionType,
    cashDividendPerShare: '',
    splitRatio: '',
    note: '',
  });
  const [tradeType, setTradeType] = useState<TradeFormType>('stock');
  const [fxBaseCurrency, setFxBaseCurrency] = useState('USD');
  const [fxQuoteCurrency, setFxQuoteCurrency] = useState('CNY');
  const [liveFxRate, setLiveFxRate] = useState<PortfolioLiveFxRateResponse | null>(null);
  const [pendingAccountDelete, setPendingAccountDelete] = useState<{ id: number; name: string } | null>(null);
  const queryAccountId = selectedAccount === 'all' ? undefined : selectedAccount;
  const refreshViewKey = buildPortfolioRefreshViewKey(selectedAccount, costMethod);
  const refreshContextRef = useRef<FxRefreshContext>({ viewKey: refreshViewKey, requestId: 0 });
  const activeAccounts = accounts.filter((item) => item.isActive !== false);
  const writableAccounts = activeAccounts;
  const hasAccounts = accounts.length > 0;
  const hasActiveAccounts = activeAccounts.length > 0;
  const hasWritableAccounts = writableAccounts.length > 0;
  const scopedAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccount = selectedTradeAccount === 'all' ? undefined : writableAccounts.find((item) => item.id === selectedTradeAccount);
  const writableAccountId = writableAccount?.id;
  const editingAccount = editingTrade ? activeAccounts.find((item) => item.id === editingTrade.accountId) : undefined;
  const ibkrConnection = brokerConnections.find((item) => item.brokerType === 'ibkr') || null;
  const ibkrSyncConfig = extractIbkrSyncConfig(ibkrConnection);
  const ibkrApiBaseUrl = ibkrApiBaseUrlDraft ?? ibkrSyncConfig.apiBaseUrl ?? '';
  const ibkrVerifySsl = ibkrVerifySslDraft ?? ibkrSyncConfig.verifySsl ?? false;
  const ibkrBrokerAccountRef = ibkrBrokerAccountRefDraft ?? ibkrSyncConfig.brokerAccountRef ?? ibkrConnection?.brokerAccountRef ?? '';
  const currentEventCount = eventType === 'trade'
    ? tradeEvents.length
    : eventType === 'cash'
      ? cashEvents.length
      : corporateEvents.length;
  const effectiveTradeCurrency = tradeCurrencyManuallyEdited
    ? tradeForm.currency
    : inferSettlementCurrency(tradeForm.symbol, writableAccount?.baseCurrency);
  const tradeCurrencyWarning = writableAccount?.baseCurrency
    && effectiveTradeCurrency !== normalizePortfolioDisplayCurrency(writableAccount.baseCurrency)
    ? (language === 'zh'
      ? '标的结算货币与账户基准币种不同，将依赖汇率折算。'
      : 'The symbol settlement currency differs from the account base currency and will rely on FX conversion.')
    : null;
  const tradeCurrencyHint = language === 'zh'
    ? '自动按标的市场推断，可手动覆盖；流水会保留该结算币种。'
    : 'Auto-inferred from the symbol market; manual override keeps the record settlement currency.';
  const editTradeTitle = language === 'zh' ? '编辑持仓流水' : 'Edit holding record';
  const saveTradeChangesLabel = language === 'zh' ? '保存修改' : 'Save Changes';
  const updateTradeSuccessLabel = language === 'zh' ? '持仓流水已更新 · 持仓已刷新' : 'Holding record updated · holdings refreshed';
  const voidTradeSuccessLabel = language === 'zh' ? '持仓流水已作废 · 持仓已刷新' : 'Holding record voided · holdings refreshed';
  const deleteTradeTitle = language === 'zh' ? '确认作废持仓流水？' : 'Void this holding record?';
  const deleteTradeMessage = language === 'zh'
    ? '该操作会从持仓与现金计算中排除此记录，但保留历史流水。'
    : 'This removes the record from holdings and cash calculations while preserving the audit trail.';
  const voidTradeConfirmLabel = language === 'zh' ? '确认作废' : 'Confirm Void';
  const voidedTradeLabel = language === 'zh' ? '已作废' : 'Voided';
  const editTradeActionLabel = language === 'zh' ? '编辑' : 'Edit';
  const deleteTradeActionLabel = language === 'zh' ? '作废' : 'Void';
  const moreTradeActionsLabel = language === 'zh' ? '更多' : 'More';
  const manualLedgerDisclosure = language === 'zh'
    ? '手工记账入口'
    : 'Manual ledger';
  const effectiveEditTradeCurrency = editingTrade
    ? (
      editingTrade.currencyManuallyEdited
        ? editingTrade.currency
        : inferSettlementCurrency(editingTrade.symbol, editingAccount?.baseCurrency)
    )
    : 'CNY';

  useEffect(() => {
    savePortfolioDisplayCurrency(displayCurrency);
  }, [displayCurrency]);

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }
    const handleDisplayCurrencyChange = (event: Event) => {
      const next = event instanceof CustomEvent
        ? normalizePortfolioDisplayCurrency(event.detail?.currency)
        : readPortfolioDisplayCurrency();
      setDisplayCurrency(next);
    };
    const handleStorage = (event: StorageEvent) => {
      if (
        event.key === PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY
        || event.key === LEGACY_PORTFOLIO_DISPLAY_CURRENCY_STORAGE_KEY
      ) {
        setDisplayCurrency(readPortfolioDisplayCurrency());
      }
    };
    window.addEventListener(PORTFOLIO_DISPLAY_CURRENCY_CHANGED_EVENT, handleDisplayCurrencyChange);
    window.addEventListener('storage', handleStorage);
    return () => {
      window.removeEventListener(PORTFOLIO_DISPLAY_CURRENCY_CHANGED_EVENT, handleDisplayCurrencyChange);
      window.removeEventListener('storage', handleStorage);
    };
  }, []);

  const isActiveRefreshContext = (requestedViewKey: string, requestedRequestId: number) => {
    return (
      refreshContextRef.current.viewKey === requestedViewKey
      && refreshContextRef.current.requestId === requestedRequestId
    );
  };

  const resetIbkrConnectionDrafts = () => {
    setIbkrApiBaseUrlDraft(null);
    setIbkrVerifySslDraft(null);
    setIbkrBrokerAccountRefDraft(null);
  };

  const resetImportPreviewState = () => {
    setImportParseResult(null);
    setImportPreview(null);
    setImportCommitResult(null);
  };

  const invalidateFxRefreshScope = (
    nextSelectedAccount: AccountOption = selectedAccount,
    nextCostMethod: PortfolioCostMethod = costMethod,
  ) => {
    refreshContextRef.current = {
      viewKey: buildPortfolioRefreshViewKey(nextSelectedAccount, nextCostMethod),
      requestId: refreshContextRef.current.requestId + 1,
    };
    setFxRefreshing(false);
    setFxRefreshFeedback(null);
  };

  const resetHistoryNavigation = () => {
    setEventPage(1);
    setOpenTradeActionMenuId(null);
  };

  const clearAccountRequirementWarning = () => {
    setWriteWarning((prev) => (
      prev === copy.writeRequiresAccount
      || prev === copy.syncRequiresAccount
      || prev === copy.deleteRequiresAccount
        ? null
        : prev
    ));
  };

  const loadAccounts = useCallback(async () => {
    try {
      const response = await portfolioApi.getAccounts(false);
      const items = response.accounts || [];
      const nextActiveAccounts = items.filter((item) => item.isActive !== false);
      const nextWritableAccounts = nextActiveAccounts;
      setAccounts(items);
      setSelectedAccount((prev) => {
        if (items.length === 0) return 'all';
        if (prev !== 'all' && !items.some((item) => item.id === prev)) return items[0].id;
        return prev;
      });
      setSelectedTradeAccount((prev) => {
        if (nextWritableAccounts.length === 0) return 'all';
        if (prev === 'all' || !nextWritableAccounts.some((item) => item.id === prev)) return nextWritableAccounts[0].id;
        return prev;
      });
      if (items.length === 0) setShowCreateAccount(true);
    } catch (err) {
      setError(getParsedApiError(err));
    }
  }, []);

  const loadBrokers = useCallback(async () => {
    if (!canManagePortfolioOperations) {
      setBrokers([]);
      setSelectedBroker('');
      setBrokerListUnavailable(false);
      return;
    }
    try {
      const response = await portfolioApi.listImportBrokers();
      const brokerItems = response.brokers || [];
      if (brokerItems.length === 0) {
        setBrokers([]);
        setSelectedBroker('');
        setBrokerListUnavailable(true);
        return;
      }
      setBrokers(brokerItems);
      setBrokerListUnavailable(false);
      setSelectedBroker((prev) => (
        brokerItems.some((item) => item.broker === prev)
          ? prev
          : brokerItems[0].broker
      ));
    } catch {
      setBrokers([]);
      setSelectedBroker('');
      setBrokerListUnavailable(true);
    }
  }, [canManagePortfolioOperations]);

  const loadBrokerConnections = useCallback(async (accountId?: number) => {
    if (!canManagePortfolioOperations || !accountId) {
      setBrokerConnections([]);
      return;
    }
    try {
      const response = await portfolioApi.listBrokerConnections(accountId);
      setBrokerConnections(response.connections || []);
    } catch {
      setBrokerConnections([]);
    }
  }, [canManagePortfolioOperations]);

  const loadSnapshotAndRisk = useCallback(async () => {
    setIsLoading(true);
    setRiskWarning(null);
    setStructureReview(null);
    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: queryAccountId,
        costMethod,
      });
      setSnapshot(snapshotData);
      setError(null);

      const [riskResult, structureReviewResult] = await Promise.allSettled([
        portfolioApi.getRisk({
          accountId: queryAccountId,
          costMethod,
        }),
        portfolioApi.getStructureReview({
          accountId: queryAccountId,
          costMethod,
        }),
      ]);

      if (riskResult.status === 'rejected') {
        const parsed = getParsedApiError(riskResult.reason);
        setRiskWarning(parsed.message || riskFallbackMessage);
      }

      if (structureReviewResult.status === 'fulfilled') {
        setStructureReview(structureReviewResult.value);
      }
    } catch (err) {
      setSnapshot(null);
      setStructureReview(null);
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [queryAccountId, costMethod, riskFallbackMessage]);

  const loadEventsPage = async (page: number) => {

    try {
      if (eventType === 'trade') {
        const response = await portfolioApi.listTrades({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          side: eventSide || undefined,
          includeVoided: true,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setTradeEvents(response.items || []);
      } else if (eventType === 'cash') {
        const response = await portfolioApi.listCashLedger({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          direction: eventDirection || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCashEvents(response.items || []);
      } else {
        const response = await portfolioApi.listCorporateActions({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          actionType: eventActionType || undefined,
          page,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCorporateEvents(response.items || []);
      }
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const loadEvents = useCallback(async () => {
    try {
      if (eventType === 'trade') {
        const response = await portfolioApi.listTrades({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          side: eventSide || undefined,
          includeVoided: true,
          page: eventPage,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setTradeEvents(response.items || []);
      } else if (eventType === 'cash') {
        const response = await portfolioApi.listCashLedger({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          direction: eventDirection || undefined,
          page: eventPage,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCashEvents(response.items || []);
      } else {
        const response = await portfolioApi.listCorporateActions({
          accountId: queryAccountId,
          dateFrom: eventDateFrom || undefined,
          dateTo: eventDateTo || undefined,
          symbol: eventSymbol || undefined,
          actionType: eventActionType || undefined,
          page: eventPage,
          pageSize: DEFAULT_PAGE_SIZE,
        });
        setCorporateEvents(response.items || []);
      }
    } catch (err) {
      setError(getParsedApiError(err));
    }
  }, [eventType, queryAccountId, eventDateFrom, eventDateTo, eventSymbol, eventSide, eventDirection, eventActionType, eventPage]);

  const refreshPortfolioData = async (page = eventPage) => {
    await Promise.all([loadSnapshotAndRisk(), loadEventsPage(page)]);
  };

  useEffect(() => {
    void loadAccounts();
    void loadBrokers();
  }, [loadAccounts, loadBrokers]);

  useEffect(() => {
    void loadBrokerConnections(writableAccountId);
  }, [loadBrokerConnections, writableAccountId]);

  useEffect(() => {
    void loadSnapshotAndRisk();
  }, [loadSnapshotAndRisk]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  const positionRows = useMemo<FlatPosition[]>(() => {
    if (!snapshot) return [];
    const rows: FlatPosition[] = [];
    for (const account of snapshot.accounts || []) {
      for (const position of account.positions || []) {
        rows.push({
          ...position,
          accountId: account.accountId,
          accountName: formatConsumerAccountLabel(account.accountName, language),
        });
      }
    }
    rows.sort((a, b) => Number(b.marketValueBase || 0) - Number(a.marketValueBase || 0));
    return rows;
  }, [language, snapshot]);

  const handleTradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.writeRequiresAccount);
      return;
    }
    if (tradeSubmitting) {
      return;
    }
    const submittedSymbol = tradeForm.symbol.trim().toUpperCase();
    const submittedSide = tradeForm.side;
    try {
      setTradeSubmitting(true);
      setTradeFeedback(null);
      setWriteWarning(null);
      await portfolioApi.createTrade({
        accountId: writableAccountId,
        symbol: submittedSymbol || tradeForm.symbol,
        tradeDate: tradeForm.tradeDate,
        side: submittedSide,
        quantity: Number(tradeForm.quantity),
        price: Number(tradeForm.price),
        fee: Number(tradeForm.fee || 0),
        tax: Number(tradeForm.tax || 0),
        currency: effectiveTradeCurrency,
        tradeUid: tradeForm.tradeUid || undefined,
        note: tradeForm.note || undefined,
      });
      await refreshPortfolioData();
      setTradeFeedback({
        tone: 'success',
        text: `${submittedSymbol || tradeForm.symbol} ${formatSideLabel(submittedSide, language)}已保存 · 已刷新持仓`,
      });
      setTradeForm((prev) => ({ ...prev, symbol: '', currency: inferSettlementCurrency('', writableAccount?.baseCurrency), tradeUid: '', note: '' }));
      setTradeCurrencyManuallyEdited(false);
    } catch (err) {
      const parsed = getParsedApiError(err);
      setTradeFeedback({ tone: 'error', text: parsed.message || parsed.title });
      setError(parsed);
    } finally {
      setTradeSubmitting(false);
    }
  };

  const handleCashSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.writeRequiresAccount);
      return;
    }
    try {
      setWriteWarning(null);
      await portfolioApi.createCashLedger({
        accountId: writableAccountId,
        eventDate: cashForm.eventDate,
        direction: cashForm.direction,
        amount: Number(cashForm.amount),
        currency: cashForm.currency || undefined,
        note: cashForm.note || undefined,
      });
      await refreshPortfolioData();
      setCashForm((prev) => ({ ...prev, amount: '', note: '' }));
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const handleCorporateSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.writeRequiresAccount);
      return;
    }
    try {
      setWriteWarning(null);
      await portfolioApi.createCorporateAction({
        accountId: writableAccountId,
        symbol: corpForm.symbol,
        effectiveDate: corpForm.effectiveDate,
        actionType: corpForm.actionType,
        cashDividendPerShare: corpForm.cashDividendPerShare ? Number(corpForm.cashDividendPerShare) : undefined,
        splitRatio: corpForm.splitRatio ? Number(corpForm.splitRatio) : undefined,
        note: corpForm.note || undefined,
      });
      await refreshPortfolioData();
      setCorpForm((prev) => ({ ...prev, symbol: '', cashDividendPerShare: '', splitRatio: '', note: '' }));
    } catch (err) {
      setError(getParsedApiError(err));
    }
  };

  const handleSyncIbkr = async () => {
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.syncRequiresAccount);
      return;
    }
    if (!ibkrSessionToken.trim()) {
      setWriteWarning(copy.syncRequiresToken);
      return;
    }
    try {
      setWriteWarning(null);
      setIbkrSyncing(true);
      const result = await portfolioApi.syncIbkrReadOnly({
        accountId: writableAccountId,
        brokerConnectionId: ibkrConnection?.id,
        brokerAccountRef: ibkrBrokerAccountRef.trim() || undefined,
        sessionToken: ibkrSessionToken.trim(),
        apiBaseUrl: ibkrApiBaseUrl.trim() || undefined,
        verifySsl: ibkrVerifySsl,
      });
      setIbkrSyncResult(result);
      setIbkrSessionToken('');
      await loadBrokerConnections(writableAccountId);
      await refreshPortfolioData();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setIbkrSyncing(false);
    }
  };

  const handleImportFileChange = (event: React.ChangeEvent<HTMLInputElement>) => {
    setImportFile(event.target.files?.[0] ?? null);
    resetImportPreviewState();
  };

  const handlePreviewImport = async () => {
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.writeRequiresAccount);
      return;
    }
    if (!importFile) {
      setWriteWarning(t('portfolio.importFileRequired'));
      return;
    }
    if (!selectedBroker) {
      setWriteWarning(copy.brokerFallbackUnavailable);
      return;
    }
    try {
      setImportParsing(true);
      setWriteWarning(null);
      setImportCommitResult(null);
      const parsed = await portfolioApi.parseCsvImport(selectedBroker, importFile);
      const preview = await portfolioApi.commitCsvImport(writableAccountId, selectedBroker, importFile, true);
      setImportParseResult(parsed);
      setImportPreview(preview);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setImportParsing(false);
    }
  };

  const handleConfirmImport = async () => {
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!writableAccountId) {
      setWriteWarning(copy.writeRequiresAccount);
      return;
    }
    if (!importFile || !importPreview) {
      setWriteWarning(t('portfolio.importPreviewRequired'));
      return;
    }
    try {
      setImportCommitting(true);
      setWriteWarning(null);
      const committed = await portfolioApi.commitCsvImport(writableAccountId, selectedBroker, importFile, false);
      setImportCommitResult(committed);
      setImportPreview(null);
      await loadBrokerConnections(writableAccountId);
      await refreshPortfolioData();
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setImportCommitting(false);
    }
  };

  const handleConfirmDelete = async () => {
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!pendingDelete || deleteLoading) return;
    if (!writableAccountId) {
      setWriteWarning(copy.deleteRequiresAccount);
      setPendingDelete(null);
      return;
    }

    const nextPage = currentEventCount === 1 && eventPage > 1 ? eventPage - 1 : eventPage;
    try {
      setDeleteLoading(true);
      setWriteWarning(null);
      if (pendingDelete.eventType === 'trade') {
        await portfolioApi.deleteTrade(pendingDelete.id);
        setTradeFeedback({ tone: 'success', text: voidTradeSuccessLabel });
      } else if (pendingDelete.eventType === 'cash') {
        await portfolioApi.deleteCashLedger(pendingDelete.id);
      } else {
        await portfolioApi.deleteCorporateAction(pendingDelete.id);
      }
      setPendingDelete(null);
      if (nextPage !== eventPage) {
        setEventPage(nextPage);
      }
      await refreshPortfolioData(nextPage);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setDeleteLoading(false);
    }
  };

  const openTradeEditor = (item: PortfolioTradeListItem) => {
    setOpenTradeActionMenuId(null);
    const tradeAccount = activeAccounts.find((account) => account.id === item.accountId);
    const inferredCurrency = inferSettlementCurrency(item.symbol, tradeAccount?.baseCurrency);
    setEditingTrade({
      id: item.id,
      accountId: item.accountId,
      symbol: item.symbol,
      side: item.side,
      quantity: String(item.quantity),
      price: String(item.price),
      tradeDate: item.tradeDate,
      currency: item.currency,
      currencyManuallyEdited: item.currency !== inferredCurrency,
      fee: String(item.fee ?? 0),
      tax: String(item.tax ?? 0),
      note: item.note || '',
    });
  };

  const openTradeVoidDialog = (item: PortfolioTradeListItem) => {
    setOpenTradeActionMenuId(null);
    setPendingDelete({
      eventType: 'trade',
      id: item.id,
      title: deleteTradeTitle,
      message: deleteTradeMessage,
      confirmText: voidTradeConfirmLabel,
    });
  };

  const handleTradeEditSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!editingTrade || tradeEditSubmitting) {
      return;
    }
    const payload: PortfolioTradeUpdateRequest = {
      accountId: editingTrade.accountId,
      symbol: editingTrade.symbol,
      side: editingTrade.side,
      quantity: Number(editingTrade.quantity),
      price: Number(editingTrade.price),
      tradeDate: editingTrade.tradeDate,
      currency: effectiveEditTradeCurrency,
      fee: Number(editingTrade.fee || 0),
      tax: Number(editingTrade.tax || 0),
      note: editingTrade.note || undefined,
    };
    try {
      setTradeEditSubmitting(true);
      setTradeFeedback(null);
      await portfolioApi.updateTrade(editingTrade.id, payload);
      await refreshPortfolioData();
      setEditingTrade(null);
      setTradeFeedback({ tone: 'success', text: updateTradeSuccessLabel });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setTradeEditSubmitting(false);
    }
  };

  const handleConfirmAccountDelete = async () => {
    if (!canManagePortfolioOperations) {
      return;
    }
    if (!pendingAccountDelete || deleteLoading) return;
    try {
      setDeleteLoading(true);
      setWriteWarning(null);
      const result = await portfolioApi.deleteAccount(pendingAccountDelete.id);
      const accountsResponse = await portfolioApi.getAccounts(false);
      const activeAccounts = accountsResponse.accounts || [];
      setAccounts(activeAccounts);
      const recoveryAccountId = result.nextAccountId ?? activeAccounts[0]?.id;
      setSelectedAccount(recoveryAccountId ?? 'all');
      setSelectedTradeAccount(recoveryAccountId ?? 'all');
      resetHistoryNavigation();
      invalidateFxRefreshScope(recoveryAccountId ?? 'all', costMethod);
      resetIbkrConnectionDrafts();
      setIbkrSyncResult(null);
      setPendingAccountDelete(null);
      setAccountCreateSuccess(copy.accountArchived);
      setAccountCreateError(null);
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setDeleteLoading(false);
    }
  };

  const handleCreateAccount = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!canManagePortfolioOperations) {
      return;
    }
    const name = accountForm.name.trim();
    if (!name) {
      setAccountCreateError(copy.accountNameRequired);
      setAccountCreateSuccess(null);
      return;
    }
    try {
      setAccountCreating(true);
      setAccountCreateError(null);
      setAccountCreateSuccess(null);
      const created = await portfolioApi.createAccount({
        name,
        broker: accountForm.broker.trim() || undefined,
        market: accountForm.market,
        baseCurrency: accountForm.baseCurrency.trim() || 'CNY',
      });
      await loadAccounts();
      setSelectedAccount(created.id);
      setSelectedTradeAccount(created.id);
      resetHistoryNavigation();
      invalidateFxRefreshScope(created.id, costMethod);
      resetIbkrConnectionDrafts();
      setIbkrSyncResult(null);
      setShowCreateAccount(false);
      setWriteWarning(null);
      setAccountForm({
        name: '',
        broker: '',
        market: accountForm.market,
        baseCurrency: accountForm.baseCurrency,
      });
      setAccountCreateSuccess(copy.accountCreated);
    } catch (err) {
      const parsed = getParsedApiError(err);
      setAccountCreateError(parsed.message || copy.accountCreateFailed);
      setAccountCreateSuccess(null);
    } finally {
      setAccountCreating(false);
    }
  };

  const handleRefresh = async () => {
    await Promise.all([loadAccounts(), loadSnapshotAndRisk(), loadEvents(), loadBrokers(), loadBrokerConnections(writableAccountId)]);
  };

  const reloadSnapshotAndRiskForScope = async (
    requestedViewKey: string,
    requestedRequestId: number,
    requestedAccountId: number | undefined,
    requestedCostMethod: PortfolioCostMethod,
  ): Promise<boolean> => {
    if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
      return false;
    }

    setRiskWarning(null);

    try {
      const snapshotPromise = portfolioApi.getSnapshot({
        accountId: requestedAccountId,
        costMethod: requestedCostMethod,
      });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return false;
      }
      const snapshotData = await snapshotPromise;
      setSnapshot(snapshotData);
      setError(null);

      try {
        const riskPromise = portfolioApi.getRisk({
          accountId: requestedAccountId,
          costMethod: requestedCostMethod,
        });
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return false;
        }
        await riskPromise;
        setRiskWarning(null);
      } catch (riskErr) {
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return false;
        }
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || copy.riskFallback);
      }
      return true;
    } catch (err) {
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return false;
      }
      setSnapshot(null);
      setError(getParsedApiError(err));
      return false;
    }
  };

  const handleRefreshFx = async () => {
    if (isLoading || fxRefreshing) {
      return;
    }

    const requestedViewKey = refreshViewKey;
    const requestedAccountId = queryAccountId;
    const requestedCostMethod = costMethod;
    const requestedRequestId = refreshContextRef.current.requestId + 1;
    refreshContextRef.current = {
      viewKey: requestedViewKey,
      requestId: requestedRequestId,
    };

    try {
      setFxRefreshing(true);
      setFxRefreshFeedback(null);
      const result = await portfolioApi.refreshFxRate({
        base: fxBaseCurrency,
        quote: fxQuoteCurrency,
      });
      setLiveFxRate(result);
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return;
      }
      if (hasAccounts) {
        const reloaded = await reloadSnapshotAndRiskForScope(
          requestedViewKey,
          requestedRequestId,
          requestedAccountId,
          requestedCostMethod,
        );
        if (!reloaded || !isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return;
        }
      }
      setFxRefreshFeedback({
        tone: result.stale ? 'warning' : 'success',
        text: consumerFxRefreshFeedback(result.stale, language),
      });
    } catch (err) {
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return;
      }
      setError(getParsedApiError(err));
    } finally {
      if (isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        setFxRefreshing(false);
      }
    }
  };

  const snapshotCurrency = snapshot?.currency || 'CNY';
  const fxRateRows: PortfolioFxRateItem[] = snapshot?.fxRates || [];
  const fxLastUpdated = (() => {
    const timestamps = fxRateRows
      .map((item) => item.updatedAt || item.rateDate)
      .filter((value): value is string => Boolean(value));
    if (timestamps.length === 0) return '--';
    const sorted = timestamps.sort();
    return formatFxTimestamp(sorted[sorted.length - 1]);
  })();
  const selectedFxRate: DisplayFxRate | null = (() => {
    if (
      liveFxRate
      && liveFxRate.baseCurrency === fxBaseCurrency
      && liveFxRate.quoteCurrency === fxQuoteCurrency
    ) {
      return {
        rate: liveFxRate.rate,
        timestamp: liveFxRate.fetchedAt,
        provider: liveFxRate.provider,
        cacheHit: liveFxRate.cacheHit,
        isStale: liveFxRate.stale,
      };
    }

    if (fxBaseCurrency === fxQuoteCurrency) {
      return { rate: 1, timestamp: fxLastUpdated === '--' ? undefined : fxLastUpdated, provider: 'identity', isStale: false };
    }

    const direct = fxRateRows.find((item) => item.fromCurrency === fxBaseCurrency && item.toCurrency === fxQuoteCurrency);
    if (direct && typeof direct.rate === 'number') {
      return {
        rate: direct.rate,
        timestamp: direct.updatedAt || direct.rateDate || undefined,
        provider: direct.source,
        isStale: direct.isStale,
      };
    }

    const reverse = fxRateRows.find((item) => item.fromCurrency === fxQuoteCurrency && item.toCurrency === fxBaseCurrency);
    if (reverse && typeof reverse.rate === 'number' && reverse.rate !== 0) {
      return {
        rate: 1 / reverse.rate,
        timestamp: reverse.updatedAt || reverse.rateDate || undefined,
        provider: reverse.source,
        isStale: reverse.isStale,
      };
    }

    return null;
  })();
  const totalEquity = snapshot?.totalEquity ?? 0;
  const totalCash = snapshot?.totalCash ?? 0;
  const totalMarketValue = snapshot?.totalMarketValue ?? 0;
  const totalUnrealizedPnl = positionRows.reduce((sum, row) => sum + row.unrealizedPnlBase, 0);
  const convertMoney = (value: number, fromCurrency: string | undefined | null): ConvertedMoney => {
    const rate = getFxRateForDisplay(fxRateRows, fromCurrency, displayCurrency);
    if (!rate) {
      return null;
    }
    return {
      value: value * rate.rate,
      currency: displayCurrency,
      rate: rate.rate,
      stale: rate.stale,
    };
  };
  const totalEquityDisplay = convertMoney(totalEquity, snapshotCurrency);
  const totalCashDisplay = convertMoney(totalCash, snapshotCurrency);
  const totalMarketValueDisplay = convertMoney(totalMarketValue, snapshotCurrency);
  const totalUnrealizedDisplay = convertMoney(totalUnrealizedPnl, snapshotCurrency);
  const hasHoldings = positionRows.length > 0;
  const hasHistory = tradeEvents.length > 0 || cashEvents.length > 0 || corporateEvents.length > 0;
  const isEmptyPortfolio = !hasHoldings;
  const totalHistoryRows = tradeEvents.length + cashEvents.length + corporateEvents.length;
  const hasSmallHistory = totalHistoryRows <= 5;
  const shouldRenderFullHistory = hasHoldings || (isEmptyPortfolio && hasHistory && (!hasSmallHistory || showEmptyFullHistory));
  const formatDisplayMoney = (value: number, converted: ConvertedMoney, fromCurrency: string) => {
    if (converted) return formatMoney(converted.value, displayCurrency);
    if (value === 0) return formatMoney(0, displayCurrency);
    return formatMoney(value, fromCurrency);
  };
  const hasFxUnavailable = fxRateRows.some((item) => item.source === 'missing' || item.rate == null)
    || (!totalEquityDisplay && totalEquity !== 0)
    || (!totalCashDisplay && totalCash !== 0)
    || (!totalMarketValueDisplay && totalMarketValue !== 0)
    || (!totalUnrealizedDisplay && totalUnrealizedPnl !== 0);
  const hasPriceFallback = positionRows.some((row) => row.isPriceFallback);
  const hasUpdatingPrice = hasHoldings && positionRows.some((row) => !row.priceAsOf && !row.isPriceFallback);
  const hasLimitedConfidence = positionRows.some(hasLimitedValuationConfidence);
  const { notice: valuationLineageNotice, trustItem: valuationLineageTrustItem } = mapValuationLineageState(snapshot?.valuationLineageState, language);
  const portfolioLineageSummary = snapshot?.portfolioLineageSummary ?? null;
  const hasDataLineage = hasPortfolioLineage(portfolioLineageSummary);
  const consumerDataNotice = consumerPortfolioDataNotice({
    valuationLineageNotice,
    hasDataLineage: hasDataLineage,
    hasPriceFallback,
    hasUpdatingPrice,
    hasLimitedConfidence,
    hasFxUnavailable,
    hasFxStale: snapshot?.fxStale,
  }, language);
  const historyHasNextPage = currentEventCount >= DEFAULT_PAGE_SIZE;
  const totalAssetsTitle = language === 'zh' ? '总资产' : 'Total Assets';
  const historyDrawerTitle = language === 'en' ? 'Ledger History' : '历史记录';
  const fxUnavailableLabel = language === 'zh' ? '折算暂不可用' : 'Conversion unavailable';
  const noHoldingsHistoryNote = language === 'zh' ? '历史记录存在，当前无持仓' : 'History exists while current holdings are empty';
  const recentActivityTitle = language === 'zh' ? '近期活动' : 'Recent Activity';
  const emptyRecentActivityLabel = language === 'zh' ? '暂无历史记录' : 'No history yet';
  const viewFullHistoryLabel = language === 'zh' ? '查看全部历史' : 'View full history';
  const hideFullHistoryLabel = language === 'zh' ? '收起完整历史' : 'Hide full history';
  const portfolioEmptyStateGuidance = language === 'zh'
    ? '添加持仓后显示'
    : 'Displays after adding holdings';
  const formatConvertedDisplay = (value: number, nativeCurrency: string) => {
    if (nativeCurrency === displayCurrency) {
      return null;
    }
    const converted = convertMoney(value, nativeCurrency);
    return converted ? `≈ ${formatMoney(converted.value, displayCurrency)}` : fxUnavailableLabel;
  };
  const analytics = snapshot?.analytics ?? null;
  const pnlSourceCurrency = analytics?.pnl.displayCurrency || snapshotCurrency;
  const realizedPnl = analytics?.pnl.realized.amount ?? snapshot?.realizedPnl ?? 0;
  const unrealizedPnl = analytics?.pnl.unrealized.amount ?? totalUnrealizedPnl;
  const totalPnl = analytics?.pnl.total.amount ?? realizedPnl + unrealizedPnl;
  const realizedPnlDisplay = convertMoney(realizedPnl, pnlSourceCurrency);
  const unrealizedPnlDisplay = convertMoney(unrealizedPnl, pnlSourceCurrency);
  const totalPnlDisplay = convertMoney(totalPnl, pnlSourceCurrency);
  const analyticsEmptyText = language === 'zh' ? '暂无持仓，保存持仓流水后生成盈亏与资产配置。' : 'No holdings yet. Save holding records to generate P&L and allocation.';
  const pnlLabels = {
    realized: language === 'zh' ? '已实现盈亏' : 'Realized',
    unrealized: language === 'zh' ? '未实现盈亏' : 'Unrealized',
    total: language === 'zh' ? '总盈亏' : 'Total P&L',
    native: language === 'zh' ? '原币' : 'Native',
  };
  const exposureTitle = language === 'zh' ? '资产配置' : 'Exposure';
  const riskTitle = language === 'zh' ? '组合风险' : 'Portfolio Risk';
  const exposureEmpty = language === 'zh' ? '暂无配置数据' : 'No exposure data';
  const riskWarningLabels: Record<string, string> = {
    no_holdings: language === 'zh' ? '暂无持仓' : 'No holdings',
    single_position_gt_30: language === 'zh' ? '单一标的占比较高' : 'Single position concentration',
    single_currency_gt_80: language === 'zh' ? '单一币种占比较高' : 'Single currency concentration',
    single_market_gt_80: language === 'zh' ? '单一市场占比较高' : 'Single market concentration',
    fx_conversion_unavailable: language === 'zh' ? '部分折算暂不可用，已保留原币值' : 'Some conversion data is unavailable; native values remain visible',
  };
  const exposureTabs = [
    { value: 'account', label: language === 'zh' ? '账户' : 'Account' },
    { value: 'currency', label: language === 'zh' ? '币种' : 'Currency' },
    { value: 'market', label: language === 'zh' ? '市场' : 'Market' },
    { value: 'symbol', label: language === 'zh' ? '标的' : 'Symbol' },
    ...(analytics?.exposure.sectorStatus === 'available' ? [{ value: 'sector', label: language === 'zh' ? '行业' : 'Sector' }] : []),
  ];
  const exposureRows: PortfolioExposureItem[] = (() => {
    const exposure = analytics?.exposure;
    if (!exposure) return [];
    if (exposureTab === 'account') return exposure.byAccount || [];
    if (exposureTab === 'currency') return exposure.byCurrency || [];
    if (exposureTab === 'market') return exposure.byMarket || [];
    if (exposureTab === 'symbol') return exposure.bySymbol || [];
    return exposure.bySector || [];
  })();
  const formatAnalyticsMoney = (value: number, currency: string) => {
    const converted = convertMoney(value, currency);
    if (converted) return formatMoney(converted.value, displayCurrency);
    if (value === 0) return formatMoney(0, displayCurrency);
    return formatMoney(value, currency);
  };
  const renderExposureValue = (row: PortfolioExposureItem) => {
    const currency = row.displayCurrency || snapshotCurrency;
    const display = formatAnalyticsMoney(row.displayValue ?? row.marketValue ?? 0, currency);
    const native = row.nativeCurrency && row.nativeCurrency !== displayCurrency && row.nativeValue != null
      ? formatMoney(row.nativeValue, row.nativeCurrency)
      : null;
    return { display, native };
  };
  const formatExposureRowLabel = (row: PortfolioExposureItem) => {
    if (exposureTab === 'market') {
      return formatExposureMarketLabel(row, language);
    }
    return row.label || row.key;
  };
  const symbolExposureRows = sortExposureRowsByPercent(analytics?.exposure.bySymbol);
  const currencyExposureRows = sortExposureRowsByPercent(analytics?.exposure.byCurrency);
  const marketExposureRows = sortExposureRowsByPercent(analytics?.exposure.byMarket);
  const accountExposureRows = sortExposureRowsByPercent(analytics?.exposure.byAccount);
  const topPosition = symbolExposureRows[0] || analytics?.risk.largestPosition || null;
  const topCurrency = currencyExposureRows[0] || analytics?.risk.largestCurrency || null;
  const topMarket = marketExposureRows[0] || analytics?.risk.largestMarket || null;
  const topAccount = accountExposureRows[0] || null;
  const topPositionPercent = Number(topPosition?.percent || 0);
  const concentrationLabel = !hasHoldings || !topPosition
    ? (language === 'zh' ? '待生成' : 'Pending')
    : topPositionPercent < 20
      ? (language === 'zh' ? '分散' : 'Diversified')
      : topPositionPercent < 35
        ? (language === 'zh' ? '适中' : 'Balanced')
        : topPositionPercent < 50
          ? (language === 'zh' ? '集中' : 'Concentrated')
          : (language === 'zh' ? '高度集中' : 'Highly concentrated');
  const concentrationToneClass = topPositionPercent >= 50
    ? 'text-rose-300'
    : topPositionPercent >= 35
      ? 'text-amber-300'
      : topPositionPercent >= 20
        ? 'text-[color:var(--wolfy-accent)]'
        : 'text-emerald-300';
  const concentrationDescription = !hasHoldings || !topPosition
    ? (language === 'zh' ? '完成首笔持仓后，系统会按真实持仓自动生成集中度与暴露判断。' : 'After the first holding is saved, concentration and exposure are generated from real positions automatically.')
    : language === 'zh'
      ? `最大持仓占 ${formatPercent(topPositionPercent)}，按持仓市值占比判定为${concentrationLabel}。`
      : `Largest holding is ${formatPercent(topPositionPercent)} of exposure, classified as ${concentrationLabel}.`;
  const riskHintTexts = [
    topPositionPercent >= 35 ? (language === 'zh' ? '最大持仓偏高' : 'Largest holding elevated') : null,
    Number(topCurrency?.percent || 0) >= 80 ? (language === 'zh' ? '币种集中' : 'Currency concentrated') : null,
    Number(topMarket?.percent || 0) >= 80 ? (language === 'zh' ? '市场集中' : 'Market concentrated') : null,
    hasHoldings && (analytics?.risk.holdingCount ?? positionRows.length) < 3 ? (language === 'zh' ? '持仓数量较少' : 'Few holdings') : null,
    analytics?.risk.fxUnavailable ? (language === 'zh' ? '汇率数据暂不可用' : 'Exchange-rate data unavailable') : null,
  ].filter(Boolean) as string[];
  const safeRiskWarningLabels = (analytics?.risk.warnings || []).reduce<string[]>((acc, warning) => {
    const label = riskWarningLabels[warning];
    if (label) acc.push(label);
    return acc;
  }, []);
  const portfolioEvidenceSummary = snapshot ? normalizePortfolioRiskEvidence(snapshot, { maxLimitationLabels: 6 }) : null;
  const hasPortfolioEvidenceSummary = Boolean(
    portfolioEvidenceSummary
    && (
      portfolioEvidenceSummary.posture !== 'unknown'
      || portfolioEvidenceSummary.confidenceCap != null
      || portfolioEvidenceSummary.limitationLabels.length > 0
      || portfolioEvidenceSummary.freshnessLabel != null
    ),
  );
  const valuationTrustItems = uniqueTrustItems([
    lineageTrustItem('price', hasDataLineage ? portfolioLineageSummary.price : null),
    lineageTrustItem('fx', hasDataLineage ? portfolioLineageSummary.fx : null),
    lineageTrustItem('snapshot', hasDataLineage ? portfolioLineageSummary.snapshot : null),
    valuationLineageTrustItem,
    hasPriceFallback
      ? { key: 'valuation-delayed', label: language === 'zh' ? '价格可能延迟' : 'Pricing may be delayed', variant: 'caution' }
      : hasLimitedConfidence
        ? { key: 'valuation-limited', label: limitedConfidenceLabel(language), variant: 'caution' }
      : !hasDataLineage && hasHoldings
        ? { key: 'valuation-partial-without-lineage', label: language === 'zh' ? '估值部分可用' : 'Valuation partial', variant: 'caution' }
        : null,
    summarizePortfolioPriceFreshness(positionRows, language),
    summarizePortfolioPriceAsOf(positionRows, language),
    hasPortfolioEvidenceSummary ? consumerTrustItemFromLabel(portfolioEvidenceSummary?.displayLabel, language, 'snapshot-posture') : null,
    portfolioEvidenceSummary?.confidenceCap != null ? { key: 'snapshot-limited-confidence', label: limitedConfidenceLabel(language), variant: 'caution' } : null,
    consumerTrustItemFromLabel(portfolioEvidenceSummary?.freshnessLabel, language, 'snapshot-freshness'),
    buildTrustStateItem('fxFreshness', snapshot?.fxFreshnessState, language),
    buildTrustStateItem('holdingsLineage', snapshot?.holdingsLineageState, language),
    buildTrustStateItem('cashLedgerCompleteness', snapshot?.cashLedgerCompletenessState, language),
  ]);
  const riskTrustItems = uniqueTrustItems([
    lineageTrustItem('analytics', hasDataLineage ? portfolioLineageSummary.analytics : null),
    portfolioEvidenceSummary
      ? {
        key: `risk-posture-${portfolioEvidenceSummary.posture}`,
        label: sanitizePortfolioConsumerLabel(portfolioEvidenceSummary.displayLabel, language) || (language === 'zh' ? '数据状态待确认' : 'Data status pending'),
        variant: portfolioEvidenceVariant(portfolioEvidenceSummary),
      }
      : null,
    portfolioEvidenceSummary?.confidenceCap != null
      ? {
        key: `risk-cap-${portfolioEvidenceSummary.confidenceCap}`,
        label: limitedConfidenceLabel(language),
        variant: 'caution',
      }
      : null,
    portfolioEvidenceSummary?.freshnessLabel
      ? consumerTrustItemFromLabel(portfolioEvidenceSummary.freshnessLabel, language, 'risk-freshness')
      : null,
    ...(portfolioEvidenceSummary?.limitationLabels || [])
      .map((label) => consumerTrustItemFromLabel(label, language, 'risk-limitation')),
    buildTrustStateItem('benchmarkMapping', snapshot?.benchmarkMappingState, language),
    buildTrustStateItem('factorMapping', snapshot?.factorMappingState, language),
    buildTrustStateItem('fxFreshness', snapshot?.fxFreshnessState, language),
    buildTrustStateItem('holdingsLineage', snapshot?.holdingsLineageState, language),
    buildTrustStateItem('cashLedgerCompleteness', snapshot?.cashLedgerCompletenessState, language),
  ]);
  const exposureSummaryFxTrustItem = buildTrustStateItem('fxFreshness', snapshot?.fxFreshnessState, language);
  const exposureSummaryTrustItems = uniqueTrustItems([
    exposureSummaryFxTrustItem,
    !exposureSummaryFxTrustItem && (hasFxUnavailable || analytics?.risk.fxUnavailable)
      ? { key: 'exposure-fx-unavailable', label: consumerFxLabel('missing', language), variant: 'danger' }
      : null,
    !exposureSummaryFxTrustItem && snapshot?.fxStale
      ? { key: 'exposure-fx-stale', label: consumerFxLabel('stale', language), variant: 'caution' }
      : null,
    hasPortfolioEvidenceSummary && portfolioEvidenceSummary?.confidenceCap != null
      ? { key: 'exposure-limited-confidence', label: limitedConfidenceLabel(language), variant: 'caution' }
      : null,
    buildTrustStateItem('benchmarkMapping', snapshot?.benchmarkMappingState, language),
    buildTrustStateItem('factorMapping', snapshot?.factorMappingState, language),
    buildTrustStateItem('holdingsLineage', snapshot?.holdingsLineageState, language),
  ]).slice(0, 4);
  const exposureSummaryTitle = language === 'zh' ? '风险暴露摘要' : 'Risk Exposure Summary';
  const exposureSummaryLargestLabel = language === 'zh' ? '最大持仓' : 'Largest holding';
  const exposureSummaryCashLabel = language === 'zh' ? '现金占比' : 'Cash percent';
  const topMarketAccountLabel = [
    topMarket ? formatExposureMarketLabel(topMarket, language) : null,
    topAccount ? formatConsumerAccountLabel(topAccount.accountName || topAccount.label || topAccount.key, language) : null,
  ].filter(Boolean).join(' / ') || '--';
  const topMarketAccountPercent = [
    topMarket ? formatPercent(topMarket.percent) : null,
    topAccount ? formatPercent(topAccount.percent) : null,
  ].filter(Boolean).join(' / ') || '--';
  const exposureSummaryRows = [
    {
      key: 'largest-position',
      label: exposureSummaryLargestLabel,
      value: topPosition?.label || topPosition?.key || '--',
      detail: formatPercent(topPosition?.percent),
    },
    {
      key: 'largest-currency',
      label: language === 'zh' ? '主币种' : 'Largest currency',
      value: topCurrency?.label || topCurrency?.currency || topCurrency?.key || '--',
      detail: formatPercent(topCurrency?.percent),
    },
    {
      key: 'largest-market-account',
      label: language === 'zh' ? '主市场 / 账户' : 'Largest market / account',
      value: topMarketAccountLabel,
      detail: topMarketAccountPercent,
    },
    {
      key: 'cash-percent',
      label: exposureSummaryCashLabel,
      value: formatPercent(analytics?.risk.cashPercent),
      detail: language === 'zh' ? '当前组合权益' : 'Current portfolio equity',
    },
  ];
  const exposureSummaryDisclosureSummary = !hasHoldings
    ? (language === 'zh' ? '完成首笔持仓后自动生成风险暴露摘要。' : 'Exposure summary appears automatically after the first holding is saved.')
    : `${exposureSummaryLargestLabel} ${formatPercent(topPosition?.percent)} · ${exposureSummaryCashLabel} ${formatPercent(analytics?.risk.cashPercent)}`;
  const exposureSummaryBasisNote = language === 'zh'
    ? '仅基于当前页面快照汇总，不展示尚未确认的行业、主题、因子或相关性分类。'
    : 'Summarized only from the current page snapshot; unconfirmed sector, theme, factor, and correlation categories stay out of the default summary.';
  const holdingsPrimaryValue = hasHoldings
    ? (language === 'zh' ? `${positionRows.length} 项持仓` : `${positionRows.length} holdings`)
    : (language === 'zh' ? '等待首笔持仓' : 'Awaiting first holding');
  const showHeaderPortfolioActions = hasHoldings && canManagePortfolioOperations;
  const accountStateSummary = !hasActiveAccounts
    ? (language === 'zh' ? '暂无可用账户' : 'No available account')
    : selectedAccount === 'all'
      ? (language === 'zh' ? `${activeAccounts.length} 个活跃账户` : `${activeAccounts.length} active accounts`)
      : scopedAccount?.name || copy.allAccounts;
  const compactNoHoldingText = language === 'zh'
    ? '先创建或选择账户，再添加第一笔持仓或导入历史记录。'
    : 'Create or select an account, then add the first holding or import records.';
  const portfolioEmptyHelpText = language === 'zh'
    ? '保存后会在下方自动展开真实持仓、风险摘要与近期活动。'
    : 'Once saved, the real holdings, risk summary, and recent activity appear below.';
  const addHoldingActionLabel = language === 'zh' ? '添加持仓' : 'Add holding';
  const importTradesActionLabel = language === 'zh' ? '导入记录' : 'Import records';
  const manualLedgerActionLabel = language === 'zh' ? '手工记账' : 'Manual ledger';
  const onboardingTitle = !hasAccounts
    ? (language === 'zh' ? '创建你的首个组合' : 'Create your first portfolio')
    : (language === 'zh' ? '开始配置首个组合' : 'Start setting up the first portfolio');
  const onboardingBody = !hasAccounts
    ? (language === 'zh'
      ? '先创建一个真实组合账户，再选择手工记账或导入历史记录。保存前不会生成示例持仓、收益或建议。'
      : 'Create a real portfolio account first, then use manual ledger or import history. No sample holdings, returns, or advice are generated before saving.')
    : (language === 'zh'
      ? '当前工作区已准备好接收第一笔持仓或导入历史记录；完成后会自动生成真实持仓、风险与时间线。'
      : 'This workspace is ready for the first holding or imported history. Real holdings, risk, and timeline views appear automatically after that.');
  const onboardingPrimaryActionLabel = !hasAccounts
    ? copy.createAccount
    : hasWritableAccounts
      ? addHoldingActionLabel
      : (language === 'zh' ? '管理账户' : 'Manage accounts');
  const onboardingPrimaryAction = () => {
    if (!hasAccounts || !hasWritableAccounts) {
      openManualLedger('account');
      return;
    }
    openManualLedger('trade', 'stock');
  };
  const onboardingSteps = [
    {
      key: 'account',
      label: language === 'zh' ? '账户准备' : 'Account setup',
      detail: hasAccounts
        ? accountStateSummary
        : (language === 'zh' ? '先创建一个真实组合账户' : 'Create a real portfolio account first'),
    },
    {
      key: 'records',
      label: language === 'zh' ? '首笔记录' : 'First records',
      detail: hasWritableAccounts
        ? (language === 'zh' ? '添加第一笔持仓或导入历史记录' : 'Add the first holding or import historical records')
        : (language === 'zh' ? '账户可写后开放持仓与导入入口' : 'Holdings and import open once the account is writable'),
    },
    {
      key: 'workspace',
      label: language === 'zh' ? '工作区生成' : 'Workspace activation',
      detail: language === 'zh'
        ? '完成后自动显示持仓、风险与近期活动'
        : 'Real holdings, risk, and recent activity appear automatically after completion',
    },
  ];
  const emptyRiskPreviewItems = [
    {
      key: 'position',
      label: language === 'zh' ? '集中度' : 'Concentration',
      detail: language === 'zh' ? '首笔持仓后生成' : 'Appears after the first holding',
    },
    {
      key: 'currency',
      label: language === 'zh' ? '币种暴露' : 'Currency exposure',
      detail: language === 'zh' ? '按真实持仓自动汇总' : 'Aggregated from real holdings automatically',
    },
    {
      key: 'market',
      label: language === 'zh' ? '市场暴露' : 'Market exposure',
      detail: language === 'zh' ? '按组合结构自动分类' : 'Classified from the real portfolio structure',
    },
  ];
  const buildHoldingTrustItems = (row: FlatPosition) => uniqueTrustItems([
    {
      key: `${row.symbol}-freshness`,
      label: positionPriceFreshnessLabel(row, language),
      variant: row.isPriceFallback ? 'caution' : 'neutral',
    },
    hasLimitedValuationConfidence(row)
      ? {
        key: `${row.symbol}-limited-confidence`,
        label: limitedConfidenceLabel(language),
        variant: 'caution',
      }
      : null,
    topPosition?.key === row.symbol && topPositionPercent >= 35
      ? {
        key: `${row.symbol}-concentration`,
        label: language === 'zh' ? '集中' : 'Concentrated',
        variant: topPositionPercent >= 50 ? 'danger' : 'caution',
      }
      : null,
  ]).slice(0, 3);
  const structureReviewHoldings = structureReview?.holdingsStructure ?? [];
  const structureReviewExposure = structureReview?.exposureByThemeOrSector?.[0] ?? null;
  const structureReviewLargestHolding = structureReview?.aggregateSummary?.largestHolding ?? null;
  const structureReviewStateEntries = Object.entries(structureReview?.countsByStructureState ?? {})
    .filter(([, count]) => typeof count === 'number' && count > 0)
    .sort((left, right) => right[1] - left[1]);
  const structureReviewGapMessages = Array.from(new Set([
    ...(structureReview?.missingEvidence ?? []).map((item) => item.message),
    ...structureReviewHoldings.flatMap((holding) => [
      ...holding.riskFlags,
      ...holding.researchNotes.needsMoreEvidence,
      ...holding.missingEvidence.map((item) => item.message),
    ]),
  ]
    .map((item) => sanitizeStructureReviewMessage(item, language))
    .filter((item): item is string => Boolean(item)))).slice(0, 6);
  const structureReviewStatusText = structureReviewDataStatusLabel(structureReview?.dataQuality.status, language);
  const structureReviewEvidenceText = structureReviewEvidenceStatusLabel(
    structureReview?.dataQuality.structureEvidenceStatus ?? structureReview?.dataQuality.status,
    language,
  );
  const structureReviewIntro = language === 'zh'
    ? '研究工作流：先看结构状态，再补证据，再进入个股详情。'
    : 'Research workflow: review structure state, close evidence gaps, then open stock detail.';
  const structureReviewUnavailableTitle = language === 'zh' ? '结构审查暂不可用' : 'Structure review unavailable';
  const structureReviewUnavailableBody = language === 'zh'
    ? '当前保留账务、现金与盈亏视图；结构研究视角会在只读审查恢复后显示。'
    : 'Accounting, cash, and P&L views remain available. The structure research view appears again once the read-only review recovers.';
  const structureReviewEmptyTitle = language === 'zh' ? '等待首笔持仓' : 'Awaiting first holding';
  const structureReviewEmptyBody = language === 'zh'
    ? '保存首笔持仓后，这里会展示结构状态、证据缺口与个股结构详情入口。'
    : 'After the first holding is saved, this section will show structure state, evidence gaps, and stock-level structure detail links.';
  const structureReviewContextLabel = language === 'zh' ? '只读研究上下文' : 'Read-only research context';
  const structureReviewDetailLabel = language === 'zh' ? '查看结构详情' : 'Open structure detail';
  const scenarioRiskPositions = useMemo<PortfolioScenarioRiskVisiblePosition[]>(
    () => positionRows.map((row) => ({
      symbol: row.symbol,
      marketValue: row.marketValueBase,
      marketValueBase: row.marketValueBase,
      bucketLabel: formatConsumerAccountLabel(row.accountName, language),
      currency: row.currency || row.valuationCurrency || null,
    })),
    [language, positionRows],
  );
  const syncDataActionLabel = language === 'zh' ? '同步数据' : 'Sync data';
  const openManualLedger = (nextLeftTab: 'trade' | 'account' | 'sync' | 'fx', nextTradeType?: TradeFormType) => {
    if (!canManagePortfolioOperations) {
      return;
    }
    setLeftTab(nextLeftTab);
    if (nextTradeType) {
      setTradeType(nextTradeType);
    }
    setManualLedgerOpen(true);
  };
  const heroStatusChips = uniqueTrustItems([
    {
      key: 'hero-account-scope',
      label: selectedAccount === 'all'
        ? (language === 'zh' ? '全账户视角' : 'All accounts')
        : (scopedAccount?.name || copy.allAccounts),
      variant: 'neutral',
    },
    hasFxUnavailable
      ? {
        key: 'hero-valuation-paused',
        label: language === 'zh' ? '估值已暂停' : 'Valuation paused',
        variant: 'danger',
      }
      : hasDataLineage
        ? portfolioLineageSummary.snapshot.label === '估值完整'
          && portfolioLineageSummary.price.label === '价格可用'
          && portfolioLineageSummary.fx.label === '汇率已确认'
          ? {
            key: 'hero-valuation-current',
            label: language === 'zh' ? '估值完整' : 'Valuation complete',
            variant: 'success',
          }
          : portfolioLineageSummary.snapshot.label === '估值不可用'
            || portfolioLineageSummary.price.label === '价格缺失'
            || portfolioLineageSummary.fx.label === '汇率缺失'
            ? {
              key: 'hero-valuation-unavailable',
              label: language === 'zh' ? '估值不可用' : 'Valuation unavailable',
              variant: 'danger',
            }
            : {
              key: 'hero-valuation-partial',
              label: language === 'zh' ? '估值部分可用' : 'Valuation partial',
              variant: 'caution',
            }
        : hasHoldings
          ? {
            key: 'hero-valuation-partial',
            label: language === 'zh' ? '估值部分可用' : 'Valuation partial',
            variant: 'caution',
          }
          : {
            key: 'hero-valuation-pending',
            label: language === 'zh' ? '等待估值' : 'Valuation pending',
            variant: 'neutral',
          },
    !hasHoldings
      ? {
        key: 'hero-risk-pending',
        label: language === 'zh' ? '风险待生成' : 'Risk pending',
        variant: 'neutral',
      }
      : topPositionPercent >= 50
        ? {
          key: 'hero-risk-high',
          label: language === 'zh' ? '风险偏高' : 'Elevated risk',
          variant: 'danger',
        }
        : topPositionPercent >= 35
          ? {
            key: 'hero-risk-focused',
            label: language === 'zh' ? '风险偏集中' : 'Focused risk',
            variant: 'caution',
          }
          : {
            key: 'hero-risk-balanced',
            label: language === 'zh' ? '风险可控' : 'Risk balanced',
            variant: 'success',
          }
  ]).slice(0, 3);
  const heroConclusion = !hasActiveAccounts
    ? (language === 'zh'
      ? '先创建账户，再开始记录持仓、现金与组合表现。'
      : 'Create an account first to start tracking holdings, cash, and portfolio performance.')
    : !hasHoldings
      ? compactNoHoldingText
      : consumerDataNotice
        ? `${holdingsPrimaryValue} · ${concentrationLabel} · ${consumerDataNotice}`
        : language === 'zh'
          ? `${holdingsPrimaryValue}，当前为${concentrationLabel}结构，可继续查看持仓、风险与近期活动。`
          : `${holdingsPrimaryValue} with a ${concentrationLabel.toLowerCase()} profile. Review holdings, risk, and recent activity next.`;
  const holdingsHeaderNote = hasHoldings
    ? (language === 'zh'
      ? `${accountStateSummary} · ${positionRows.length} 项持仓`
      : `${accountStateSummary} · ${positionRows.length} holdings`)
    : (language === 'zh' ? '添加持仓后显示' : 'The real ledger appears after first holding is saved.');
  const valuationSnapshotNote = hasHoldings
    ? summarizePortfolioPriceAsOf(positionRows, language)?.label
      || (language === 'zh' ? '价格快照待确认' : 'Price snapshot pending')
    : (language === 'zh' ? '首笔持仓后显示价格快照' : 'Price snapshots appear after the first holding');
  const nextActionHeadline = !hasAccounts
    ? (language === 'zh' ? '先创建一个组合账户' : 'Create your first portfolio account')
    : !hasHoldings
      ? (language === 'zh' ? '先补第一笔持仓或导入历史记录' : 'Add the first holding or import records')
      : hasFxUnavailable
        ? (language === 'zh' ? '先确认汇率与估值状态' : 'Check FX and valuation status first')
        : hasHistory
          ? (language === 'zh' ? '继续核对近期活动与组合变化' : 'Review recent activity and portfolio changes')
          : (language === 'zh' ? '继续补充记录，完善组合画像' : 'Add more records to complete the portfolio picture');
  const nextActionBody = !hasAccounts
    ? (language === 'zh'
      ? '账户准备好后即可添加持仓、导入历史记录，并查看风险与数据说明。'
      : 'Once the account is ready, you can add holdings, import records, and review risk and evidence.')
    : !hasHoldings
      ? (language === 'zh'
        ? '组合为空，请添加持仓。数据不足，暂不形成结论。'
        : 'Portfolio empty, add holdings. Evidence is insufficient for a conclusion.')
      : hasFxUnavailable
        ? (language === 'zh'
          ? '部分汇率暂不可用'
          : 'Some FX data unavailable')
        : hasHistory
          ? (language === 'zh'
            ? '近期活动已保留在下方时间线，可继续核对风险与持仓集中度。'
            : 'Recent activity remains in the timeline below. Continue by checking risk and concentration.')
          : (language === 'zh'
            ? '当前组合已可观察，下一步可补录现金、公司行为或同步新数据。'
            : 'The portfolio is ready to observe. Next you can add cash flows, corporate actions, or sync new data.');
  const hasFreshValuationState = hasDataLineage
    ? portfolioLineageSummary.snapshot.label === '估值完整'
    : false;
  const valuationNextEvidenceCopy = hasDataLineage
    ? (
      portfolioLineageSummary.snapshot.label === '估值完整'
        ? (language === 'zh'
          ? '下一步：当前估值已完整，可继续观察价格、汇率与风险变化。'
          : 'Next step: valuation is complete; keep observing price, FX, and risk changes.')
        : [
          portfolioLineageSummary.price.label !== '价格可用'
            ? (language === 'zh' ? '补齐价格' : 'complete price')
            : null,
          portfolioLineageSummary.fx.label !== '汇率已确认'
            ? (language === 'zh' ? '确认汇率' : 'confirm FX')
            : null,
          portfolioLineageSummary.snapshot.label !== '估值完整'
            ? (language === 'zh' ? '补齐估值快照' : 'complete valuation snapshot')
            : null,
        ].filter(Boolean).join(language === 'zh' ? '、' : ', ').replace(/^/, language === 'zh' ? '下一步：' : 'Next step: ')
    )
    : hasHoldings
      ? (language === 'zh'
        ? '下一步：先确认价格与汇率，再补齐估值快照。'
        : 'Next step: confirm price and FX, then complete the valuation snapshot.')
      : (language === 'zh'
        ? '下一步：先接入持仓，再确认价格与汇率。'
        : 'Next step: connect holdings first, then confirm price and FX.');
  const valuationEvidenceBlocked = Boolean(
    snapshot
    && hasHoldings
    && hasBlockedValuationEvidence(portfolioLineageSummary, snapshot.valuationSnapshotLineage, hasFxUnavailable),
  );
  const valuationEvidenceWarnings = [
    ...safeRiskWarningLabels,
    consumerDataNotice,
    ...valuationTrustItems.map((item) => item.label),
  ].filter((item): item is string => Boolean(item));
  const portfolioValuationEvidencePack = snapshot && hasHoldings && !valuationEvidenceBlocked
    ? buildPortfolioValuationEvidencePack({
      snapshot,
      language,
      accountScope: selectedAccount === 'all' ? 'all_accounts' : 'selected_account',
      accountLabel: selectedAccount === 'all'
        ? copy.allAccounts
        : formatConsumerAccountLabel(scopedAccount?.name, language),
      positions: positionRows,
      summary: portfolioLineageSummary,
      priceLineage: snapshot.priceLineage,
      fxLineage: snapshot.fxLineage,
      valuationLineage: snapshot.valuationSnapshotLineage,
      totalMarketValue,
      totalEquity,
      totalCash,
      unrealizedPnl: totalUnrealizedPnl,
      currency: snapshotCurrency,
      warnings: valuationEvidenceWarnings,
    })
    : null;
  const portfolioValuationEvidenceJson = portfolioValuationEvidencePack
    ? JSON.stringify(portfolioValuationEvidencePack, null, 2)
    : null;
  const handleCopyValuationEvidence = useCallback(async () => {
    if (!portfolioValuationEvidenceJson) {
      setValuationEvidenceFeedback(language === 'zh' ? '估值证据待补证，暂不可复制。' : 'Valuation evidence is pending and cannot be copied yet.');
      return;
    }
    if (typeof navigator === 'undefined' || !navigator.clipboard?.writeText) {
      setValuationEvidenceFeedback(language === 'zh' ? '当前浏览器暂不支持复制，请使用导出。' : 'Clipboard is unavailable; use export instead.');
      return;
    }
    await navigator.clipboard.writeText(portfolioValuationEvidenceJson);
    setValuationEvidenceFeedback(language === 'zh' ? '估值证据包已复制。' : 'Valuation evidence pack copied.');
  }, [language, portfolioValuationEvidenceJson]);
  const handleDownloadValuationEvidence = useCallback(() => {
    if (!portfolioValuationEvidenceJson || typeof document === 'undefined' || typeof Blob === 'undefined' || typeof URL === 'undefined') {
      setValuationEvidenceFeedback(language === 'zh' ? '估值证据待补证，暂不可导出。' : 'Valuation evidence is pending and cannot be exported yet.');
      return;
    }
    const blob = new Blob([portfolioValuationEvidenceJson], { type: 'application/json;charset=utf-8' });
    const url = URL.createObjectURL(blob);
    const link = document.createElement('a');
    link.href = url;
    link.download = `portfolio-valuation-evidence-${snapshot?.asOf || 'unknown'}.json`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setValuationEvidenceFeedback(language === 'zh' ? '估值证据包已导出 JSON。' : 'Valuation evidence JSON exported.');
  }, [language, portfolioValuationEvidenceJson, snapshot?.asOf]);
  const researchStateNextAction = !canManagePortfolioOperations
    ? (language === 'zh' ? '查看接入指引' : 'Review setup guidance')
    : !hasHoldings
    ? (language === 'zh' ? '补持仓或导入流水' : 'Add records or import ledger')
    : hasFxUnavailable || snapshot?.fxStale
      ? (language === 'zh' ? '确认FX与估值' : 'Confirm FX and valuation')
      : (language === 'zh' ? '查看风险暴露' : 'Review risk exposure');
  const portfolioProductizationOrder = language === 'zh'
    ? ['账户上下文', '组合观察', '集中度 / 暴露', '持仓账本', '新鲜度', '限制', '导入预览', '显式确认', '个股研究交接']
    : ['Account context', 'Portfolio observation', 'Concentration / exposure', 'Holdings ledger', 'Freshness', 'Limitations', 'Import preview', 'Explicit confirm', 'Stock Research handoff'];
  const primaryResearchHolding = positionRows.find((row) => row.symbol);
  const stockResearchHandoffPath = primaryResearchHolding
    ? buildResearchWorkspacePath('stock-structure', language, {
      symbol: primaryResearchHolding.symbol,
      market: primaryResearchHolding.market,
      source: 'portfolio',
    })
    : null;
  const researchStatePreviewItems = [
    {
      key: 'account-readiness',
      label: hasActiveAccounts
        ? (language === 'zh' ? '账户已设置' : 'Account ready')
        : (language === 'zh' ? '账户待设置' : 'Account setup pending'),
      value: hasActiveAccounts ? accountStateSummary : (language === 'zh' ? '账户待设置' : 'Account setup pending'),
      detail: hasWritableAccounts
        ? (language === 'zh' ? '可继续接入真实流水。' : 'Ready for real ledger records.')
        : (language === 'zh' ? '先创建账户。' : 'Create an account first.'),
      variant: hasActiveAccounts ? 'success' : 'neutral',
    },
    {
      key: 'holding-readiness',
      label: hasHoldings
        ? (language === 'zh' ? '可评估持仓' : 'Evaluable positions')
        : (language === 'zh' ? '持仓待接入' : 'Position records pending'),
      value: hasHoldings
        ? (language === 'zh' ? `${positionRows.length} 项` : `${positionRows.length} positions`)
        : (language === 'zh' ? '持仓待接入' : 'Position records pending'),
      detail: hasHoldings
        ? (language === 'zh' ? '已进入首屏风险与估值摘要。' : 'Shown in first-screen risk and valuation summary.')
        : (language === 'zh' ? '接入后评估市值、盈亏与暴露。' : 'Adds valuation, P&L, and exposure context.'),
      variant: hasHoldings ? 'success' : 'neutral',
    },
    {
      key: 'price-readiness',
      label: hasDataLineage
        ? portfolioLineageSummary.price.label
        : hasHoldings && (hasPriceFallback || hasUpdatingPrice)
          ? '价格延迟'
          : hasHoldings
            ? '价格缺失'
            : '价格待补',
      value: hasDataLineage
        ? portfolioLineageSummary.price.label
        : hasHoldings && (hasPriceFallback || hasUpdatingPrice)
          ? '价格延迟'
          : hasHoldings
            ? '价格缺失'
            : '价格待补',
      detail: hasDataLineage
        ? lineagePreviewDetail(portfolioLineageSummary.price, language === 'zh' ? '价格状态待补。' : 'Price readiness pending.')
        : hasHoldings
          ? (hasPriceFallback || hasUpdatingPrice
            ? (language === 'zh' ? '价格可能延迟。' : 'Price may be delayed.')
            : (language === 'zh' ? '价格来源待确认。' : 'Price source pending.'))
          : (language === 'zh' ? '首笔持仓后确认价格。' : 'Price readiness appears after positions exist.'),
      variant: hasDataLineage
        ? portfolioLineageSummary.price.variant
        : hasHoldings && (hasPriceFallback || hasUpdatingPrice)
          ? 'caution'
          : hasHoldings
            ? 'danger'
            : 'neutral',
    },
    {
      key: 'valuation-readiness',
      label: hasDataLineage
        ? portfolioLineageSummary.snapshot.label
        : hasHoldings
        ? (hasFxUnavailable ? '估值不可用' : '估值部分可用')
        : '估值不可用',
      value: hasDataLineage
        ? portfolioLineageSummary.snapshot.label
        : hasHoldings && !hasFxUnavailable
        ? valuationSnapshotNote
        : (language === 'zh' ? '估值不可用' : 'Valuation unavailable'),
      detail: hasDataLineage
        ? lineagePreviewDetail(portfolioLineageSummary.snapshot, language === 'zh' ? '估值状态待补。' : 'Valuation readiness pending.')
        : hasHoldings
        ? (hasFxUnavailable
          ? (language === 'zh' ? '汇率缺失，估值暂停。' : 'FX is missing, so valuation is paused.')
          : (language === 'zh' ? '估值完整性待确认。' : 'Valuation completeness is still pending.'))
        : (language === 'zh' ? '首笔持仓后生成估值与盈亏。' : 'Valuation and P&L appear after positions exist.'),
      variant: hasDataLineage ? portfolioLineageSummary.snapshot.variant : hasHoldings && hasFxUnavailable ? 'danger' : hasHoldings ? 'caution' : 'neutral',
    },
    {
      key: 'fx-readiness',
      label: hasDataLineage
        ? portfolioLineageSummary.fx.label
        : hasFxUnavailable || snapshot?.fxStale
        ? (language === 'zh' ? '汇率缺失' : 'FX missing')
        : (language === 'zh' ? '汇率待确认' : 'FX pending'),
      value: hasDataLineage
        ? portfolioLineageSummary.fx.label
        : hasFxUnavailable || snapshot?.fxStale
        ? (language === 'zh' ? '汇率缺失' : 'FX missing')
        : (language === 'zh' ? '汇率待确认' : 'FX pending'),
      detail: hasDataLineage
        ? lineagePreviewDetail(portfolioLineageSummary.fx, language === 'zh' ? 'FX状态待确认。' : 'FX readiness pending.')
        : hasFxUnavailable || snapshot?.fxStale
        ? (language === 'zh' ? '跨币种折算暂不可用。' : 'Cross-currency conversion is unavailable.')
        : (language === 'zh' ? '汇率来源待确认。' : 'FX source pending.'),
      variant: hasDataLineage ? portfolioLineageSummary.fx.variant : hasFxUnavailable || snapshot?.fxStale ? 'danger' : 'caution',
    },
    {
      key: 'risk-readiness',
      label: hasDataLineage
        ? portfolioLineageSummary.analytics.label
        : hasHoldings
        ? (language === 'zh' ? '仅观察' : 'Observation only')
        : (language === 'zh' ? '风险视图待生成' : 'Risk view pending'),
      value: hasDataLineage
        ? portfolioLineageSummary.analytics.label
        : hasHoldings ? (language === 'zh' ? '仅观察' : 'Observation only') : (language === 'zh' ? '风险视图待生成' : 'Risk view pending'),
      detail: hasDataLineage
        ? lineagePreviewDetail(portfolioLineageSummary.analytics, language === 'zh' ? '风险视图待生成。' : 'Risk view pending.')
        : hasHoldings
        ? (language === 'zh' ? '风险读数仅供观察。' : 'Risk readings are observation only.')
        : (language === 'zh' ? '持仓接入后生成暴露与集中度。' : 'Exposure and concentration appear after records exist.'),
      variant: hasDataLineage ? portfolioLineageSummary.analytics.variant : hasHoldings ? 'info' : 'neutral',
    },
  ] satisfies Array<{
    key: string;
    label: string;
    value: string;
    detail: string;
    variant: PortfolioTrustChipItem['variant'];
  }>;
  const filteredSafeRiskWarningLabels = safeRiskWarningLabels.filter((warning) => warning !== riskWarningLabels.no_holdings);
  const holdingsTableStatusLabel = language === 'zh' ? '状态' : 'Status';
  const portfolioResearchStatePreview = (
    <TerminalPanel as="section" data-testid="portfolio-research-state-preview" className="min-w-0 flex flex-col gap-4 border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]">
      <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '组合研究状态' : 'Portfolio research state'}</h2>
          <p className="mt-2 max-w-[72ch] text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
            {hasHoldings
              ? (language === 'zh' ? '当前可先评估持仓、估值、FX与风险暴露。' : 'Current positions, valuation, FX, and risk exposure are ready for first read.')
              : (language === 'zh' ? '首屏先说明可评估什么、缺什么，以及下一步。' : 'The first screen shows what can be evaluated, what is pending, and the next action.')}
          </p>
        </div>
        <TerminalChip variant={hasHoldings ? 'success' : 'neutral'}>{researchStateNextAction}</TerminalChip>
      </div>
      <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-6">
        {researchStatePreviewItems.map((item) => (
          <div key={item.key} className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
            <div className="flex min-w-0 items-center justify-between gap-2">
              <div className="truncate text-[11px] font-semibold uppercase tracking-[0.14em] text-[color:var(--wolfy-text-muted)]">{item.label}</div>
              <TerminalChip variant={item.variant} className="shrink-0">{item.value}</TerminalChip>
            </div>
            <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{item.detail}</p>
          </div>
        ))}
      </div>
      <ol
        data-testid="portfolio-productization-order"
        className="grid min-w-0 grid-cols-1 gap-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)] sm:grid-cols-3"
      >
        {portfolioProductizationOrder.map((item, index) => (
          <li key={item} className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2">
            <span className="mr-2 font-mono text-[10px] font-bold text-[color:var(--wolfy-text-muted)]">{String(index + 1).padStart(2, '0')}</span>
            {item}
          </li>
        ))}
      </ol>
      <div data-testid="portfolio-research-next-evidence" className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
        {valuationNextEvidenceCopy}
      </div>
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-3 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2.5">
        <span className="text-xs font-medium text-[color:var(--wolfy-text-secondary)]">{language === 'zh' ? '下一步' : 'Next action'}</span>
        {canManagePortfolioOperations ? (
        <div className="flex min-w-0 flex-wrap gap-2">
          <TerminalButton
            type="button"
            variant="primary"
            className="h-9 px-3"
            onClick={() => {
              if (!hasAccounts || !hasWritableAccounts) {
                openManualLedger('account');
                return;
              }
              if (hasHoldings && (hasFxUnavailable || snapshot?.fxStale)) {
                openManualLedger('fx');
                return;
              }
              openManualLedger('trade', 'stock');
            }}
          >
            {researchStateNextAction}
          </TerminalButton>
          <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
            {importTradesActionLabel}
          </TerminalButton>
          {stockResearchHandoffPath ? (
            <a
              data-testid="portfolio-stock-research-handoff"
              href={stockResearchHandoffPath}
              className="inline-flex min-h-9 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
            >
              {language === 'zh' ? '进入个股研究' : 'Open Stock Research'}
            </a>
          ) : null}
        </div>
        ) : (
          <div className="flex min-w-0 flex-wrap items-center gap-2">
            <span className="text-xs text-[color:var(--wolfy-text-muted)]">
              {language === 'zh' ? '连接步骤将在具备操作权限后显示。' : 'Connection steps appear when operator access is available.'}
            </span>
            {stockResearchHandoffPath ? (
              <a
                data-testid="portfolio-stock-research-handoff"
                href={stockResearchHandoffPath}
                className="inline-flex min-h-9 items-center rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs font-medium text-[color:var(--wolfy-text-secondary)] transition-colors hover:border-[color:var(--wolfy-divider)] hover:text-[color:var(--wolfy-text-primary)]"
              >
                {language === 'zh' ? '进入个股研究' : 'Open Stock Research'}
              </a>
            ) : null}
          </div>
        )}
      </div>
    </TerminalPanel>
  );

  const handleToggleTradeActionMenu = (id: number) => {
    if (!canManagePortfolioOperations) {
      return;
    }
    setOpenTradeActionMenuId((prev) => (prev === id ? null : id));
  };

  const historyPanelContent = (
    <div className="flex h-full min-h-0 flex-col bg-[var(--surface-1)] lg:bg-transparent">
      <div className="flex items-center justify-between gap-3 border-b border-[color:var(--wolfy-border-subtle)] px-0 pb-4">
        <div>
          <h2 className="text-xs text-muted-text uppercase tracking-widest">{historyDrawerTitle}</h2>
          <p className="mt-2 text-sm text-secondary-text">{copy.pageLabel} {eventPage}</p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            type="button"
            variant="ghost"
            className={PORTFOLIO_ICON_BUTTON_CLASS}
            onClick={() => void loadEvents()}
            aria-label={copy.refreshLedger}
            title={copy.refreshLedger}
          >
            <RefreshCw className="size-4" aria-hidden="true" />
          </Button>
        </div>
      </div>

      <div className="flex-1 min-h-0 overflow-y-auto no-scrollbar [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none] pt-5">
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <PortfolioSegmentedControl
              value={eventType}
              onChange={(next) => {
                setEventType(next as EventType);
                resetHistoryNavigation();
              }}
              options={[
                { value: 'trade', label: copy.tradeLedger },
                { value: 'cash', label: copy.cashLedger },
                { value: 'corporate', label: copy.corporateLedger },
              ]}
              className="sm:w-auto"
              itemClassName="px-3 text-xs uppercase tracking-widest sm:flex-none"
            />
            <div className="flex items-center gap-2 text-xs text-secondary-text">
              <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} disabled={eventPage <= 1} onClick={() => setEventPage((prev) => Math.max(1, prev - 1))}>{copy.prevPage}</Button>
              <span>{copy.pageLabel} {eventPage}</span>
              <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} disabled={!historyHasNextPage} onClick={() => setEventPage((prev) => prev + 1)}>{copy.nextPage}</Button>
            </div>
          </div>

          {eventType === 'trade' ? (
            tradeEvents.length === 0 ? (
              <div className="theme-panel-subtle rounded-xl px-5 py-4 text-sm text-secondary-text">
                {!hasHoldings && hasHistory
                  ? noHoldingsHistoryNote
                  : copy.emptyEventsBody}
              </div>
            ) : (
              tradeEvents.map((item) => (
                <div key={`trade-${item.id}`} className="border-b border-[color:var(--wolfy-border-subtle)] px-1 py-4 transition-colors hover:bg-[var(--wolfy-surface-input)]">
                  <div className="flex items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex flex-wrap items-center gap-2 text-foreground">
                        <span>{item.symbol}</span>
                        <span className="text-xs text-muted-text">{formatSideLabel(item.side, language)}</span>
                        {item.isActive === false ? (
                          <TerminalChip variant="neutral">
                            {voidedTradeLabel}
                          </TerminalChip>
                        ) : null}
                      </div>
                      <div className="mt-1 text-xs text-muted-text">{item.tradeDate} · {item.quantity} @ {item.price}</div>
                    </div>
                    {canManagePortfolioOperations ? (
                      <PortfolioTradeActions
                        item={item}
                        context="history"
                        isNarrowViewport={isNarrowViewport}
                        openTradeActionMenuId={openTradeActionMenuId}
                        voidedTradeLabel={voidedTradeLabel}
                        moreTradeActionsLabel={moreTradeActionsLabel}
                        editTradeActionLabel={editTradeActionLabel}
                        deleteTradeActionLabel={deleteTradeActionLabel}
                        onToggleMenu={handleToggleTradeActionMenu}
                        onEdit={openTradeEditor}
                        onVoid={openTradeVoidDialog}
                      />
                    ) : null}
                  </div>
                </div>
              ))
            )
          ) : null}

          {eventType === 'cash' ? (
            cashEvents.length === 0 ? (
              <div className="theme-panel-subtle rounded-xl px-5 py-4 text-sm text-secondary-text">
                {!hasHoldings && hasHistory
                  ? noHoldingsHistoryNote
                  : copy.emptyEventsBody}
              </div>
            ) : (
              cashEvents.map((item) => (
                <div key={`cash-${item.id}`} className="border-b border-[color:var(--wolfy-border-subtle)] px-1 py-4 transition-colors hover:bg-[var(--wolfy-surface-input)]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-foreground">{formatCashDirectionLabel(item.direction, language)} <span className="text-xs text-muted-text">{item.currency}</span></div>
                      <div className="mt-1 text-xs text-muted-text">{item.eventDate} · {formatMoney(item.amount, item.currency)}</div>
                    </div>
                    {canManagePortfolioOperations ? (
                      <Button type="button" variant="ghost" className={PORTFOLIO_DANGER_GHOST_CLASS} onClick={() => setPendingDelete({ eventType: 'cash', id: item.id, message: copy.cashDeleteMessage(item) })} aria-label={copy.deleteConfirm} title={copy.deleteConfirm}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))
            )
          ) : null}

          {eventType === 'corporate' ? (
            corporateEvents.length === 0 ? (
              <div className="theme-panel-subtle rounded-xl px-5 py-4 text-sm text-secondary-text">
                {!hasHoldings && hasHistory
                  ? noHoldingsHistoryNote
                  : copy.emptyEventsBody}
              </div>
            ) : (
              corporateEvents.map((item) => (
                <div key={`corporate-${item.id}`} className="border-b border-[color:var(--wolfy-border-subtle)] px-1 py-4 transition-colors hover:bg-[var(--wolfy-surface-input)]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatCorporateActionLabel(item.actionType, language)}</span></div>
                      <div className="mt-1 text-xs text-muted-text">
                        {item.effectiveDate}
                        {item.cashDividendPerShare != null ? ` · ${copy.dividendPerShare} ${item.cashDividendPerShare}` : ''}
                        {item.splitRatio != null ? ` · ${copy.splitRatio} ${item.splitRatio}` : ''}
                      </div>
                    </div>
                    {canManagePortfolioOperations ? (
                      <Button type="button" variant="ghost" className={PORTFOLIO_DANGER_GHOST_CLASS} onClick={() => setPendingDelete({ eventType: 'corporate', id: item.id, message: copy.corporateDeleteMessage(item) })} aria-label={copy.deleteConfirm} title={copy.deleteConfirm}>
                        <Trash2 className="size-4" aria-hidden="true" />
                      </Button>
                    ) : null}
                  </div>
                </div>
              ))
            )
          ) : null}
        </div>
      </div>
    </div>
  );

  const recentActivityContent = (
    <TerminalPanel
      as="section"
      data-testid="portfolio-recent-activity"
      className="min-w-0 flex flex-col gap-3"
    >
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-xs uppercase tracking-widest text-muted-text">{recentActivityTitle}</h2>
          {!hasHoldings && hasHistory ? (
            <p className="mt-1 text-xs text-amber-200/80">{noHoldingsHistoryNote}</p>
          ) : null}
        </div>
        {hasHistory && hasSmallHistory ? (
          <Button
            type="button"
            variant="ghost"
            className={PORTFOLIO_TEXT_BUTTON_CLASS}
            onClick={() => setShowEmptyFullHistory((prev) => !prev)}
          >
            {showEmptyFullHistory ? hideFullHistoryLabel : viewFullHistoryLabel}
          </Button>
        ) : hasHistory ? (
          <span className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{viewFullHistoryLabel}</span>
        ) : null}
      </div>
      {hasHistory ? (
        <div className="flex flex-col gap-2">
          {tradeEvents.slice(0, 5).map((item) => (
            <div key={`recent-trade-${item.id}`} className="flex items-start justify-between gap-3 border-b border-[color:var(--wolfy-border-subtle)] px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatSideLabel(item.side, language)}</span></div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.tradeDate} · {item.quantity} @ {item.price}</div>
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <span className="font-mono text-xs text-[color:var(--wolfy-text-muted)]">{item.currency}</span>
                {canManagePortfolioOperations ? (
                  <PortfolioTradeActions
                    item={item}
                    context="recent"
                    isNarrowViewport={isNarrowViewport}
                    openTradeActionMenuId={openTradeActionMenuId}
                    voidedTradeLabel={voidedTradeLabel}
                    moreTradeActionsLabel={moreTradeActionsLabel}
                    editTradeActionLabel={editTradeActionLabel}
                    deleteTradeActionLabel={deleteTradeActionLabel}
                    onToggleMenu={handleToggleTradeActionMenu}
                    onEdit={openTradeEditor}
                    onVoid={openTradeVoidDialog}
                  />
                ) : null}
              </div>
            </div>
          ))}
          {cashEvents.slice(0, Math.max(0, 5 - tradeEvents.length)).map((item) => (
            <div key={`recent-cash-${item.id}`} className="flex items-start justify-between gap-3 border-b border-[color:var(--wolfy-border-subtle)] px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{formatCashDirectionLabel(item.direction, language)}</div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.eventDate} · {formatMoney(item.amount, item.currency)}</div>
              </div>
              <span className="shrink-0 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{item.currency}</span>
            </div>
          ))}
          {corporateEvents.slice(0, Math.max(0, 5 - tradeEvents.length - cashEvents.length)).map((item) => (
            <div key={`recent-corporate-${item.id}`} className="flex items-start justify-between gap-3 border-b border-[color:var(--wolfy-border-subtle)] px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatCorporateActionLabel(item.actionType, language)}</span></div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.effectiveDate}</div>
              </div>
              <span className="shrink-0 font-mono text-xs text-[color:var(--wolfy-text-muted)]">ACT</span>
            </div>
          ))}
        </div>
      ) : (
        <TerminalEmptyState title={emptyRecentActivityLabel} className="min-h-[72px]" />
      )}
    </TerminalPanel>
  );

  return (
    <>
      <div
        ref={surfaceRef}
        data-testid="portfolio-bento-page"
        data-bento-surface="true"
        aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
        aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
        className={getSafariReadySurfaceClassName(
          isSafariReady,
          'w-full flex-1 flex flex-col min-h-0 min-w-0 bg-transparent text-[color:var(--wolfy-text-secondary)]',
        )}
      >
        <ConsumerWorkspaceScope className="flex-1">
        <ConsumerWorkspacePageShell className="flex-1 min-w-0 min-h-0">
          <div
            data-testid="portfolio-workspace-grid"
            className="grid min-w-0 grid-cols-1 items-start gap-4 xl:grid-cols-12"
          >
            {error || riskWarning || writeWarning ? (
              <div data-testid="portfolio-row-alerts" className="order-0 col-span-12 xl:col-span-12 min-w-0 flex flex-col gap-3">
                {error ? <ApiErrorAlert error={error} onDismiss={() => setError(null)} /> : null}
                {riskWarning ? (
                  <div className="rounded-xl border border-[hsl(var(--accent-warning-hsl)/0.35)] bg-[hsl(var(--accent-warning-hsl)/0.1)] px-4 py-3 text-[hsl(var(--accent-warning-hsl))] text-sm">
                    {copy.riskDegraded}: {riskWarning}
                  </div>
                ) : null}
                {writeWarning ? (
                  <div className="rounded-xl border border-[hsl(var(--accent-warning-hsl)/0.35)] bg-[hsl(var(--accent-warning-hsl)/0.1)] px-4 py-3 text-[hsl(var(--accent-warning-hsl))] text-sm">
                    {copy.actionHint}: {writeWarning}
                  </div>
                ) : null}
              </div>
            ) : null}

            <div data-testid="portfolio-row-status" className="order-1 col-span-12 min-w-0">
              <TerminalPanel
                as="section"
                dense
                data-testid="portfolio-account-status-strip"
                className="grid gap-5 xl:grid-cols-[minmax(0,1.6fr)_minmax(360px,1fr)]"
              >
                <div data-testid="portfolio-total-assets-card" className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <h1 className="text-[1.45rem] font-semibold leading-tight tracking-normal text-[color:var(--wolfy-text-primary)] md:text-[1.75rem]">
                      {language === 'zh' ? '持仓与组合暴露' : 'Holdings and portfolio exposure'}
                    </h1>
                    <TerminalChip variant="neutral">
                      {selectedAccount === 'all' ? copy.allAccounts : scopedAccount?.name || copy.allAccounts}
                    </TerminalChip>
                  </div>
                  <h2 className="mt-3 text-[12px] font-medium uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">
                    {totalAssetsTitle}
                  </h2>
                  <div
                    data-testid="portfolio-total-assets-value"
                    className="mt-2 font-mono text-[2.2rem] font-semibold leading-none text-[color:var(--wolfy-text-primary)] tabular-nums md:text-[2.75rem]"
                  >
                    {formatDisplayMoney(totalEquity, totalEquityDisplay, snapshotCurrency)}
                  </div>
                  <p className="mt-3 max-w-[72ch] text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                    {heroConclusion}
                  </p>
                  <div className="mt-4 flex min-w-0 flex-wrap gap-2">
                    {heroStatusChips.map((item) => (
                      <TerminalChip key={item.key} variant={item.variant || 'neutral'}>
                        {item.label}
                      </TerminalChip>
                    ))}
                  </div>
                </div>

                <div data-testid="portfolio-command-strip" className="min-w-0 flex flex-col gap-4">
                  <div className="grid min-w-0 grid-cols-1 gap-3 md:grid-cols-2">
                    <Select
                      label={copy.accountView}
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      value={String(selectedAccount)}
                      onChange={(value) => {
                        const nextAccount = value === 'all' ? 'all' : Number(value);
                        setSelectedAccount(nextAccount);
                        resetHistoryNavigation();
                        invalidateFxRefreshScope(nextAccount, costMethod);
                      }}
                      options={[
                        { value: 'all', label: copy.allAccounts },
                        ...activeAccounts.map((account) => ({ value: String(account.id), label: formatConsumerAccountLabel(account.name, language) })),
                      ]}
                      className={PORTFOLIO_SELECT_CLASS}
                      controlClassName="rounded-lg"
                    />
                    <Select
                      data-testid="portfolio-display-currency-select"
                      label={copy.reportingCurrency}
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      value={displayCurrency}
                      onChange={(value) => setDisplayCurrency(normalizePortfolioDisplayCurrency(value))}
                      options={PORTFOLIO_DISPLAY_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                      className={PORTFOLIO_SELECT_CLASS}
                      controlClassName="rounded-lg"
                    />
                  </div>

                  <div className="rounded-[14px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-4 py-3">
                    <div className="grid grid-cols-2 gap-3 text-xs text-[color:var(--wolfy-text-muted)]">
                      <div>
                        <div className="uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '账户范围' : 'Scope'}</div>
                        <div className="mt-1 text-sm text-[color:var(--wolfy-text-secondary)]">{accountStateSummary}</div>
                      </div>
                      <div>
                        <div className="uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '当前状态' : 'State'}</div>
                        <div className="mt-1 text-sm text-[color:var(--wolfy-text-secondary)]">{holdingsPrimaryValue}</div>
                      </div>
                    </div>
                  </div>

                  {showHeaderPortfolioActions ? (
                    <div className="flex min-w-0 flex-wrap gap-2">
                      <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={() => openManualLedger('trade', 'stock')}>
                        {addHoldingActionLabel}
                      </TerminalButton>
                      <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                        {importTradesActionLabel}
                      </TerminalButton>
                      <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                        {syncDataActionLabel}
                      </TerminalButton>
                    </div>
                  ) : null}
                </div>
              </TerminalPanel>
            </div>

            <div data-testid="portfolio-row-summary" className="order-2 col-span-12 min-w-0">
              {hasHoldings ? (
                <div data-testid="portfolio-summary-strip" className="flex min-w-0 flex-col gap-3">
                  <div data-testid="portfolio-summary-core-row" className="grid min-w-0 grid-cols-1 gap-3 xl:grid-cols-[minmax(0,1.05fr)_minmax(0,0.95fr)]">
                    <TerminalPanel as="section" data-testid="portfolio-summary-market-value-card" className="min-w-0 border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{copy.totalMarketValue}</div>
                      <div
                        data-testid="portfolio-summary-market-value"
                        className="mt-2 break-words font-mono text-[1.75rem] font-semibold leading-none text-[color:var(--wolfy-text-primary)] tabular-nums md:text-[2.1rem]"
                      >
                        {formatDisplayMoney(totalMarketValue, totalMarketValueDisplay, snapshotCurrency)}
                      </div>
                      <div className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{holdingsHeaderNote}</div>
                    </TerminalPanel>
                    <TerminalPanel as="section" data-testid="portfolio-pnl-summary" className="min-w-0 border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]">
                      <div data-testid="portfolio-pnl-total" className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{pnlLabels.total}</div>
                      <div
                        data-testid="portfolio-summary-pnl-value"
                        className={`mt-2 break-words font-mono text-[1.75rem] font-semibold leading-none tabular-nums md:text-[2.1rem] ${totalPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}
                      >
                        {totalPnlDisplay ? formatSignedMoney(totalPnlDisplay.value, displayCurrency) : formatSignedMoney(totalPnl, pnlSourceCurrency)}
                      </div>
                      <div className="mt-3 grid min-w-0 grid-cols-1 gap-1.5 text-xs text-[color:var(--wolfy-text-muted)] sm:grid-cols-2">
                        <span data-testid="portfolio-pnl-realized" className="min-w-0 break-words">{pnlLabels.realized} {realizedPnlDisplay ? formatSignedMoney(realizedPnlDisplay.value, displayCurrency) : formatSignedMoney(realizedPnl, pnlSourceCurrency)}</span>
                        <span data-testid="portfolio-pnl-unrealized" className="min-w-0 break-words">{pnlLabels.unrealized} {unrealizedPnlDisplay ? formatSignedMoney(unrealizedPnlDisplay.value, displayCurrency) : formatSignedMoney(unrealizedPnl, pnlSourceCurrency)}</span>
                      </div>
                    </TerminalPanel>
                  </div>

                  <div data-testid="portfolio-summary-aux-row" className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-4">
                    <TerminalPanel as="section" dense data-testid="portfolio-summary-cash-card" className="min-w-0">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{copy.totalCash}</div>
                      <div data-testid="portfolio-summary-cash-value" className="mt-1.5 break-words font-mono text-base font-medium text-[color:var(--wolfy-text-primary)] tabular-nums">{formatDisplayMoney(totalCash, totalCashDisplay, snapshotCurrency)}</div>
                      <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '可用于继续配置或缓冲波动。' : 'Available for new allocation or downside buffer.'}</div>
                    </TerminalPanel>
                    <TerminalPanel as="section" dense data-testid="portfolio-summary-holdings-card" className="min-w-0">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '持仓' : 'Holdings'}</div>
                      <div className="mt-1.5 break-words font-mono text-base font-medium text-[color:var(--wolfy-text-primary)] tabular-nums">{holdingsPrimaryValue}</div>
                      <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{accountStateSummary}</div>
                    </TerminalPanel>
                    <TerminalPanel as="section" dense data-testid="portfolio-summary-risk-card" className="min-w-0">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '风险状态' : 'Risk state'}</div>
                      <div className={`mt-1.5 break-words text-base font-semibold ${concentrationToneClass}`}>{concentrationLabel}</div>
                      <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                        {`${language === 'zh' ? '最大持仓' : 'Largest'} ${formatPercent(topPositionPercent)}`}
                      </div>
                    </TerminalPanel>
                    <TerminalPanel as="section" dense data-testid="portfolio-summary-status-card" className="min-w-0">
                      <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '状态快照' : 'Status snapshot'}</div>
                      <div className="mt-1.5 break-words text-sm font-medium text-[color:var(--wolfy-text-secondary)]">{valuationSnapshotNote}</div>
                      <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{heroStatusChips.map((item) => item.label).join(' · ')}</div>
                    </TerminalPanel>
                  </div>
                  {portfolioResearchStatePreview}
                </div>
              ) : (
                <div data-testid="portfolio-empty-onboarding-row" className="grid min-w-0 grid-cols-1 gap-4 xl:grid-cols-[minmax(0,1.2fr)_minmax(340px,0.8fr)]">
                  <TerminalPanel as="section" data-testid="portfolio-empty-workflow-column" className="min-w-0 flex flex-col gap-4 border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]">
                    <ConsumerOnboardingCtaPanel
                      data-testid="portfolio-empty-onboarding-cta"
                      language={language}
                      title={language === 'zh' ? '先完成研究上下文，只有需要组合跟踪时再创建账户' : 'Build research context first; create an account only when portfolio tracking is intentional'}
                      actions={[
                        {
                          route: '/market-overview',
                          description: language === 'zh'
                            ? '研究记录'
                            : 'Research record',
                        },
                        {
                          route: '/scanner',
                          description: language === 'zh'
                            ? '需要候选集合时，由你手动运行扫描。'
                            : 'Run scanner only when you want a candidate set.',
                        },
                        {
                          route: '/watchlist',
                          description: language === 'zh'
                            ? '先保存你明确想持续观察的代码。'
                            : 'Save only symbols you intentionally want to keep observing.',
                        },
                        {
                          route: '/research/radar',
                          description: language === 'zh'
                            ? '扫描或观察列表有活动后，再查看研究队列。'
                            : 'Review the queue after scanner or watchlist activity.',
                        },
                        {
                          route: '/portfolio',
                          description: language === 'zh'
                            ? '只有明确想记录持仓、现金与组合表现时才创建账户。'
                            : 'Create an account only when you want to track holdings, cash, and portfolio performance.',
                        },
                      ]}
                      starterResearchWorkflow={language === 'zh'
                        ? ['打开市场概览。', '运行 Scanner 或选择观察标的。', '有研究活动后查看研究雷达。', '需要组合跟踪时再创建账户。']
                        : ['Open Market Overview.', 'Run Scanner or choose a watchlist symbol.', 'Review Research Radar after activity.', 'Create an account only when tracking a portfolio.']}
                      firstRunChecklist={language === 'zh'
                        ? ['不会自动创建账户。', '不会生成示例持仓。', '不会改写持仓、现金或外部同步状态。']
                        : ['No account is created automatically.', 'No sample holdings are generated.', 'Holdings, cash, and external sync stay unchanged.']}
                    />
                    <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
                      <div className="min-w-0">
                        <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '首次配置路径' : 'First-use setup path'}</h2>
                        <p className="mt-2 text-base font-medium text-[color:var(--wolfy-text-primary)]">{onboardingTitle}</p>
                        <p className="mt-2 max-w-[68ch] text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">{onboardingBody}</p>
                      </div>
                      <TerminalChip variant="neutral">{language === 'zh' ? '真实数据接入前不生成示例收益' : 'No sample performance before real data is saved'}</TerminalChip>
                    </div>
                    <TerminalEmptyState
                      data-testid="portfolio-start-card"
                      title={language === 'zh' ? '创建或导入首个组合' : 'Create or import the first portfolio'}
                      action={hasHistory ? <TerminalChip variant="caution" className="shrink-0">{noHoldingsHistoryNote}</TerminalChip> : undefined}
                      className="min-h-[72px]"
                    >
                      {compactNoHoldingText}
                    </TerminalEmptyState>
                    <div className="grid min-w-0 grid-cols-1 gap-2 sm:grid-cols-3">
                      {onboardingSteps.map((step, index) => (
                        <div key={step.key} className="min-w-0 rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-4 py-3">
                          <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? `步骤 ${index + 1}` : `Step ${index + 1}`}</div>
                          <div className="mt-2 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{step.label}</div>
                          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{step.detail}</p>
                        </div>
                      ))}
                    </div>
                    {canManagePortfolioOperations ? (
                    <div data-testid="portfolio-empty-actions" className="flex min-w-0 flex-wrap gap-2">
                      <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={onboardingPrimaryAction}>
                        {onboardingPrimaryActionLabel}
                      </TerminalButton>
                      <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                        {importTradesActionLabel}
                      </TerminalButton>
                    </div>
                    ) : null}
                    <p data-testid="portfolio-empty-help" className="text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                      {portfolioEmptyHelpText}
                    </p>
                    {!hasWritableAccounts ? (
                      <TerminalNotice variant="caution">
                        {hasActiveAccounts
                          ? (language === 'zh' ? '当前账户不可写，请先进入账户页调整可写账户，再继续添加持仓或导入。' : 'Current accounts are not writable. Open the account lane first, then continue with holdings or import.')
                          : (language === 'zh' ? '暂无可写账户，请先创建账户。' : 'No writable account yet. Create an account first.')}
                      </TerminalNotice>
                    ) : null}
                  </TerminalPanel>

                  {portfolioResearchStatePreview}
                </div>
              )}
            </div>

            <div data-testid="portfolio-row-routing" className="order-3 col-span-12 min-w-0 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(340px,5fr)] 2xl:gap-5 items-start">
              <div data-testid="portfolio-primary-lane" className="min-w-0 flex flex-col gap-4">
                <TerminalPanel
                  as="section"
                  data-testid="portfolio-current-holdings-panel"
                  className="min-w-0 flex flex-col overflow-hidden"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-[color:var(--wolfy-border-subtle)] pb-4">
                    <div className="min-w-0">
                      <h2 className="min-w-0 text-xs uppercase tracking-widest text-muted-text">
                        {hasHoldings
                          ? (language === 'zh' ? `当前持仓（共 ${positionRows.length} 项）` : `Current Holdings (${positionRows.length})`)
                          : (language === 'zh' ? '当前持仓' : 'Current holdings')}
                      </h2>
                      <p className="mt-2 text-sm text-[color:var(--wolfy-text-muted)]">{holdingsHeaderNote}</p>
                    </div>
                    <div className="shrink-0 text-right text-xs text-[color:var(--wolfy-text-muted)]">
                      <div>{language === 'zh' ? '价格快照' : 'Pricing snapshot'}</div>
                      <div className="mt-1 text-[color:var(--wolfy-text-secondary)]">{valuationSnapshotNote}</div>
                    </div>
                  </div>

                  <div className="pt-3 lg:max-h-[560px] lg:min-h-0 lg:overflow-y-auto lg:no-scrollbar lg:[&::-webkit-scrollbar]:hidden lg:[-ms-overflow-style:none] lg:[scrollbar-width:none]">
                    {hasHoldings ? (
                        <>
                          <div data-testid="portfolio-holdings-mobile-list" className="grid gap-2 lg:hidden">
                            {positionRows.map((row) => {
                              const rowTrustItems = buildHoldingTrustItems(row);
                              return (
                                <article
                                  key={`${row.accountId}-${row.symbol}-${row.market}-mobile`}
                                  data-testid={`portfolio-holding-mobile-card-${row.symbol}`}
                                  className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3"
                                >
                                  <div className="flex min-w-0 items-start justify-between gap-3">
                                    <div className="min-w-0">
                                      <p className="font-mono text-base font-semibold text-[color:var(--wolfy-text-primary)]">{row.symbol}</p>
                                      <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                                        {row.accountName}
                                        {' · '}
                                        {translate(language, 'portfolio.positionContext', {
                                          market: formatAccountMarketLabel(row.market, language),
                                          currency: row.currency || '--',
                                        })}
                                      </p>
                                    </div>
                                    <div className={`shrink-0 text-right font-mono text-sm ${row.unrealizedPnlBase >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                      {formatSignedMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                                      <div className="mt-1 text-xs text-[color:var(--wolfy-text-secondary)]">{formatPercent(row.unrealizedPnlPct)}</div>
                                    </div>
                                  </div>
                                  <div className="mt-3 grid min-w-0 grid-cols-2 gap-2">
                                    <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2">
                                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '数量' : 'Qty'}</p>
                                      <p className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-secondary)]">{Number(row.quantity || 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}</p>
                                    </div>
                                    <div className="min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2">
                                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '成本' : 'Cost'}</p>
                                      <p className="mt-1 font-mono text-sm text-[color:var(--wolfy-text-secondary)]">{formatMoney(row.totalCost, row.currency)}</p>
                                    </div>
                                    <div className="col-span-2 min-w-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-2.5 py-2">
                                      <p className="text-[10px] font-semibold uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '市值' : 'Market Value'}</p>
                                      <p className="mt-1 break-words font-mono text-sm text-[color:var(--wolfy-text-secondary)]">{formatMoney(row.marketValueBase, row.valuationCurrency)}</p>
                                      {row.valuationCurrency !== displayCurrency ? (
                                        <p className="mt-1 break-words text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{formatConvertedDisplay(row.marketValueBase, row.valuationCurrency)}</p>
                                      ) : null}
                                      <p className={`mt-1 text-xs leading-5 ${row.isPriceFallback ? 'text-amber-300' : 'text-[color:var(--wolfy-text-secondary)]'}`}>
                                        {row.priceAsOf
                                          ? `${formatMoney(row.lastPrice, row.currency)} · ${language === 'zh' ? `截至 ${row.priceAsOf}` : `As of ${row.priceAsOf}`}`
                                          : `${formatMoney(row.lastPrice, row.currency)} · ${positionPriceFreshnessExplanation(row, language)}`}
                                      </p>
                                    </div>
                                  </div>
                                  {rowTrustItems.length ? (
                                    <PortfolioTrustStrip
                                      items={rowTrustItems}
                                      className="mt-3 border-0 bg-transparent p-0"
                                      chipsClassName="gap-1.5"
                                      data-testid={`portfolio-holding-mobile-trust-${row.symbol}`}
                                    />
                                  ) : null}
                                  {canManagePortfolioOperations ? (
                                    <Button
                                      type="button"
                                      variant="ghost"
                                      className="mt-3 min-h-10 w-full rounded-md border border-[color:var(--wolfy-border-subtle)] bg-transparent px-3 py-2 text-sm text-[color:var(--wolfy-text-secondary)] transition-colors hover:text-[color:var(--wolfy-text-primary)] disabled:text-[color:var(--wolfy-text-muted)] disabled:opacity-50"
                                      onClick={() => openManualLedger('trade', 'stock')}
                                    >
                                      {manualLedgerActionLabel}
                                    </Button>
                                  ) : null}
                                </article>
                              );
                            })}
	                          </div>
		                          <TerminalDenseTable className="hidden border-0 bg-transparent lg:block">
	                            <table className="min-w-[760px] w-full text-left text-xs">
	                              <caption className="sr-only">
	                                {language === 'zh' ? '持仓研究账本' : 'Holdings research ledger'}
	                              </caption>
	                              <thead className="text-[color:var(--wolfy-text-muted)]">
                                <tr className="border-b border-[color:var(--wolfy-border-subtle)]">
                              {[
                                language === 'zh' ? '标的' : 'Symbol',
                                language === 'zh' ? '数量' : 'Qty',
                                language === 'zh' ? '成本' : 'Cost',
                                language === 'zh' ? '市值' : 'Market Value',
                                language === 'zh' ? '盈亏' : 'P&L',
                                holdingsTableStatusLabel,
                                ...(canManagePortfolioOperations ? [language === 'zh' ? '操作' : 'Action'] : []),
                              ].map((label) => (
                                <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {positionRows.map((row) => {
                              const rowTrustItems = buildHoldingTrustItems(row);
                              return (
                                <tr key={`${row.accountId}-${row.symbol}-${row.market}`} className="border-b border-[color:var(--wolfy-border-subtle)] text-[color:var(--wolfy-text-secondary)] transition-colors hover:bg-[var(--wolfy-surface-input)]">
                                  <td className="px-3 py-2">
                                    <div className="truncate font-mono text-sm text-[color:var(--wolfy-text-primary)]">{row.symbol}</div>
                                    <div className="truncate text-[11px] text-[color:var(--wolfy-text-muted)]">
                                      {row.accountName}
                                      {' · '}
                                      {translate(language, 'portfolio.positionContext', {
                                        market: formatAccountMarketLabel(row.market, language),
                                        currency: row.currency || '--',
                                      })}
                                    </div>
                                  </td>
                                  <td className="px-3 py-2 font-mono">{Number(row.quantity || 0).toLocaleString(undefined, { maximumFractionDigits: 4 })}</td>
                                  <td className="px-3 py-2 font-mono">{formatMoney(row.totalCost, row.currency)}</td>
                                  <td className="px-3 py-2 font-mono">
                                    {formatMoney(row.marketValueBase, row.valuationCurrency)}
                                    {row.valuationCurrency !== displayCurrency ? <div className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">{formatConvertedDisplay(row.marketValueBase, row.valuationCurrency)}</div> : null}
                                    <div className={`mt-1 text-[11px] ${row.isPriceFallback ? 'text-amber-300' : 'text-[color:var(--wolfy-text-muted)]'}`}>
                                      {row.priceAsOf
                                        ? `${formatMoney(row.lastPrice, row.currency)} · ${language === 'zh' ? `截至 ${row.priceAsOf}` : `As of ${row.priceAsOf}`}`
                                        : `${formatMoney(row.lastPrice, row.currency)} · ${positionPriceFreshnessExplanation(row, language)}`}
                                    </div>
                                  </td>
                                  <td className={`px-3 py-2 font-mono ${row.unrealizedPnlBase >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {formatSignedMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                                    <div className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">{formatPercent(row.unrealizedPnlPct)}</div>
                                  </td>
                                  <td className="px-3 py-2">
                                    {rowTrustItems.length ? (
                                      <PortfolioTrustStrip
                                        items={rowTrustItems}
                                        className="border-0 bg-transparent p-0"
                                        chipsClassName="gap-1"
                                        data-testid={`portfolio-holding-trust-${row.symbol}`}
                                      />
                                    ) : (
                                      <span className="text-[color:var(--wolfy-text-muted)]">--</span>
                                    )}
                                  </td>
                                  {canManagePortfolioOperations ? (
                                    <td className="px-3 py-2">
                                      <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} onClick={() => openManualLedger('trade', 'stock')}>
                                        {manualLedgerActionLabel}
                                      </Button>
                                    </td>
                                  ) : null}
                                </tr>
                              );
                            })}
                              </tbody>
                            </table>
                          </TerminalDenseTable>
                        </>
                    ) : (
                      <div data-testid="portfolio-empty-ledger-preview" className="min-w-0">
                        <TerminalEmptyState
                          title={language === 'zh' ? '持仓台账将在这里显示' : 'Holdings ledger appears here'}
                          action={hasHistory ? <TerminalChip variant="caution" className="shrink-0">{noHoldingsHistoryNote}</TerminalChip> : undefined}
                          className="min-h-[72px]"
                        >
                          {portfolioEmptyStateGuidance}
                        </TerminalEmptyState>
                        <p data-testid="portfolio-empty-help" className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                          {language === 'zh'
                            ? '完成首笔持仓或导入后，这里会展示真实数量、估值、价格快照与数据状态。'
                            : 'After the first holding or import is saved, this area shows real quantity, valuation, pricing snapshot, and data state.'}
                        </p>
                      </div>
                    )}
                  </div>
                </TerminalPanel>
              </div>

              <div data-testid="portfolio-secondary-lane" className="min-w-0 flex flex-col gap-4">
                <TerminalPanel as="section" data-testid="portfolio-risk-card" className="min-w-0 flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{riskTitle}</h2>
                      <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">
                        {hasHoldings
                          ? (language === 'zh' ? '先看集中度，再看币种与市场暴露。' : 'Start with concentration, then review currency and market exposure.')
                          : (language === 'zh' ? '暂无持仓，风险画像将在持仓出现后自动生成。' : 'Risk profile appears automatically once holdings exist.')}
                      </p>
                    </div>
                    <span data-testid="portfolio-concentration-label">
                      <PillBadge
                        variant={topPositionPercent >= 50 ? 'danger' : topPositionPercent >= 20 ? 'warning' : hasHoldings ? 'success' : 'default'}
                        className={hasHoldings ? concentrationToneClass : 'text-[color:var(--wolfy-text-muted)]'}
                      >
                        {concentrationLabel}
                      </PillBadge>
                    </span>
                  </div>
                  {hasHoldings ? (
                    <>
                      <div data-testid="portfolio-risk-overview" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '最大持仓' : 'Largest Position'}</div>
                          <div className="mt-2 truncate text-sm text-[color:var(--wolfy-text-primary)]">{topPosition?.label || '--'}</div>
                          <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{formatPercent(topPosition?.percent)}</div>
                        </div>
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '主币种' : 'Primary Currency'}</div>
                          <div className="mt-2 truncate text-sm text-[color:var(--wolfy-text-primary)]">{topCurrency?.label || '--'}</div>
                          <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{formatPercent(topCurrency?.percent)}</div>
                        </div>
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '主市场' : 'Primary Market'}</div>
                          <div className="mt-2 truncate text-sm text-[color:var(--wolfy-text-primary)]">{formatExposureMarketLabel(topMarket, language)}</div>
                          <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{formatPercent(topMarket?.percent)}</div>
                        </div>
                      </div>
                      <div data-testid="portfolio-concentration-drilldown" className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '持仓集中度' : 'Concentration'}</div>
                          <div className={`font-mono text-xs ${concentrationToneClass}`}>{formatPercent(topPosition?.percent)}</div>
                        </div>
                        <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{concentrationDescription}</p>
                      </div>
                      <div data-testid="portfolio-risk-hints" className="flex flex-wrap gap-1.5">
                        {(riskHintTexts.length ? riskHintTexts : [language === 'zh' ? '暂无显著集中风险' : 'No notable concentration risk']).map((hint) => (
                          <PillBadge key={hint} variant="default" className="text-[color:var(--wolfy-text-secondary)]">{hint}</PillBadge>
                        ))}
                        {filteredSafeRiskWarningLabels.map((warning) => (
                          <PillBadge key={warning} variant="warning" className="text-[color:var(--wolfy-text-secondary)]">{warning}</PillBadge>
                        ))}
                      </div>
                    </>
                  ) : (
                    <>
                      <div data-testid="portfolio-risk-overview" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                        {emptyRiskPreviewItems.map((item) => (
                          <div key={item.key} className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                            <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{item.label}</div>
                            <div className="mt-2 text-sm font-medium text-[color:var(--wolfy-text-primary)]">{language === 'zh' ? '等待首笔持仓' : 'Awaiting first holding'}</div>
                            <div className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{item.detail}</div>
                          </div>
                        ))}
                      </div>
                      <div data-testid="portfolio-concentration-drilldown" className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '风险工作区说明' : 'Risk workspace note'}</div>
                        <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{concentrationDescription}</p>
                      </div>
                      <div data-testid="portfolio-risk-hints" className="flex flex-wrap gap-1.5">
                        <PillBadge variant="default" className="text-[color:var(--wolfy-text-secondary)]">{language === 'zh' ? '首笔持仓后自动生成' : 'Generated after the first holding'}</PillBadge>
                        {hasHistory ? <PillBadge variant="warning" className="text-[color:var(--wolfy-text-secondary)]">{noHoldingsHistoryNote}</PillBadge> : null}
                      </div>
                    </>
                  )}
                  <TerminalDisclosure
                    title={exposureSummaryTitle}
                    summary={exposureSummaryDisclosureSummary}
                    data-testid="portfolio-risk-exposure-summary"
                    className="border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]"
                  >
                    <div data-testid="portfolio-risk-exposure-summary-body" className="flex flex-col gap-3">
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        {exposureSummaryRows.map((item) => (
                          <div key={item.key} className="min-w-0 rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                            <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{item.label}</div>
                            <div className="mt-2 truncate text-sm font-medium text-[color:var(--wolfy-text-primary)]">{item.value}</div>
                            <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{item.detail}</div>
                          </div>
                        ))}
                      </div>
                      <p className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                        {exposureSummaryBasisNote}
                      </p>
                      {exposureSummaryTrustItems.length ? (
                        <PortfolioTrustStrip
                          title={language === 'zh' ? '数据状态' : 'Data posture'}
                          items={exposureSummaryTrustItems}
                          data-testid="portfolio-risk-exposure-trust-strip"
                        />
                      ) : null}
                    </div>
                  </TerminalDisclosure>
                  <PortfolioRiskExposureReadinessPanel
                    readiness={snapshot?.riskExposureReadiness}
                    language={language}
                  />
                  <PortfolioExposureResearchContextPanel
                    context={snapshot?.exposureResearchContext}
                    lineageSummary={portfolioLineageSummary}
                    language={language}
                  />
                  {hasHoldings ? (
                    <PortfolioScenarioRiskPanel
                      snapshotAsOf={snapshot?.asOf}
                      positions={scenarioRiskPositions}
                      onRunScenario={(payload) => portfolioApi.projectScenarioRisk(payload)}
                    />
                  ) : (
                    <TerminalNotice variant="neutral">
                      {language === 'zh'
                        ? '压力情景入口会在持仓出现后启用，并只基于真实可见持仓做观察性估算。'
                        : 'Scenario entry becomes available after holdings exist and only runs observational estimates on visible real positions.'}
                    </TerminalNotice>
                  )}
                </TerminalPanel>

                <TerminalPanel as="section" data-testid="portfolio-structure-review-panel" className="min-w-0 flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '组合结构审查' : 'Portfolio structure review'}</h2>
                      <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">{structureReviewIntro}</p>
                    </div>
                    <div className="flex flex-wrap gap-1.5">
                      {structureReview ? (
                        <>
                          <TerminalChip variant={structureReviewChipVariant(structureReview?.dataQuality.status)}>{structureReviewStatusText}</TerminalChip>
                          <TerminalChip variant={structureReviewChipVariant(structureReview?.dataQuality.structureEvidenceStatus ?? structureReview?.dataQuality.status)}>{structureReviewEvidenceText}</TerminalChip>
                          <TerminalChip variant="info">{structureReviewContextLabel}</TerminalChip>
                        </>
                      ) : null}
                    </div>
                  </div>

                  {structureReview ? (
                    <>
                      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '主题 / 行业暴露' : 'Theme / sector exposure'}</div>
                          <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{structureReviewExposure?.label || '--'}</div>
                          <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{formatPercent(structureReviewExposure?.percent)}</div>
                        </div>
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '最大持仓线索' : 'Largest holding cue'}</div>
                          <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{structureReviewLargestHolding?.ticker || '--'}</div>
                          <div className="mt-1 font-mono text-xs text-[color:var(--wolfy-text-muted)]">{formatPercent(structureReviewLargestHolding?.percent)}</div>
                        </div>
                      </div>

                      {structureReviewStateEntries.length ? (
                        <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '结构状态分布' : 'Structure states'}</div>
                          <div className="mt-2 flex flex-wrap gap-1.5">
                            {structureReviewStateEntries.map(([state, count]) => (
                              <TerminalChip key={`${state}-${count}`} variant={structureReviewChipVariant(state)}>
                                {state} · {count}
                              </TerminalChip>
                            ))}
                          </div>
                        </div>
                      ) : null}

                      <div className="space-y-2">
                        {structureReviewHoldings.slice(0, 4).map((holding) => {
                          const detailRoute = structureReviewDetailRoute(structureReview, holding.ticker);
                          const detailPath = detailRoute ? localize(detailRoute) : null;
                          const primaryGap = sanitizeStructureReviewMessage(
                            holding.researchNotes.needsMoreEvidence[0]
                              || holding.missingEvidence[0]?.message
                              || holding.riskFlags[0],
                            language,
                          )
                            || '--';

                          return (
                            <div key={`${holding.ticker}-${holding.structureState}`} className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                              <div className="flex flex-wrap items-start justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="font-mono text-sm text-[color:var(--wolfy-text-primary)]">{holding.ticker}</div>
                                  <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">{holding.structureState} · {holding.confidence}</div>
                                </div>
                                {detailPath ? (
                                  <a
                                    href={detailPath}
                                    className="text-xs text-[color:var(--wolfy-accent)] transition-colors hover:text-[color:var(--wolfy-text-primary)]"
                                  >
                                    {structureReviewDetailLabel}
                                  </a>
                                ) : null}
                              </div>
                              <div className="mt-2 flex flex-wrap gap-1.5">
                                <TerminalChip variant={structureReviewChipVariant(holding.evidenceQuality.status)}>{structureReviewDataStatusLabel(holding.evidenceQuality.status, language)}</TerminalChip>
                                <TerminalChip variant={structureReviewChipVariant(holding.structureState)}>{holding.structureState}</TerminalChip>
                              </div>
                              <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{primaryGap}</p>
                            </div>
                          );
                        })}
                      </div>

                      <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '证据缺口' : 'Evidence gaps'}</div>
                        {structureReviewGapMessages.length ? (
                          <ul className="mt-2 space-y-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                            {structureReviewGapMessages.map((message) => (
                              <li key={message}>{message}</li>
                            ))}
                          </ul>
                        ) : (
                          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">
                            {language === 'zh' ? '当前未返回额外证据缺口。' : 'No additional evidence gaps are returned right now.'}
                          </p>
                        )}
                      </div>
                    </>
                  ) : hasHoldings ? (
                    <TerminalEmptyState title={structureReviewUnavailableTitle}>
                      {structureReviewUnavailableBody}
                    </TerminalEmptyState>
                  ) : (
                    <TerminalEmptyState title={structureReviewEmptyTitle}>
                      {structureReviewEmptyBody}
                    </TerminalEmptyState>
                  )}
                </TerminalPanel>

                <TerminalPanel as="section" data-testid="portfolio-valuation-panel" className="min-w-0 flex flex-col gap-4">
                  <div>
                    <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '估值与新鲜度' : 'Valuation freshness'}</h2>
                    <p className="mt-1 text-sm text-[color:var(--wolfy-text-muted)]">
                      {hasFreshValuationState
                        ? (language === 'zh' ? '当前估值可直接用于观察组合表现。' : 'Current valuation is ready for portfolio observation.')
                        : consumerDataNotice || (language === 'zh' ? '部分估值信息仍在确认，请结合下方数据说明阅读。' : 'Some valuation details are still being confirmed. Review the notes below for context.')}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '价格快照' : 'Pricing snapshot'}</div>
                      <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{valuationSnapshotNote}</div>
                    </div>
                    <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '汇率更新时间' : 'FX updated'}</div>
                      <div className="mt-2 text-sm text-[color:var(--wolfy-text-primary)]">{hasFxUnavailable ? fxUnavailableLabel : fxLastUpdated}</div>
                    </div>
                  </div>
                  <div data-testid="portfolio-valuation-next-evidence" className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                    {valuationNextEvidenceCopy}
                  </div>
                  {valuationTrustItems.length ? (
                    <PortfolioTrustStrip
                      title={language === 'zh' ? '估值状态' : 'Valuation state'}
                      items={valuationTrustItems.slice(0, 3)}
                      data-testid="portfolio-valuation-trust-strip"
                    />
                  ) : null}
                  {hasHoldings ? (
                    <div data-testid="portfolio-valuation-evidence-pack" className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3">
                      <div className="flex flex-wrap items-start justify-between gap-3">
                        <div className="min-w-0">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
                            {language === 'zh' ? '估值证据包' : 'Valuation evidence pack'}
                          </div>
                          <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                            {portfolioValuationEvidencePack
                              ? (language === 'zh'
                                ? 'JSON 仅包含当前页面已展示或可安全派生的估值、价格与汇率证据。'
                                : 'JSON includes only valuation, price, and FX evidence already visible or safely derived on this page.')
                              : (language === 'zh'
                                ? '估值证据包暂不可导出：估值不可用或仍待补证。'
                                : 'Valuation evidence pack cannot be exported yet: valuation is unavailable or pending evidence.')}
                          </p>
                        </div>
                        {portfolioValuationEvidencePack ? (
                          <div className="flex shrink-0 flex-wrap gap-2">
                            <TerminalButton type="button" variant="secondary" className="h-9 px-3" onClick={handleCopyValuationEvidence}>
                              <Copy className="size-3.5" aria-hidden="true" />
                              {language === 'zh' ? '复制估值证据包' : 'Copy valuation evidence'}
                            </TerminalButton>
                            <TerminalButton type="button" variant="secondary" className="h-9 px-3" onClick={handleDownloadValuationEvidence}>
                              <Download className="size-3.5" aria-hidden="true" />
                              {language === 'zh' ? '导出估值证据包' : 'Export valuation evidence'}
                            </TerminalButton>
                          </div>
                        ) : (
                          <TerminalChip variant="caution">{language === 'zh' ? '待补证' : 'Evidence pending'}</TerminalChip>
                        )}
                      </div>
                      {valuationEvidenceFeedback ? (
                        <div className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">{valuationEvidenceFeedback}</div>
                      ) : null}
                    </div>
                  ) : null}
                </TerminalPanel>

                <TerminalPanel as="section" data-testid="portfolio-next-action-panel" className="min-w-0 flex flex-col gap-4">
                  <div>
                    <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-[color:var(--wolfy-text-muted)]">{language === 'zh' ? '下一步' : 'Next action'}</h2>
                    <p className="mt-1 text-sm text-[color:var(--wolfy-text-primary)]">{nextActionHeadline}</p>
                    <p className="mt-2 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{nextActionBody}</p>
                  </div>
                  {canManagePortfolioOperations ? (
                  <div className="flex flex-wrap gap-2">
                    {!hasAccounts ? (
                      <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={() => openManualLedger('account')}>
                        {copy.createAccount}
                      </TerminalButton>
                    ) : (
                      <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={() => openManualLedger('trade', 'stock')}>
                        {addHoldingActionLabel}
                      </TerminalButton>
                    )}
                    <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('trade')}>
                      {manualLedgerActionLabel}
                    </TerminalButton>
                    <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                      {syncDataActionLabel}
                    </TerminalButton>
                  </div>
                  ) : null}
                  <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-xs text-[color:var(--wolfy-text-muted)]">
                    {hasHistory
                      ? (language === 'zh' ? `近期已记录 ${totalHistoryRows} 条活动，可在下方时间线继续核对。` : `${totalHistoryRows} recent records are available in the timeline below.`)
                      : (language === 'zh' ? '近期活动会在保存持仓、现金或公司行为后出现在下方。' : 'Recent activity appears below after holdings, cash, or corporate records are saved.')}
                  </div>
                </TerminalPanel>
              </div>
            </div>

            <div data-testid="portfolio-row-notes" className="order-4 col-span-12 min-w-0">
              <details data-testid="portfolio-data-notes" className="group rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)]">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm text-[color:var(--wolfy-text-secondary)] outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)] [&::-webkit-details-marker]:hidden">
                  <span>{language === 'zh' ? '查看数据说明与配置细节' : 'View data notes and allocation detail'}</span>
                  <span className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-1 text-[11px] font-semibold text-[color:var(--wolfy-text-muted)] group-open:text-[color:var(--wolfy-text-primary)]">
                    {language === 'zh' ? '展开' : 'Expand'}
                  </span>
                </summary>
                <div className="grid gap-4 border-t border-[color:var(--wolfy-border-subtle)] px-4 pb-4 pt-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
                  <TerminalPanel
                    as="section"
                    data-testid="portfolio-exposure-card"
                    className="min-w-0 flex flex-col gap-4"
                  >
                    <div className="flex flex-wrap items-center justify-between gap-3">
                      <h2 className="text-xs uppercase tracking-widest text-muted-text">{exposureTitle}</h2>
                      <PortfolioSegmentedControl
                        value={exposureTab}
                        onChange={(value) => setExposureTab(value as ExposureTab)}
                        options={exposureTabs}
                        className="sm:w-auto"
                        itemClassName="px-3 text-xs sm:flex-none"
                        dataTestId="portfolio-exposure-tabs"
                      />
                    </div>
                    {exposureRows.length ? (
                      <TerminalDenseList className="gap-2">
                        {exposureRows.map((row) => {
                          const values = renderExposureValue(row);
                          return (
                            <TerminalNestedBlock key={`${exposureTab}-${row.key}`} className="min-w-0 p-3">
                              <div className="flex min-w-0 items-center justify-between gap-3">
                                <div className="min-w-0">
                                  <div className="truncate text-sm font-medium text-[color:var(--wolfy-text-primary)]">{formatExposureRowLabel(row)}</div>
                                  <div className="mt-1 text-xs text-[color:var(--wolfy-text-muted)]">
                                    {formatPercent(row.percent)}
                                    {row.fxStatus === 'unavailable' ? ` · ${fxUnavailableLabel}` : ''}
                                  </div>
                                </div>
                                <div className="shrink-0 text-right">
                                  <div className="font-mono text-sm text-[color:var(--wolfy-text-primary)] tabular-nums">{values.display}</div>
                                  {values.native ? <div className="mt-1 font-mono text-[11px] text-[color:var(--wolfy-text-muted)]">{values.native}</div> : null}
                                </div>
                              </div>
                              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-[var(--wolfy-surface-rail)]">
                                <div className="h-full rounded-full bg-emerald-400/70" style={{ width: `${Math.max(2, Math.min(100, row.percent || 0))}%` }} />
                              </div>
                              {exposureTab === 'symbol' && row.unrealizedPnl != null ? (
                                <div className="mt-2 flex justify-between gap-3 text-xs text-[color:var(--wolfy-text-muted)]">
                                  <span>{copy.positionUnrealized}</span>
                                  <span className={Number(row.unrealizedPnl) >= 0 ? 'text-emerald-300' : 'text-rose-300'}>
                                    {formatSignedMoney(Number(row.unrealizedPnl), row.displayCurrency || snapshotCurrency)}
                                    {' '}
                                    {formatPercent(row.unrealizedPnlPct)}
                                  </span>
                                </div>
                              ) : null}
                            </TerminalNestedBlock>
                          );
                        })}
                      </TerminalDenseList>
                    ) : (
                      <TerminalEmptyState title={hasHoldings ? exposureEmpty : analyticsEmptyText} />
                    )}
                  </TerminalPanel>

                  <TerminalPanel as="section" data-testid="portfolio-valuation-notes" className="min-w-0 flex flex-col gap-4">
                    <div>
                      <h2 className="text-xs uppercase tracking-widest text-muted-text">{language === 'zh' ? '数据说明' : 'Data notes'}</h2>
                      {consumerDataNotice ? (
                        <p data-testid="portfolio-consumer-data-notice" className="mt-2 text-sm leading-6 text-amber-200/80">
                          {consumerDataNotice}
                        </p>
                      ) : (
                        <p className="mt-2 text-sm leading-6 text-[color:var(--wolfy-text-muted)]">
                          {language === 'zh' ? '这里保留估值来源、风险参考与折算状态的消费者可读说明。' : 'This section keeps consumer-readable notes about valuation lineage, risk references, and conversion state.'}
                        </p>
                      )}
                    </div>
                    <div className="grid grid-cols-1 gap-2">
                      <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm text-[color:var(--wolfy-text-secondary)]">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{copy.snapshotBasisTitle}</div>
                        <div className="mt-2">{valuationSnapshotNote}</div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm text-[color:var(--wolfy-text-secondary)]">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{copy.fxState}</div>
                        <div className="mt-2">{snapshot?.fxStale ? copy.fxStale : copy.fxFresh}</div>
                      </div>
                      <div className="rounded-xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-3 text-sm text-[color:var(--wolfy-text-secondary)]">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">{copy.costMethod}</div>
                        <div className="mt-2">
                          {costMethod === 'fifo'
                            ? copy.costFifo
                            : costMethod === 'avg'
                              ? copy.costAvg
                              : costMethod === 'futu_diluted'
                                ? copy.costFutuDiluted
                                : copy.costThsPnl}
                        </div>
                      </div>
                    </div>
                    {valuationTrustItems.length ? (
                      <PortfolioTrustStrip
                        title={language === 'zh' ? '估值信任' : 'Valuation trust'}
                        items={valuationTrustItems}
                        data-testid="portfolio-valuation-trust-details"
                      />
                    ) : null}
                    {riskTrustItems.length ? (
                      <PortfolioTrustStrip
                        title={language === 'zh' ? '风险信任' : 'Risk trust'}
                        items={riskTrustItems}
                        data-testid="portfolio-risk-trust-strip"
                      />
                    ) : null}
                  </TerminalPanel>
                </div>
              </details>
            </div>

            <div data-testid="portfolio-workspace-lanes" className="order-5 col-span-12 min-w-0 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(320px,5fr)] 2xl:gap-5 items-start">
              <div data-testid="portfolio-activity-lane" className="min-w-0 flex flex-col gap-4">
                {shouldRenderFullHistory ? (
                  <TerminalPanel
                    as="section"
                    data-testid="portfolio-history-full"
                    className={`min-w-0 flex flex-col overflow-hidden ${currentEventCount > 5 ? 'max-h-[640px] overflow-y-auto no-scrollbar [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]' : 'max-h-none'}`}
                  >
                    {historyPanelContent}
                  </TerminalPanel>
                ) : (
                  recentActivityContent
                )}
              </div>

              <div data-testid="portfolio-manual-lane" className="min-w-0 flex flex-col gap-4">
                {canManagePortfolioOperations ? (
						          <TerminalPanel as="section" data-testid="portfolio-trade-station-card" data-execution-surface="manual-record-entry" className="min-w-0 flex flex-col gap-4 overflow-visible xl:min-h-0">
            <div className="shrink-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm text-muted-text uppercase tracking-widest">{language === 'zh' ? '手工记账台' : 'Manual Ledger'}</h2>
                  <p className="mt-1 text-xs leading-5 text-[color:var(--wolfy-text-muted)]">{manualLedgerDisclosure}</p>
                </div>
              </div>
              <details
                data-testid="portfolio-manual-record-disclosure"
                open={manualLedgerOpen}
                onToggle={(event) => setManualLedgerOpen(event.currentTarget.open)}
                className="group mt-4 rounded-[16px] border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] open:bg-[var(--wolfy-surface-input)]"
              >
                <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--wolfy-accent)] [&::-webkit-details-marker]:hidden">
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-[color:var(--wolfy-text-primary)]">{language === 'zh' ? '手工记账' : 'Manual ledger'}</span>
                  </span>
                  <span className="shrink-0 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-1 text-[11px] font-semibold text-[color:var(--wolfy-text-secondary)] group-open:text-[color:var(--wolfy-text-primary)]">
                    {copy.submitTrade}
                  </span>
                </summary>
                <div className="border-t border-[color:var(--wolfy-border-subtle)] px-4 pb-4 pt-4">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <Select
                  label={language === 'zh' ? '记账账户' : 'Ledger account'}
                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                  value={String(selectedTradeAccount)}
                  onChange={(value) => {
                    setSelectedTradeAccount(value === 'all' ? 'all' : Number(value));
                    clearAccountRequirementWarning();
                    resetIbkrConnectionDrafts();
                    setIbkrSyncResult(null);
                  }}
                  options={[
                    { value: 'all', label: copy.allAccounts },
                    ...writableAccounts.map((account) => ({ value: String(account.id), label: formatConsumerAccountLabel(account.name, language) })),
                  ]}
                  className={PORTFOLIO_SELECT_CLASS}
                  controlClassName="rounded-lg"
                />
                <Select
                  label={language === 'zh' ? '成本方法' : 'Cost method'}
                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                  value={costMethod}
                  onChange={(value) => {
                    const nextCostMethod = value as PortfolioCostMethod;
                    setCostMethod(nextCostMethod);
                    invalidateFxRefreshScope(selectedAccount, nextCostMethod);
                  }}
                  options={[
                    { value: 'fifo', label: copy.costFifo },
                    { value: 'avg', label: copy.costAvg },
                    { value: 'futu_diluted', label: copy.costFutuDiluted },
                    { value: 'ths_pnl', label: copy.costThsPnl },
                  ]}
                  className={PORTFOLIO_SELECT_CLASS}
                  controlClassName="rounded-lg"
                />
              </div>
              <div data-testid="portfolio-trade-station-summary" className="mt-3 flex flex-col gap-1 border-y border-[color:var(--wolfy-border-subtle)] py-2">
                <div className="flex justify-between gap-3 text-xs"><span className="text-muted-text">{copy.totalCash}</span><span className="font-mono text-foreground">{formatDisplayMoney(totalCash, totalCashDisplay, snapshotCurrency)}</span></div>
                <div className="flex justify-between gap-3 text-xs"><span className="text-muted-text">{copy.totalMarketValue}</span><span className="font-mono text-foreground">{formatDisplayMoney(totalMarketValue, totalMarketValueDisplay, snapshotCurrency)}</span></div>
                <div className="flex justify-between text-xs"><span className="text-muted-text">{copy.fxState}</span><span data-testid="portfolio-bento-hero-fx-value" className={snapshot?.fxStale ? 'text-amber-300' : 'text-emerald-400'}>{snapshot?.fxStale ? copy.fxStale : copy.fxFresh}</span></div>
              </div>
              {tradeFeedback ? (
                <div
                  data-testid="portfolio-trade-feedback"
                  className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
                    tradeFeedback.tone === 'success'
                      ? 'border-emerald-400/20 bg-emerald-400/10 text-emerald-300'
                      : 'border-rose-400/20 bg-rose-400/10 text-rose-300'
                  }`}
                >
                  {tradeFeedback.text}
                </div>
              ) : null}
            </div>

            <div className="shrink-0 border-b border-[color:var(--wolfy-border-subtle)] pt-4 pb-4">
              <PortfolioSegmentedControl
                value={leftTab}
                onChange={(value) => setLeftTab(value as 'trade' | 'account' | 'sync' | 'fx')}
                options={[
                  { value: 'trade', label: language === 'en' ? 'Ledger' : '记账' },
                  { value: 'account', label: language === 'en' ? 'Account' : '账户' },
                  { value: 'sync', label: language === 'en' ? 'Sync' : '同步' },
                  { value: 'fx', label: language === 'en' ? 'FX' : '汇率' },
                ]}
                dataTestId="portfolio-left-tab-switcher"
              />
            </div>

            <div
              data-testid="portfolio-trade-station-scroll"
              className="min-h-0 flex-1 overflow-y-auto no-scrollbar pt-4 [&::-webkit-scrollbar]:hidden [-ms-overflow-style:none] [scrollbar-width:none]"
            >
              {leftTab === 'trade' ? (
                <div className="flex flex-col gap-2">
                  <div
                    data-testid="portfolio-trade-type-switcher"
                    className="mb-3"
                  >
                    <PortfolioSegmentedControl
                      value={tradeType}
                      onChange={(value) => setTradeType(value as TradeFormType)}
                      options={[
                        { value: 'stock', label: language === 'en' ? 'Holding Ledger' : '持仓流水' },
                        { value: 'fund', label: language === 'en' ? 'Cash Transfer' : '资金划转' },
                        { value: 'corporate', label: language === 'en' ? 'Corporate Action' : '公司行为' },
                      ]}
                      itemClassName="text-xs"
                    />
                  </div>
                  {tradeType === 'stock' ? (
                    <ManualTradeForm
                      copy={copy}
                      language={language}
                      tradeForm={tradeForm}
                      tradeCurrencyValue={effectiveTradeCurrency}
                      writableAccountId={writableAccountId}
                      tradeSubmitting={tradeSubmitting}
                      tradeCurrencyHint={tradeCurrencyHint}
                    tradeCurrencyWarning={tradeCurrencyWarning}
                      setTradeForm={setTradeForm}
                      setTradeCurrencyManuallyEdited={setTradeCurrencyManuallyEdited}
                      onSubmit={handleTradeSubmit}
                    />
                  ) : null}

                  {tradeType === 'fund' ? (
                    <ManualCashForm
                      copy={copy}
                      cashForm={cashForm}
                      snapshotCurrency={snapshotCurrency}
                      writableAccountId={writableAccountId}
                      setCashForm={setCashForm}
                      onSubmit={handleCashSubmit}
                    />
                  ) : null}

                  {tradeType === 'corporate' ? (
                    <ManualCorporateActionForm
                      copy={copy}
                      corpForm={corpForm}
                      writableAccountId={writableAccountId}
                      setCorpForm={setCorpForm}
                      onSubmit={handleCorporateSubmit}
                    />
                  ) : null}
                </div>
              ) : null}

              {leftTab === 'account' ? (
                <AccountManagementPanel
                  copy={copy}
                  language={language}
                  accounts={accounts}
                  showCreateAccount={showCreateAccount}
                  hasAccounts={hasAccounts}
                  accountForm={accountForm}
                  accountCreating={accountCreating}
                  accountCreateError={accountCreateError}
                  accountCreateSuccess={accountCreateSuccess}
                  isLoading={isLoading}
                  setAccountForm={setAccountForm}
                  onToggleCreate={() => {
                    setShowCreateAccount((prev) => !prev);
                    setAccountCreateError(null);
                    setAccountCreateSuccess(null);
                  }}
                  onRefresh={() => void handleRefresh()}
                  onSubmit={handleCreateAccount}
                  onDeleteAccount={(account) => setPendingAccountDelete({ id: account.id, name: formatConsumerAccountLabel(account.name, language) })}
                />
              ) : null}

              {leftTab === 'sync' ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.dataSyncTitle}</p>
                    <Button type="button" variant="ghost" className={PORTFOLIO_ICON_BUTTON_CLASS} onClick={() => void handleRefresh()} disabled={isLoading} aria-label={isLoading ? copy.refreshingData : copy.refreshData} title={isLoading ? copy.refreshingData : copy.refreshData}>
                      <RefreshCw className={`size-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
                    </Button>
                  </div>
                  <div className="text-xs text-secondary-text space-y-1">
                    <p>{copy.currentImportAccount}</p>
                    <p>{writableAccount ? `${writableAccount.name} (#${writableAccount.id})` : copy.brokerFallbackEmpty}</p>
                    <p>{brokerListUnavailable ? copy.brokerFallbackUnavailable : selectedBroker === 'ibkr' ? copy.ibkrImportHint : copy.brokerImportHint}</p>
                  </div>
                  <Select label={language === 'zh' ? '导入来源' : 'Broker'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={selectedBroker} onChange={(value) => {
                    setSelectedBroker(value);
                    setIbkrSyncResult(null);
                    setImportFile(null);
                    resetImportPreviewState();
                    resetIbkrConnectionDrafts();
                    if (value !== 'ibkr') {
                      setIbkrSessionToken('');
                    }
                  }} options={brokers.map((broker) => ({ value: broker.broker, label: formatBrokerLabel(broker.broker, broker.displayName, language) }))} disabled={brokerListUnavailable || brokers.length === 0} />
                  {brokerListUnavailable ? (
                    <div className="rounded-2xl border border-amber-300/15 bg-amber-300/[0.05] p-4 text-xs leading-5 text-amber-100/80">
                      {copy.brokerFallbackUnavailable}
                    </div>
                  ) : null}
                  {!brokerListUnavailable && selectedBroker === 'ibkr' ? (
                    <SectionShell className="rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4" contentClassName="space-y-3">
                      <PortfolioIbkrImportHeader copy={copy} />
                      {ibkrConnection ? <p className="text-sm text-foreground">{ibkrConnection.connectionName}</p> : null}
                      <Input label={language === 'zh' ? 'IBKR 连接端点' : 'IBKR connection endpoint'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrApiBasePlaceholder} value={ibkrApiBaseUrl} onChange={(e) => setIbkrApiBaseUrlDraft(e.target.value)} />
                      <Input label={language === 'zh' ? 'IBKR 账户映射' : 'IBKR account mapping'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrAccountRefPlaceholder} value={ibkrBrokerAccountRef} onChange={(e) => setIbkrBrokerAccountRefDraft(e.target.value)} />
                      <Input label={language === 'zh' ? 'IBKR 临时授权' : 'IBKR temporary authorization'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrSessionTokenPlaceholder} value={ibkrSessionToken} onChange={(e) => setIbkrSessionToken(e.target.value)} />
                      <Checkbox checked={ibkrVerifySsl} onChange={(e) => setIbkrVerifySslDraft(e.target.checked)} label={copy.verifyIbkrSsl} containerClassName="text-xs text-secondary-text" />
                      <Button type="button" variant="primary" className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`} onClick={() => void handleSyncIbkr()} disabled={!writableAccountId || ibkrSyncing}>
                        {ibkrSyncing ? copy.syncing : copy.syncIbkr}
                      </Button>
                      {ibkrSyncResult ? <PortfolioIbkrSyncResultCard copy={copy} result={ibkrSyncResult} /> : null}
                    </SectionShell>
                  ) : !brokerListUnavailable ? (
                    <div className="rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4 text-xs text-secondary-text">
                      {copy.brokerImportHint}
                    </div>
                  ) : null}
                  {!brokerListUnavailable && selectedBroker ? (
                    <div data-testid="portfolio-import-workflow-panel">
                    <SectionShell className="rounded-2xl border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-4" contentClassName="space-y-3">
                      <div className="min-w-0">
                        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-muted-text">{t('portfolio.importPreviewTitle')}</p>
                        <p className="mt-1 text-xs leading-5 text-secondary-text">{t('portfolio.importPreviewOnly')}</p>
                      </div>
                      <Input
                        type="file"
                        label={t('portfolio.importChooseFile')}
                        labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                        className={PORTFOLIO_INPUT_CLASS}
                        accept={selectedBroker === 'ibkr' ? '.xml,text/xml,application/xml' : '.csv,text/csv'}
                        onChange={handleImportFileChange}
                      />
                      <div className="flex min-w-0 flex-wrap gap-2">
                        <Button
                          type="button"
                          variant="secondary"
                          className={PORTFOLIO_SECONDARY_BUTTON_CLASS}
                          onClick={() => void handlePreviewImport()}
                          disabled={!writableAccountId || !importFile || importParsing || importCommitting}
                        >
                          {importParsing ? copy.parsing : t('portfolio.previewImport')}
                        </Button>
                        <Button
                          type="button"
                          variant="primary"
                          className={PORTFOLIO_PRIMARY_BUTTON_CLASS}
                          onClick={() => void handleConfirmImport()}
                          disabled={!writableAccountId || !importPreview || importParsing || importCommitting || Number(importPreview.acceptedCount ?? importPreview.insertedCount ?? 0) <= 0}
                        >
                          {importCommitting ? copy.committing : t('portfolio.confirmImport')}
                        </Button>
                      </div>
                      {importPreview ? (
                        <PortfolioImportPreviewCard
                          title={t('portfolio.importPreviewTitle')}
                          boundary={t('portfolio.importConfirmBoundary')}
                          acceptedLabel={t('portfolio.acceptedRows')}
                          rejectedLabel={t('portfolio.rejectedRows')}
                          duplicateLabel={t('portfolio.duplicateCandidates')}
                          currencyLabel={t('portfolio.currencyIssues')}
                          unknownLabel={t('portfolio.unknownSymbols')}
                          recoveryLabel={t('portfolio.recoveryActions')}
                          parseResult={importParseResult}
                          result={importPreview}
                        />
                      ) : null}
                      {importCommitResult ? (
                        <PortfolioImportPreviewCard
                          title={copy.commitResult}
                          boundary={importCommitResult.duplicateImport ? copy.duplicateFingerprintHint : t('portfolio.importConfirmBoundary')}
                          acceptedLabel={t('portfolio.acceptedRows')}
                          rejectedLabel={t('portfolio.rejectedRows')}
                          duplicateLabel={t('portfolio.duplicateCandidates')}
                          currencyLabel={t('portfolio.currencyIssues')}
                          unknownLabel={t('portfolio.unknownSymbols')}
                          recoveryLabel={t('portfolio.recoveryActions')}
                          parseResult={null}
                          result={importCommitResult}
                        />
                      ) : null}
                    </SectionShell>
                    </div>
                  ) : null}
                </div>
              ) : null}

              {leftTab === 'fx' ? (
                <div data-testid="portfolio-fx-panel" className="space-y-4">
                  <div>
	                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{language === 'zh' ? '汇率参考' : 'Exchange-rate reference'}</p>
                    <p className="mt-1 text-[11px] text-[color:var(--wolfy-text-muted)]">
                      {language === 'en' ? 'Last update' : '最后更新'} {selectedFxRate?.timestamp ? formatFxTimestamp(selectedFxRate.timestamp) : fxLastUpdated}
                      {selectedFxRate?.isStale ? ` · ${copy.fxStale}` : ''}
                    </p>
                  </div>
                  <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-2">
                    <Select
	                      label={language === 'zh' ? '基准币种' : 'Base Currency'}
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      className={PORTFOLIO_SELECT_CLASS}
                      value={fxBaseCurrency}
                      onChange={setFxBaseCurrency}
                      options={FX_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                    />
                    <span className="mb-2 flex h-10 w-8 items-center justify-center rounded-lg bg-[var(--wolfy-surface-rail)] text-[color:var(--wolfy-text-muted)]" aria-hidden="true">
                      <ArrowRightLeft className="size-4" />
                    </span>
                    <Select
	                      label={language === 'zh' ? '报价币种' : 'Quote Currency'}
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      className={PORTFOLIO_SELECT_CLASS}
                      value={fxQuoteCurrency}
                      onChange={setFxQuoteCurrency}
                      options={FX_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                    />
                  </div>
		                  <TerminalNestedBlock className="px-4 py-5">
		                    <div className="text-[11px] uppercase tracking-[0.16em] text-[color:var(--wolfy-text-muted)]">
		                      {fxBaseCurrency}/{fxQuoteCurrency}
		                    </div>
	                    <div data-testid="portfolio-fx-rate-value" className="mt-2 flex items-baseline gap-1.5 whitespace-nowrap">
	                      <span className="text-sm text-[color:var(--wolfy-text-secondary)]">1 {fxBaseCurrency} =</span>
	                      {' '}
		                    <span className="font-mono text-xl text-[color:var(--wolfy-accent)]">{selectedFxRate ? formatFxRate(selectedFxRate.rate) : '--'}</span>
	                      {' '}
		                      <span className="text-sm text-[color:var(--wolfy-text-secondary)]">{fxQuoteCurrency}</span>
		                    </div>
		                    <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-[color:var(--wolfy-text-muted)]">
		                      <span>{selectedFxRate ? consumerFxLabel(selectedFxRate.isStale ? 'stale' : 'fresh', language) : consumerFxLabel('pending', language)}</span>
		                    </div>
		                  </TerminalNestedBlock>
	                  <Button
	                    type="button"
	                    variant="primary"
	                    className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`}
	                    onClick={() => void handleRefreshFx()}
	                    disabled={isLoading || fxRefreshing}
                    aria-label={fxRefreshing ? copy.refreshingFx : copy.refreshFx}
                    title={fxRefreshing ? copy.refreshingFx : copy.refreshFx}
                    isLoading={fxRefreshing}
                    loadingText={copy.refreshingFx}
	                  >
	                    {copy.refreshFx}
	                  </Button>
                  {fxRefreshFeedback ? (
                    <p className={`text-xs ${
                      fxRefreshFeedback.tone === 'success'
                        ? 'text-emerald-300'
                        : fxRefreshFeedback.tone === 'warning'
                          ? 'text-amber-200'
                          : 'text-secondary-text'
                    }`}>
                      {fxRefreshFeedback.text}
                    </p>
                  ) : null}
                </div>
              ) : null}
            </div>
		              </details>
		            </div>
		          </TerminalPanel>
                ) : (
                  <TerminalPanel as="section" data-testid="portfolio-consumer-setup-boundary" className="min-w-0 flex flex-col gap-3">
                    <h2 className="text-sm uppercase tracking-widest text-muted-text">
                      {language === 'zh' ? '组合数据接入' : 'Portfolio data connection'}
                    </h2>
                    <p className="text-sm leading-6 text-[color:var(--wolfy-text-secondary)]">
                      {language === 'zh'
                        ? '当前视图仅展示已接入的组合、持仓与估值状态。连接、导入和同步步骤由具备操作权限的人员配置后开放。'
                        : 'This view only shows connected portfolio, holdings, and valuation status. Connection, import, and sync steps appear after an operator configures access.'}
                    </p>
                    <TerminalNestedBlock className="px-3 py-3 text-xs leading-5 text-[color:var(--wolfy-text-secondary)]">
                      {language === 'zh'
                        ? '这里保留消费者可读状态，具体接入配置由具备操作权限的人员在受控入口完成。'
                        : 'This area keeps consumer-readable status while operational setup stays in the controlled operator surface.'}
                    </TerminalNestedBlock>
                  </TerminalPanel>
                )}
              </div>
            </div>
	          </div>
      </ConsumerWorkspacePageShell>
      </ConsumerWorkspaceScope>
    </div>

      <Drawer
        isOpen={Boolean(editingTrade)}
        onClose={() => {
          if (tradeEditSubmitting) {
            return;
          }
          setEditingTrade(null);
        }}
        title={editTradeTitle}
        width="max-w-[min(96vw,38rem)]"
        bodyClassName="gap-4"
      >
        {editingTrade ? (
          <form className="flex flex-col gap-4" onSubmit={handleTradeEditSubmit}>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <Select
                label={language === 'zh' ? '账户' : 'Account'}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_SELECT_CLASS}
                value={String(editingTrade.accountId)}
                onChange={(value) => setEditingTrade((prev) => (prev ? {
                  ...prev,
                  accountId: Number(value),
                } : prev))}
                options={writableAccounts.map((account) => ({ value: String(account.id), label: formatConsumerAccountLabel(account.name, language) }))}
              />
              <Input
                label={copy.stockCode}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                value={editingTrade.symbol}
                onChange={(e) => setEditingTrade((prev) => (
                  prev
                    ? {
                      ...prev,
                      symbol: e.target.value,
                    }
                    : prev
                ))}
                required
              />
              <Select
                label={copy.sideLabel}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_SELECT_CLASS}
                value={editingTrade.side}
                onChange={(value) => setEditingTrade((prev) => (prev ? { ...prev, side: value as PortfolioSide } : prev))}
                options={[{ value: 'buy', label: copy.buy }, { value: 'sell', label: copy.sell }]}
              />
              <Input
                label={copy.tradeDate}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                type="date"
                value={editingTrade.tradeDate}
                onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, tradeDate: e.target.value } : prev))}
                required
              />
              <Input
                label={copy.quantity}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                type="number"
                min="0"
                step="0.0001"
                value={editingTrade.quantity}
                onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, quantity: e.target.value } : prev))}
                required
              />
              <Input
                label={copy.price}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                type="number"
                min="0"
                step="0.0001"
                value={editingTrade.price}
                onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, price: e.target.value } : prev))}
                required
              />
              <Select
                label={copy.currency}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_SELECT_CLASS}
                value={effectiveEditTradeCurrency}
                onChange={(value) => {
                  setEditingTrade((prev) => (prev ? {
                    ...prev,
                    currency: value,
                    currencyManuallyEdited: true,
                  } : prev));
                }}
                options={FX_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
              />
              <Input
                label={copy.feeOptional}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                type="number"
                min="0"
                step="0.0001"
                value={editingTrade.fee}
                onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, fee: e.target.value } : prev))}
              />
              <Input
                label={copy.taxOptional}
                labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                className={PORTFOLIO_INPUT_CLASS}
                type="number"
                min="0"
                step="0.0001"
                value={editingTrade.tax}
                onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, tax: e.target.value } : prev))}
              />
            </div>
            <Input
              label={copy.note}
              labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
              className={PORTFOLIO_INPUT_CLASS}
              value={editingTrade.note}
              onChange={(e) => setEditingTrade((prev) => (prev ? { ...prev, note: e.target.value } : prev))}
            />
            <div className="flex flex-col gap-2 sm:flex-row sm:justify-end">
              <Button
                type="button"
                variant="ghost"
                className={PORTFOLIO_TEXT_BUTTON_CLASS}
                onClick={() => {
                  setEditingTrade(null);
                }}
                disabled={tradeEditSubmitting}
              >
                {copy.cancel}
              </Button>
              <Button type="submit" variant="primary" className={PORTFOLIO_PRIMARY_BUTTON_CLASS} disabled={tradeEditSubmitting}>
                {saveTradeChangesLabel}
              </Button>
            </div>
          </form>
        ) : null}
      </Drawer>

      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title={pendingDelete?.eventType === 'trade' ? pendingDelete.title : copy.deleteTitle}
        message={pendingDelete?.message || copy.deleteMessage}
        confirmText={deleteLoading ? copy.deleteInProgress : (pendingDelete?.eventType === 'trade' ? pendingDelete.confirmText : copy.deleteConfirm)}
        cancelText={copy.cancel}
        isDanger
        onConfirm={() => void handleConfirmDelete()}
        onCancel={() => {
          if (!deleteLoading) {
            setPendingDelete(null);
          }
        }}
      />
      <ConfirmDialog
        isOpen={Boolean(pendingAccountDelete)}
        title={copy.accountDeleteTitle}
        message={copy.accountDeleteMessage}
        confirmText={deleteLoading ? copy.deleteInProgress : copy.deleteConfirm}
        cancelText={copy.cancel}
        isDanger
        onConfirm={() => void handleConfirmAccountDelete()}
        onCancel={() => {
          if (!deleteLoading) {
            setPendingAccountDelete(null);
          }
        }}
      />
    </>
  );
};

export default PortfolioPage;
