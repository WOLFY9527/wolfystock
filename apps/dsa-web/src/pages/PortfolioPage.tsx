import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { MoreHorizontal, PenSquare, RefreshCw, Trash2 } from 'lucide-react';
import { portfolioApi } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button, Checkbox, ConfirmDialog, Drawer, Input, PillBadge, SectionShell, SegmentedControl, Select } from '../components/common';
import { EvidenceChips } from '../components/evidence/EvidenceChips';
import {
  TerminalButton,
  TerminalDenseList,
  TerminalDenseTable,
  TerminalChip,
  TerminalEmptyState,
  TerminalGrid,
  TerminalMetric,
  TerminalNestedBlock,
  TerminalNotice,
  TerminalPageShell,
  TerminalPanel,
} from '../components/terminal';
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

const PORTFOLIO_FIELD_LABEL_CLASS = '!mb-1 text-[10px] font-bold uppercase tracking-widest text-white/40';
const PORTFOLIO_FIELD_WRAPPER_CLASS = 'flex flex-col gap-1.5';
const PORTFOLIO_FORM_GRID_CLASS = 'mt-4 grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2';
const PORTFOLIO_INPUT_CLASS = 'h-10 rounded-lg border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm text-white placeholder:text-white/20 outline-none focus:border-emerald-500/50';
const PORTFOLIO_SELECT_CLASS = 'min-w-0';
const PORTFOLIO_PRIMARY_BUTTON_CLASS = 'border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[#6f79dc] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SUBMIT_BUTTON_CLASS = 'mt-5 w-full border border-[color:var(--wolfy-accent)] bg-[var(--wolfy-accent)] text-[#f7f8ff] font-medium px-5 py-2.5 rounded-md transition-colors hover:bg-[#6f79dc] disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SECONDARY_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] hover:border-[color:var(--wolfy-divider)] px-4 py-2.5 rounded-md transition-colors';
const PORTFOLIO_TEXT_BUTTON_CLASS = 'border border-[color:var(--wolfy-border-subtle)] bg-transparent text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)] px-3 py-1.5 rounded-md text-xs transition-colors disabled:text-white/15 disabled:opacity-50';
const PORTFOLIO_ICON_BUTTON_CLASS = 'h-9 w-9 rounded-md border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] p-0 text-[color:var(--wolfy-text-secondary)] hover:text-[color:var(--wolfy-text-primary)]';
const PORTFOLIO_DANGER_GHOST_CLASS = 'h-8 w-8 rounded-md border border-[color:color-mix(in_srgb,var(--wolfy-market-down)_34%,transparent)] bg-transparent p-0 text-[color:var(--wolfy-market-down)] hover:bg-[color:color-mix(in_srgb,var(--wolfy-market-down)_10%,transparent)]';
const CASH_CURRENCY_OPTIONS = ['CNY', 'HKD', 'USD'] as const;
const FX_CURRENCY_OPTIONS = ['USD', 'CNY', 'HKD', 'EUR', 'JPY', 'GBP'] as const;

const DEFAULT_PAGE_SIZE = 20;
const FALLBACK_BROKERS: PortfolioImportBrokerItem[] = [
  { broker: 'huatai', aliases: [], displayName: translate('zh', 'portfolio.brokerName.huatai'), fileExtensions: ['csv'] },
  { broker: 'citic', aliases: ['zhongxin'], displayName: translate('zh', 'portfolio.brokerName.citic'), fileExtensions: ['csv'] },
  { broker: 'cmb', aliases: ['cmbchina', 'zhaoshang'], displayName: translate('zh', 'portfolio.brokerName.cmb'), fileExtensions: ['csv'] },
  { broker: 'ibkr', aliases: ['interactivebrokers'], displayName: translate('zh', 'portfolio.brokerName.ibkr'), fileExtensions: ['xml'] },
];

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

function positionPriceStateLabel(position: Pick<PortfolioPositionItem, 'isPriceFallback'>, language: PortfolioLanguage): string {
  if (position.isPriceFallback) {
    return language === 'zh' ? '估算价格' : 'Estimated price';
  }
  return language === 'zh' ? '现价快照' : 'Live quote';
}

function positionPriceSourceHint(
  position: Pick<PortfolioPositionItem, 'priceSource' | 'priceSourceLabel'>,
  language: PortfolioLanguage,
): string {
  switch (position.priceSource) {
    case 'avg_cost_fallback':
      return language === 'zh' ? '均价回退' : 'Avg-cost fallback';
    case 'broker_sync_snapshot':
      return language === 'zh' ? '同步快照' : 'Synced snapshot';
    case 'daily_close_quote':
      return language === 'zh' ? '收盘报价' : 'Daily close quote';
    default:
      return position.priceSourceLabel || (language === 'zh' ? '价格来源待确认' : 'Price source pending');
  }
}

function positionPriceFallbackReasonLabel(
  position: Pick<PortfolioPositionItem, 'priceFallbackReason'>,
  language: PortfolioLanguage,
): string | null {
  if (position.priceFallbackReason === 'current_quote_unavailable') {
    return language === 'zh' ? '现价缺失' : 'Current quote unavailable';
  }
  return null;
}

function positionPriceDisclosure(position: PortfolioPositionItem, language: PortfolioLanguage): string {
  const sourceHint = positionPriceSourceHint(position, language);
  const fallbackReason = positionPriceFallbackReasonLabel(position, language);
  const confidence = typeof position.valuationConfidence === 'number' && position.valuationConfidence < 1
    ? `${language === 'zh' ? '置信度' : 'Confidence'} ${Math.round(position.valuationConfidence * 100)}%`
    : null;
  return [
    positionPriceStateLabel(position, language),
    sourceHint,
    position.priceSourceLabel && position.priceSourceLabel !== sourceHint ? position.priceSourceLabel : null,
    fallbackReason,
    position.priceAsOf || null,
    confidence,
  ].filter(Boolean).join(' · ');
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

const PortfolioPage: React.FC = () => {
  const { isReady: isSafariReady, surfaceRef } = useSafariRenderReady();
  const shouldGuardA11y = shouldApplySafariA11yGuard();
  const { language, t } = useI18n();
  const copy = useMemo(() => getPortfolioCopy(t, language), [language, t]);

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
  const [accountForm, setAccountForm] = useState({
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
  const [tradeEditCurrencyManuallyEdited, setTradeEditCurrencyManuallyEdited] = useState(false);
  const [openTradeActionMenuId, setOpenTradeActionMenuId] = useState<number | null>(null);
  const [isNarrowViewport, setIsNarrowViewport] = useState(() => (
    typeof window !== 'undefined' ? window.innerWidth <= 390 : false
  ));

  const [tradeForm, setTradeForm] = useState({
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
  const [cashForm, setCashForm] = useState({
    eventDate: getTodayIso(),
    direction: 'in' as PortfolioCashDirection,
    amount: '',
    currency: '',
    note: '',
  });
  const [corpForm, setCorpForm] = useState({
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
  const activeAccounts = useMemo(() => accounts.filter((item) => item.isActive !== false), [accounts]);
  const writableAccounts = activeAccounts;
  const hasAccounts = accounts.length > 0;
  const hasActiveAccounts = activeAccounts.length > 0;
  const hasWritableAccounts = writableAccounts.length > 0;
  const scopedAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccount = selectedTradeAccount === 'all' ? undefined : writableAccounts.find((item) => item.id === selectedTradeAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const editingAccount = editingTrade ? activeAccounts.find((item) => item.id === editingTrade.accountId) : undefined;
  const ibkrConnection = useMemo(
    () => brokerConnections.find((item) => item.brokerType === 'ibkr') || null,
    [brokerConnections],
  );
  const currentEventCount = eventType === 'trade'
    ? tradeEvents.length
    : eventType === 'cash'
      ? cashEvents.length
      : corporateEvents.length;
  const inferredTradeCurrency = useMemo(
    () => inferSettlementCurrency(tradeForm.symbol, writableAccount?.baseCurrency),
    [tradeForm.symbol, writableAccount?.baseCurrency],
  );
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
  const inferredEditTradeCurrency = useMemo(
    () => inferSettlementCurrency(editingTrade?.symbol || '', editingAccount?.baseCurrency),
    [editingAccount?.baseCurrency, editingTrade?.symbol],
  );

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

  useEffect(() => {
    if (typeof window === 'undefined') {
      return undefined;
    }
    const handleResize = () => setIsNarrowViewport(window.innerWidth <= 390);
    handleResize();
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
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
        setRiskWarning(parsed.message || copy.riskFallback);
      }
    } catch (err) {
      setSnapshot(null);
      setError(getParsedApiError(err));
    } finally {
      setIsLoading(false);
    }
  }, [copy.riskFallback, costMethod, queryAccountId]);

  const loadEventsPage = useCallback(async (page: number) => {

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
  }, [
    eventActionType,
    eventDateFrom,
    eventDateTo,
    eventDirection,
    eventSide,
    eventSymbol,
    eventType,
    queryAccountId,
  ]);

  const loadEvents = useCallback(async () => {
    await loadEventsPage(eventPage);
  }, [eventPage, loadEventsPage]);

  const refreshPortfolioData = useCallback(async (page = eventPage) => {
    await Promise.all([loadSnapshotAndRisk(), loadEventsPage(page)]);
  }, [eventPage, loadEventsPage, loadSnapshotAndRisk]);

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
    if (!editingTrade || tradeEditCurrencyManuallyEdited) {
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
  }, [editingTrade, inferredEditTradeCurrency, tradeEditCurrencyManuallyEdited]);

  const positionRows: FlatPosition[] = useMemo(() => {
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
  }, [snapshot]);

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

  const openTradeEditor = useCallback((item: PortfolioTradeListItem) => {
    setOpenTradeActionMenuId(null);
    setTradeEditCurrencyManuallyEdited(false);
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
  }, []);

  const openTradeVoidDialog = useCallback((item: PortfolioTradeListItem) => {
    setOpenTradeActionMenuId(null);
    setPendingDelete({
      eventType: 'trade',
      id: item.id,
      title: deleteTradeTitle,
      message: deleteTradeMessage,
      confirmText: voidTradeConfirmLabel,
    });
  }, [deleteTradeMessage, deleteTradeTitle, voidTradeConfirmLabel]);

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
      setTradeEditCurrencyManuallyEdited(false);
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

  const reloadSnapshotAndRiskForScope = useCallback(async (
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
  }, [copy.riskFallback]);

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
        text: result.stale
          ? translate(language, 'portfolio.fxRefreshFallbackWarning', { updatedCount: 0, staleCount: 1, errorCount: result.error ? 1 : 0 })
          : translate(language, 'portfolio.fxRefreshUpdated', { count: 1 }),
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
  const fxRateRows = useMemo<PortfolioFxRateItem[]>(() => snapshot?.fxRates || [], [snapshot?.fxRates]);
  const fxLastUpdated = useMemo(() => {
    const timestamps = fxRateRows
      .map((item) => item.updatedAt || item.rateDate)
      .filter((value): value is string => Boolean(value));
    if (timestamps.length === 0) return '--';
    const sorted = timestamps.sort();
    return formatFxTimestamp(sorted[sorted.length - 1]);
  }, [fxRateRows]);
  const selectedFxRate = useMemo<DisplayFxRate | null>(() => {
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
  }, [fxBaseCurrency, fxQuoteCurrency, fxLastUpdated, fxRateRows, liveFxRate]);
  const totalEquity = snapshot?.totalEquity ?? 0;
  const totalCash = snapshot?.totalCash ?? 0;
  const totalMarketValue = snapshot?.totalMarketValue ?? 0;
  const totalUnrealizedPnl = positionRows.reduce((sum, row) => sum + row.unrealizedPnlBase, 0);
  const convertMoney = useCallback((value: number, fromCurrency: string | undefined | null): ConvertedMoney => {
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
  }, [displayCurrency, fxRateRows]);
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
  const historyHasNextPage = currentEventCount >= DEFAULT_PAGE_SIZE;
  const totalAssetsTitle = language === 'zh' ? '总资产' : 'Total Assets';
  const historyDrawerTitle = language === 'en' ? 'Ledger History' : '历史记录';
  const fxUnavailableLabel = language === 'zh' ? '折算不可用' : 'FX unavailable';
  const noHoldingsHistoryNote = language === 'zh' ? '历史记录存在，当前无持仓' : 'History exists while current holdings are empty';
  const recentActivityTitle = language === 'zh' ? '近期活动' : 'Recent Activity';
  const emptyRecentActivityLabel = language === 'zh' ? '暂无历史记录' : 'No history yet';
  const viewFullHistoryLabel = language === 'zh' ? '查看全部历史' : 'View full history';
  const hideFullHistoryLabel = language === 'zh' ? '收起完整历史' : 'Hide full history';
  const renderConvertedDisplay = (value: number, nativeCurrency: string) => {
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
    fx_conversion_unavailable: language === 'zh' ? '部分折算不可用，已保留原币值' : 'Some FX conversion is unavailable; native values remain visible',
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
  const renderPnlTile = (key: 'realized' | 'unrealized' | 'total', value: number, converted: ConvertedMoney) => (
    <TerminalMetric
      data-testid={`portfolio-pnl-${key}`}
      label={pnlLabels[key]}
      value={converted ? formatSignedMoney(converted.value, displayCurrency) : formatSignedMoney(value, pnlSourceCurrency)}
      valueClassName={value >= 0 ? 'text-emerald-400' : 'text-rose-400'}
      subvalue={pnlSourceCurrency !== displayCurrency ? `${pnlLabels.native} ${formatSignedMoney(value, pnlSourceCurrency)}` : undefined}
    />
  );
  const renderExposureValue = (row: PortfolioExposureItem) => {
    const currency = row.displayCurrency || snapshotCurrency;
    const display = formatAnalyticsMoney(row.displayValue ?? row.marketValue ?? 0, currency);
    const native = row.nativeCurrency && row.nativeCurrency !== displayCurrency && row.nativeValue != null
      ? formatMoney(row.nativeValue, row.nativeCurrency)
      : null;
    return { display, native };
  };
  const symbolExposureRows = [...(analytics?.exposure.bySymbol || [])]
    .sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0));
  const currencyExposureRows = [...(analytics?.exposure.byCurrency || [])]
    .sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0));
  const marketExposureRows = [...(analytics?.exposure.byMarket || [])]
    .sort((a, b) => Number(b.percent || 0) - Number(a.percent || 0));
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
  const gainContributors = [...symbolExposureRows]
    .filter((row) => Number(row.unrealizedPnl || 0) > 0)
    .sort((a, b) => Number(b.unrealizedPnl || 0) - Number(a.unrealizedPnl || 0))
    .slice(0, 3);
  const lossContributors = [...symbolExposureRows]
    .filter((row) => Number(row.unrealizedPnl || 0) < 0)
    .sort((a, b) => Number(a.unrealizedPnl || 0) - Number(b.unrealizedPnl || 0))
    .slice(0, 3);
  const marketRiskHint = !marketExposureRows.length
    ? (language === 'zh' ? '暂无市场分类' : 'No market category')
    : marketExposureRows.length === 1
      ? (language === 'zh' ? '单一市场集中' : 'Single-market concentration')
      : Number(topMarket?.percent || 0) >= 80
        ? (language === 'zh' ? '单一市场集中' : 'Single-market concentration')
        : (language === 'zh' ? '跨市场持仓' : 'Cross-market holdings');
  const currencyFxContext = topCurrency?.fxStatus === 'unavailable'
    ? (language === 'zh' ? '汇率待确认' : 'FX pending')
    : topCurrency?.nativeCurrency && topCurrency.nativeCurrency !== displayCurrency
      ? (language === 'zh' ? '原币统计可用' : 'Native analytics available')
      : (language === 'zh' ? '主币种' : 'Primary currency');
  const riskHintTexts = [
    topPositionPercent >= 35 ? (language === 'zh' ? '最大持仓偏高' : 'Largest holding elevated') : null,
    Number(topCurrency?.percent || 0) >= 80 ? (language === 'zh' ? '币种集中' : 'Currency concentrated') : null,
    Number(topMarket?.percent || 0) >= 80 ? (language === 'zh' ? '市场集中' : 'Market concentrated') : null,
    hasHoldings && (analytics?.risk.holdingCount ?? positionRows.length) < 3 ? (language === 'zh' ? '持仓数量较少' : 'Few holdings') : null,
    analytics?.risk.fxUnavailable ? (language === 'zh' ? '汇率数据不可用' : 'FX data unavailable') : null,
  ].filter(Boolean) as string[];
  const safeRiskWarningLabels = (analytics?.risk.warnings || [])
    .map((warning) => riskWarningLabels[warning])
    .filter(Boolean);
  const portfolioEvidenceSummary = useMemo(
    () => (snapshot ? normalizePortfolioRiskEvidence(snapshot, { maxLimitationLabels: 6 }) : null),
    [snapshot],
  );
  const showPortfolioEvidenceChips = Boolean(
    portfolioEvidenceSummary
    && (
      portfolioEvidenceSummary.posture !== 'unknown'
      || portfolioEvidenceSummary.confidenceCap != null
      || portfolioEvidenceSummary.limitationLabels.length > 0
      || portfolioEvidenceSummary.freshnessLabel != null
    ),
  );
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
  const openManualLedger = (nextLeftTab: 'trade' | 'account' | 'sync' | 'fx', nextTradeType?: TradeFormType) => {
    setLeftTab(nextLeftTab);
    if (nextTradeType) {
      setTradeType(nextTradeType);
    }
    setManualLedgerOpen(true);
  };
  const renderMiniExposureRow = (
    row: PortfolioExposureItem,
    options: { testIdPrefix: string; label?: string; showNative?: boolean },
  ) => {
    const values = renderExposureValue(row);
    return (
      <TerminalNestedBlock key={`${options.testIdPrefix}-${row.key}`} data-testid={`${options.testIdPrefix}-${row.key}`} className="min-w-0 px-3 py-2">
        <div className="flex min-w-0 items-center justify-between gap-3">
          <div className="min-w-0">
            <div className="truncate text-xs font-medium text-white">{options.label || row.label || row.key}</div>
            <div className="mt-0.5 font-mono text-[11px] text-white/40">{formatPercent(row.percent)}</div>
          </div>
          <div className="min-w-0 shrink-0 text-right">
            <div className="font-mono text-xs text-white tabular-nums">{values.display}</div>
            {options.showNative && values.native ? <div className="mt-0.5 font-mono text-[10px] text-white/35">{values.native}</div> : null}
          </div>
        </div>
      </TerminalNestedBlock>
    );
  };
  const renderContributorRow = (row: PortfolioExposureItem, toneClass: string, prefix: string) => (
    <TerminalNestedBlock key={`${prefix}-${row.key}`} data-testid={`${prefix}-${row.key}`} className="flex min-w-0 items-center justify-between gap-3 px-3 py-2">
      <div className="min-w-0">
        <div className="truncate text-xs font-medium text-white">{row.label || row.symbol || row.key}</div>
        <div className="mt-0.5 font-mono text-[11px] text-white/40">{formatPercent(row.unrealizedPnlPct)}</div>
      </div>
      <div className={`shrink-0 font-mono text-xs tabular-nums ${toneClass}`}>
        {formatSignedMoney(Number(row.unrealizedPnl || 0), row.displayCurrency || snapshotCurrency)}
      </div>
    </TerminalNestedBlock>
  );

  const renderTradeActions = (item: PortfolioTradeListItem, context: 'history' | 'recent') => {
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
            onClick={() => setOpenTradeActionMenuId((prev) => (prev === item.id ? null : item.id))}
          >
            <MoreHorizontal className="h-3.5 w-3.5" aria-hidden="true" />
            {moreTradeActionsLabel}
          </Button>
          {isOpen ? (
            <TerminalNestedBlock
              data-testid={`${menuKey}-menu`}
              className="absolute right-0 z-20 mt-2 flex min-w-[132px] flex-col gap-1 bg-[#0f1726] p-2 shadow-2xl"
            >
              <Button type="button" variant="ghost" className="justify-start rounded-lg px-2 text-xs text-white/75" onClick={() => openTradeEditor(item)}>
                <PenSquare className="h-3.5 w-3.5" aria-hidden="true" />
                {editTradeActionLabel}
              </Button>
              <Button type="button" variant="ghost" className="justify-start rounded-lg px-2 text-xs text-red-300 hover:text-red-200" onClick={() => openTradeVoidDialog(item)}>
                <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
                {deleteTradeActionLabel}
              </Button>
            </TerminalNestedBlock>
          ) : null}
        </div>
      );
    }

    return (
      <div className="flex shrink-0 items-center gap-1">
        <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} onClick={() => openTradeEditor(item)}>
          <PenSquare className="h-3.5 w-3.5" aria-hidden="true" />
          {editTradeActionLabel}
        </Button>
        <Button type="button" variant="ghost" className={`${PORTFOLIO_TEXT_BUTTON_CLASS} text-red-300 hover:text-red-200`} onClick={() => openTradeVoidDialog(item)}>
          <Trash2 className="h-3.5 w-3.5" aria-hidden="true" />
          {deleteTradeActionLabel}
        </Button>
      </div>
    );
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
            <RefreshCw className="h-4 w-4" aria-hidden="true" />
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
                    {renderTradeActions(item, 'history')}
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
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
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
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
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
                {renderTradeActions(item, 'recent')}
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
        <TerminalPageShell className="flex-1 min-w-0 min-h-0">
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
                className="grid gap-4 xl:grid-cols-[minmax(0,1.85fr)_minmax(0,1.15fr)]"
              >
                <div data-testid="portfolio-total-assets-card" className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <h1 className="text-[10px] font-bold uppercase tracking-widest text-white/40">{totalAssetsTitle}</h1>
                    <TerminalChip variant="neutral">
                      {selectedAccount === 'all' ? copy.allAccounts : scopedAccount?.name || copy.allAccounts}
                    </TerminalChip>
                    {hasFxUnavailable ? <TerminalChip variant="caution">{fxUnavailableLabel}</TerminalChip> : null}
                  </div>
                  <div
                    data-testid="portfolio-total-assets-value"
                    className="mt-2 font-mono text-2xl font-semibold leading-none text-white tabular-nums md:text-3xl"
                  >
                    {formatDisplayMoney(totalEquity, totalEquityDisplay, snapshotCurrency)}
                  </div>
                  <p className="mt-2 text-xs leading-5 text-white/35">
                    {hasHoldings ? `${holdingsPrimaryValue} · ${accountStateSummary}` : compactNoHoldingText}
                  </p>
                  {showPortfolioEvidenceChips ? (
                    <EvidenceChips
                      summary={portfolioEvidenceSummary}
                      maxLabels={0}
                      className="mt-3"
                      data-testid="portfolio-snapshot-evidence-chips"
                    />
                  ) : null}
                </div>

                <div data-testid="portfolio-command-strip" className="min-w-0 flex flex-col gap-3">
                  <div className="grid min-w-0 grid-cols-1 gap-2 md:grid-cols-2">
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

                  <div className="grid min-w-0 grid-cols-2 gap-2">
                    <TerminalMetric label={copy.totalCash} value={formatDisplayMoney(totalCash, totalCashDisplay, snapshotCurrency)} />
                    <TerminalMetric label={copy.totalMarketValue} value={formatDisplayMoney(totalMarketValue, totalMarketValueDisplay, snapshotCurrency)} />
                    <TerminalMetric
                      label={copy.positionUnrealized}
                      value={totalUnrealizedDisplay ? formatSignedMoney(totalUnrealizedDisplay.value, displayCurrency) : formatSignedMoney(0, displayCurrency)}
                      valueClassName={totalUnrealizedPnl >= 0 ? 'text-emerald-400' : 'text-rose-400'}
                    />
                    <TerminalMetric label={language === 'zh' ? '持仓数' : 'Holdings'} value={positionRows.length} />
                  </div>

                  <div className="flex min-w-0 flex-wrap gap-2">
                    <TerminalButton type="button" variant="primary" className="h-9 px-3" onClick={() => openManualLedger('trade', 'stock')}>
                      {addHoldingActionLabel}
                    </TerminalButton>
                    <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('sync')}>
                      {importTradesActionLabel}
                    </TerminalButton>
                    <TerminalButton type="button" variant="secondary" onClick={() => openManualLedger('trade')}>
                      {manualLedgerActionLabel}
                    </TerminalButton>
                  </div>
                </div>
              </TerminalPanel>
            </div>

            <div data-testid="portfolio-row-routing" className="order-2 col-span-12 min-w-0 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(360px,5fr)] 2xl:gap-5 items-start">
              <div data-testid="portfolio-primary-lane" className="min-w-0 flex flex-col gap-4">
                <TerminalPanel
                  as="section"
                  data-testid="portfolio-current-holdings-panel"
                  className="min-w-0 flex flex-col overflow-hidden"
                >
                  <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/5 pb-4">
                    <h2 className="min-w-0 text-xs uppercase tracking-widest text-muted-text">
                      {hasHoldings
                        ? (language === 'zh' ? `当前持仓（共 ${positionRows.length} 项）` : `Current Holdings (${positionRows.length})`)
                        : (language === 'zh' ? '当前持仓' : 'Current holdings')}
                    </h2>
                    {!hasHoldings ? (
                      <span className="text-xs text-white/35">{language === 'zh' ? '等待流水' : 'Awaiting records'}</span>
                    ) : null}
                  </div>

                  <div className="pt-3 lg:max-h-[460px] lg:min-h-0 lg:overflow-y-auto lg:no-scrollbar lg:[&::-webkit-scrollbar]:hidden lg:[-ms-overflow-style:none] lg:[scrollbar-width:none]">
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
                                language === 'zh' ? '风险/状态' : 'Risk/State',
                                language === 'zh' ? '操作' : 'Action',
                              ].map((label) => (
                                <th key={label} className="px-3 py-2 font-semibold">{label}</th>
                              ))}
                            </tr>
                          </thead>
                          <tbody>
                            {positionRows.map((row) => (
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
                                  {row.valuationCurrency !== displayCurrency ? <div className="mt-1 text-[11px] text-white/35">{renderConvertedDisplay(row.marketValueBase, row.valuationCurrency)}</div> : null}
                                  <div className={`mt-1 text-[11px] ${row.isPriceFallback ? 'text-amber-300' : 'text-white/35'}`}>
                                    {`${formatMoney(row.lastPrice, row.currency)} · ${positionPriceDisclosure(row, language)}`}
                                  </div>
                                </td>
                                <td className={`px-3 py-2 font-mono ${row.unrealizedPnlBase >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
                                  {formatSignedMoney(row.unrealizedPnlBase, row.valuationCurrency)}
                                  <div className="mt-1 text-[11px] text-white/40">{formatPercent(row.unrealizedPnlPct)}</div>
                                </td>
                                <td className="px-3 py-2 text-white/45">{topPosition?.key === row.symbol && topPositionPercent >= 35 ? (language === 'zh' ? '集中' : 'Concentrated') : (language === 'zh' ? '观察' : 'Observe')}</td>
                                <td className="px-3 py-2">
                                  <Button type="button" variant="ghost" className={PORTFOLIO_TEXT_BUTTON_CLASS} onClick={() => openManualLedger('trade', 'stock')}>
                                    {manualLedgerActionLabel}
                                  </Button>
                                </td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      </TerminalDenseTable>
                    ) : (
                      <div data-testid="portfolio-empty-workflow-column" className="min-w-0">
                        <TerminalEmptyState
                          data-testid="portfolio-start-card"
                          title={language === 'zh' ? '暂无持仓' : 'No holdings'}
                          action={hasHistory ? <TerminalChip variant="caution" className="shrink-0">{noHoldingsHistoryNote}</TerminalChip> : undefined}
                        >
                          {compactNoHoldingText}
                        </TerminalEmptyState>
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
                <TerminalPanel
                  as="section"
                  data-testid="portfolio-pnl-summary"
                  className="min-w-0 grid gap-2 sm:grid-cols-3"
                >
                  {renderPnlTile('realized', realizedPnl, realizedPnlDisplay)}
                  {renderPnlTile('unrealized', unrealizedPnl, unrealizedPnlDisplay)}
                  {renderPnlTile('total', totalPnl, totalPnlDisplay)}
                </TerminalPanel>

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
                          <TerminalNestedBlock key={`${exposureTab}-${row.key}`} className="min-w-0 px-3 py-3">
                            <div className="flex min-w-0 items-center justify-between gap-3">
                              <div className="min-w-0">
                                <div className="truncate text-sm font-medium text-white">{row.label}</div>
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

		                  <TerminalPanel
                      as="section"
		                    data-testid="portfolio-risk-card"
		                    className="min-w-0 flex flex-col gap-3"
		                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <h2 className="text-[10px] font-bold uppercase tracking-widest text-white/40">{riskTitle}</h2>
                        <p className="mt-1 text-xs leading-5 text-white/40">
                          {hasHoldings ? (language === 'zh' ? '集中度、币种与市场敞口。' : 'Concentration, currency, and market exposure.') : (language === 'zh' ? '暂无持仓，风险指标待生成。' : 'No holdings yet. Risk metrics pending.')}
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
                    {showPortfolioEvidenceChips ? (
                      <EvidenceChips
                        summary={portfolioEvidenceSummary}
                        maxLabels={6}
                        data-testid="portfolio-risk-evidence-chips"
                      />
                    ) : null}

                    <div data-testid="portfolio-risk-overview" className="grid grid-cols-2 gap-2">
                      <div className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '最大持仓' : 'Largest Position'}</div>
                        <div className="mt-1 truncate text-sm text-white">{topPosition?.label || '--'}</div>
                        <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topPosition?.percent)}</div>
                      </div>
                      <div className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '持仓数量' : 'Holdings'}</div>
                        <div className="mt-1 font-mono text-sm text-white">{analytics?.risk.holdingCount ?? positionRows.length}</div>
                        <div className="mt-1 font-mono text-xs text-white/45">{language === 'zh' ? '账户' : 'Accounts'} {analytics?.risk.accountCount ?? snapshot?.accountCount ?? 0}</div>
                      </div>
                    </div>

                    {hasHoldings ? (<>
                    <div data-testid="portfolio-concentration-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '持仓集中度' : 'Concentration'}</div>
                        <div className={`font-mono text-xs ${hasHoldings ? concentrationToneClass : 'text-white/35'}`}>{formatPercent(topPosition?.percent)}</div>
                      </div>
                      <p className="mt-2 text-xs leading-5 text-white/45">{concentrationDescription}</p>
                      {symbolExposureRows.length ? (
                        <div className="mt-2 flex flex-col gap-1.5">
                          {symbolExposureRows.slice(0, 3).map((row) => renderMiniExposureRow(row, { testIdPrefix: 'portfolio-top-position' }))}
                        </div>
                      ) : null}
                    </div>

                    <div className="grid gap-2">
                      <div data-testid="portfolio-currency-exposure-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '币种敞口' : 'Currency Exposure'}</div>
                          <PillBadge variant={topCurrency?.fxStatus === 'unavailable' ? 'warning' : 'info'} className="shrink-0 text-cyan-200">{currencyFxContext}</PillBadge>
                        </div>
                        <div className="mt-2 text-[10px] uppercase tracking-widest text-white/35">{language === 'zh' ? '最大币种' : 'Largest Currency'}</div>
                        <div className="mt-2 text-sm text-white">{topCurrency?.label || '--'}</div>
                        <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topCurrency?.percent)}</div>
                        {topCurrency ? (
                          <div className="mt-2">{renderMiniExposureRow(topCurrency, { testIdPrefix: 'portfolio-top-currency', showNative: true })}</div>
                        ) : (
                          <div className="mt-2 text-xs text-white/35">{language === 'zh' ? '暂无持仓，风险指标待生成。' : 'No holdings yet. Risk metrics pending.'}</div>
                        )}
                        {topCurrency?.fxStatus === 'unavailable' ? (
                          <div className="mt-2 text-[11px] text-amber-200">{language === 'zh' ? '折算值仅供参考，原币统计可用。' : 'Converted value is indicative; native analytics remain available.'}</div>
                        ) : null}
                      </div>

                      <div data-testid="portfolio-market-exposure-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3">
                        <div className="flex items-center justify-between gap-3">
                          <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '市场敞口' : 'Market Exposure'}</div>
                          <PillBadge variant={marketExposureRows.length <= 1 || Number(topMarket?.percent || 0) >= 80 ? 'warning' : 'info'} className="shrink-0 text-cyan-200">{marketRiskHint}</PillBadge>
                        </div>
                        <div className="mt-2 text-[10px] uppercase tracking-widest text-white/35">{language === 'zh' ? '最大市场' : 'Largest Market'}</div>
                        <div className="mt-2 text-sm text-white">{formatExposureMarketLabel(topMarket, language)}</div>
                        <div className="mt-1 font-mono text-xs text-white/45">{formatPercent(topMarket?.percent)} · {language === 'zh' ? '市场数' : 'Markets'} {marketExposureRows.length}</div>
                        {topMarket ? (
                          <div className="mt-2">{renderMiniExposureRow(topMarket, { testIdPrefix: 'portfolio-top-market', label: formatExposureMarketLabel(topMarket, language) })}</div>
                        ) : (
                          <div className="mt-2 text-xs text-white/35">{language === 'zh' ? '暂无市场分类。' : 'No market category.'}</div>
                        )}
                      </div>
                    </div>

                    <div data-testid="portfolio-pnl-contributors" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3">
                      <div className="flex flex-wrap items-center justify-between gap-2">
                        <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '盈亏贡献' : 'P&L Contribution'}</div>
                        <div className="font-mono text-[11px] text-white/40">
                          {pnlLabels.realized} {formatSignedMoney(realizedPnl, pnlSourceCurrency)} · {pnlLabels.unrealized} {formatSignedMoney(unrealizedPnl, pnlSourceCurrency)}
                        </div>
                      </div>
                      <div className="mt-2 grid gap-2">
                        <div className="min-w-0">
                          <div className="mb-1 text-[10px] text-emerald-300">{language === 'zh' ? '贡献盈利' : 'Gain contributors'}</div>
                          {gainContributors.length ? (
                            <div className="flex flex-col gap-1.5">
                              {gainContributors.map((row) => renderContributorRow(row, 'text-emerald-300', 'portfolio-gain-contributor'))}
                            </div>
                          ) : (
                            <div className="rounded-lg bg-white/[0.015] px-3 py-2 text-xs text-white/35">{language === 'zh' ? '暂无盈利贡献' : 'No gain contributor'}</div>
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="mb-1 text-[10px] text-rose-300">{language === 'zh' ? '拖累亏损' : 'Loss contributors'}</div>
                          {lossContributors.length ? (
                            <div className="flex flex-col gap-1.5">
                              {lossContributors.map((row) => renderContributorRow(row, 'text-rose-300', 'portfolio-loss-contributor'))}
                            </div>
                          ) : (
                            <div className="rounded-lg bg-white/[0.015] px-3 py-2 text-xs text-white/35">{language === 'zh' ? '暂无亏损拖累' : 'No loss contributor'}</div>
                          )}
                        </div>
                      </div>
                    </div>

                    <div data-testid="portfolio-risk-hints" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3 text-xs text-white/45">
                      <div className="mb-2 text-[10px] font-bold uppercase tracking-widest text-white/40">{language === 'zh' ? '风险提示' : 'Risk Hints'}</div>
                      <div className="flex flex-wrap gap-1.5">
                        {(riskHintTexts.length ? riskHintTexts : [language === 'zh' ? '暂无显著集中风险' : 'No notable concentration risk']).map((hint) => (
                          <PillBadge key={hint} variant="default" className="text-white/55">{hint}</PillBadge>
                        ))}
                        {safeRiskWarningLabels.map((warning) => (
                          <PillBadge key={warning} variant="warning" className="text-white/55">{warning}</PillBadge>
                        ))}
                      </div>
                    </div>
                    </>) : (
                      <div className="grid gap-2">
                        <div data-testid="portfolio-concentration-drilldown" className="min-h-[72px] rounded-xl border border-white/[0.02] bg-black/20 px-3 py-3 text-xs leading-5 text-white/35">
                          {language === 'zh' ? '暂无持仓，风险指标待生成。' : 'No holdings yet. Risk metrics pending.'}
                        </div>
                        <div data-testid="portfolio-currency-exposure-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2 text-xs text-white/35">
                          {language === 'zh' ? '暂无持仓，风险指标待生成。' : 'No holdings yet. Risk metrics pending.'}
                        </div>
                        <div data-testid="portfolio-market-exposure-drilldown" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2 text-xs text-white/35">
                          {language === 'zh' ? '暂无市场分类。' : 'No market category.'}
                        </div>
                        <div data-testid="portfolio-pnl-contributors" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2 text-xs text-white/35">
                          {language === 'zh' ? '暂无盈亏贡献。' : 'No P&L contribution.'}
                        </div>
                        <div data-testid="portfolio-risk-hints" className="rounded-xl border border-white/[0.02] bg-black/20 px-3 py-2 text-xs text-white/35">
                          {language === 'zh' ? '暂无显著集中风险。' : 'No notable concentration risk.'}
                        </div>
                      </div>
                    )}
		                  </TerminalPanel>
              </div>
            </div>

            <div data-testid="portfolio-workspace-lanes" className="order-3 col-span-12 min-w-0 grid grid-cols-1 gap-4 xl:grid-cols-[minmax(0,7fr)_minmax(320px,5fr)] 2xl:gap-5 items-start">
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
                  label={language === 'zh' ? '记账账户' : 'LEDGER ACCOUNT'}
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
                  label={language === 'zh' ? '成本方法' : 'COST METHOD'}
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
                    <div>
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualTrade}</p>
                      <form onSubmit={handleTradeSubmit}>
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
                                  : inferSettlementCurrency(symbol, writableAccount?.baseCurrency),
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
                  ) : null}

                  {tradeType === 'fund' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCash}</p>
                      <form onSubmit={handleCashSubmit}>
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
                  ) : null}

                  {tradeType === 'corporate' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCorporate}</p>
                      <form onSubmit={handleCorporateSubmit}>
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
                  ) : null}
                </div>
              ) : null}

              {leftTab === 'account' ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.createAccountTitle}</p>
                    <div className="flex gap-2">
                      <Button
                        type="button"
                        variant="secondary"
                        className={PORTFOLIO_SECONDARY_BUTTON_CLASS}
                        onClick={() => {
                          setShowCreateAccount((prev) => !prev);
                          setAccountCreateError(null);
                          setAccountCreateSuccess(null);
                        }}
                      >
                        {showCreateAccount ? copy.collapseCreate : copy.createAccount}
                      </Button>
                      <Button type="button" variant="ghost" className={PORTFOLIO_ICON_BUTTON_CLASS} onClick={() => void handleRefresh()} disabled={isLoading} aria-label={isLoading ? copy.refreshingData : copy.refreshData} title={isLoading ? copy.refreshingData : copy.refreshData}>
                        <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
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
	                              onClick={() => setPendingAccountDelete({ id: account.id, name: account.name })}
	                              aria-label={language === 'en' ? `Delete ${account.name}` : `删除 ${account.name}`}
	                              title={copy.accountDeleteTitle}
	                            >
	                              <Trash2 className="h-4 w-4" aria-hidden="true" />
	                            </Button>
	                          </div>
	                        </div>
                        <div className="mt-1 text-xs text-muted-text">{formatAccountMarketLabel(account.market, language)} · {account.baseCurrency} · {account.broker || '--'}</div>
                      </div>
                    ))}
                  </div>
                  {(showCreateAccount || !hasAccounts) ? (
                    <form className="space-y-3 rounded-2xl border border-white/5 bg-white/[0.02] p-4" onSubmit={handleCreateAccount}>
                      <Input label="ACCOUNT NAME" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder="Core Portfolio" value={accountForm.name} onChange={(e) => setAccountForm((prev) => ({ ...prev, name: e.target.value }))} />
                      <div className="grid grid-cols-2 gap-4">
                        <Input label="BROKER" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder="Demo" value={accountForm.broker} onChange={(e) => setAccountForm((prev) => ({ ...prev, broker: e.target.value }))} />
                        <Input label="BASE CCY" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder="CNY" value={accountForm.baseCurrency} onChange={(e) => setAccountForm((prev) => ({ ...prev, baseCurrency: e.target.value.toUpperCase() }))} />
                      </div>
                      <Select label="MARKET" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={accountForm.market} onChange={(value) => setAccountForm((prev) => ({ ...prev, market: value as 'cn' | 'hk' | 'us' | 'global' }))} options={[{ value: 'cn', label: copy.marketCn }, { value: 'hk', label: copy.marketHk }, { value: 'us', label: copy.marketUs }, { value: 'global', label: copy.marketGlobal }]} />
                      <Button type="submit" variant="primary" className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`} disabled={accountCreating}>{accountCreating ? copy.creatingAccount : copy.createAccount}</Button>
                    </form>
                  ) : null}
                </div>
              ) : null}

              {leftTab === 'sync' ? (
                <div className="space-y-4">
                  <div className="flex items-center justify-between gap-3">
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.dataSyncTitle}</p>
                    <Button type="button" variant="ghost" className={PORTFOLIO_ICON_BUTTON_CLASS} onClick={() => void handleRefresh()} disabled={isLoading} aria-label={isLoading ? copy.refreshingData : copy.refreshData} title={isLoading ? copy.refreshingData : copy.refreshData}>
                      <RefreshCw className={`h-4 w-4 ${isLoading ? 'animate-spin' : ''}`} aria-hidden="true" />
                    </Button>
                  </div>
                  <div className="text-xs text-secondary-text space-y-1">
                    <p>{copy.currentImportAccount}</p>
                    <p>{writableAccount ? `${writableAccount.name} (#${writableAccount.id})` : copy.brokerFallbackEmpty}</p>
                    <p>{selectedBroker === 'ibkr' ? copy.ibkrImportHint : copy.brokerImportHint}</p>
                  </div>
                  <Select label="BROKER" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={selectedBroker} onChange={setSelectedBroker} options={brokers.map((broker) => ({ value: broker.broker, label: formatBrokerLabel(broker.broker, broker.displayName, language) }))} />
                  {selectedBroker === 'ibkr' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="space-y-3">
                      <div className="flex items-center justify-between gap-3">
                        <div className="space-y-1 text-xs text-secondary-text">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{copy.ibkrReadOnlyTitle}</p>
                          <p>{copy.ibkrReadOnlyBody}</p>
                        </div>
                        <PillBadge variant="info">{copy.readOnlyBadge}</PillBadge>
                      </div>
                      {ibkrConnection ? <p className="text-sm text-foreground">{ibkrConnection.connectionName}</p> : null}
                      <Input label="API BASE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrApiBasePlaceholder} value={ibkrApiBaseUrl} onChange={(e) => setIbkrApiBaseUrl(e.target.value)} />
                      <Input label="ACCOUNT REF" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrAccountRefPlaceholder} value={ibkrBrokerAccountRef} onChange={(e) => setIbkrBrokerAccountRef(e.target.value)} />
                      <Input label="SESSION TOKEN" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder={copy.ibkrSessionTokenPlaceholder} value={ibkrSessionToken} onChange={(e) => setIbkrSessionToken(e.target.value)} />
                      <Checkbox checked={ibkrVerifySsl} onChange={(e) => setIbkrVerifySsl(e.target.checked)} label={copy.verifyIbkrSsl} containerClassName="text-xs text-secondary-text" />
                      <Button type="button" variant="primary" className={`${PORTFOLIO_PRIMARY_BUTTON_CLASS} w-full`} onClick={() => void handleSyncIbkr()} disabled={!writableAccountId || ibkrSyncing}>
                        {ibkrSyncing ? copy.syncing : copy.syncIbkr}
                      </Button>
                      {ibkrSyncResult ? (
                        <div className="theme-panel-subtle rounded-[16px] px-4 py-3 text-xs text-secondary-text space-y-1">
                          <p className="text-[11px] uppercase tracking-[0.18em] text-muted-text">{copy.syncResult}</p>
                          <div>{copy.positionsCountLabel} <span className="text-foreground">{ibkrSyncResult.positionCount ?? '--'}</span></div>
                          <div>{copy.cashCurrenciesLabel} <span className="text-foreground">{ibkrSyncResult.cashBalanceCount ?? 0}</span></div>
                          <div>{copy.syncedAt}: <span className="text-foreground">{ibkrSyncResult.syncedAt ? ibkrSyncResult.syncedAt.replace('T', ' ') : '--'}</span></div>
                          <div>{copy.totalEquity} <span className="text-foreground">{formatMoney(ibkrSyncResult.totalEquity, ibkrSyncResult.baseCurrency)}</span></div>
                        </div>
                      ) : null}
                    </SectionShell>
                  ) : (
                    <div className="rounded-2xl border border-white/5 bg-white/[0.02] px-4 py-4 text-xs text-secondary-text">
                      {copy.brokerImportHint}
                    </div>
                  )}
                </div>
              ) : null}

              {leftTab === 'fx' ? (
                <div data-testid="portfolio-fx-panel" className="space-y-4">
                  <div>
	                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">实时汇率引擎</p>
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
		                      <span className="truncate">{selectedFxRate?.provider || 'frankfurter'}</span>
			                      <span>{selectedFxRate?.cacheHit ? (language === 'zh' ? '缓存' : 'CACHE') : (language === 'zh' ? '实时' : 'LIVE')}</span>
		                      {selectedFxRate?.isStale ? <span className="text-amber-300">{copy.fxStale}</span> : null}
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
      </TerminalPageShell>
    </div>

      <Drawer
        isOpen={Boolean(editingTrade)}
        onClose={() => {
          if (tradeEditSubmitting) {
            return;
          }
          setEditingTrade(null);
          setTradeEditCurrencyManuallyEdited(false);
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
                      currency: tradeEditCurrencyManuallyEdited
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
                  setTradeEditCurrencyManuallyEdited(true);
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
                  setTradeEditCurrencyManuallyEdited(false);
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
