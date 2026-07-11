import type { MarketOverviewPanel } from '../api/marketOverview';
import { marketApi } from '../api/market';
import type {
  CryptoRealtimeStatus,
  PanelKey,
  PanelState,
} from '../components/market-overview/MarketOverviewWorkbench';

type CryptoStreamSubscriber = (update: {
  status: CryptoRealtimeStatus;
  panel?: MarketOverviewPanel;
}) => void;

const inFlightPanelRequestCache = new Map<string, Promise<PanelState[PanelKey]>>();
const inFlightReadinessRequestCache = new Map<string, Promise<unknown>>();
const cryptoStreamSubscribers = new Set<CryptoStreamSubscriber>();

let sharedCryptoEventSource: EventSource | null = null;
let latestCryptoStreamStatus: CryptoRealtimeStatus = 'snapshot';

function panelRequestCacheKey(panelKey: PanelKey): string {
  return `market-overview:${String(panelKey)}`;
}

export function loadPanelWithRequestDedupe(
  panelKey: PanelKey,
  loadPanel: () => Promise<PanelState[PanelKey]>,
): Promise<PanelState[PanelKey]> {
  const cacheKey = panelRequestCacheKey(panelKey);
  const cached = inFlightPanelRequestCache.get(cacheKey);
  if (cached) {
    return cached;
  }
  const promise = loadPanel().finally(() => {
    if (inFlightPanelRequestCache.get(cacheKey) === promise) {
      inFlightPanelRequestCache.delete(cacheKey);
    }
  });
  inFlightPanelRequestCache.set(cacheKey, promise);
  return promise;
}

export function loadReadinessWithRequestDedupe<T>(cacheKey: string, load: () => Promise<T>): Promise<T> {
  const cached = inFlightReadinessRequestCache.get(cacheKey) as Promise<T> | undefined;
  if (cached) {
    return cached;
  }
  const promise = load().finally(() => {
    if (inFlightReadinessRequestCache.get(cacheKey) === promise) {
      inFlightReadinessRequestCache.delete(cacheKey);
    }
  });
  inFlightReadinessRequestCache.set(cacheKey, promise);
  return promise;
}

function publishCryptoStreamUpdate(update: { status: CryptoRealtimeStatus; panel?: MarketOverviewPanel }): void {
  latestCryptoStreamStatus = update.status;
  cryptoStreamSubscribers.forEach((subscriber) => subscriber(update));
}

function ensureSharedCryptoStream(): void {
  if (typeof window === 'undefined' || typeof window.EventSource === 'undefined') {
    publishCryptoStreamUpdate({ status: 'snapshot' });
    return;
  }
  if (sharedCryptoEventSource) {
    return;
  }
  const eventSource = new window.EventSource(marketApi.cryptoStreamUrl(), { withCredentials: true });
  sharedCryptoEventSource = eventSource;
  eventSource.onopen = () => {
    publishCryptoStreamUpdate({ status: 'live' });
  };
  eventSource.onmessage = (event) => {
    try {
      const payload = JSON.parse(event.data) as Record<string, unknown>;
      const panel = marketApi.normalizeCryptoStreamPayload(payload);
      publishCryptoStreamUpdate({
        panel,
        status: panel.freshness === 'live' ? 'live' : 'snapshot',
      });
    } catch {
      publishCryptoStreamUpdate({ status: 'snapshot' });
    }
  };
  eventSource.onerror = () => {
    publishCryptoStreamUpdate({ status: 'reconnecting' });
  };
}

export function subscribeToCryptoStream(subscriber: CryptoStreamSubscriber): () => void {
  cryptoStreamSubscribers.add(subscriber);
  ensureSharedCryptoStream();
  subscriber({ status: latestCryptoStreamStatus });
  return () => {
    cryptoStreamSubscribers.delete(subscriber);
    if (cryptoStreamSubscribers.size > 0 || typeof window === 'undefined') {
      return;
    }
    window.queueMicrotask(() => {
      if (cryptoStreamSubscribers.size === 0) {
        sharedCryptoEventSource?.close();
        sharedCryptoEventSource = null;
        latestCryptoStreamStatus = 'snapshot';
      }
    });
  };
}

export function resetMarketOverviewRequestOwnershipForTests(): void {
  if (!import.meta.env.TEST) {
    return;
  }
  inFlightPanelRequestCache.clear();
  inFlightReadinessRequestCache.clear();
  cryptoStreamSubscribers.clear();
  sharedCryptoEventSource?.close();
  sharedCryptoEventSource = null;
  latestCryptoStreamStatus = 'snapshot';
}
