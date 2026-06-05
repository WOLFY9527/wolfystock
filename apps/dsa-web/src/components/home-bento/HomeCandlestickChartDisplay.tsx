import type React from 'react';
import { cn } from '../../utils/cn';

export type HomeChartTimeframeControl = {
  key: string;
  label: string;
  description: string;
  pressed: boolean;
  disabled: boolean;
};

export type HomeChartIndicatorChip = {
  key: string;
  label: string;
  color: string;
  pressed: boolean;
  available: boolean;
  title: string;
};

type HomeCandlestickChartTimeframeStripProps = {
  controls: HomeChartTimeframeControl[];
  ticker: string;
  sourceHint?: string;
  maStructure?: string;
  onSelect: (key: string) => void;
};

type HomeCandlestickChartIndicatorChipsProps = {
  chips: HomeChartIndicatorChip[];
  vwapUnavailableLabel?: string | null;
  onToggle: (key: string) => void;
};

type HomeCandlestickChartContextBadgesProps = {
  priceLabel: string;
  volumeLabel: string;
  rangeHintLabel: string;
};

type HomeCandlestickChartUnavailablePanelProps = {
  statusLabel: string;
  timeframeLabel: string;
  title: string;
  body?: string | null;
  isLoading: boolean;
};

export const HomeCandlestickChartTimeframeStrip: React.FC<HomeCandlestickChartTimeframeStripProps> = ({
  controls,
  ticker,
  sourceHint,
  maStructure,
  onSelect,
}) => (
  <div className="flex min-w-0 flex-wrap items-center justify-between gap-2">
    <div className="flex min-w-0 flex-wrap items-center gap-2">
      <div
        className="flex min-w-0 flex-wrap items-center gap-1 rounded-[18px] border border-[color:var(--wolfy-border-faint)] bg-white/[0.025] p-1 sm:gap-0.5 sm:rounded-full sm:p-0.5"
        data-testid="home-chart-timeframe-controls"
      >
        {controls.map((control) => (
          <button
            key={control.key}
            type="button"
            aria-pressed={control.pressed}
            data-testid={`home-chart-timeframe-${control.key}`}
            className={cn(
              'touch-manipulation min-h-[40px] rounded-full px-3.5 py-2 text-[11px] font-medium leading-none transition-colors sm:min-h-0 sm:px-2.5 sm:py-1 sm:text-[10px]',
              control.pressed
                ? 'bg-[var(--wolfy-accent-soft)] text-white/86'
                : 'text-white/42 hover:bg-white/[0.04] hover:text-white/72',
            )}
            onClick={() => onSelect(control.key)}
            disabled={control.disabled}
            title={control.description}
          >
            {control.label}
          </button>
        ))}
      </div>
      <span className="hidden text-[10px] text-white/30 sm:inline">{ticker}</span>
      {sourceHint ? (
        <span className="text-[10px] text-white/30">{sourceHint}</span>
      ) : null}
    </div>
    {maStructure ? (
      <span className="text-[10px] text-white/30">{maStructure}</span>
    ) : null}
  </div>
);

export const HomeCandlestickChartIndicatorChips: React.FC<HomeCandlestickChartIndicatorChipsProps> = ({
  chips,
  vwapUnavailableLabel,
  onToggle,
}) => (
  <div className="flex min-w-0 flex-wrap items-center gap-2 sm:gap-1.5" data-testid="home-chart-indicator-controls">
    {chips.map((chip) => (
      <button
        key={chip.key}
        type="button"
        aria-pressed={chip.pressed}
        disabled={!chip.available}
        data-testid={`home-chart-indicator-${chip.key}`}
        className={cn(
          'touch-manipulation inline-flex min-h-[40px] items-center gap-1.5 rounded-full border px-3.5 py-2 text-[11px] font-medium leading-none transition-colors sm:min-h-0 sm:px-2.5 sm:py-1 sm:text-[10px]',
          chip.pressed
            ? 'border-white/[0.12] bg-white/[0.07] text-white/84'
            : 'border-white/[0.05] bg-white/[0.012] text-white/46 hover:border-white/[0.09] hover:bg-white/[0.03] hover:text-white/70',
          !chip.available ? 'cursor-not-allowed opacity-40 hover:border-white/[0.05] hover:bg-white/[0.012] hover:text-white/46' : '',
        )}
        onClick={() => onToggle(chip.key)}
        title={chip.title}
      >
        <span className="inline-block size-1.5 rounded-full" style={{ backgroundColor: chip.color }} />
        <span>{chip.label}</span>
      </button>
    ))}
    {vwapUnavailableLabel ? (
      <span className="text-[10px] text-white/30">{vwapUnavailableLabel}</span>
    ) : null}
  </div>
);

export const HomeCandlestickChartContextBadges: React.FC<HomeCandlestickChartContextBadgesProps> = ({
  priceLabel,
  volumeLabel,
  rangeHintLabel,
}) => (
  <div className="flex min-w-0 flex-wrap items-center gap-2 text-[10px] text-white/36">
    <span
      className="inline-flex min-h-6 items-center rounded-full border border-white/[0.06] bg-white/[0.03] px-2.5"
      data-testid="home-chart-context-price"
    >
      {priceLabel}
    </span>
    <span
      className="inline-flex min-h-6 items-center rounded-full border border-white/[0.06] bg-white/[0.03] px-2.5"
      data-testid="home-chart-context-volume"
    >
      {volumeLabel}
    </span>
    <span
      className="inline-flex min-h-6 items-center rounded-full border border-white/[0.05] bg-white/[0.015] px-2.5"
      data-testid="home-chart-range-hint"
    >
      {rangeHintLabel}
    </span>
  </div>
);

export const HomeCandlestickChartUnavailablePanel: React.FC<HomeCandlestickChartUnavailablePanelProps> = ({
  statusLabel,
  timeframeLabel,
  title,
  body,
  isLoading,
}) => (
  <div
    className={cn(
      'relative flex h-[224px] min-w-0 max-w-full flex-col justify-center overflow-hidden rounded-[12px] border border-[color:var(--wolfy-border-faint)] bg-[linear-gradient(180deg,rgba(17,22,38,0.92),rgba(13,18,32,0.98))] px-5 text-left sm:h-[236px] xl:h-[248px]',
      isLoading ? 'text-white/46' : 'text-white/42',
    )}
    data-testid="home-candlestick-unavailable"
  >
    <div
      aria-hidden="true"
      className="pointer-events-none absolute inset-x-5 top-5 h-px bg-gradient-to-r from-transparent via-white/14 to-transparent"
    />
    <div className="flex flex-wrap items-center gap-2">
      <span className="inline-flex items-center rounded-full border border-white/[0.08] bg-white/[0.04] px-2.5 py-1 text-[10px] font-medium uppercase tracking-[0.16em] text-white/48">
        {statusLabel}
      </span>
      <span className="text-[10px] uppercase tracking-[0.16em] text-white/24">{timeframeLabel}</span>
    </div>
    <div className="mt-4 max-w-sm">
      <p className="text-sm font-semibold text-white/72">{title}</p>
      {body ? (
        <p className="mt-2 text-xs leading-5 text-white/36">
          {body}
        </p>
      ) : null}
    </div>
  </div>
);
