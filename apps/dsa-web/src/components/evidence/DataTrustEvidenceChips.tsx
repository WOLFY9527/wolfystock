import type React from 'react';
import { TerminalChip } from '../terminal/TerminalPrimitives';
import { cn } from '../../utils/cn';
import {
  createDataTrustEvidenceViewModel,
  type DataTrustEvidenceInput,
  type DataTrustEvidenceTone,
  type DataTrustEvidenceViewModel,
} from '../../utils/dataTrustEvidenceDisplay';

type DataTrustEvidenceChipsProps = {
  input?: DataTrustEvidenceInput;
  viewModel?: DataTrustEvidenceViewModel | null;
  maxStates?: number;
  showMessage?: boolean;
  className?: string;
  'data-testid'?: string;
};

function variantFromTone(tone: DataTrustEvidenceTone): React.ComponentProps<typeof TerminalChip>['variant'] {
  if (tone === 'success') return 'success';
  if (tone === 'danger') return 'danger';
  if (tone === 'caution') return 'caution';
  if (tone === 'info') return 'info';
  return 'neutral';
}

function createSafeViewModelFromResolvedInput(
  input: DataTrustEvidenceInput | undefined,
  viewModel: DataTrustEvidenceViewModel | null | undefined,
) {
  if (!viewModel) return createDataTrustEvidenceViewModel(input);

  return createDataTrustEvidenceViewModel({
    locale: viewModel.locale,
    states: viewModel.states,
    confidenceCap: viewModel.confidenceCap,
    asOf: viewModel.asOf,
    includeSafetyState: viewModel.states.includes('not-investment-advice'),
  });
}

export function DataTrustEvidenceChips({
  input,
  viewModel,
  maxStates,
  showMessage = false,
  className,
  'data-testid': dataTestId,
}: DataTrustEvidenceChipsProps) {
  const resolvedViewModel = createSafeViewModelFromResolvedInput(input, viewModel);
  const visibleChips = maxStates == null ? resolvedViewModel.chips : resolvedViewModel.chips.slice(0, maxStates);
  const hasMeta = Boolean(resolvedViewModel.confidenceCapLabel || resolvedViewModel.asOf);

  if (!visibleChips.length && !hasMeta) return null;

  return (
    <div
      data-testid={dataTestId}
      className={cn('flex min-w-0 flex-wrap items-center gap-1.5', className)}
      aria-label={visibleChips.map((chip) => chip.label).join(' · ') || undefined}
    >
      {visibleChips.map((chip) => (
        <TerminalChip key={chip.state} variant={variantFromTone(chip.tone)}>
          {chip.label}
        </TerminalChip>
      ))}
      {resolvedViewModel.confidenceCapLabel ? (
        <TerminalChip variant="caution">
          {resolvedViewModel.confidenceCapLabel}
        </TerminalChip>
      ) : null}
      {resolvedViewModel.asOf ? (
        <TerminalChip variant="neutral">
          {resolvedViewModel.asOf}
        </TerminalChip>
      ) : null}
      {showMessage && resolvedViewModel.message ? (
        <span className="basis-full text-[11px] leading-5 text-white/52">
          {resolvedViewModel.message}
        </span>
      ) : null}
    </div>
  );
}
