import type React from 'react';
import { Button } from '../common';
import type { BentoHeroItem } from '../home-bento';
import { DensityRail, GuidedDisclosure, InsightStack, SectionIntro } from '../guidance';
import {
  describeSettingsSystemHealthStatus,
  type DisplayStatusTone,
} from '../../utils/displayStatus';
import { SettingsAlert } from './SettingsAlert';
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
const DISCLOSURE_SUMMARY_CLASS = 'flex min-h-[58px] cursor-pointer list-none items-center justify-between gap-3 px-4 py-3 text-left outline-none focus-visible:ring-2 focus-visible:ring-cyan-300/40 [&::-webkit-details-marker]:hidden';
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
}) => {
  const healthCard = summaryCards.find((item) => item.key === 'health');
  const healthTone = describeSettingsSystemHealthStatus(healthCard?.status || 'unknown').tone;
  const introTone = healthTone === 'success' ? 'ready' : healthTone === 'danger' ? 'risk' : 'watch';
  const attentionCards = statusCards.filter((card) => (
    card.status === 'attention'
    || card.status === 'not_configured'
    || card.status === 'unavailable'
    || card.status === 'unknown'
  ));
  const insightCards = attentionCards.length ? attentionCards.slice(0, 4) : statusCards.slice(0, 3);
  const railItems = overviewStats.slice(0, 4).map((item, index) => ({
    id: `overview-${index}`,
    label: item.label,
    value: item.value,
    helper: typeof item.detail === 'string' ? item.detail : undefined,
    tone: item.tone === 'bullish' ? 'positive' as const : item.tone === 'bearish' ? 'negative' as const : 'neutral' as const,
  }));

  return (
    <section className="space-y-5" aria-labelledby="system-control-plane-heading">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cyan-100/55">operator control plane</p>
          <h2 id="system-control-plane-heading" className="mt-1 text-xl font-semibold tracking-normal text-white">
            {t('settings.controlPlaneTitle')}
          </h2>
        </div>
        <span className={GHOST_TAG_CLASS}>{t('settings.adminSurfaceGlobalScope')}</span>
      </div>

      <div
        data-testid="system-operator-dashboard"
        className="grid gap-5 xl:grid-cols-[minmax(0,1.38fr)_minmax(20rem,0.62fr)]"
      >
        <div className="min-w-0 space-y-5">
          <SectionIntro
            purpose="系统当前能否安全运行"
            summary={`当前状态：${healthCard?.value || '等待快照'}。先处理需关注项，再进入具体设置组。`}
            nextStep="按 AI、数据源、通知、系统配置的顺序检查；深层配置、原始字段和危险系统动作都在二级区域。"
            status={{ label: String(healthCard?.value || '等待配置快照'), tone: introTone }}
          />

          <section
            data-testid="system-health-summary"
            className="rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-cyan-300">系统健康</p>
                <p className="mt-1 text-sm font-semibold text-foreground">环境状态、可用能力和待处理风险先合并查看</p>
              </div>
              <span className={GHOST_TAG_CLASS}>当前配置快照</span>
            </div>
            <div className="mt-4 grid grid-cols-2 gap-2 lg:grid-cols-4">
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
          </section>

          <section
            data-testid="system-priority-settings"
            className="rounded-[16px] border border-white/5 bg-white/[0.02] p-4 backdrop-blur-md"
          >
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">重要设置组</p>
                <p className="mt-1 text-sm font-semibold text-foreground">按运行影响整理，不把每个配置键都铺在首屏</p>
              </div>
              <span className={GHOST_TAG_CLASS}>常规配置</span>
            </div>
            <div data-testid="system-subsystem-cards" className="mt-4 grid grid-cols-1 gap-2 lg:grid-cols-2">
              {statusCards.map((card) => {
                const status = describeSettingsSystemHealthStatus(card.status);
                return (
                  <article key={card.key} className="min-w-0 rounded-xl border border-white/[0.04] bg-black/20 px-3 py-3">
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="truncate text-sm font-semibold text-foreground">{card.label}</p>
                        <p className="mt-1 line-clamp-2 text-xs leading-5 text-white/52">{card.reason}</p>
                      </div>
                      <span className={`shrink-0 rounded-full border px-2 py-1 text-[10px] font-semibold ${STATUS_CLASS[status.tone]}`}>
                        {status.label}
                      </span>
                    </div>
                    <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-white/35">
                      {card.optional ? <span className="rounded-full border border-cyan-300/15 bg-cyan-300/[0.05] px-2 py-1 text-cyan-200">可选</span> : null}
                      <span>{card.checkedAt || '最近检查：当前快照'}</span>
                    </div>
                    {card.nextAction ? <p className="mt-2 text-[11px] leading-5 text-white/45">下一步：{card.nextAction}</p> : null}
                  </article>
                );
              })}
            </div>
          </section>
        </div>

        <div className="min-w-0 space-y-5">
          <InsightStack
            title="优先处理"
            insights={insightCards.map((card) => ({
              id: card.key,
              severity: card.status === 'unavailable' ? 'critical' : card.status === 'available' ? 'success' : 'warning',
              title: card.label,
              explanation: card.reason,
              detail: card.nextAction ? `下一步：${card.nextAction}` : '无需进入原始配置即可判断当前状态。',
            }))}
          />
          <div data-testid="settings-bento-hero">
            <DensityRail
              title="控制面上下文"
              items={railItems}
              className="md:max-w-none"
            />
            {overviewStats.map((item) => (
              item.valueTestId ? (
                <span key={item.valueTestId} className="sr-only" data-testid={item.valueTestId}>
                  {item.value}
                </span>
              ) : null
            ))}
          </div>
          <div className="rounded-[16px] border border-emerald-300/10 bg-emerald-400/[0.04] p-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-emerald-200/80">
              {t('settings.adminSurfaceActiveLabel')}
            </p>
            <p className="mt-2 text-sm font-semibold text-foreground">{t('settings.adminSurfaceActiveTitle')}</p>
            <p className="mt-2 text-xs leading-5 text-white/48">常规设置通过左侧分组进入，危险动作不与常规保存按钮混排。</p>
          </div>
        </div>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <details
          data-testid="system-duckdb-disclosure"
          className="group rounded-[16px] border border-white/5 bg-white/[0.02] backdrop-blur-md transition-colors open:border-cyan-200/15 open:bg-white/[0.03]"
        >
          <summary className={DISCLOSURE_SUMMARY_CLASS}>
            <span className="min-w-0">
              <span className="block text-sm font-semibold text-white">二级细节：DuckDB / 高级诊断</span>
              <span className="mt-1 block text-xs leading-5 text-white/48">DuckDB 量化引擎属于可选技术面板，默认收起，不作为首屏焦点。</span>
            </span>
            <span className={GHOST_TAG_CLASS}>深层配置</span>
          </summary>
          <div className="border-t border-white/[0.04] p-4">
            <DuckDBQuantPanel configEnabledState={duckdbConfigEnabledState} />
          </div>
        </details>

        <GuidedDisclosure
          title="开发者细节"
          summary="二级细节：原始字段、原始诊断、配置键、环境摘要默认收起，供审计时展开。"
          beginner={<p>日常操作先看系统健康和重要设置组；这些内容主要帮助排障，不用于判断是否保存常规配置。</p>}
          professional={(
            <div className="grid gap-3">
              {developerDetails.map((detail) => (
                <div key={detail.key} className="min-w-0 rounded-xl border border-white/5 bg-black/20 px-3 py-3">
                  <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/35">{detail.label}</p>
                  <p className="mt-2 text-xs leading-5 text-white/55">{detail.detail}</p>
                </div>
              ))}
            </div>
          )}
        />
      </div>

      <details
        data-testid="system-danger-zone"
        className="group rounded-[16px] border border-amber-300/14 bg-amber-300/[0.035] backdrop-blur-md transition-colors open:border-amber-200/25 open:bg-amber-300/[0.055]"
      >
        <summary className={DISCLOSURE_SUMMARY_CLASS}>
          <span className="min-w-0">
            <span className="block text-sm font-semibold text-amber-100">危险系统动作</span>
            <span className="mt-1 block text-xs font-semibold leading-5 text-white/60">展开维护操作与日志入口</span>
            <span className="mt-1 block text-xs leading-5 text-white/52">确认后才执行；维护、缓存和重置动作与 routine 设置隔离。</span>
          </span>
          <span className={GHOST_TAG_CLASS}>二级动作区</span>
        </summary>
        <div className="grid gap-4 border-t border-white/[0.04] p-4 xl:grid-cols-[minmax(0,0.9fr)_minmax(0,1.1fr)]">
          <div className="rounded-2xl border border-white/5 bg-black/20 px-4 py-4">
            <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-foreground">{t('settings.controlPlaneLogsTitle')}</p>
            <p className="mt-2 text-xs leading-5 text-white/45">查看审计日志不会修改运行时状态。</p>
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
          </div>

          <div className="rounded-2xl border border-amber-300/16 bg-black/25 px-4 py-4">
            <div className="flex flex-wrap items-start justify-between gap-3">
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-[hsl(var(--accent-warning-hsl))]">
                  {t('settings.adminActionsTitle')}
                </p>
                <p className="mt-1 text-sm font-semibold text-foreground">{t('settings.adminActionsDesc')}</p>
              </div>
            </div>
            <div className="mt-4 divide-y divide-white/5 rounded-2xl border border-white/5 bg-white/[0.025]">
              <div className="px-3 py-3">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-semibold text-foreground">{t('settings.adminMaintenanceTitle')}</p>
                    <p className="mt-1 text-xs leading-5 text-white/42">清理缓存前会先进入确认对话。</p>
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
                    <p className="mt-1 text-xs leading-5 text-white/42">高风险重置动作保持在隔离区域内。</p>
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
        </div>
      </details>
    </section>
  );
};

export default SystemControlPlane;
