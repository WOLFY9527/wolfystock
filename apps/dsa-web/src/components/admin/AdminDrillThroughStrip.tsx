import type React from 'react';
import { ExternalLink } from 'lucide-react';
import { TerminalChip } from '../terminal';
import { cn } from '../../utils/cn';
import { resolveProductSetupSurface } from '../../utils/productSetupSurface';

type AdminDrillTarget =
  | 'logs'
  | 'evidence'
  | 'marketProviders'
  | 'providerCircuits'
  | 'cost'
  | 'users'
  | 'userDetail'
  | 'userActivity';

export type AdminDrillThroughItem = {
  label: string;
  target: AdminDrillTarget;
  evidenceType: string;
  reason: string;
  redacted?: boolean;
  params?: Record<string, unknown>;
  hash?: string | null;
  userId?: string | null;
  hrefOverride?: string | null;
};

type AdminDrillThroughStripProps = {
  items: AdminDrillThroughItem[];
  title?: string;
  className?: string;
  dataTestId?: string;
};

const LOG_TABS = new Set(['business', 'analysis', 'scanner', 'backtest', 'data_source', 'security', 'raw']);
const LOG_WINDOWS = new Set(['15m', '1h', '24h', '7d']);
const COST_WINDOWS = new Set(['15m', '1h', '24h', '7d']);
const COST_BUCKETS = new Set(['hour', 'day']);
const COST_AREAS = new Set(['all', 'llm', 'provider', 'market-cache', 'scanner-ai']);
const USER_TABS = new Set(['detail', 'portfolio', 'security']);
const SAFE_TEXT_RE = /[^a-zA-Z0-9 _:-]/g;
const SAFE_CODE_RE = /[^a-zA-Z0-9:_-]/g;
const URL_FRAGMENT_RE = /https?:\/\/\S+|www\.\S+/gi;
const SECRET_FRAGMENT_RE = /\b(token|secret|cookie|session|password|bearer|api[_-]?key|stack|trace|payload|prompt|credential)\b[:=]?\S*/gi;

function sanitizeSearchText(value: unknown, maxLength = 80): string | null {
  const cleaned = String(value || '')
    .replace(URL_FRAGMENT_RE, ' ')
    .replace(SECRET_FRAGMENT_RE, ' ')
    .replace(SAFE_TEXT_RE, ' ')
    .replace(/\s+/g, ' ')
    .trim()
    .slice(0, maxLength);
  return cleaned || null;
}

function sanitizeCode(value: unknown, maxLength = 64, lower = false): string | null {
  const normalized = String(value || '')
    .replace(URL_FRAGMENT_RE, '')
    .replace(SECRET_FRAGMENT_RE, '')
    .replace(SAFE_CODE_RE, '')
    .slice(0, maxLength);
  if (!normalized) return null;
  return lower ? normalized.toLowerCase() : normalized;
}

function sanitizeHash(value: unknown): string | null {
  const normalized = sanitizeCode(value, 40, true);
  return normalized || null;
}

function sanitizePositiveInt(value: unknown, min: number, max: number): string | null {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return null;
  return String(Math.min(Math.max(Math.trunc(parsed), min), max));
}

function appendQuery(query: URLSearchParams, key: string, value: string | null): void {
  if (value) query.set(key, value);
}

function routeForTarget(target: AdminDrillTarget, userId?: string | null): string | null {
  if (target === 'logs') return '/zh/admin/logs';
  if (target === 'evidence') return '/zh/admin/evidence-workflow';
  if (target === 'marketProviders') return '/zh/admin/market-providers';
  if (target === 'providerCircuits') return '/zh/admin/provider-circuits';
  if (target === 'cost') return '/zh/admin/cost-observability';
  if (target === 'users') return '/zh/admin/users';
  if (target === 'userDetail') {
    const safeUserId = sanitizeCode(userId, 80, false);
    return safeUserId ? `/zh/admin/users/${encodeURIComponent(safeUserId)}` : null;
  }
  if (target === 'userActivity') {
    const safeUserId = sanitizeCode(userId, 80, false);
    return safeUserId ? `/zh/admin/users/${encodeURIComponent(safeUserId)}/activity` : null;
  }
  return null;
}

function applyTargetQuery(target: AdminDrillTarget, params: Record<string, unknown> | undefined, query: URLSearchParams): void {
  if (target === 'logs') {
    const tab = sanitizeCode(params?.tab, 24, false);
    appendQuery(query, 'tab', tab && LOG_TABS.has(tab) ? tab : null);
    appendQuery(query, 'query', sanitizeSearchText(params?.query));
    appendQuery(query, 'since', LOG_WINDOWS.has(String(params?.since || '')) ? String(params?.since) : null);
    appendQuery(query, 'eventId', sanitizeCode(params?.eventId, 80, false));
    appendQuery(query, 'requestId', sanitizeCode(params?.requestId, 80, false));
    appendQuery(query, 'userId', sanitizeCode(params?.userId, 80, false));
    return;
  }

  if (target === 'evidence') {
    appendQuery(query, 'ref', sanitizeCode(params?.ref, 80, false));
    return;
  }

  if (target === 'marketProviders') {
    const surface = resolveProductSetupSurface(params?.surface);
    appendQuery(query, 'surface', surface?.key || null);
    return;
  }

  if (target === 'providerCircuits') {
    appendQuery(query, 'provider', sanitizeCode(params?.provider, 64, true));
    appendQuery(query, 'routeFamily', sanitizeCode(params?.routeFamily, 64, true));
    appendQuery(query, 'since', LOG_WINDOWS.has(String(params?.since || '')) ? String(params?.since) : null);
    return;
  }

  if (target === 'cost') {
    appendQuery(query, 'window', COST_WINDOWS.has(String(params?.window || '')) ? String(params?.window) : null);
    appendQuery(query, 'bucket', COST_BUCKETS.has(String(params?.bucket || '')) ? String(params?.bucket) : null);
    appendQuery(query, 'area', COST_AREAS.has(String(params?.area || '')) ? String(params?.area) : null);
    appendQuery(query, 'limit', sanitizePositiveInt(params?.limit, 1, 200));
    return;
  }

  if (target === 'userDetail') {
    const tab = sanitizeCode(params?.tab, 24, false);
    appendQuery(query, 'tab', tab && USER_TABS.has(tab) ? tab : null);
    return;
  }

  if (target === 'users') {
    appendQuery(query, 'q', sanitizeSearchText(params?.q, 48));
  }
}

function buildAdminDrillHref(item: Pick<AdminDrillThroughItem, 'target' | 'params' | 'hash' | 'userId' | 'hrefOverride'>): string | null {
  if (item.hrefOverride) {
    if (!item.hrefOverride.startsWith('/zh/admin/') && !item.hrefOverride.startsWith('/en/admin/')) {
      return null;
    }
  }

  const route = routeForTarget(item.target, item.userId);
  if (!route) return null;

  const query = new URLSearchParams();
  applyTargetQuery(item.target, item.params, query);
  const hash = sanitizeHash(item.hash);
  const queryText = query.toString().replace(/\+/g, '%20');
  return `${route}${queryText ? `?${queryText}` : ''}${hash ? `#${hash}` : ''}`;
}

const AdminDrillThroughStrip: React.FC<AdminDrillThroughStripProps> = ({
  items,
  title = '安全下钻',
  className,
  dataTestId = 'admin-drill-through-strip',
}) => {
  const visibleItems = items
    .map((item) => ({ ...item, href: buildAdminDrillHref(item) }))
    .filter((item): item is AdminDrillThroughItem & { href: string } => Boolean(item.label && item.href));

  if (!visibleItems.length) return null;

  return (
    <section
      data-testid={dataTestId}
      className={cn('rounded-xl border border-white/[0.08] bg-white/[0.02] px-3 py-3', className)}
      aria-label={title}
    >
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[10px] font-semibold uppercase tracking-[0.18em] text-white/34">{title}</p>
        <TerminalChip variant="neutral">已脱敏引用</TerminalChip>
      </div>
      <div className="mt-3 grid gap-2 lg:grid-cols-2">
        {visibleItems.map((item) => (
          <a
            key={`${item.target}-${item.label}-${item.href}`}
            href={item.href}
            className="group rounded-lg border border-white/8 bg-black/10 px-3 py-2.5 transition hover:border-cyan-300/25 hover:bg-white/[0.04]"
          >
            <div className="flex items-center justify-between gap-2">
              <span className="text-sm font-semibold text-white/86">{item.label}</span>
              <ExternalLink className="h-3.5 w-3.5 text-white/42 transition group-hover:text-cyan-100" aria-hidden="true" />
            </div>
            <p className="mt-1 text-[11px] text-white/42">{item.evidenceType}{item.redacted === false ? '' : ' · 已脱敏引用'}</p>
            <p className="mt-1 text-[11px] leading-5 text-white/58">{item.reason}</p>
          </a>
        ))}
      </div>
    </section>
  );
};

export default AdminDrillThroughStrip;
