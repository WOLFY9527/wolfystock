import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState, useSyncExternalStore } from 'react';
import { MoreHorizontal, PenSquare, RefreshCw, Trash2 } from 'lucide-react';
import { portfolioApi } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert } from '../components/common/ApiErrorAlert';
import { Button } from '../components/common/Button';
import { Checkbox } from '../components/common/Checkbox';
import { ConfirmDialog } from '../components/common/ConfirmDialog';
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
import { PortfolioTrustStrip, type PortfolioTrustChipItem } from '../components/portfolio/PortfolioTrustStrip';
import {
  TerminalButton,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalChip,
  TerminalEmptyState,
  TerminalGrid,
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
import { translate } from '../i18n/core';
import { normalizePortfolioRiskEvidence } from '../utils/evidenceDisplay';
import { toDateInputValue } from '../utils/format';
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
  PortfolioIbkrSyncResponse,
  PortfolioLiveFxRateResponse,
  PortfolioPositionItem,
  PortfolioSide,
  PortfolioSnapshotResponse,
  PortfolioTradeListItem,
  PortfolioTradeUpdateRequest,
} from '../types/portfolio';

const PORTFOLIO_FIELD_LABEL_CLASS = '!mb-1 text-[11px] font-medium tracking-normal text-white/55';
const PORTFOLIO_FIELD_WRAPPER_CLASS = 'flex flex-col gap-1.5';
const PORTFOLIO_FORM_GRID_CLASS = 'mt-4 grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2';
const PORTFOLIO_INPUT_CLASS = 'h-10 rounded-lg border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm text-white placeholder:text-white/20 outline-none focus:border-emerald-500/50';
const PORTFOLIO_SELECT_CLASS = 'min-w-0';
const PORTFOLIO_PRIMARY_BUTTON_CLASS = 'border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[#6f79dc] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SUBMIT_BUTTON_CLASS = 'mt-5 w-full border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[#6f79dc] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SECONDARY_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-divider)] px-4 py-2.5 rounded-md transition-colors';
const PORTFOLIO_TEXT_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-transparent text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] px-3 py-1.5 rounded-md text-xs transition-colors disabled:text-white/15 disabled:opacity-50';
const PORTFOLIO_ICON_BUTTON_CLASS = 'size-9 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-0 text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]';
const PORTFOLIO_DANGER_GHOST_CLASS = 'size-8 rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-transparent p-0 text-[color:var(--wolfy-market-down)] hover:bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)]';
const CASH_CURRENCY_OPTIONS = ['CNY', 'HKD', 'USD'] as const;
const FX_CURRENCY_OPTIONS = ['USD', 'CNY', 'HKD', 'EUR', 'JPY', 'GBP'] as const;

const DEFAULT_PAGE_SIZE = 20;
const FALLBACK_BROKERS: PortfolioImportBrokerItem[] = [
  { broker: 'huatai', aliases: [], displayName: translate('zh', 'portfolio.brokerName.huatai'), fileExtensions: ['csv'] },
  { broker: 'citic', aliases: ['zhongxin'], displayName: translate('zh', 'portfolio.brokerName.citic'), fileExtensions: ['csv'] },
  { broker: 'cmb', aliases: ['cmbchina', 'zhaoshang'], displayName: translate('zh', 'portfolio.brokerName.cmb'), fileExtensions: ['csv'] },
  { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: translate('zh', 'portfolio.brokerName.ibkr'), fileExtensions: ['xml'] },
];

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
  if (normalized.includes('fallback') || normalized.includes('备用') || normalized.includes('回退')) {
    return language === 'zh' ? '当前估值可能存在延迟' : 'Current valuation may be delayed';
  }
  if (normalized.includes('confidence') || normalized.includes('置信')) {
    return limitedConfidenceLabel(language);
  }
  if (normalized.includes('stale') || normalized.includes('过期') || normalized.includes('expired')) {
    return language === 'zh' ? '数据可能延迟' : 'Data may be delayed';
  }
  return label || null;
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
        label: language === 'zh' ? '估值已更新' : 'Valuation current',
        variant: 'success',
      },
    };
  }

  if (token === 'price_fallback' || token === 'fx_stale') {
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
    token === 'fx_fallback_1_to_1'
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
        listClassName="ui-scroll-x-quiet w-full rounded-xl border-0 bg-white/[0.05] p-1"
        buttonClassName={`rounded-lg border-0 text-center text-sm font-medium ${itemClassName}`}
        activeButtonClassName="bg-white/10 text-white shadow-sm"
        inactiveButtonClassName="bg-transparent text-white/40 hover:bg-transparent hover:text-white/70"
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
            className="absolute right-0 z-20 mt-2 flex min-w-[132px] flex-col gap-1 bg-[#0f1726] p-2 shadow-2xl"
          >
            <Button type="button" variant="ghost" className="justify-start rounded-lg px-2 text-xs text-white/75" onClick={() => onEdit(item)}>
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
  tradeCurrencyManuallyEdited,
  writableAccountBaseCurrency,
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
  tradeCurrencyManuallyEdited: boolean;
  writableAccountBaseCurrency?: string;
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
                currency: tradeCurrencyManuallyEdited
                  ? prev.currency
                  : inferSettlementCurrency(symbol, writableAccountBaseCurrency),
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
            value={tradeForm.currency}
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
        <div className="mt-3 rounded-lg bg-white/[0.025] px-3 py-2 text-xs leading-5 text-white/45">
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
    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
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
    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
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
              <span className="min-w-0 truncate text-foreground">{account.name}</span>
              <div className="flex shrink-0 items-center gap-2">
                <span className="font-mono text-muted-text">#{account.id}</span>
                <Button
                  type="button"
                  variant="ghost"
                  className={PORTFOLIO_DANGER_GHOST_CLASS}
                  onClick={() => onDeleteAccount(account)}
                  aria-label={language === 'en' ? `Delete ${account.name}` : `删除 ${account.name}`}
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
        <form className="space-y-3 rounded-xl border border-white/5 bg-white/[0.02] p-3" onSubmit={onSubmit}>
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

function sortExposureRowsByPercent(rows: PortfolioExposureItem[] | undefined): PortfolioExposureItem[] {
  const sorted = [...(rows || [])];
  sorted.sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0));
  return sorted;
}

const PortfolioPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { language, t } = useI18n();
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
    broker: 'Demo',
    market: 'cn' as 'cn' | 'hk' | 'us' | 'global',
    baseCurrency: 'CNY',
  });
  const [costMethod, setCostMethod] = useState<PortfolioCostMethod>('fifo');
  const [displayCurrency, setDisplayCurrency] = useState<DisplayCurrency>(() => readPortfolioDisplayCurrency());
  const [snapshot, setSnapshot] = useState<PortfolioSnapshotResponse | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [fxRefreshing, setFxRefreshing] = useState(false);
  const [fxRefreshFeedback, setFxRefreshFeedback] = useState<FxRefreshFeedback | null>(null);
  const [error, setError] = useState<ParsedApiError | null>(null);
  const [riskWarning, setRiskWarning] = useState<string | null>(null);
  const [writeWarning, setWriteWarning] = useState<string | null>(null);
  const [tradeSubmitting, setTradeSubmitting] = useState(false);
  const [tradeFeedback, setTradeFeedback] = useState<{ tone: 'success' | 'error'; text: string } | null>(null);

  const [brokers, setBrokers] = useState<PortfolioImportBrokerItem[]>([]);
  const [brokerConnections, setBrokerConnections] = useState<PortfolioBrokerConnectionItem[]>([]);
  const [selectedBroker, setSelectedBroker] = useState('huatai');
  const [ibkrApiBaseUrl, setIbkrApiBaseUrl] = useState('https://localhost:5000/v1/api');
  const [ibkrVerifySsl, setIbkrVerifySsl] = useState(false);
  const [ibkrSessionToken, setIbkrSessionToken] = useState('');
  const [ibkrBrokerAccountRef, setIbkrBrokerAccountRef] = useState('');
  const [ibkrSyncing, setIbkrSyncing] = useState(false);
  const [ibkrSyncResult, setIbkrSyncResult] = useState<PortfolioIbkrSyncResponse | null>(null);

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
  const refreshViewKey = `${selectedAccount === 'all' ? 'all' : `account:${selectedAccount}`}:cost:${costMethod}`;
  const refreshContextRef = useRef<FxRefreshContext>({ viewKey: refreshViewKey, requestId: 0 });
  const tradeEditCurrencyManuallyEditedRef = useRef(false);
  const activeAccounts = accounts.filter((item) => item.isActive !== false);
  const writableAccounts = activeAccounts;
  const hasAccounts = accounts.length > 0;
  const hasActiveAccounts = activeAccounts.length > 0;
  const hasWritableAccounts = writableAccounts.length > 0;
  const scopedAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccount = selectedTradeAccount === 'all' ? undefined : writableAccounts.find((item) => item.id === selectedTradeAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const editingAccount = editingTrade ? activeAccounts.find((item) => item.id === editingTrade.accountId) : undefined;
  const ibkrConnection = brokerConnections.find((item) => item.brokerType === 'ibkr') || null;
  const currentEventCount = eventType === 'trade'
    ? tradeEvents.length
    : eventType === 'cash'
      ? cashEvents.length
      : corporateEvents.length;
  const inferredTradeCurrency = inferSettlementCurrency(tradeForm.symbol, writableAccount?.baseCurrency);
  const tradeCurrencyWarning = writableAccount?.baseCurrency
    && tradeForm.currency !== normalizePortfolioDisplayCurrency(writableAccount.baseCurrency)
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
  const inferredEditTradeCurrency = inferSettlementCurrency(editingTrade?.symbol || '', editingAccount?.baseCurrency);

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
    try {
      const response = await portfolioApi.listImportBrokers();
      const brokerItems = response.brokers || [];
      if (brokerItems.length === 0) {
        setBrokers(FALLBACK_BROKERS);
        setSelectedBroker((prev) => (
          FALLBACK_BROKERS.some((item) => item.broker === prev)
            ? prev
            : FALLBACK_BROKERS[0].broker
        ));
        return;
      }
      setBrokers(brokerItems);
      setSelectedBroker((prev) => (
        brokerItems.some((item) => item.broker === prev)
          ? prev
          : brokerItems[0].broker
      ));
    } catch {
      setBrokers(FALLBACK_BROKERS);
      setSelectedBroker((prev) => (
        FALLBACK_BROKERS.some((item) => item.broker === prev)
          ? prev
          : FALLBACK_BROKERS[0].broker
      ));
    }
  }, []);

  const loadBrokerConnections = useCallback(async (accountId?: number) => {
    if (!accountId) {
      setBrokerConnections([]);
      return;
    }
    try {
      const response = await portfolioApi.listBrokerConnections(accountId);
      setBrokerConnections(response.connections || []);
    } catch {
      setBrokerConnections([]);
    }
  }, []);

  const loadSnapshotAndRisk = useCallback(async () => {
    setIsLoading(true);
    setRiskWarning(null);
    try {
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: queryAccountId,
        costMethod,
      });
      setSnapshot(snapshotData);
      setError(null);

      try {
        await portfolioApi.getRisk({
          accountId: queryAccountId,
          costMethod,
        });
      } catch (riskErr) {
        const parsed = getParsedApiError(riskErr);
        setRiskWarning(parsed.message || riskFallbackMessage);
      }
    } catch (err) {
      setSnapshot(null);
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
    const config = extractIbkrSyncConfig(ibkrConnection);
    setIbkrApiBaseUrl(config.apiBaseUrl || 'https://localhost:5000/v1/api');
    setIbkrVerifySsl(config.verifySsl ?? false);
    setIbkrBrokerAccountRef(config.brokerAccountRef || ibkrConnection?.brokerAccountRef || '');
  }, [ibkrConnection, writableAccountId]);

  useEffect(() => {
    setIbkrSyncResult(null);
    if (selectedBroker !== 'ibkr') {
      setIbkrSessionToken('');
    }
  }, [selectedBroker, writableAccountId]);

  useEffect(() => {
    void loadSnapshotAndRisk();
  }, [loadSnapshotAndRisk]);

  useEffect(() => {
    void loadEvents();
  }, [loadEvents]);

  useEffect(() => {
    refreshContextRef.current = {
      viewKey: refreshViewKey,
      requestId: refreshContextRef.current.requestId + 1,
    };
    setFxRefreshing(false);
    setFxRefreshFeedback(null);
  }, [refreshViewKey]);

  useEffect(() => {
    setEventPage(1);
    setOpenTradeActionMenuId(null);
  }, [eventType, queryAccountId, eventDateFrom, eventDateTo, eventSymbol, eventSide, eventDirection, eventActionType]);

  useEffect(() => {
    if (!writeBlocked) {
      setWriteWarning(null);
    }
  }, [writeBlocked]);

  useEffect(() => {
    if (!tradeCurrencyManuallyEdited) {
      setTradeForm((prev) => ({ ...prev, currency: inferredTradeCurrency }));
    }
  }, [inferredTradeCurrency, tradeCurrencyManuallyEdited]);

  useEffect(() => {
    if (!editingTrade || tradeEditCurrencyManuallyEditedRef.current) {
      return;
    }
    if (editingTrade.currency === inferredEditTradeCurrency) {
      return;
    }
    setEditingTrade((prev) => (
      prev
        ? { ...prev, currency: inferredEditTradeCurrency }
        : prev
    ));
  }, [editingTrade, inferredEditTradeCurrency]);

  const positionRows: FlatPosition[] = (() => {
    if (!snapshot) return [];
    const rows: FlatPosition[] = [];
    for (const account of snapshot.accounts || []) {
      for (const position of account.positions || []) {
        rows.push({
          ...position,
          accountId: account.accountId,
          accountName: account.accountName,
        });
      }
    }
    rows.sort((a, b) => Number(b.marketValueBase || 0) - Number(a.marketValueBase || 0));
    return rows;
  })();

  const handleTradeSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
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
        currency: tradeForm.currency,
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

  const handleConfirmDelete = async () => {
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
    tradeEditCurrencyManuallyEditedRef.current = false;
    setEditingTrade({
      id: item.id,
      accountId: item.accountId,
      symbol: item.symbol,
      side: item.side,
      quantity: String(item.quantity),
      price: String(item.price),
      tradeDate: item.tradeDate,
      currency: item.currency,
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
      currency: editingTrade.currency,
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
      tradeEditCurrencyManuallyEditedRef.current = false;
      setTradeFeedback({ tone: 'success', text: updateTradeSuccessLabel });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setTradeEditSubmitting(false);
    }
  };

  const handleConfirmAccountDelete = async () => {
    if (!pendingAccountDelete || deleteLoading) return;
    try {
      setDeleteLoading(true);
      setWriteWarning(null);
      const result = await portfolioApi.deleteAccount(pendingAccountDelete.id);
      const accountsResponse = await portfolioApi.getAccounts(false);
      const activeAccounts = accountsResponse.accounts || [];
      setAccounts(activeAccounts);
      const fallbackId = result.nextAccountId ?? activeAccounts[0]?.id;
      setSelectedAccount(fallbackId ?? 'all');
      setSelectedTradeAccount(fallbackId ?? 'all');
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
      setShowCreateAccount(false);
      setWriteWarning(null);
      setAccountForm({
        name: '',
        broker: 'Demo',
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
      const snapshotData = await portfolioApi.getSnapshot({
        accountId: requestedAccountId,
        costMethod: requestedCostMethod,
      });
      if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
        return false;
      }
      setSnapshot(snapshotData);
      setError(null);

      try {
        await portfolioApi.getRisk({
          accountId: requestedAccountId,
          costMethod: requestedCostMethod,
        });
        if (!isActiveRefreshContext(requestedViewKey, requestedRequestId)) {
          return false;
        }
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
  const consumerDataNotice = consumerPortfolioDataNotice({
    valuationLineageNotice,
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
  const topPosition = symbolExposureRows[0] || analytics?.risk.largestPosition || null;
  const topCurrency = currencyExposureRows[0] || analytics?.risk.largestCurrency || null;
  const topMarket = marketExposureRows[0] || analytics?.risk.largestMarket || null;
  const topPositionPercent = Number(topPosition?.percent || 0);
  const concentrationLabel = !hasHoldings || !topPosition
    ? (language === 'zh' ? '暂无持仓' : 'No holdings')
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
        ? 'text-cyan-300'
        : 'text-emerald-300';
  const concentrationDescription = !hasHoldings || !topPosition
    ? (language === 'zh' ? '暂无持仓，保存持仓流水后生成集中度。' : 'No holdings yet. Save holding records to generate concentration.')
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
    valuationLineageTrustItem,
    hasPriceFallback
      ? { key: 'valuation-delayed', label: language === 'zh' ? '价格可能延迟' : 'Pricing may be delayed', variant: 'caution' }
      : hasLimitedConfidence
        ? { key: 'valuation-limited', label: limitedConfidenceLabel(language), variant: 'caution' }
      : hasHoldings
        ? { key: 'valuation-reliable', label: language === 'zh' ? '估值已更新' : 'Valuation current', variant: 'success' }
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
    portfolioEvidenceSummary
      ? {
        key: `risk-posture-${portfolioEvidenceSummary.posture}`,
        label: sanitizePortfolioConsumerLabel(portfolioEvidenceSummary.displayLabel, language) || (language === 'zh' ? '数据状态待确认' : 'Data status pending'),
        variant: portfolioEvidenceSummary.tone === 'danger'
          ? 'danger'
          : portfolioEvidenceSummary.tone === 'warning'
            ? 'caution'
            : portfolioEvidenceSummary.tone === 'info'
              ? 'info'
              : portfolioEvidenceSummary.tone === 'success'
                ? 'success'
                : 'neutral',
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
  const holdingsPrimaryValue = hasHoldings
    ? (language === 'zh' ? `${positionRows.length} 项持仓` : `${positionRows.length} holdings`)
    : (language === 'zh' ? '无持仓' : 'No holdings');
  const accountStateSummary = !hasActiveAccounts
    ? (language === 'zh' ? '暂无可用账户' : 'No available account')
    : selectedAccount === 'all'
      ? (language === 'zh' ? `${activeAccounts.length} 个活跃账户` : `${activeAccounts.length} active accounts`)
      : scopedAccount?.name || copy.allAccounts;
  const compactNoHoldingText = language === 'zh'
    ? '暂无持仓。添加持仓或导入交易后显示组合状态。'
    : 'No holdings yet. Add holdings or import transactions to show portfolio state.';
  const addHoldingActionLabel = language === 'zh' ? '添加持仓' : 'Add holding';
  const importTradesActionLabel = language === 'zh' ? '导入交易' : 'Import transactions';
  const manualLedgerActionLabel = language === 'zh' ? '手工记账' : 'Manual ledger';
  const scenarioRiskPositions = useMemo<PortfolioScenarioRiskVisiblePosition[]>(
    () => positionRows.map((row) => ({
      symbol: row.symbol,
      marketValue: row.marketValueBase,
      marketValueBase: row.marketValueBase,
      bucketLabel: row.accountName,
      currency: row.currency || row.valuationCurrency || null,
    })),
    [positionRows],
  );
  const syncDataActionLabel = language === 'zh' ? '同步数据' : 'Sync data';
  const openManualLedger = (nextLeftTab: 'trade' | 'account' | 'sync' | 'fx', nextTradeType?: TradeFormType) => {
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
      : hasPriceFallback || snapshot?.fxStale || hasLimitedConfidence
        ? {
          key: 'hero-valuation-delayed',
          label: language === 'zh' ? '估值可能延迟' : 'Valuation may be delayed',
          variant: 'caution',
        }
        : hasHoldings
          ? {
            key: 'hero-valuation-current',
            label: language === 'zh' ? '估值已更新' : 'Valuation current',
            variant: 'success',
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
          },
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
    : (language === 'zh' ? '持仓列表将在保存记录后出现' : 'Holdings appear after records are saved');
  const valuationSnapshotNote = hasHoldings
    ? summarizePortfolioPriceAsOf(positionRows, language)?.label
      || (language === 'zh' ? '价格快照待确认' : 'Price snapshot pending')
    : (language === 'zh' ? '暂无价格快照' : 'No price snapshot yet');
  const nextActionHeadline = !hasAccounts
    ? (language === 'zh' ? '先创建一个组合账户' : 'Create your first portfolio account')
    : !hasHoldings
      ? (language === 'zh' ? '先补第一笔持仓或导入交易' : 'Add the first holding or import transactions')
      : hasFxUnavailable
        ? (language === 'zh' ? '先确认汇率与估值状态' : 'Check FX and valuation status first')
        : hasHistory
          ? (language === 'zh' ? '继续跟踪近期活动与调仓节奏' : 'Review recent activity and rebalance pace')
          : (language === 'zh' ? '继续补充记录，完善组合画像' : 'Add more records to complete the portfolio picture');
  const nextActionBody = !hasAccounts
    ? (language === 'zh'
      ? '账户创建后即可记录持仓、导入交易并查看组合风险。'
      : 'After the account is created, you can record holdings, import transactions, and review risk.')
    : !hasHoldings
      ? (language === 'zh'
        ? '当前组合仍为空；建议优先添加持仓，或从现有券商流水导入。'
        : 'The portfolio is still empty. Add holdings first or import an existing broker ledger.')
      : hasFxUnavailable
        ? (language === 'zh'
          ? '部分汇率或折算暂不可用，先查看估值说明，再决定是否同步或刷新。'
          : 'Some FX or conversion data is unavailable. Review valuation notes before syncing or refreshing.')
        : hasHistory
          ? (language === 'zh'
            ? '近期活动已保留在下方时间线，可继续核对风险与持仓集中度。'
            : 'Recent activity remains in the timeline below. Continue by checking risk and concentration.')
          : (language === 'zh'
            ? '当前组合已可观察，下一步可补录现金、公司行为或同步新数据。'
            : 'The portfolio is ready to observe. Next you can add cash flows, corporate actions, or sync new data.');
  const hasFreshValuationState = !hasFxUnavailable && !hasPriceFallback && !snapshot?.fxStale && !hasLimitedConfidence;
  const holdingsTableStatusLabel = language === 'zh' ? '状态' : 'Status';

  const handleToggleTradeActionMenu = (id: number) => {
    setOpenTradeActionMenuId((prev) => (prev === id ? null : id));
  };

  const historyPanelContent = (
    <div className="flex h-full min-h-0 flex-col bg-[var(--surface-1)] lg:bg-transparent">
      <div className="flex items-center justify-between gap-3 border-b border-white/5 px-0 pb-4">
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
              onChange={(next) => setEventType(next as EventType)}
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
                <div key={`trade-${item.id}`} className="border-b border-white/5 px-1 py-4 transition-colors hover:bg-white/[0.03]">
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
                <div key={`cash-${item.id}`} className="border-b border-white/5 px-1 py-4 transition-colors hover:bg-white/[0.03]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-foreground">{formatCashDirectionLabel(item.direction, language)} <span className="text-xs text-muted-text">{item.currency}</span></div>
                      <div className="mt-1 text-xs text-muted-text">{item.eventDate} · {formatMoney(item.amount, item.currency)}</div>
                    </div>
                    <Button type="button" variant="ghost" className={PORTFOLIO_DANGER_GHOST_CLASS} onClick={() => setPendingDelete({ eventType: 'cash', id: item.id, message: copy.cashDeleteMessage(item) })} aria-label={copy.deleteConfirm} title={copy.deleteConfirm}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </Button>
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
                <div key={`corporate-${item.id}`} className="border-b border-white/5 px-1 py-4 transition-colors hover:bg-white/[0.03]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatCorporateActionLabel(item.actionType, language)}</span></div>
                      <div className="mt-1 text-xs text-muted-text">
                        {item.effectiveDate}
                        {item.cashDividendPerShare != null ? ` · ${copy.dividendPerShare} ${item.cashDividendPerShare}` : ''}
                        {item.splitRatio != null ? ` · ${copy.splitRatio} ${item.splitRatio}` : ''}
                      </div>
                    </div>
                    <Button type="button" variant="ghost" className={PORTFOLIO_DANGER_GHOST_CLASS} onClick={() => setPendingDelete({ eventType: 'corporate', id: item.id, message: copy.corporateDeleteMessage(item) })} aria-label={copy.deleteConfirm} title={copy.deleteConfirm}>
                      <Trash2 className="size-4" aria-hidden="true" />
                    </Button>
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
          <span className="text-[10px] font-bold uppercase tracking-widest text-white/35">{viewFullHistoryLabel}</span>
        ) : null}
      </div>
      {hasHistory ? (
        <div className="flex flex-col gap-2">
          {tradeEvents.slice(0, 5).map((item) => (
            <div key={`recent-trade-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatSideLabel(item.side, language)}</span></div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.tradeDate} · {item.quantity} @ {item.price}</div>
              </div>
              <div className="flex shrink-0 items-start gap-2">
                <span className="font-mono text-xs text-white/45">{item.currency}</span>
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
              </div>
            </div>
          ))}
          {cashEvents.slice(0, Math.max(0, 5 - tradeEvents.length)).map((item) => (
            <div key={`recent-cash-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{formatCashDirectionLabel(item.direction, language)}</div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.eventDate} · {formatMoney(item.amount, item.currency)}</div>
              </div>
              <span className="shrink-0 font-mono text-xs text-white/45">{item.currency}</span>
            </div>
          ))}
          {corporateEvents.slice(0, Math.max(0, 5 - tradeEvents.length - cashEvents.length)).map((item) => (
            <div key={`recent-corporate-${item.id}`} className="flex items-start justify-between gap-3 border-b border-white/5 px-1 py-2.5 last:border-b-0">
              <div className="min-w-0">
                <div className="truncate text-sm text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatCorporateActionLabel(item.actionType, language)}</span></div>
                <div className="mt-1 truncate text-xs text-muted-text">{item.effectiveDate}</div>
              </div>
              <span className="shrink-0 font-mono text-xs text-white/45">ACT</span>
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
          'w-full flex-1 flex flex-col min-h-0 min-w-0 bg-transparent text-white/72',
        )}
      >
        <ConsumerWorkspaceScope className="flex-1">
        <ConsumerWorkspacePageShell className="flex-1 min-w-0 min-h-0">
          <TerminalGrid data-testid="portfolio-workspace-grid">
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
                    <h1 className="text-[10px] font-bold uppercase tracking-[0.22em] text-white/40">
                      {language === 'zh' ? '组合总览' : 'Portfolio Overview'}
                    </h1>
                    <TerminalChip variant="neutral">
                      {selectedAccount === 'all' ? copy.allAccounts : scopedAccount?.name || copy.allAccounts}
                    </TerminalChip>
                  </div>
                  <h2 className="mt-3 text-[12px] font-medium uppercase tracking-[0.18em] text-white/38">
                    {totalAssetsTitle}
                  </h2>
                  <div
                    data-testid="portfolio-total-assets-value"
                    className="mt-2 font-mono text-[2.2rem] font-semibold leading-none text-white tabular-nums md:text-[2.75rem]"
                  >
                    {formatDisplayMoney(totalEquity, totalEquityDisplay, snapshotCurrency)}
                  </div>
                  <p className="mt-3 max-w-[72ch] text-sm leading-6 text-white/62">
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
                      onChange={(value) => setSelectedAccount(value === 'all' ? 'all' : Number(value))}
                      options={[
                        { value: 'all', label: copy.allAccounts },
                        ...activeAccounts.map((account) => ({ value: String(account.id), label: account.name })),
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

                  <div className="rounded-[14px] border border-white/[0.05] bg-white/[0.03] px-4 py-3">
                    <div className="grid grid-cols-2 gap-3 text-xs text-white/45">
                      <div>
                        <div className="uppercase tracking-[0.18em] text-white/32">{language === 'zh' ? '账户范围' : 'Scope'}</div>
                        <div className="mt-1 text-sm text-white/72">{accountStateSummary}</div>
                      </div>
                      <div>
                        <div className="uppercase tracking-[0.18em] text-white/32">{language === 'zh' ? '当前状态' : 'State'}</div>
                        <div className="mt-1 text-sm text-white/72">{holdingsPrimaryValue}</div>
                      </div>
                    </div>
                  </div>

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
                </div>
              </TerminalPanel>
            </div>

            <div data-testid="portfolio-row-summary" className="order-2 col-span-12 min-w-0">
              <div data-testid="portfolio-summary-strip" className="grid min-w-0 grid-cols-1 gap-3 lg:grid-cols-3">
                <TerminalPanel as="section" data-testid="portfolio-summary-cash-card" className="min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/38">{copy.totalCash}</div>
                  <div className="mt-2 font-mono text-xl text-white tabular-nums">{formatDisplayMoney(totalCash, totalCashDisplay, snapshotCurrency)}</div>
                  <div className="mt-2 text-xs text-white/40">{language === 'zh' ? '可用于继续配置或缓冲波动。' : 'Available for new allocation or downside buffer.'}</div>
                </TerminalPanel>
                <TerminalPanel as="section" data-testid="portfolio-summary-market-value-card" className="min-w-0">
                  <div className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/38">{copy.totalMarketValue}</div>
                  <div className="mt-2 font-mono text-xl text-white tabular-nums">{formatDisplayMoney(totalMarketValue, totalMarketValueDisplay, snapshotCurrency)}</div>
                  <div className="mt-2 text-xs text-white/40">{holdingsHeaderNote}</div>
                </TerminalPanel>
                <TerminalPanel as="section" data-testid="portfolio-pnl-summary" className="min-w-0">
                  <div data-testid="portfolio-pnl-total" className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/38">{pnlLabels.total}</div>
                  <div className={`mt-2 font-mono text-xl tabular-nums ${totalPnl >= 0 ? 'text-emerald-300' : 'text-rose-300'}`}>
                    {totalPnlDisplay ? formatSignedMoney(totalPnlDisplay.value, displayCurrency) : formatSignedMoney(totalPnl, pnlSourceCurrency)}
                  </div>
                  <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-xs text-white/40">
                    <span data-testid="portfolio-pnl-realized">{pnlLabels.realized} {realizedPnlDisplay ? formatSignedMoney(realizedPnlDisplay.value, displayCurrency) : formatSignedMoney(realizedPnl, pnlSourceCurrency)}</span>
                    <span data-testid="portfolio-pnl-unrealized">{pnlLabels.unrealized} {unrealizedPnlDisplay ? formatSignedMoney(unrealizedPnlDisplay.value, displayCurrency) : formatSignedMoney(unrealizedPnl, pnlSourceCurrency)}</span>
                  </div>
                </TerminalPanel>
              </div>
            </div>

            <div data-testid="portfolio-row-routing" className="order-3 col-span-12 min-w-0 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(340px,5fr)] 2xl:gap-5 items-start">
              <div data-testid="portfolio-primary-lane" className="min-w-0 flex flex-col gap-4">
                <TerminalPanel
                  as="section"
                  data-testid="portfolio-current-holdings-panel"
                  className="min-w-0 flex flex-col overflow-hidden"
                >
                  <div className="flex flex-wrap items-start justify-between gap-3 border-b border-white/5 pb-4">
                    <div className="min-w-0">
                      <h2 className="min-w-0 text-xs uppercase tracking-widest text-muted-text">
                        {hasHoldings
                          ? (language === 'zh' ? `当前持仓（共 ${positionRows.length} 项）` : `Current Holdings (${positionRows.length})`)
                          : (language === 'zh' ? '当前持仓' : 'Current holdings')}
                      </h2>
                      <p className="mt-2 text-sm text-white/45">{holdingsHeaderNote}</p>
                    </div>
                    <div className="shrink-0 text-right text-xs text-white/38">
                      <div>{language === 'zh' ? '价格快照' : 'Pricing snapshot'}</div>
                      <div className="mt-1 text-white/60">{valuationSnapshotNote}</div>
                    </div>
                  </div>

                  <div className="pt-3 lg:max-h-[560px] lg:min-h-0 lg:overflow-y-auto lg:no-scrollbar lg:[&::-webkit-scrollbar]:hidden lg:[-ms-overflow-style:none] lg:[scrollbar-width:none]">
                    {hasHoldings ? (
                      <TerminalDenseTable className="border-0 bg-transparent">
                        <table className="min-w-[760px] w-full text-left text-xs">
                          <thead className="text-white/35">
                            <tr className="border-b border-white/5">
                              {[
                                language === 'zh' ? '标的' : 'Symbol',
                                language === 'zh' ? '数量' : 'Qty',
                                language === 'zh' ? '成本' : 'Cost',
                                language === 'zh' ? '市值' : 'Market Value',
                                language === 'zh' ? '盈亏' : 'P&L',
                                holdingsTableStatusLabel,
                                language === 'zh' ? '操作' : 'Action',
                              ].map((label) => (
                                <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {positionRows.map((row) => {
                              const rowTrustItems = uniqueTrustItems([
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

                              return (
                                <tr key={`${row.accountId}-${row.symbol}-${row.market}`} className="border-b border-white/5 text-white/62 transition-colors hover:bg-white/[0.03]">
                                  <td className="px-3 py-2">
                                    <div className="truncate font-mono text-sm text-white">{row.symbol}</div>
                                    <div className="truncate text-[11px] text-white/35">
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
                                    {row.valuationCurrency !== displayCurrency ? <div className="mt-1 text-[11px] text-white/35">{formatConvertedDisplay(row.marketValueBase, row.valuationCurrency)}</div> : null}
                                    <div className={`mt-1 text-[11px] ${row.isPriceFallback ? 'text-amber-300' : 'text-white/35'}`}>
                                      {row.priceAsOf
                                        ? `${formatMoney(row.lastPrice, row.currency)} · ${language === 'zh' ? `截至 ${row.priceAsOf}` : `As of ${row.priceAsOf}`}`
                                        : `${formatMoney(row.lastPrice, row.currency)} · ${positionPriceFreshnessExplanation(row, language)}`}
                                    </div>
                                  </td>
                                  <td className={`px-3 py-2 font-mono ${row.unrealizedPnlBase >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                    {formatSignedMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                                    <div className="mt-1 text-[11px] text-white/40">{formatPercent(row.unrealizedPnlPct)}</div>
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
                                      <span className="text-white/35">--</span>
                                    )}
                                  </td>
                                  <td className="px-3 py-2">
                                    <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} onClick={() => openManualLedger('trade', 'stock')}>
                                      {manualLedgerActionLabel}
                                    </Button>
                                  </td>
                                </tr>
                              );
                            })}
                          </tbody>
                        </table>
                      </TerminalDenseTable>
                    ) : (
                      <div data-testid="portfolio-empty-workflow-column" className="min-w-0">
                        <TerminalEmptyState
                          data-testid="portfolio-start-card"
                          title={language === 'zh' ? '暂无持仓' : 'No holdings'}
                          action={hasHistory ? <TerminalChip variant="caution" className="shrink-0">{noHoldingsHistoryNote}</TerminalChip> : undefined}
                          className="min-h-[72px]"
                        >
                          {compactNoHoldingText}
                        </TerminalEmptyState>
                        <div className="mt-3 flex flex-wrap gap-2">
                          <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={() => openManualLedger('trade', 'stock')}>
                            {addHoldingActionLabel}
                          </TerminalButton>
                          <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                            {importTradesActionLabel}
                          </TerminalButton>
                        </div>
                        {!hasWritableAccounts ? (
                          <TerminalNotice variant="caution" className="mt-3">
                            {hasActiveAccounts
                              ? (language === 'zh' ? '当前账户不可写，请选择具体可写账户。' : 'Current accounts are not writable. Select a writable account.')
                              : (language === 'zh' ? '暂无可写账户，请先创建账户。' : 'No writable account yet. Create an account first.')}
                          </TerminalNotice>
                        ) : null}
                      </div>
                    )}
                  </div>
                </TerminalPanel>
              </div>

              <div data-testid="portfolio-secondary-lane" className="min-w-0 flex flex-col gap-4">
                <TerminalPanel as="section" data-testid="portfolio-risk-card" className="min-w-0 flex flex-col gap-4">
                  <div className="flex flex-wrap items-start justify-between gap-3">
                    <div>
                      <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">{riskTitle}</h2>
                      <p className="mt-1 text-sm text-white/45">
                        {hasHoldings
                          ? (language === 'zh' ? '先看集中度，再看币种与市场暴露。' : 'Start with concentration, then review currency and market exposure.')
                          : (language === 'zh' ? '暂无持仓，风险画像将在持仓出现后自动生成。' : 'Risk profile appears automatically once holdings exist.')}
                      </p>
                    </div>
                    <span data-testid="portfolio-concentration-label">
                      <PillBadge
                        variant={topPositionPercent >= 50 ? 'danger' : topPositionPercent >= 20 ? 'warning' : hasHoldings ? 'success' : 'default'}
                        className={hasHoldings ? concentrationToneClass : 'text-white/35'}
                      >
                        {concentrationLabel}
                      </PillBadge>
                    </span>
                  </div>
                  <div data-testid="portfolio-risk-overview" className="grid grid-cols-1 gap-2 sm:grid-cols-3">
                    <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '最大持仓' : 'Largest Position'}</div>
                      <div className="mt-2 truncate text-sm text-white">{topPosition?.label || '--'}</div>
                      <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topPosition?.percent)}</div>
                    </div>
                    <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '主币种' : 'Primary Currency'}</div>
                      <div className="mt-2 truncate text-sm text-white">{topCurrency?.label || '--'}</div>
                      <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topCurrency?.percent)}</div>
                    </div>
                    <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '主市场' : 'Primary Market'}</div>
                      <div className="mt-2 truncate text-sm text-white">{formatExposureMarketLabel(topMarket, language)}</div>
                      <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topMarket?.percent)}</div>
                    </div>
                  </div>
                  <div data-testid="portfolio-concentration-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                    <div className="flex items-center justify-between gap-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '持仓集中度' : 'Concentration'}</div>
                      <div className={`font-mono text-xs ${hasHoldings ? concentrationToneClass : 'text-white/35'}`}>{formatPercent(topPosition?.percent)}</div>
                    </div>
                    <p className="mt-2 text-xs leading-5 text-white/45">{concentrationDescription}</p>
                  </div>
                  <div data-testid="portfolio-risk-hints" className="flex flex-wrap gap-1.5">
                    {(riskHintTexts.length ? riskHintTexts : [language === 'zh' ? '暂无显著集中风险' : 'No notable concentration risk']).map((hint) => (
                      <PillBadge key={hint} variant="default" className="text-white/55">{hint}</PillBadge>
                    ))}
                    {safeRiskWarningLabels.map((warning) => (
                      <PillBadge key={warning} variant="warning" className="text-white/55">{warning}</PillBadge>
                    ))}
                  </div>
                  <PortfolioScenarioRiskPanel
                    snapshotAsOf={snapshot?.asOf}
                    positions={scenarioRiskPositions}
                    onRunScenario={(payload) => portfolioApi.projectScenarioRisk(payload)}
                  />
                </TerminalPanel>

                <TerminalPanel as="section" data-testid="portfolio-valuation-panel" className="min-w-0 flex flex-col gap-4">
                  <div>
                    <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">{language === 'zh' ? '估值与新鲜度' : 'Valuation freshness'}</h2>
                    <p className="mt-1 text-sm text-white/45">
                      {hasFreshValuationState
                        ? (language === 'zh' ? '当前估值可直接用于观察组合表现。' : 'Current valuation is ready for portfolio observation.')
                        : consumerDataNotice || (language === 'zh' ? '部分估值信息仍在确认，请结合下方数据说明阅读。' : 'Some valuation details are still being confirmed. Review the notes below for context.')}
                    </p>
                  </div>
                  <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
                    <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '价格快照' : 'Pricing snapshot'}</div>
                      <div className="mt-2 text-sm text-white">{valuationSnapshotNote}</div>
                    </div>
                    <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3">
                      <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '汇率更新时间' : 'FX updated'}</div>
                      <div className="mt-2 text-sm text-white">{hasFxUnavailable ? fxUnavailableLabel : fxLastUpdated}</div>
                    </div>
                  </div>
                  {valuationTrustItems.length ? (
                    <PortfolioTrustStrip
                      title={language === 'zh' ? '估值状态' : 'Valuation state'}
                      items={valuationTrustItems.slice(0, 3)}
                      data-testid="portfolio-valuation-trust-strip"
                    />
                  ) : null}
                </TerminalPanel>

                <TerminalPanel as="section" data-testid="portfolio-next-action-panel" className="min-w-0 flex flex-col gap-4">
                  <div>
                    <h2 className="text-[10px] font-bold uppercase tracking-[0.18em] text-white/40">{language === 'zh' ? '下一步' : 'Next action'}</h2>
                    <p className="mt-1 text-sm text-white">{nextActionHeadline}</p>
                    <p className="mt-2 text-xs leading-5 text-white/45">{nextActionBody}</p>
                  </div>
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
                  <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3 text-xs text-white/45">
                    {hasHistory
                      ? (language === 'zh' ? `近期已记录 ${totalHistoryRows} 条活动，可在下方时间线继续核对。` : `${totalHistoryRows} recent records are available in the timeline below.`)
                      : (language === 'zh' ? '近期活动会在保存持仓、现金或公司行为后出现在下方。' : 'Recent activity appears below after holdings, cash, or corporate records are saved.')}
                  </div>
                </TerminalPanel>
              </div>
            </div>

            <div data-testid="portfolio-row-notes" className="order-4 col-span-12 min-w-0">
              <details data-testid="portfolio-data-notes" className="group rounded-[16px] border border-white/[0.05] bg-white/[0.02]">
                <summary className="flex cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-sm text-white/72 outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40 [&::-webkit-details-marker]:hidden">
                  <span>{language === 'zh' ? '查看数据说明与配置细节' : 'View data notes and allocation detail'}</span>
                  <span className="rounded-lg border border-white/8 bg-white/[0.03] px-3 py-1 text-[11px] font-semibold text-white/45 group-open:text-cyan-100">
                    {language === 'zh' ? '展开' : 'Expand'}
                  </span>
                </summary>
                <div className="grid gap-4 border-t border-white/[0.04] px-4 pb-4 pt-4 xl:grid-cols-[minmax(0,1.15fr)_minmax(0,0.85fr)]">
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
                                  <div className="truncate text-sm font-medium text-white">{formatExposureRowLabel(row)}</div>
                                  <div className="mt-1 text-xs text-white/40">
                                    {formatPercent(row.percent)}
                                    {row.fxStatus === 'unavailable' ? ` · ${fxUnavailableLabel}` : ''}
                                  </div>
                                </div>
                                <div className="shrink-0 text-right">
                                  <div className="font-mono text-sm text-white tabular-nums">{values.display}</div>
                                  {values.native ? <div className="mt-1 font-mono text-[11px] text-white/35">{values.native}</div> : null}
                                </div>
                              </div>
                              <div className="mt-2 h-1.5 overflow-hidden rounded-full bg-white/[0.04]">
                                <div className="h-full rounded-full bg-emerald-400/70" style={{ width: `${Math.max(2, Math.min(100, row.percent || 0))}%` }} />
                              </div>
                              {exposureTab === 'symbol' && row.unrealizedPnl != null ? (
                                <div className="mt-2 flex justify-between gap-3 text-xs text-white/40">
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
                        <p className="mt-2 text-sm leading-6 text-white/45">
                          {language === 'zh' ? '这里保留估值来源、风险参考与折算状态的消费者可读说明。' : 'This section keeps consumer-readable notes about valuation lineage, risk references, and conversion state.'}
                        </p>
                      )}
                    </div>
                    <div className="grid grid-cols-1 gap-2">
                      <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3 text-sm text-white/72">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.snapshotBasisTitle}</div>
                        <div className="mt-2">{valuationSnapshotNote}</div>
                      </div>
                      <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3 text-sm text-white/72">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.fxState}</div>
                        <div className="mt-2">{snapshot?.fxStale ? copy.fxStale : copy.fxFresh}</div>
                      </div>
                      <div className="rounded-xl border border-white/[0.02] bg-black/20 p-3 text-sm text-white/72">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.costMethod}</div>
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
					          <TerminalPanel as="section" data-testid="portfolio-trade-station-card" data-execution-surface="manual-record-entry" className="min-w-0 flex flex-col gap-4 overflow-visible xl:min-h-0">
            <div className="shrink-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm text-muted-text uppercase tracking-widest">{language === 'zh' ? '手工记账台' : 'Manual Ledger'}</h2>
                  <p className="mt-1 text-xs leading-5 text-white/45">{manualLedgerDisclosure}</p>
                </div>
              </div>
              <details
                data-testid="portfolio-manual-record-disclosure"
                open={manualLedgerOpen}
                onToggle={(event) => setManualLedgerOpen(event.currentTarget.open)}
                className="group mt-4 rounded-[16px] border border-white/[0.05] bg-black/20 open:bg-white/[0.02]"
              >
                <summary className="flex min-h-[56px] cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40 [&::-webkit-details-marker]:hidden">
                  <span className="min-w-0">
                    <span className="block text-sm font-medium text-white">{language === 'zh' ? '手工记账' : 'Manual ledger'}</span>
                  </span>
                  <span className="shrink-0 rounded-lg border border-white/8 bg-white/[0.03] px-3 py-1 text-[11px] font-semibold text-white/50 group-open:text-cyan-100">
                    {copy.submitTrade}
                  </span>
                </summary>
                <div className="border-t border-white/[0.04] px-4 pb-4 pt-4">
              <div className="grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <Select
                  label={language === 'zh' ? '记账账户' : 'Ledger account'}
                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                  value={String(selectedTradeAccount)}
                  onChange={(value) => setSelectedTradeAccount(value === 'all' ? 'all' : Number(value))}
                  options={[
                    { value: 'all', label: copy.allAccounts },
                    ...writableAccounts.map((account) => ({ value: String(account.id), label: account.name })),
                  ]}
                  className={PORTFOLIO_SELECT_CLASS}
                  controlClassName="rounded-lg"
                />
                <Select
                  label={language === 'zh' ? '成本方法' : 'Cost method'}
                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                  value={costMethod}
                  onChange={(value) => setCostMethod(value as PortfolioCostMethod)}
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
              <div data-testid="portfolio-trade-station-summary" className="mt-3 flex flex-col gap-1 border-y border-white/5 py-2">
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

            <div className="shrink-0 border-b border-white/5 pt-4 pb-4">
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
                      tradeCurrencyManuallyEdited={tradeCurrencyManuallyEdited}
                      writableAccountBaseCurrency={writableAccount?.baseCurrency}
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
                  onDeleteAccount={(account) => setPendingAccountDelete({ id: account.id, name: account.name })}
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
                    <p>{selectedBroker === 'ibkr' ? copy.ibkrImportHint : copy.brokerImportHint}</p>
                  </div>
                  <Select label={language === 'zh' ? '导入来源' : 'Broker'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={selectedBroker} onChange={setSelectedBroker} options={brokers.map((broker) => ({ value: broker.broker, label: formatBrokerLabel(broker.broker, broker.displayName, language) }))} />
                  {selectedBroker === 'ibkr' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="space-y-3">
                      <PortfolioIbkrImportHeader copy={copy} />
                      {ibkrConnection ? <p className="text-sm text-foreground">{ibkrConnection.connectionName}</p> : null}
                      <Input label={language === 'zh' ? 'IBKR API 地址' : 'IBKR API base URL'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrApiBasePlaceholder} value={ibkrApiBaseUrl} onChange={(e) => setIbkrApiBaseUrl(e.target.value)} />
                      <Input label={language === 'zh' ? 'IBKR 账户引用' : 'IBKR account ref'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrAccountRefPlaceholder} value={ibkrBrokerAccountRef} onChange={(e) => setIbkrBrokerAccountRef(e.target.value)} />
                      <Input label={language === 'zh' ? 'IBKR 会话令牌' : 'IBKR session token'} labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrSessionTokenPlaceholder} value={ibkrSessionToken} onChange={(e) => setIbkrSessionToken(e.target.value)} />
                      <Checkbox checked={ibkrVerifySsl} onChange={(e) => setIbkrVerifySsl(e.target.checked)} label={copy.verifyIbkrSsl} containerClassName="text-xs text-secondary-text" />
                      <Button type="button" variant="primary" className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`} onClick={() => void handleSyncIbkr()} disabled={!writableAccountId || ibkrSyncing}>
                        {ibkrSyncing ? copy.syncing : copy.syncIbkr}
                      </Button>
                      {ibkrSyncResult ? <PortfolioIbkrSyncResultCard copy={copy} result={ibkrSyncResult} /> : null}
                    </SectionShell>
                  ) : (
                    <div className="rounded-2xl border border-white/5 bg-white/[0.02] p-4 text-xs text-secondary-text">
                      {copy.brokerImportHint}
                    </div>
                  )}
                </div>
              ) : null}

              {leftTab === 'fx' ? (
                <div data-testid="portfolio-fx-panel" className="space-y-4">
                  <div>
	                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{language === 'zh' ? '汇率参考' : 'Exchange-rate reference'}</p>
                    <p className="mt-1 text-[11px] text-white/35">
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
                    <span className="mb-2 flex h-10 w-8 items-center justify-center rounded-lg bg-white/[0.04] text-white/45" aria-hidden="true">⇄</span>
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
		                    <div className="text-[11px] uppercase tracking-[0.16em] text-white/35">
		                      {fxBaseCurrency}/{fxQuoteCurrency}
		                    </div>
	                    <div data-testid="portfolio-fx-rate-value" className="mt-2 flex items-baseline gap-1.5 whitespace-nowrap">
	                      <span className="text-sm text-white/60">1 {fxBaseCurrency} =</span>
	                      {' '}
	                      <span className="font-mono text-xl text-indigo-400">{selectedFxRate ? formatFxRate(selectedFxRate.rate) : '--'}</span>
	                      {' '}
		                      <span className="text-sm text-white/60">{fxQuoteCurrency}</span>
		                    </div>
		                    <div className="mt-3 flex min-w-0 flex-wrap items-center gap-2 text-[10px] font-bold uppercase tracking-widest text-white/40">
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
              </div>
            </div>
	          </TerminalGrid>
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
          tradeEditCurrencyManuallyEditedRef.current = false;
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
                onChange={(value) => setEditingTrade((prev) => (prev ? { ...prev, accountId: Number(value) } : prev))}
                options={writableAccounts.map((account) => ({ value: String(account.id), label: account.name }))}
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
                      currency: tradeEditCurrencyManuallyEditedRef.current
                        ? prev.currency
                        : inferSettlementCurrency(e.target.value, editingAccount?.baseCurrency),
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
                value={editingTrade.currency}
                onChange={(value) => {
                  tradeEditCurrencyManuallyEditedRef.current = true;
                  setEditingTrade((prev) => (prev ? { ...prev, currency: value } : prev));
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
                  tradeEditCurrencyManuallyEditedRef.current = false;
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
