import type React from 'react';
import { Button } from '../common/Button';
import { GlassCard } from '../common/GlassCard';
import { SettingsSectionCard } from './SettingsSectionCard';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

type SystemLogsConfigProps = {
  t: TranslateFn;
  showRuntimeExecutionSummary: boolean;
  adminLocked: boolean;
  isSaving: boolean;
  onOpenRuntimeVisibilityDrawer: () => void;
};

const SystemLogsConfig: React.FC<SystemLogsConfigProps> = ({
  t,
  showRuntimeExecutionSummary,
  adminLocked,
  isSaving,
  onOpenRuntimeVisibilityDrawer,
}) => (
  <SettingsSectionCard
    title={t('settings.runtimeSummaryVisibilityTitle')}
    description={t('settings.runtimeSummaryVisibilityDesc')}
  >
    <GlassCard className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div>
          <p className="text-sm font-semibold text-foreground">
            {showRuntimeExecutionSummary ? t('settings.runtimeSummaryVisibleOn') : t('settings.runtimeSummaryVisibleOff')}
          </p>
          <p className="mt-1 text-xs text-secondary-text">{t('settings.runtimeSummaryVisibilityDesc')}</p>
        </div>
        <Button
          type="button"
          size="sm"
          variant="settings-secondary"
          onClick={onOpenRuntimeVisibilityDrawer}
          disabled={adminLocked || isSaving}
        >
          {t('settings.dataSourceManageAction')}
        </Button>
      </div>
    </GlassCard>
  </SettingsSectionCard>
);

export default SystemLogsConfig;
