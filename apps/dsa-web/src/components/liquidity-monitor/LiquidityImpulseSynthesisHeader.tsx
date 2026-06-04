import type React from 'react';
import { TerminalChip, TerminalPanel } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import { SynthesisEvidenceColumn, type SynthesisEvidenceItem } from '../common/SynthesisEvidenceColumn';

export type LiquidityImpulseHeaderEvidenceView = SynthesisEvidenceItem;

export type LiquidityImpulseSynthesisHeaderView = {
  state: 'ready' | 'insufficient' | 'missing';
  title: string;
  summary: string;
  stateChipLabel: string;
  stateChipVariant: 'neutral' | 'success' | 'caution' | 'danger' | 'info';
  impulseLabel?: string;
  subtypeLabel?: string;
  confidenceLabel: string;
  confidenceValueText: string;
  directionScoreText?: string;
  qualityLine?: string;
  dominantDrivers: LiquidityImpulseHeaderEvidenceView[];
  counterEvidence: LiquidityImpulseHeaderEvidenceView[];
  dataGaps: LiquidityImpulseHeaderEvidenceView[];
  notInvestmentAdvice?: boolean;
};

export const LiquidityImpulseSynthesisHeader: React.FC<{
  view: LiquidityImpulseSynthesisHeaderView;
}> = ({ view }) => (
  <TerminalPanel
    as="section"
    dense
    data-testid="liquidity-impulse-synthesis-header"
    data-market-research-flow="liquidity-impulse"
    className="relative overflow-hidden bg-white/[0.02]"
  >
    <div
      className={cn(
        'absolute inset-x-0 top-0 h-px',
        view.state === 'ready'
          ? 'bg-gradient-to-r from-emerald-400/0 via-cyan-300/55 to-sky-400/0'
          : view.state === 'missing'
            ? 'bg-gradient-to-r from-white/0 via-white/18 to-white/0'
            : 'bg-gradient-to-r from-amber-400/0 via-amber-200/50 to-rose-300/0',
      )}
      aria-hidden="true"
    />
    <div className="grid min-w-0 gap-4 p-4 xl:grid-cols-[minmax(0,1.04fr)_minmax(0,1.36fr)]">
      <div className="min-w-0">
        <div className="flex min-w-0 flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <p className="text-[10px] font-bold tracking-[0.24em] text-white/38">流动性脉冲</p>
            <p
              data-testid="liquidity-impulse-synthesis-title"
              className="mt-1 text-base font-semibold leading-6 text-white/90 md:text-lg"
            >
              {view.title}
            </p>
            <p
              data-testid="liquidity-impulse-synthesis-summary"
              className="mt-2 max-w-2xl text-xs leading-5 text-white/56"
            >
              {view.summary}
            </p>
          </div>
          <TerminalChip
            data-testid="liquidity-impulse-synthesis-state-chip"
            variant={view.stateChipVariant}
            className="shrink-0 px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
          >
            {view.stateChipLabel}
          </TerminalChip>
        </div>

        <div className="mt-3 flex min-w-0 flex-wrap gap-2">
          {view.impulseLabel ? (
            <TerminalChip
              data-testid="liquidity-impulse-synthesis-impulse-chip"
              variant={view.state === 'ready' ? 'success' : 'neutral'}
              className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
            >
              <span className="text-white/36">结论</span>
              <span className="max-w-[240px] truncate font-mono normal-case tracking-normal">
                {view.impulseLabel}
              </span>
            </TerminalChip>
          ) : null}
          {view.subtypeLabel ? (
            <TerminalChip
              data-testid="liquidity-impulse-synthesis-subtype-chip"
              variant="neutral"
              className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
            >
              <span className="text-white/36">子类型</span>
              <span className="max-w-[220px] truncate font-mono normal-case tracking-normal">
                {view.subtypeLabel}
              </span>
            </TerminalChip>
          ) : null}
          <TerminalChip
            data-testid="liquidity-impulse-synthesis-confidence-chip"
            variant={view.state === 'ready' ? 'success' : view.state === 'missing' ? 'neutral' : 'caution'}
            className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
          >
            <span className="text-white/36">置信度</span>
            <span className="font-mono normal-case tracking-normal">
              {view.confidenceLabel}
              {view.confidenceValueText ? ` · ${view.confidenceValueText}` : ''}
            </span>
          </TerminalChip>
          {view.directionScoreText ? (
            <TerminalChip
              data-testid="liquidity-impulse-synthesis-direction-chip"
              variant="neutral"
              className="px-2.5 py-1.5 text-[10px] font-bold uppercase tracking-widest"
            >
              <span className="text-white/36">方向分</span>
              <span className="font-mono normal-case tracking-normal">
                {view.directionScoreText}
              </span>
            </TerminalChip>
          ) : null}
        </div>

        {view.qualityLine ? (
          <p
            data-testid="liquidity-impulse-synthesis-quality-line"
            className="mt-3 truncate font-mono text-[11px] leading-5 text-white/34"
          >
            {view.qualityLine}
          </p>
        ) : null}

        {view.notInvestmentAdvice ? (
          <p
            data-testid="liquidity-impulse-synthesis-disclaimer"
            className="mt-3 text-[11px] leading-5 text-white/34"
          >
            非投资建议
          </p>
        ) : null}
      </div>

      <div className="grid min-w-0 gap-3 md:grid-cols-3">
        <SynthesisEvidenceColumn
          testId="liquidity-impulse-synthesis-dominant-drivers"
          title="支持证据"
          emptyLabel="暂无可展示驱动"
          items={view.dominantDrivers}
          accentClassName="text-emerald-300"
        />
        <SynthesisEvidenceColumn
          testId="liquidity-impulse-synthesis-counter-evidence"
          title="反证"
          emptyLabel="暂无显式反证"
          items={view.counterEvidence}
          accentClassName="text-amber-200"
        />
        <SynthesisEvidenceColumn
          testId="liquidity-impulse-synthesis-data-gaps"
          title="数据缺口"
          emptyLabel="暂无显式缺口"
          items={view.dataGaps}
          accentClassName="text-sky-200"
        />
      </div>
    </div>
  </TerminalPanel>
);
