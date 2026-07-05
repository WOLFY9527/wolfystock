import type React from 'react';
import { useState } from 'react';
import { Copy, Download } from 'lucide-react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import {
  consumerPresentationArtifactVersionLabel,
  consumerPresentationText,
  type ConsumerPresentationLocale,
} from '../../utils/consumerPresentationBoundary';

export type ResearchArtifactRegistryLocale = 'zh' | 'en';
export type ResearchArtifactRegistryState = 'available' | 'blocked' | 'unavailable';

export type ResearchArtifactRegistryEntry = {
  packKey: string;
  label: string;
  schemaVersion?: string | null;
  sourceSurface?: string | null;
  state: ResearchArtifactRegistryState;
  description: string;
  contents?: string[];
  exportContent?: string | null;
  fileName?: string;
  copyLabel?: string;
  downloadLabel?: string;
  copyTestId?: string;
  downloadTestId?: string;
  blockedCopyTestId?: string;
};

type ResearchArtifactRegistryProps = {
  entries: ResearchArtifactRegistryEntry[];
  locale?: ResearchArtifactRegistryLocale;
  title?: string;
  className?: string;
  testId?: string;
};

const UNKNOWN_LABELS: Record<ResearchArtifactRegistryLocale, string> = {
  zh: '待补证',
  en: 'unknown',
};

const STATE_LABELS: Record<ResearchArtifactRegistryState, Record<ResearchArtifactRegistryLocale, string>> = {
  available: { zh: '可用', en: 'Available' },
  blocked: { zh: '阻断', en: 'Blocked' },
  unavailable: { zh: '待补证', en: 'Unavailable' },
};

const STATUS_MESSAGES: Record<string, Record<ResearchArtifactRegistryLocale, string>> = {
  copied: { zh: '研究记录已复制。', en: 'Research record copied.' },
  exported: { zh: '研究记录已保存。', en: 'Research record saved.' },
  pending: { zh: '研究记录待补证，未复制。', en: 'Research record pending; nothing copied.' },
};

function stateVariant(state: ResearchArtifactRegistryState): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (state === 'available') return 'success';
  if (state === 'blocked') return 'danger';
  return 'caution';
}

function unknown(locale: ResearchArtifactRegistryLocale): string {
  return UNKNOWN_LABELS[locale];
}

function safeText(value: string | null | undefined, locale: ResearchArtifactRegistryLocale): string {
  const text = String(value || '').trim();
  return text ? consumerPresentationText(text, locale as ConsumerPresentationLocale, unknown(locale)) : unknown(locale);
}

function versionText(value: string | null | undefined, locale: ResearchArtifactRegistryLocale): string {
  return value ? consumerPresentationArtifactVersionLabel(locale as ConsumerPresentationLocale) : unknown(locale);
}

function normalizeEntryState(entry: ResearchArtifactRegistryEntry): ResearchArtifactRegistryState {
  if (entry.state !== 'available') return entry.state;
  return entry.exportContent ? 'available' : 'unavailable';
}

function downloadJsonFile(filename: string, content: string): void {
  const blob = new Blob([content], { type: 'application/json;charset=utf-8' });
  const url = URL.createObjectURL(blob);
  const link = document.createElement('a');
  link.href = url;
  link.download = filename;
  link.click();
  URL.revokeObjectURL(url);
}

export default function ResearchArtifactRegistry({
  entries,
  locale = 'zh',
  title,
  className,
  testId,
}: ResearchArtifactRegistryProps) {
  const [statusByKey, setStatusByKey] = useState<Record<string, string>>({});
  const resolvedTitle = title || (locale === 'en' ? 'Research records' : '研究记录');
  const actionBaseClass = 'inline-flex min-h-[36px] items-center justify-center gap-1.5 rounded-md border border-white/10 bg-white/[0.03] px-2.5 py-1.5 text-xs font-semibold text-white/78 transition-colors hover:border-white/20 hover:bg-white/[0.06] disabled:cursor-not-allowed disabled:opacity-45';

  if (!entries.length) return null;

  const handleCopy = async (entry: ResearchArtifactRegistryEntry, state: ResearchArtifactRegistryState) => {
    if (state !== 'available' || !entry.exportContent || !navigator.clipboard?.writeText) {
      setStatusByKey((current) => ({ ...current, [entry.packKey]: STATUS_MESSAGES.pending[locale] }));
      return;
    }
    await navigator.clipboard.writeText(entry.exportContent);
    setStatusByKey((current) => ({ ...current, [entry.packKey]: STATUS_MESSAGES.copied[locale] }));
  };

  const handleDownload = (entry: ResearchArtifactRegistryEntry, state: ResearchArtifactRegistryState) => {
    if (state !== 'available' || !entry.exportContent) {
      setStatusByKey((current) => ({ ...current, [entry.packKey]: STATUS_MESSAGES.pending[locale] }));
      return;
    }
    downloadJsonFile(entry.fileName || `${entry.packKey}.json`, entry.exportContent);
    setStatusByKey((current) => ({ ...current, [entry.packKey]: STATUS_MESSAGES.exported[locale] }));
  };

  return (
    <section
      data-testid={testId}
      className={cn('rounded-lg border border-white/5 bg-white/[0.02] p-3', className)}
    >
      <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] font-bold uppercase tracking-widest text-white/42">{resolvedTitle}</p>
          <p className="mt-1 text-xs leading-5 text-white/54">
            {locale === 'en'
              ? 'One registry for available and pending research artifacts.'
              : '统一登记可用与待补证的研究产物。'}
          </p>
        </div>
      </div>
      <div className="mt-3 grid gap-2">
        {entries.map((entry) => {
          const state = normalizeEntryState(entry);
          const contents = entry.contents?.filter(Boolean);
          const status = statusByKey[entry.packKey];
          return (
            <article
              key={entry.packKey}
              aria-label={`${entry.label} ${STATE_LABELS[state][locale]}`}
              className="rounded-lg border border-white/[0.06] bg-black/10 p-3"
            >
              <div className="flex min-w-0 flex-col gap-3 lg:flex-row lg:items-start lg:justify-between">
                <div className="min-w-0">
                  <div className="flex min-w-0 flex-wrap items-center gap-2">
                    <h4 className="text-sm font-semibold text-white/88">{entry.label}</h4>
                    <TerminalChip variant={stateVariant(state)}>{STATE_LABELS[state][locale]}</TerminalChip>
                  </div>
                  <p className="mt-1 text-xs leading-5 text-white/58">{safeText(entry.description, locale)}</p>
                  <dl className="mt-2 grid gap-2 text-[11px] leading-5 text-white/58 sm:grid-cols-2">
                    <div>
                      <dt className="text-white/38">{locale === 'en' ? 'Record type' : '记录类型'}</dt>
                      <dd className="break-all text-white/72">{versionText(entry.schemaVersion, locale)}</dd>
                    </div>
                    <div>
                      <dt className="text-white/38">{locale === 'en' ? 'Source page' : '来源页面'}</dt>
                      <dd className="text-white/72">{safeText(entry.sourceSurface, locale)}</dd>
                    </div>
                  </dl>
                  <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
                    {(contents?.length ? contents : [unknown(locale)]).map((item) => (
                      <TerminalChip key={item} variant="neutral">{item}</TerminalChip>
                    ))}
                  </div>
                  {status ? (
                    <p className="mt-2 text-[11px] leading-5 text-white/52">{status}</p>
                  ) : null}
                </div>
                <div className="flex min-w-0 flex-wrap gap-2">
                  {state === 'available' ? (
                    <>
                      <button
                        type="button"
                        className={actionBaseClass}
                        onClick={() => void handleCopy(entry, state)}
                        data-testid={entry.copyTestId}
                      >
                        <Copy className="size-3.5" aria-hidden="true" />
                        {entry.copyLabel || (locale === 'en' ? 'Copy record' : '复制研究记录')}
                      </button>
                      <button
                        type="button"
                        className={actionBaseClass}
                        onClick={() => handleDownload(entry, state)}
                        data-testid={entry.downloadTestId}
                      >
                        <Download className="size-3.5" aria-hidden="true" />
                        {entry.downloadLabel || (locale === 'en' ? 'Save record' : '保存研究记录')}
                      </button>
                    </>
                  ) : (
                    <button
                      type="button"
                      className={actionBaseClass}
                      disabled
                      data-testid={entry.blockedCopyTestId}
                    >
                      <Copy className="size-3.5" aria-hidden="true" />
                      {locale === 'en' ? 'Copy pending' : '复制待补证'}
                    </button>
                  )}
                </div>
              </div>
            </article>
          );
        })}
      </div>
    </section>
  );
}
