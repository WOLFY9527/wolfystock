import type React from 'react';
import { Button } from '../common/Button';

type ApiSourceCardProps = {
  testId: string;
  label: string;
  kindLabel: string;
  validationBadge: React.ReactNode;
  isConfigured: boolean;
  capabilities: string[];
  impactLabel: string;
  impactSurfaces: string[];
  impactCapabilities: string[];
  impactStates: string[];
  impactEvidenceText: string;
  statusText: string;
  validationMessage: string;
  usedByText: string;
  endpointText: string;
  internalFlagText: string;
  manageLabel: string;
  validateLabel: string;
  validateDisabled?: boolean;
  onManage: () => void;
  onValidate: () => void;
};

const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';

export const ApiSourceCard: React.FC<ApiSourceCardProps> = ({
  testId,
  label,
  kindLabel,
  validationBadge,
  isConfigured,
  capabilities = [],
  impactLabel,
  impactSurfaces = [],
  impactCapabilities = [],
  impactStates = [],
  impactEvidenceText,
  statusText,
  validationMessage,
  usedByText,
  endpointText,
  internalFlagText,
  manageLabel,
  validateLabel,
  validateDisabled = false,
  onManage,
  onValidate,
}) => (
  <div
    className="flex items-center justify-between gap-4 border-b border-white/5 py-3 transition-colors hover:bg-white/[0.02]"
    data-testid={testId}
    data-layout="row"
  >
    <div className="flex min-w-[13rem] items-center gap-3">
      <span
        className={isConfigured
          ? 'h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-400 shadow-[0_0_8px_rgba(52,211,153,0.5)]'
          : 'h-1.5 w-1.5 shrink-0 rounded-full bg-white/20'}
        aria-hidden="true"
      />
      <div className="min-w-0">
        <p className="w-48 truncate text-sm font-bold text-white">{label}</p>
        <p className="mt-1 text-[10px] uppercase tracking-[0.16em] text-white/30">{kindLabel}</p>
      </div>
    </div>

    <div className="min-w-0 flex-1">
      <div className="flex flex-wrap gap-2">
        {validationBadge}
        {capabilities.map((capability) => (
          <span
            key={`${testId}-${capability}`}
            className={GHOST_TAG_CLASS}
          >
            {capability}
          </span>
        ))}
      </div>
      <div className="mt-1 flex min-w-0 flex-wrap gap-x-3 gap-y-1 text-[11px] text-white/35">
        <span className="truncate">{statusText}</span>
        <span className="truncate">{validationMessage}</span>
        <span className="truncate">{usedByText}</span>
        <span className="truncate">{endpointText}</span>
        <span className="truncate">{internalFlagText}</span>
      </div>
      <div className="mt-2 grid gap-2 lg:grid-cols-[minmax(0,1.1fr)_minmax(0,1fr)]">
        <div className="min-w-0">
          <p className="mb-1 text-[10px] font-bold uppercase text-white/35">{impactLabel}</p>
          <div className="flex flex-wrap gap-1.5">
            {impactSurfaces.map((surface) => (
              <span key={`${testId}-surface-${surface}`} className={GHOST_TAG_CLASS}>
                {surface}
              </span>
            ))}
          </div>
        </div>
        <div className="min-w-0">
          <div className="flex flex-wrap gap-1.5">
            {impactCapabilities.map((capability) => (
              <span key={`${testId}-capability-${capability}`} className={GHOST_TAG_CLASS}>
                {capability}
              </span>
            ))}
            {impactStates.map((state) => (
              <span key={`${testId}-state-${state}`} className={GHOST_TAG_CLASS}>
                {state}
              </span>
            ))}
          </div>
          <p className="mt-1 text-[11px] text-white/45">{impactEvidenceText}</p>
        </div>
      </div>
    </div>

    <div className="flex shrink-0 items-center justify-end gap-2">
      <Button
        type="button"
        size="sm"
        variant="settings-secondary"
        className={CONTROL_GHOST_BUTTON_CLASS}
        onClick={onManage}
      >
        {manageLabel}
      </Button>
      <Button
        type="button"
        size="sm"
        variant="settings-secondary"
        className={CONTROL_GHOST_BUTTON_CLASS}
        disabled={validateDisabled}
        onClick={onValidate}
      >
        {validateLabel}
      </Button>
    </div>
  </div>
);
