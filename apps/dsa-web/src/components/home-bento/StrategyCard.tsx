import type React from 'react';
import { PanelRightOpen } from 'lucide-react';
import { useUiPreferences } from '../../contexts/UiPreferencesContext';
import { useSafariWarmActivation } from '../../hooks/useSafariInteractionReady';
import { BentoCard } from './BentoCard';
import { CARD_BUTTON_CLASS } from './theme';
import { getToneColor } from '../../utils/marketColors';

type StrategyMetric = {
  label: string;
  value: string;
  tone?: 'bullish' | 'bearish' | 'neutral';
};

type StrategyCardProps = {
  title: string;
  subtitle?: string;
  metrics: StrategyMetric[];
  positionLabel: string;
  positionBody: string;
  detailLabel: string;
  onOpenDetails: () => void;
  researchCard?: string;
};

export const StrategyCard: React.FC<StrategyCardProps> = ({
  title,
  subtitle,
  metrics,
  positionLabel,
  positionBody,
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
  const isEntryMetric = (label: string) => label === '观察区间' || label === '建仓区间' || label === 'Watch Zone' || label === 'Entry Zone';
  const getMetricLabel = (label: string) => {
    if (label === '观察区间' || label === '建仓区间') {
      return '观察条件区';
    }
    if (label === 'Watch Zone' || label === 'Entry Zone') {
      return 'Watch Zone';
    }
    return label;
  };
  const getMetricTone = (tone: StrategyMetric['tone']) => getToneColor(tone || 'neutral', marketColorConvention);
  const getMetricValueClass = (tone: StrategyMetric['tone']) => {
    return getMetricTone(tone).textClass;
  };
  const positionParagraphs = positionBody
    .split(/\n+/)
    .map((paragraph) => paragraph.trim())
    .filter(Boolean);
  const entryMetric = metrics.find((metric) => isEntryMetric(metric.label));
  const targetMetrics = metrics.filter((metric) => !isEntryMetric(metric.label));

  return (
    <BentoCard
      eyebrow={title}
      subtitle={subtitle}
      className="w-full overflow-visible rounded-[24px]"
      contentClassName="h-auto"
      researchCard={researchCard}
      testId="home-bento-card-strategy"
      action={(
        <button
          ref={openDetailsButtonRef}
          type="button"
          className={CARD_BUTTON_CLASS}
          data-testid="home-bento-drawer-trigger-strategy"
          onClick={handleOpenDetailsClick}
          onPointerUp={handleOpenDetailsPointerUp}
        >
          <PanelRightOpen className="h-3.5 w-3.5" />
          <span>{detailLabel}</span>
        </button>
      )}
    >
      <div className="mt-4 flex w-full min-w-0 flex-col">
        {entryMetric ? (
          <div
            className="flex min-w-0 flex-col gap-1.5"
            data-testid={`home-bento-strategy-metric-${entryMetric.label}`}
          >
            <p className="truncate text-[10px] font-semibold uppercase tracking-widest text-white/40">{getMetricLabel(entryMetric.label)}</p>
            <p
              className={`break-words whitespace-normal text-sm font-medium leading-relaxed ${getMetricValueClass(entryMetric.tone || 'neutral')}`}
              style={{ textShadow: getMetricTone(entryMetric.tone).glowShadow }}
            >
              {entryMetric.value}
            </p>
          </div>
        ) : null}
        <div className="mt-6 grid w-full grid-cols-2 gap-4">
          {targetMetrics.map((metric) => (
            <div
              key={metric.label}
              className="flex min-w-0 flex-col gap-1.5"
              data-testid={`home-bento-strategy-metric-${metric.label}`}
            >
              <p className="truncate text-[10px] font-semibold uppercase tracking-widest text-white/40">{getMetricLabel(metric.label)}</p>
              <p
                className={`break-words whitespace-normal text-sm font-medium leading-relaxed ${getMetricValueClass(metric.tone || 'neutral')}`}
                style={{ textShadow: getMetricTone(metric.tone).glowShadow }}
              >
                {metric.value}
              </p>
            </div>
          ))}
        </div>
        <div className="mt-6 border-t border-white/5 pt-4">
          <p className="block truncate text-[10px] font-semibold uppercase tracking-widest text-white/40">{positionLabel}</p>
          <div className="mt-3 space-y-2 break-words text-[13px] leading-[1.7] text-white/70 whitespace-normal">
            {(positionParagraphs.length ? positionParagraphs : [positionBody]).map((paragraph) => (
              <p key={paragraph}>{paragraph}</p>
            ))}
          </div>
        </div>
      </div>
    </BentoCard>
  );
};
