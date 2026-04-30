import type React from 'react';
import { Button, Disclosure, GlassCard } from '../common';
import { BentoHeroStrip, type BentoHeroItem } from '../home-bento';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';

type AdminActionDialogKey = 'runtime_cache' | 'factory_reset' | null;

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';

type SystemControlPlaneProps = {
  t: TranslateFn;
  overviewStats: BentoHeroItem[];
  isRunningAdminAction: boolean;
  adminActionDialog: AdminActionDialogKey;
  adminActionMessage: string | null;
  adminActionTone: 'success' | 'error';
  onOpenAdminLogs: () => void;
  onSetAdminActionDialog: (value: Exclude<AdminActionDialogKey, null>) => void;
};

const SystemControlPlane: React.FC<SystemControlPlaneProps> = ({
  t,
  overviewStats,
  isRunningAdminAction,
  adminActionDialog,
  adminActionMessage,
  adminActionTone,
  onOpenAdminLogs,
  onSetAdminActionDialog,
}) => (
  <SettingsSectionCard
    title={t('settings.controlPlaneTitle')}
    description={t('settings.controlPlaneDesc')}
  >
    <div className="space-y-4">
      <BentoHeroStrip items={overviewStats} testId="settings-bento-hero" />
      <div className="grid gap-4 xl:grid-cols-[minmax(0,1.35fr)_minmax(0,0.95fr)]">
      <GlassCard className="px-4 py-4">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-positive-hsl))]">
              {t('settings.adminSurfaceActiveLabel')}
            </p>
            <p className="mt-1 text-base font-semibold text-foreground">{t('settings.adminSurfaceActiveTitle')}</p>
          </div>
          <span className={GHOST_TAG_CLASS}>
            {t('settings.adminSurfaceGlobalScope')}
          </span>
        </div>
      </GlassCard>

      <Disclosure
        summary={(
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-warning-hsl))]">
                {t('settings.controlPlaneMaintenanceTitle')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.controlPlaneMaintenanceSummary')}</p>
            </div>
            <span className={GHOST_TAG_CLASS}>
              {t('settings.controlPlaneMaintenanceBadge')}
            </span>
          </div>
        )}
        className="rounded-2xl border border-white/5 bg-white/[0.02]"
        summaryClassName="px-4 py-4"
        bodyClassName="space-y-4 px-4 pb-4"
      >
        <GlassCard className="px-4 py-4">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground">{t('settings.controlPlaneLogsTitle')}</p>
          <div className="mt-4 flex justify-end">
            <Button
              type="button"
              size="sm"
              variant="settings-secondary"
              className={CONTROL_GHOST_BUTTON_CLASS}
              onClick={onOpenAdminLogs}
            >
              {t('settings.viewAdminLogs')}
            </Button>
          </div>
        </GlassCard>

        <div className="rounded-2xl bg-[hsl(var(--accent-warning-hsl)/0.08)] px-4 py-4">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-warning-hsl))]">
                {t('settings.adminActionsTitle')}
              </p>
              <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.adminActionsDesc')}</p>
            </div>
          </div>
          <div className="mt-4 divide-y divide-white/5 rounded-2xl bg-white/[0.03]">
            <div className="px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">{t('settings.adminMaintenanceTitle')}</p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="settings-secondary"
                  className={CONTROL_GHOST_BUTTON_CLASS}
                  onClick={() => onSetAdminActionDialog('runtime_cache')}
                  disabled={isRunningAdminAction}
                >
                  {isRunningAdminAction && adminActionDialog === 'runtime_cache'
                    ? t('settings.saving')
                    : t('settings.adminActionResetRuntimeCaches')}
                </Button>
              </div>
            </div>
            <div className="px-3 py-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-sm font-semibold text-foreground">{t('settings.adminFactoryResetTitle')}</p>
                </div>
                <Button
                  type="button"
                  size="sm"
                  variant="danger-subtle"
                  onClick={() => onSetAdminActionDialog('factory_reset')}
                  disabled={isRunningAdminAction}
                >
                  {isRunningAdminAction && adminActionDialog === 'factory_reset'
                    ? t('settings.saving')
                    : t('settings.adminActionFactoryReset')}
                </Button>
              </div>
            </div>
          </div>
          {adminActionMessage ? (
            <div className="mt-3">
              <span className="sr-only">
                {(adminActionTone === 'success' ? t('settings.success') : t('settings.adminActionErrorTitle'))}:{adminActionMessage}
              </span>
              <SettingsAlert
                title={adminActionTone === 'success' ? t('settings.success') : t('settings.adminActionErrorTitle')}
                message={adminActionMessage}
                variant={adminActionTone === 'success' ? 'success' : 'error'}
              />
            </div>
          ) : null}
        </div>
      </Disclosure>
      </div>
    </div>
  </SettingsSectionCard>
);

export default SystemControlPlane;
