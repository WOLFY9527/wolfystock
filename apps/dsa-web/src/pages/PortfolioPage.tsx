import type React from 'react';
import { useCallback, useEffect, useMemo, useRef, useState } from 'react';
import { RefreshCw, Trash2 } from 'lucide-react';
import { portfolioApi } from '../api/portfolio';
import type { ParsedApiError } from '../api/error';
import { getParsedApiError } from '../api/error';
import { ApiErrorAlert, Button, Checkbox, ConfirmDialog, Input, PillBadge, SectionShell, Select } from '../components/common';
import { useI18n } from '../contexts/UiLanguageContext';
import {
  getSafariReadySurfaceClassName,
  shouldApplySafariA11yGuard,
  useSafariRenderReady,
} from '../hooks/useSafariInteractionReady';
import { translate } from '../i18n/core';
import { toDateInputValue } from '../utils/format';
import type {
  PortfolioAccountItem,
  PortfolioBrokerConnectionItem,
  PortfolioCashDirection,
  PortfolioCashLedgerListItem,
  PortfolioCorporateActionListItem,
  PortfolioCorporateActionType,
  PortfolioCostMethod,
  PortfolioFxRateItem,
  PortfolioImportBrokerItem,
  PortfolioIbkrSyncResponse,
  PortfolioLiveFxRateResponse,
  PortfolioPositionItem,
  PortfolioSide,
  PortfolioSnapshotResponse,
  PortfolioTradeListItem,
} from '../types/portfolio';

const HERO_PNL_POSITIVE_GLOW = '0 0 30px rgba(52, 211, 153, 0.4)';
const PORTFOLIO_GLASS_CARD_CLASS = 'bg-white/[0.02] border border-white/5 rounded-xl backdrop-blur-md p-5 transition-all hover:border-white/10';
const PORTFOLIO_FIELD_LABEL_CLASS = '!mb-1 text-[10px] font-bold uppercase tracking-widest text-white/40';
const PORTFOLIO_FIELD_WRAPPER_CLASS = 'flex flex-col gap-1.5';
const PORTFOLIO_FORM_GRID_CLASS = 'mt-4 grid grid-cols-1 gap-x-4 gap-y-4 sm:grid-cols-2';
const PORTFOLIO_INPUT_CLASS = 'h-10 rounded-lg border-white/10 bg-white/[0.02] px-3 py-2.5 text-sm text-white placeholder:text-white/20 outline-none focus:border-emerald-500/50';
const PORTFOLIO_SELECT_CLASS = 'min-w-0';
const PORTFOLIO_PRIMARY_BUTTON_CLASS = 'h-10 rounded-xl border-0 bg-gradient-to-r from-blue-600 to-purple-600 px-4 text-sm font-bold text-white shadow-[0_0_15px_rgba(139,92,246,0.3)] hover:from-blue-500 hover:to-purple-500';
const PORTFOLIO_SUBMIT_BUTTON_CLASS = 'w-full mt-5 bg-gradient-to-r from-blue-600 to-purple-600 hover:from-blue-500 hover:to-purple-500 text-white font-medium rounded-lg px-6 py-2.5 shadow-[0_0_15px_rgba(139,92,246,0.3)] transition-all disabled:opacity-50 disabled:cursor-not-allowed';
const PORTFOLIO_SECONDARY_BUTTON_CLASS = 'h-9 rounded-xl border border-white/10 bg-white/5 px-3 text-xs text-white/70 hover:bg-white/10 hover:text-white';
const PORTFOLIO_TEXT_BUTTON_CLASS = 'h-8 rounded-md border-0 bg-transparent px-2 text-xs text-white/40 hover:bg-transparent hover:text-white disabled:text-white/15';
const PORTFOLIO_ICON_BUTTON_CLASS = 'h-9 w-9 rounded-xl border-0 bg-white/[0.04] p-0 text-white/45 hover:bg-white/10 hover:text-white';
const PORTFOLIO_DANGER_GHOST_CLASS = 'h-8 w-8 rounded-lg border-0 bg-transparent p-0 text-white/30 hover:bg-red-500/10 hover:text-red-400';
const CASH_CURRENCY_OPTIONS = ['CNY', 'HKD', 'USD'] as const;
const FX_CURRENCY_OPTIONS = ['USD', 'CNY', 'HKD', 'EUR', 'JPY', 'GBP'] as const;
const DISPLAY_CURRENCY_OPTIONS = ['CNY', 'USD', 'HKD', 'EUR', 'JPY'] as const;
const DISPLAY_CURRENCY_STORAGE_KEY = 'wolfystock.portfolio.displayCurrency.v1';

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

type FlatPosition = PortfolioPositionItem & {
  accountId: number;
  accountName: string;
};

type SeamlessSegmentOption = {
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

type DisplayCurrency = typeof DISPLAY_CURRENCY_OPTIONS[number];

type ConvertedMoney = {
  value: number;
  currency: DisplayCurrency;
  rate: number;
  stale: boolean;
} | null;

type PendingDelete =
  | { eventType: 'trade'; id: number; message: string }
  | { eventType: 'cash'; id: number; message: string }
  | { eventType: 'corporate'; id: number; message: string };

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

function SeamlessSegmentedControl({
  value,
  options,
  onChange,
  className = '',
  itemClassName = '',
  dataTestId,
}: {
  value: string;
  options: SeamlessSegmentOption[];
  onChange: (value: string) => void;
  className?: string;
  itemClassName?: string;
  dataTestId?: string;
}) {
  return (
    <div data-testid={dataTestId} className={`ui-scroll-x-quiet flex min-w-0 w-full max-w-full rounded-xl bg-white/[0.05] p-1 ${className}`}>
      {options.map((option) => {
        const active = option.value === value;
        return (
          <button
            key={option.value}
            type="button"
            aria-pressed={active}
            onClick={() => onChange(option.value)}
            className={`min-w-0 appearance-none border-0 flex-1 shrink-0 rounded-lg px-2 py-1.5 text-center text-sm font-medium transition-all duration-200 cursor-pointer ${active ? 'bg-white/10 text-white shadow-sm' : 'bg-transparent text-white/40 hover:text-white/70'} ${itemClassName}`}
          >
            <span className="ui-truncate block w-full">{option.label}</span>
          </button>
        );
      })}
    </div>
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
    buy: t('portfolio.buy'),
    sell: t('portfolio.sell'),
    quantity: t('portfolio.quantity'),
    price: t('portfolio.price'),
    feeOptional: t('portfolio.feeOptional'),
    taxOptional: t('portfolio.taxOptional'),
    submitTrade: t('portfolio.submitTrade'),
    manualCash: t('portfolio.manualCash'),
    cashIn: t('portfolio.cashIn'),
    cashOut: t('portfolio.cashOut'),
    amount: t('portfolio.amount'),
    currencyOptional: (currency: string) => t('portfolio.currencyOptional', {
      currency: currency || t('portfolio.accountBaseCurrencyFallback'),
    }),
    submitCash: t('portfolio.submitCash'),
    manualCorporate: t('portfolio.manualCorporate'),
    stockCode: t('portfolio.stockCode'),
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
    tradeUidPlaceholder: language === 'en' ? 'Trade reference (optional)' : '交易引用 (可选)',
    notePlaceholder: language === 'en' ? 'Note (optional)' : '备注 (可选)',
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

function formatPositionContext(market: string, currency: string, language: PortfolioLanguage): string {
  const marketLabel = formatAccountMarketLabel(market, language);
  return translate(language, 'portfolio.positionContext', {
    market: marketLabel,
    currency: currency || '--',
  });
}

function formatSignedMoney(value: number, currency: string): string {
  const formatted = formatMoney(Math.abs(value), currency);
  if (value > 0) return `+${formatted}`;
  if (value < 0) return `-${formatted}`;
  return formatted;
}

function normalizeDisplayCurrency(value: unknown): DisplayCurrency {
  const normalized = typeof value === 'string' ? value.toUpperCase() : '';
  return DISPLAY_CURRENCY_OPTIONS.includes(normalized as DisplayCurrency)
    ? (normalized as DisplayCurrency)
    : 'CNY';
}

function readInitialDisplayCurrency(): DisplayCurrency {
  if (typeof window === 'undefined') {
    return 'CNY';
  }
  return normalizeDisplayCurrency(window.localStorage.getItem(DISPLAY_CURRENCY_STORAGE_KEY));
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
  const [displayCurrency, setDisplayCurrency] = useState<DisplayCurrency>(() => readInitialDisplayCurrency());
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
  const [pendingDelete, setPendingDelete] = useState<PendingDelete | null>(null);
  const [deleteLoading, setDeleteLoading] = useState(false);

  const [tradeForm, setTradeForm] = useState({
    symbol: '',
    tradeDate: getTodayIso(),
    side: 'buy' as PortfolioSide,
    quantity: '',
    price: '',
    fee: '',
    tax: '',
    tradeUid: '',
    note: '',
  });
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
  const hasAccounts = accounts.length > 0;
  const writableAccount = selectedAccount === 'all' ? undefined : accounts.find((item) => item.id === selectedAccount);
  const writableAccountId = writableAccount?.id;
  const writeBlocked = !writableAccountId;
  const ibkrConnection = useMemo(
    () => brokerConnections.find((item) => item.brokerType === 'ibkr') || null,
    [brokerConnections],
  );
  const currentEventCount = eventType === 'trade'
    ? tradeEvents.length
    : eventType === 'cash'
      ? cashEvents.length
      : corporateEvents.length;

  useEffect(() => {
    if (typeof window !== 'undefined') {
      window.localStorage.setItem(DISPLAY_CURRENCY_STORAGE_KEY, displayCurrency);
    }
  }, [displayCurrency]);

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
      setAccounts(items);
      setSelectedAccount((prev) => {
        if (items.length === 0) return 'all';
        if (prev !== 'all' && !items.some((item) => item.id === prev)) return items[0].id;
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
  }, [eventType, queryAccountId, eventDateFrom, eventDateTo, eventSymbol, eventSide, eventDirection, eventActionType]);

  useEffect(() => {
    if (!writeBlocked) {
      setWriteWarning(null);
    }
  }, [writeBlocked]);

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
        tradeUid: tradeForm.tradeUid || undefined,
        note: tradeForm.note || undefined,
      });
      await refreshPortfolioData();
      setTradeFeedback({
        tone: 'success',
        text: `${submittedSymbol || tradeForm.symbol} ${formatSideLabel(submittedSide, language)}已记录 · 已刷新持仓`,
      });
      setTradeForm((prev) => ({ ...prev, symbol: '', tradeUid: '', note: '' }));
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

  const handleRefreshDisplayFx = async () => {
    if (isLoading || fxRefreshing) {
      return;
    }
    try {
      setFxRefreshing(true);
      setFxRefreshFeedback(null);
      const result = await portfolioApi.refreshFx({ accountId: queryAccountId });
      await loadSnapshotAndRisk();
      setFxRefreshFeedback({
        tone: result.errorCount > 0 || result.staleCount > 0 ? 'warning' : 'success',
        text: result.errorCount > 0 || result.staleCount > 0
          ? translate(language, 'portfolio.fxRefreshFallbackWarning', {
            updatedCount: result.updatedCount,
            staleCount: result.staleCount,
            errorCount: result.errorCount,
          })
          : translate(language, 'portfolio.fxRefreshUpdated', { count: result.updatedCount }),
      });
    } catch (err) {
      setError(getParsedApiError(err));
    } finally {
      setFxRefreshing(false);
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
  const fxFreshnessLabel = fxRateRows.some((item) => item.isStale || item.source === 'missing')
    ? copy.fxStale
    : copy.fxFresh;
  const fxProviderLabel = fxRateRows.find((item) => item.source && item.source !== 'missing')?.source || 'frankfurter';
  const historyHasNextPage = currentEventCount >= DEFAULT_PAGE_SIZE;
  const hasAnyHistoryRecords = tradeEvents.length > 0 || cashEvents.length > 0 || corporateEvents.length > 0;
  const totalAssetsTitle = '总资产 Total Assets';
  const historyDrawerTitle = language === 'en' ? 'Order History' : '历史记录';

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
            <SeamlessSegmentedControl
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
                {positionRows.length === 0 && hasAnyHistoryRecords
                  ? (language === 'zh' ? '历史记录存在，当前无持仓' : 'History exists while current holdings are empty')
                  : copy.emptyEventsBody}
              </div>
            ) : (
              tradeEvents.map((item) => (
                <div key={`trade-${item.id}`} className="border-b border-white/5 px-1 py-4 transition-colors hover:bg-white/[0.03]">
                  <div className="flex items-start justify-between gap-4">
                    <div>
                      <div className="text-foreground">{item.symbol} <span className="text-xs text-muted-text">{formatSideLabel(item.side, language)}</span></div>
                      <div className="mt-1 text-xs text-muted-text">{item.tradeDate} · {item.quantity} @ {item.price}</div>
                    </div>
                    <Button type="button" variant="ghost" className={PORTFOLIO_DANGER_GHOST_CLASS} onClick={() => setPendingDelete({ eventType: 'trade', id: item.id, message: copy.tradeDeleteMessage(item) })} aria-label={copy.deleteConfirm} title={copy.deleteConfirm}>
                      <Trash2 className="h-4 w-4" aria-hidden="true" />
                    </Button>
                  </div>
                </div>
              ))
            )
          ) : null}

          {eventType === 'cash' ? (
            cashEvents.length === 0 ? (
              <div className="theme-panel-subtle rounded-xl px-5 py-4 text-sm text-secondary-text">
                {positionRows.length === 0 && hasAnyHistoryRecords
                  ? (language === 'zh' ? '历史记录存在，当前无持仓' : 'History exists while current holdings are empty')
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
                {positionRows.length === 0 && hasAnyHistoryRecords
                  ? (language === 'zh' ? '历史记录存在，当前无持仓' : 'History exists while current holdings are empty')
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

  return (
    <>
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

      <div
        ref={surfaceRef}
        data-testid="portfolio-bento-page"
        data-bento-surface="true"
        aria-hidden={shouldGuardA11y && !isSafariReady ? true : undefined}
        aria-live={shouldGuardA11y ? (isSafariReady ? 'polite' : 'off') : undefined}
        className={getSafariReadySurfaceClassName(
          isSafariReady,
          'w-full flex-1 flex flex-col gap-6 min-h-0 min-w-0 bg-transparent text-white/72',
        )}
      >
        <section className="mx-auto w-full max-w-[1880px] px-4 sm:px-6 lg:px-8 2xl:px-10">
          <div data-testid="portfolio-workspace-grid" className="grid grid-cols-12 items-start gap-5 xl:gap-6">
	            <div
	              data-testid="portfolio-total-assets-card"
	              className={`${PORTFOLIO_GLASS_CARD_CLASS} col-span-12 flex shrink-0 flex-col gap-5 lg:flex-row lg:items-stretch lg:justify-between`}
	            >
	              <div className="flex min-w-0 flex-1 flex-col justify-between gap-5">
                  <div className="min-w-0">
	                <div className="mb-3 flex min-w-0 flex-wrap items-center gap-3">
	                  <h1 className="text-xs uppercase tracking-widest text-muted-text">{totalAssetsTitle}</h1>
	                  {selectedAccount === 'all' ? (
	                    <span className="rounded-md bg-white/[0.04] px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white/35">{copy.allAccounts}</span>
	                  ) : writableAccount ? (
	                    <span className="rounded-md bg-white/[0.04] px-2 py-1 text-[10px] font-bold uppercase tracking-widest text-white/35">{writableAccount.name}</span>
	                  ) : null}
	                </div>
	                <div
	                  data-testid="portfolio-total-assets-value"
	                  className="font-mono text-[2.4rem] font-bold leading-none text-foreground tabular-nums md:text-[3.6rem]"
	                  style={{ textShadow: HERO_PNL_POSITIVE_GLOW }}
	                >
	                  {totalEquityDisplay ? formatMoney(totalEquityDisplay.value, displayCurrency) : formatMoney(totalEquity, snapshotCurrency)}
	                </div>
	                {snapshotCurrency !== displayCurrency ? (
	                  <div className="mt-2 font-mono text-xs text-white/35">{formatMoney(totalEquity, snapshotCurrency)}</div>
	                ) : null}
                  </div>
                  <div className="flex min-w-0 flex-wrap gap-2">
                    <span className="rounded-full border border-white/5 bg-white/[0.025] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-white/40">
                      {copy.accountCount} {snapshot?.accountCount ?? accounts.length}
                    </span>
                    <span className="rounded-full border border-white/5 bg-white/[0.025] px-3 py-1 text-[10px] font-bold uppercase tracking-widest text-white/40">
                      {copy.costMethodLabel} {costMethod.toUpperCase()}
                    </span>
                  </div>
	              </div>
	              <div className="grid w-full min-w-0 gap-3 sm:grid-cols-2 lg:w-[680px] xl:grid-cols-4">
	                <Select
	                  label="DISPLAY CURRENCY"
	                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
	                  value={displayCurrency}
	                  onChange={(value) => setDisplayCurrency(normalizeDisplayCurrency(value))}
	                  options={DISPLAY_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
	                  className={PORTFOLIO_SELECT_CLASS}
	                />
	                <div className="flex flex-col justify-end gap-2 xl:col-span-2">
	                  <Button
	                    type="button"
	                    variant="ghost"
	                    className={`${PORTFOLIO_SECONDARY_BUTTON_CLASS} w-full`}
	                    onClick={() => void handleRefreshDisplayFx()}
	                    disabled={isLoading || fxRefreshing}
	                  >
	                    {copy.refreshFx}
	                  </Button>
	                  <div className="min-w-0 text-[10px] font-bold uppercase tracking-widest text-white/35">
	                    {fxProviderLabel.toUpperCase()} · {fxFreshnessLabel} · {fxLastUpdated}
	                  </div>
	                  {fxRefreshFeedback && leftTab !== 'fx' ? (
	                    <div className={`text-xs ${
	                      fxRefreshFeedback.tone === 'success'
	                        ? 'text-emerald-300'
	                        : fxRefreshFeedback.tone === 'warning'
	                          ? 'text-amber-200'
	                          : 'text-secondary-text'
	                    }`}>
	                      {fxRefreshFeedback.text}
	                    </div>
	                  ) : null}
	                </div>
	                <div className="rounded-xl bg-white/[0.025] px-3 py-3">
	                  <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.totalCash}</div>
	                  <div className="mt-1 font-mono text-sm text-white tabular-nums">{totalCashDisplay ? formatMoney(totalCashDisplay.value, displayCurrency) : 'FX unavailable'}</div>
	                </div>
	                <div className="rounded-xl bg-white/[0.025] px-3 py-3">
	                  <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.totalMarketValue}</div>
	                  <div className="mt-1 font-mono text-sm text-white tabular-nums">{totalMarketValueDisplay ? formatMoney(totalMarketValueDisplay.value, displayCurrency) : 'FX unavailable'}</div>
	                </div>
	                <div className="rounded-xl bg-white/[0.025] px-3 py-3">
	                  <div className="text-[10px] font-bold uppercase tracking-widest text-white/40">{copy.positionUnrealized}</div>
	                  <div className={`mt-1 font-mono text-sm tabular-nums ${totalUnrealizedPnl >= 0 ? 'text-emerald-400 drop-shadow-[0_0_8px_rgba(52,211,153,0.4)]' : 'text-rose-400 drop-shadow-[0_0_8px_rgba(251,113,133,0.4)]'}`}>
	                    {totalUnrealizedDisplay ? formatSignedMoney(totalUnrealizedDisplay.value, displayCurrency) : 'FX unavailable'}
	                  </div>
	                </div>
	              </div>
	            </div>
	
	            <div
	              data-testid="portfolio-current-holdings-panel"
	              className={`${PORTFOLIO_GLASS_CARD_CLASS} col-span-12 flex flex-col overflow-visible xl:col-span-7 xl:min-h-[300px] 2xl:col-span-8`}
	            >
	              <div className="flex shrink-0 items-center justify-between gap-3 border-b border-white/5 pb-4">
	                <h2 className="min-w-0 text-xs uppercase tracking-widest text-muted-text">
	                  Current Holdings ({positionRows.length === 0 ? '共 0 项' : `共 ${positionRows.length} 项`})
	                </h2>
	              </div>
	
	              <div className="pt-4 lg:min-h-0 lg:flex-1 lg:overflow-y-auto lg:no-scrollbar lg:[&::-webkit-scrollbar]:hidden lg:[-ms-overflow-style:none] lg:[scrollbar-width:none]">
	                <div className="flex flex-col">
	                  {positionRows.length === 0 ? (
	                    <div data-testid="portfolio-empty-holdings" className="rounded-xl border border-white/5 bg-white/[0.02] px-5 py-4 text-sm text-secondary-text">
	                      <div className="text-foreground">{language === 'zh' ? '当前无持仓' : 'No current holdings'}</div>
	                      <div className="mt-1 text-xs text-muted-text">{language === 'zh' ? '录入交易后自动生成持仓' : 'New trades generate positions automatically.'}</div>
	                    </div>
	                  ) : (
	                    positionRows.map((row) => (
	                      <div
	                        key={`${row.accountId}-${row.symbol}-${row.market}`}
	                        className="flex flex-col gap-3 border-b border-white/5 px-1 py-3 transition-colors hover:bg-white/[0.03] sm:flex-row sm:items-center sm:justify-between"
	                      >
	                        <div className="min-w-0">
	                          <div className="truncate text-lg font-medium text-foreground">{row.symbol}</div>
	                          <div className="truncate text-xs text-muted-text">{row.accountName} · {formatPositionContext(row.market, row.currency, language)}</div>
	                        </div>
	                        <div className="flex shrink-0 flex-wrap items-center justify-between gap-4 sm:justify-end">
	                          <div className="text-right">
	                            <div className="text-[11px] uppercase tracking-[0.16em] text-muted-text">{copy.positionMarketValue}</div>
	                            <div className="font-mono text-foreground tabular-nums">{formatMoney(row.marketValueBase, row.valuationCurrency)}</div>
	                            {row.valuationCurrency !== displayCurrency ? (
	                              <div className="mt-1 font-mono text-xs text-white/40">
	                                {convertMoney(row.marketValueBase, row.valuationCurrency)
	                                  ? `≈ ${formatMoney(convertMoney(row.marketValueBase, row.valuationCurrency)?.value, displayCurrency)}`
	                                  : 'FX unavailable'}
	                              </div>
	                            ) : null}
	                          </div>
	                          <div className={`font-mono text-lg tabular-nums ${row.unrealizedPnlBase >= 0 ? 'text-emerald-400' : 'text-rose-400'}`}>
	                            {row.valuationCurrency === displayCurrency
	                              ? formatSignedMoney(row.unrealizedPnlBase, row.valuationCurrency)
	                              : (convertMoney(row.unrealizedPnlBase, row.valuationCurrency)
	                                ? formatSignedMoney(convertMoney(row.unrealizedPnlBase, row.valuationCurrency)?.value ?? 0, displayCurrency)
	                                : 'FX unavailable')}
	                          </div>
	                        </div>
	                      </div>
	                    ))
	                  )}
	                </div>
	              </div>
	            </div>
	
	          <section data-testid="portfolio-trade-station-card" className={`${PORTFOLIO_GLASS_CARD_CLASS} col-span-12 flex flex-col gap-5 overflow-visible xl:col-span-5 xl:min-h-[300px] 2xl:col-span-4`}>
            <div className="shrink-0">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="text-sm text-muted-text uppercase tracking-widest">Trade Station</h2>
                </div>
              </div>
              <div className="mt-3 grid grid-cols-1 gap-2.5 sm:grid-cols-2">
                <Select
                  label="ACCOUNT"
                  labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                  value={String(selectedAccount)}
                  onChange={(value) => setSelectedAccount(value === 'all' ? 'all' : Number(value))}
                  options={[
                    { value: 'all', label: copy.allAccounts },
                    ...accounts.map((account) => ({ value: String(account.id), label: account.name })),
                  ]}
                  className={PORTFOLIO_SELECT_CLASS}
                  controlClassName="rounded-lg"
                />
                <Select
                  label="COST METHOD"
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
                <div className="flex justify-between gap-3 text-xs"><span className="text-muted-text">{copy.totalCash}</span><span className="font-mono text-foreground">{totalCashDisplay ? formatMoney(totalCashDisplay.value, displayCurrency) : 'FX unavailable'}</span></div>
                <div className="flex justify-between gap-3 text-xs"><span className="text-muted-text">{copy.totalMarketValue}</span><span className="font-mono text-foreground">{totalMarketValueDisplay ? formatMoney(totalMarketValueDisplay.value, displayCurrency) : 'FX unavailable'}</span></div>
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
              <SeamlessSegmentedControl
                value={leftTab}
                onChange={(value) => setLeftTab(value as 'trade' | 'account' | 'sync' | 'fx')}
                options={[
                  { value: 'trade', label: language === 'en' ? 'Trade' : '交易' },
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
                    <SeamlessSegmentedControl
                      value={tradeType}
                      onChange={(value) => setTradeType(value as TradeFormType)}
                      options={[
                        { value: 'stock', label: language === 'en' ? 'Stock Trade' : '股票买卖' },
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
                          <Input label="SYMBOL" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder="AAPL" value={tradeForm.symbol} onChange={(e) => setTradeForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                          <Input label="TRADE DATE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={tradeForm.tradeDate} onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeDate: e.target.value }))} required />
                          <Select label="SIDE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={tradeForm.side} onChange={(value) => setTradeForm((prev) => ({ ...prev, side: value as PortfolioSide }))} options={[{ value: 'buy', label: copy.buy }, { value: 'sell', label: copy.sell }]} />
                          <Input label="REFERENCE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="text" placeholder="optional" value={tradeForm.tradeUid} onChange={(e) => setTradeForm((prev) => ({ ...prev, tradeUid: e.target.value }))} />
                          <Input label="QUANTITY" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={tradeForm.quantity} onChange={(e) => setTradeForm((prev) => ({ ...prev, quantity: e.target.value }))} required />
                          <Input label="PRICE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={tradeForm.price} onChange={(e) => setTradeForm((prev) => ({ ...prev, price: e.target.value }))} required />
                          <Input label="FEE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="optional" value={tradeForm.fee} onChange={(e) => setTradeForm((prev) => ({ ...prev, fee: e.target.value }))} />
                          <Input label="TAX" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="optional" value={tradeForm.tax} onChange={(e) => setTradeForm((prev) => ({ ...prev, tax: e.target.value }))} />
                        </div>
                        <Input label="NOTE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder="optional" value={tradeForm.note} onChange={(e) => setTradeForm((prev) => ({ ...prev, note: e.target.value }))} />
                        {!writableAccountId ? (
                          <div className="mt-3 rounded-lg border border-amber-300/15 bg-amber-300/10 px-3 py-2 text-xs text-amber-200">
                            {language === 'zh' ? '请选择具体账户后录入交易' : 'Select a specific account before recording trades'}
                          </div>
                        ) : null}
                        <button type="submit" className={PORTFOLIO_SUBMIT_BUTTON_CLASS} disabled={!writableAccountId || tradeSubmitting}>{tradeSubmitting ? copy.refreshingData : copy.submitTrade}</button>
                      </form>
                    </div>
                  ) : null}

                  {tradeType === 'fund' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCash}</p>
                      <form onSubmit={handleCashSubmit}>
                        <div data-testid="portfolio-cash-amount-currency-grid" className={PORTFOLIO_FORM_GRID_CLASS}>
                          <Input label="EVENT DATE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={cashForm.eventDate} onChange={(e) => setCashForm((prev) => ({ ...prev, eventDate: e.target.value }))} required />
                          <Select label="DIRECTION" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={cashForm.direction} onChange={(value) => setCashForm((prev) => ({ ...prev, direction: value as PortfolioCashDirection }))} options={[{ value: 'in', label: copy.cashIn }, { value: 'out', label: copy.cashOut }]} />
                          <Input label="AMOUNT" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.01" placeholder="0.00" value={cashForm.amount} onChange={(e) => setCashForm((prev) => ({ ...prev, amount: e.target.value }))} required />
                          <Select
                            data-testid="portfolio-cash-currency-select"
                            label="CURRENCY"
                            labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                            className={PORTFOLIO_SELECT_CLASS}
                            value={cashForm.currency}
                            onChange={(value) => setCashForm((prev) => ({ ...prev, currency: value }))}
                            options={CASH_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                            placeholder={copy.currencyOptional(snapshotCurrency)}
                          />
                        </div>
                        <Input label="NOTE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder="optional" value={cashForm.note} onChange={(e) => setCashForm((prev) => ({ ...prev, note: e.target.value }))} />
                        <button type="submit" className={PORTFOLIO_SUBMIT_BUTTON_CLASS} disabled={!writableAccountId}>{copy.submitCash}</button>
                      </form>
                    </SectionShell>
                  ) : null}

                  {tradeType === 'corporate' ? (
                    <SectionShell className="rounded-2xl border border-white/5 bg-white/[0.02] p-4" contentClassName="">
                      <p className="text-xs uppercase tracking-[0.18em] text-muted-text">{copy.manualCorporate}</p>
                      <form onSubmit={handleCorporateSubmit}>
                        <div className={PORTFOLIO_FORM_GRID_CLASS}>
                          <Input label="SYMBOL" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} placeholder="AAPL" value={corpForm.symbol} onChange={(e) => setCorpForm((prev) => ({ ...prev, symbol: e.target.value }))} required />
                          <Input label="EFFECTIVE DATE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="date" value={corpForm.effectiveDate} onChange={(e) => setCorpForm((prev) => ({ ...prev, effectiveDate: e.target.value }))} required />
                          <Select label="ACTION TYPE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} className={PORTFOLIO_SELECT_CLASS} value={corpForm.actionType} onChange={(value) => setCorpForm((prev) => ({ ...prev, actionType: value as PortfolioCorporateActionType }))} options={[{ value: 'cash_dividend', label: copy.cashDividend }, { value: 'split_adjustment', label: copy.splitAdjustment }]} />
                          <Input label="DIVIDEND" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="0.0000" value={corpForm.cashDividendPerShare} onChange={(e) => setCorpForm((prev) => ({ ...prev, cashDividendPerShare: e.target.value }))} />
                          <Input label="SPLIT RATIO" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={PORTFOLIO_FIELD_WRAPPER_CLASS} className={PORTFOLIO_INPUT_CLASS} type="number" min="0" step="0.0001" placeholder="1.0000" value={corpForm.splitRatio} onChange={(e) => setCorpForm((prev) => ({ ...prev, splitRatio: e.target.value }))} />
                        </div>
                        <Input label="NOTE" labelClassName={PORTFOLIO_FIELD_LABEL_CLASS} containerClassName={`${PORTFOLIO_FIELD_WRAPPER_CLASS} mt-5`} className={PORTFOLIO_INPUT_CLASS} placeholder="optional" value={corpForm.note} onChange={(e) => setCorpForm((prev) => ({ ...prev, note: e.target.value }))} />
                        <button type="submit" className={PORTFOLIO_SUBMIT_BUTTON_CLASS} disabled={!writableAccountId}>{copy.submitCorporate}</button>
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
                    <p className="text-xs uppercase tracking-[0.18em] text-muted-text">LIVE EXCHANGE ENGINE</p>
                    <p className="mt-1 text-[11px] text-white/35">
                      {language === 'en' ? 'Last update' : '最后更新'} {selectedFxRate?.timestamp ? formatFxTimestamp(selectedFxRate.timestamp) : fxLastUpdated}
                      {selectedFxRate?.isStale ? ` · ${copy.fxStale}` : ''}
                    </p>
                  </div>
                  <div className="grid grid-cols-[minmax(0,1fr)_auto_minmax(0,1fr)] items-end gap-2">
                    <Select
                      label="Base Currency"
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      className={PORTFOLIO_SELECT_CLASS}
                      value={fxBaseCurrency}
                      onChange={setFxBaseCurrency}
                      options={FX_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                    />
                    <span className="mb-2 flex h-10 w-8 items-center justify-center rounded-lg bg-white/[0.04] text-white/45" aria-hidden="true">⇄</span>
                    <Select
                      label="Quote Currency"
                      labelClassName={PORTFOLIO_FIELD_LABEL_CLASS}
                      className={PORTFOLIO_SELECT_CLASS}
                      value={fxQuoteCurrency}
                      onChange={setFxQuoteCurrency}
                      options={FX_CURRENCY_OPTIONS.map((currency) => ({ value: currency, label: currency }))}
                    />
                  </div>
	                  <div className="rounded-2xl bg-white/[0.025] px-4 py-5">
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
	                      <span>{selectedFxRate?.cacheHit ? 'CACHE' : 'LIVE'}</span>
	                      {selectedFxRate?.isStale ? <span className="text-amber-300">{copy.fxStale}</span> : null}
	                    </div>
	                  </div>
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
          </section>

            <section data-testid="portfolio-history-panel" className={`${PORTFOLIO_GLASS_CARD_CLASS} col-span-12 flex max-h-[560px] min-h-[300px] flex-col overflow-hidden`}>
              {historyPanelContent}
            </section>
          </div>
        </section>
      </div>

      <ConfirmDialog
        isOpen={Boolean(pendingDelete)}
        title={copy.deleteTitle}
        message={pendingDelete?.message || copy.deleteMessage}
        confirmText={deleteLoading ? copy.deleteInProgress : copy.deleteConfirm}
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
