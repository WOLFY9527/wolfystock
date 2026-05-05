import type React from 'react';
import { Button, Disclosure, GlassCard } from '../common';
import { BentoHeroStrip, type BentoHeroItem } from '../home-bento';
import {
  describeSettingsSystemHealthStatus,
  type DisplayStatusTone,
} from '../../utils/displayStatus';
import { SettingsAlert } from './SettingsAlert';
import { SettingsSectionCard } from './SettingsSectionCard';
import DuckDBQuantPanel from './DuckDBQuantPanel';
import type {
  DeveloperDetailGroup,
  SystemHealthStatusCard,
  SystemHealthSummaryCard,
} from './settingsDerivedState';

type AdminActionDialogKey = 'runtime_cache' | 'factory_reset' | null;
type DuckDBConfigState = 'enabled' | 'disabled' | 'unknown';

type TranslateFn = (key: string, vars?: Record<string, string | number | undefined>) => string;

const GHOST_TAG_CLASS = 'inline-flex items-center px-1.5 py-0.5 rounded text-[10px] uppercase tracking-widest font-bold bg-white/5 text-white/40 border border-white/5';
const CONTROL_GHOST_BUTTON_CLASS = 'px-3 py-1.5 rounded-lg bg-white/[0.03] border border-white/10 hover:bg-white/10 text-xs transition-colors';
const STATUS_CLASS: Record<DisplayStatusTone, string> = {
  success: 'border-emerald-400/20 text-emerald-300 bg-emerald-400/[0.06]',
  warning: 'border-amber-300/20 text-amber-300 bg-amber-300/[0.06]',
  danger: 'border-rose-400/20 text-rose-300 bg-rose-400/[0.06]',
  info: 'border-cyan-300/15 text-cyan-200 bg-cyan-300/[0.05]',
  muted: 'border-white/10 text-white/45 bg-white/[0.03]',
  neutral: 'border-white/10 text-white/45 bg-white/[0.03]',
};
const STATUS_TEXT_CLASS: Record<DisplayStatusTone, string> = {
  success: 'text-emerald-300',
  warning: 'text-amber-300',
  danger: 'text-rose-300',
  info: 'text-cyan-200',
  muted: 'text-white/45',
  neutral: 'text-white/45',
};

type SystemControlPlaneProps = {
  t: TranslateFn;
  overviewStats: BentoHeroItem[];
  summaryCards: SystemHealthSummaryCard[];
  statusCards: SystemHealthStatusCard[];
  developerDetails: DeveloperDetailGroup[];
  isRunningAdminAction: boolean;
  adminActionDialog: AdminActionDialogKey;
  adminActionMessage: string | null;
  adminActionTone: 'success' | 'error';
  duckdbConfigEnabledState: DuckDBConfigState;
  onOpenAdminLogs: () => void;
  onSetAdminActionDialog: (value: Exclude<AdminActionDialogKey, null>) => void;
};

const SystemControlPlane: React.FC<SystemControlPlaneProps> = ({
  t,
  overviewStats,
  summaryCards,
  statusCards,
  developerDetails,
  isRunningAdminAction,
  adminActionDialog,
  adminActionMessage,
  adminActionTone,
  duckdbConfigEnabledState,
  onOpenAdminLogs,
  onSetAdminActionDialog,
}) => (
  <SettingsSectionCard
    title={t('settings.controlPlaneTitle')}
    description={t('settings.controlPlaneDesc')}
  >
    <div className="space-y-4">
      <BentoHeroStrip items={overviewStats} testId="settings-bento-hero" />
      <GlassCard className="px-4 py-4" data-testid="system-health-summary">
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-300">系统健康</p>
            <p className="mt-1 text-sm font-semibold text-foreground">环境状态与可选依赖一屏确认</p>
          </div>
          <span className={GHOST_TAG_CLASS}>当前配置快照</span>
        </div>
        <div className="mt-4 grid grid-cols-2 gap-2 md:grid-cols-4 xl:grid-cols-7">
          {summaryCards.map((item) => (
            <div key={item.key} className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-3">
              <p className="truncate text-[10px] font-semibold uppercase tracking-[0.14em] text-white/35">{item.label}</p>
              <p className={`mt-2 truncate text-sm font-semibold ${item.status ? STATUS_TEXT_CLASS[describeSettingsSystemHealthStatus(item.status).tone] : 'text-white'}`}>
                {item.value}
              </p>
              <p className="mt-1 truncate text-[11px] text-white/45">{item.detail}</p>
            </div>
          ))}
        </div>
      </GlassCard>

      <GlassCard className="px-4 py-4" data-testid="system-subsystem-cards">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground">子系统状态</p>
            <p className="mt-1 text-xs text-white/45">未启用与可选缺失不会被标成故障。</p>
          </div>
        </div>
        <div className="mt-4 grid grid-cols-1 gap-3 md:grid-cols-2 xl:grid-cols-3">
          {statusCards.map((card) => {
            const status = describeSettingsSystemHealthStatus(card.status);
            return (
              <article key={card.key} className="min-w-0 rounded-xl border border-white/5 bg-white/[0.02] px-3 py-3">
                <div className="flex min-w-0 items-start justify-between gap-3">
                  <div className="min-w-0">
                    <p className="truncate text-sm font-semibold text-foreground">{card.label}</p>
                    <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/50">{card.reason}</p>
                  </div>
                  <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold ${STATUS_CLASS[status.tone]}`}>
                    {status.label}
                  </span>
                </div>
                <div className="mt-3 flex flex-wrap items-center gap-2 text-[11px] text-white/35">
                  {card.optional ? <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2 py-1 text-cyan-200">可选</span> : null}
                  <span>{card.checkedAt || '最近检查：当前快照'}</span>
                </div>
                {card.nextAction ? <p className="mt-2 text-[11px] leading-5 text-white/45">下一步：{card.nextAction}</p> : null}
              </article>
            );
          })}
        </div>
      </GlassCard>

      <DuckDBQuantPanel configEnabledState={duckdbConfigEnabledState} />

      <Disclosure
        summary={(
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/40">开发者细节</p>
              <p className="mt-1 text-sm font-semibold text-foreground">原始诊断、配置键与环境摘要默认收起</p>
            </div>
            <span className={GHOST_TAG_CLASS}>安全摘要</span>
          </div>
        )}
        className="rounded-2xl border border-white/5 bg-white/[0.02]"
        summaryClassName="px-4 py-4"
        bodyClassName="grid gap-3 px-4 pb-4 md:grid-cols-3"
      >
        {developerDetails.map((detail) => (
          <div key={detail.key} className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-3">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">{detail.label}</p>
            <p className="mt-2 text-xs leading-5 text-white/55">{detail.detail}</p>
          </div>
        ))}
      </Disclosure>

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
