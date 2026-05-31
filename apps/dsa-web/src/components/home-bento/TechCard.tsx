import type React from 'react';
import { PanelRightOpen } from 'lucide-react';
import { useUiPreferences } from '../../contexts/UiPreferencesContext';
import { useSafariWarmActivation } from '../../hooks/useSafariInteractionReady';
import { getToneColor } from '../../utils/marketColors';
import { BentoCard } from './BentoCard';
import { type SignalTone } from './theme';

type TechSignal = {
  label: string;
  value: string;
  tone: SignalTone;
  description?: string | null;
  rawValue?: string;
  details?: string;
};

type TechCardProps = {
  title: string;
  signals: TechSignal[];
  detailLabel: string;
  onOpenDetails: () => void;
  researchCard?: string;
};

function isMutedValue(value: string): boolean {
  const normalized = String(value || '').trim().toUpperCase();
  return normalized === '' || normalized === '-' || normalized === 'N/A';
}

function getTechSignalDescription(signal: TechSignal): string | null {
  const description = String(signal.description || signal.details || signal.rawValue || '').trim();
  if (!description || description === signal.value || isMutedValue(description)) {
    return null;
  }
  return description;
}

export const TechCard: React.FC<TechCardProps> = ({
  title,
  signals,
  detailLabel,
  onOpenDetails,
  researchCard,
}) => {
  const { marketColorConvention } = useUiPreferences();
  const {
    ref: openDetailsButtonRef,
    onClick: handleOpenDetailsClick,
    onPointerUp: handleOpenDetailsPointerUp,
  } = useSafariWarmActivation<HTMLButtonElement>(onOpenDetails);
  const normalizedSignals = signals.map((signal) => ({
    ...signal,
    description: getTechSignalDescription(signal),
  }));

  return (
    <BentoCard
      eyebrow={title}
      className="w-full rounded-[12px] px-4 py-3"
      researchCard={researchCard}
      testId="home-bento-card-tech"
      action={(
        <button
          ref={openDetailsButtonRef}
          type="button"
          className="inline-flex cursor-pointer items-center gap-1.5 text-xs text-white/40 transition-colors hover:text-white"
          data-testid="home-bento-drawer-trigger-tech"
          onClick={handleOpenDetailsClick}
          onPointerUp={handleOpenDetailsPointerUp}
        >
          <PanelRightOpen className="size-3.5" />
          <span>{detailLabel}</span>
        </button>
      )}
    >
      <div className="divide-y divide-white/5 px-1">
        {normalizedSignals.map((signal) => {
          const toneColor = getToneColor(signal.tone, marketColorConvention);
          return (
            <div
              key={signal.label}
              data-testid={`home-bento-tech-signal-${signal.label}`}
              className="flex flex-col gap-1 border-b border-white/5 py-2 last:border-b-0"
            >
              <div className="flex min-w-0 items-center justify-between gap-4">
                <span className="shrink-0 text-[10px] font-bold uppercase tracking-widest text-white/40">
                  {signal.label}
                </span>
                <span
                  className={`min-w-0 break-words text-right text-xs font-medium whitespace-normal ${
                    isMutedValue(signal.value) ? 'text-white/20' : toneColor.textClass
                  }`}
                  style={{ textShadow: isMutedValue(signal.value) ? 'none' : toneColor.glowShadow }}
                >
                  {signal.value}
                </span>
              </div>
              {signal.description ? (
                <p
                  className="mt-1 block w-full break-words text-xs text-white/40 whitespace-normal"
                  data-testid={`home-bento-tech-signal-detail-${signal.label}`}
                  title={signal.description}
                >
                  {signal.description}
                </p>
              ) : null}
            </div>
          );
        })}
      </div>
    </BentoCard>
  );
};
