import type React from 'react';
import { Label } from '../common';
import { useUiPreferences } from '../../contexts/UiPreferencesContext';
import { BentoCard } from './BentoCard';
import {
  SYSTEM_ACCENT_GLOW_CLASS,
  type SignalTone,
  getToneTextClass,
  getToneTextStyle,
} from './theme';

type DecisionReason = {
  body: string;
  title: string;
};

type SupportingIndicator = {
  context: string;
  label: string;
  value: string;
};

type SignalActionKey = 'buy' | 'sell' | 'hold';

type DecisionCardProps = {
  badge: string;
  company: string;
  eyebrow: string;
  heroLabel: string;
  heroUnit: string;
  heroValue: string;
  confidenceValue?: string;
  locale: 'zh' | 'en';
  reason: DecisionReason;
  reportActions?: React.ReactNode;
  qualityChip?: React.ReactNode;
  riskBoundaryValue?: string;
  scoreLabel: string;
  scoreValue: string;
  signalLabel: string;
  signalTone: SignalTone;
  sourceSummary?: string;
  sector?: string;
  summary: string;
  ticker: string;
  triggerLevelsValue?: string;
  isGuest?: boolean;
  guestPaywall?: React.ReactNode;
};

function resolveSignalActionKey(signalLabel: string, tone: SignalTone): SignalActionKey {
  const normalized = signalLabel.trim().toUpperCase();

  if (/SELL|SHORT|BEAR|REDUCE|TRIM|卖|空|看空|减仓|不建议|风险复核/.test(normalized)) {
    return 'sell';
  }
  if (/HOLD|NEUTRAL|WAIT|WATCH|OBSERVE|持有|中性|观望|观察|等待确认|数据不足/.test(normalized)) {
    return 'hold';
  }
  if (/BUY|LONG|BULL|买|多|看多|乐观|偏多/.test(normalized)) {
    return 'buy';
  }
  return tone === 'bearish' ? 'sell' : tone === 'neutral' ? 'hold' : 'buy';
}

function normalizeSignalCommandLabel(locale: 'zh' | 'en', signalLabel: string): string | null {
  const normalized = signalLabel.trim().toLowerCase();
  if (!normalized || normalized === '-') {
    return null;
  }
  if (/(reduce|trim|减仓)/i.test(signalLabel)) {
    return locale === 'en' ? 'REDUCE' : '减仓';
  }
  return null;
}

function formatSectorLabel(locale: 'zh' | 'en', sector?: string): string {
  const normalized = String(sector || '').trim();
  const lower = normalized.toLowerCase();

  if (locale === 'en') {
    return (normalized || 'UNCLASSIFIED').toUpperCase();
  }

  if (!normalized || lower === 'unclassified') {
    return '未分类';
  }

  const sectorLabels: Record<string, string> = {
    'communication services': '通信服务',
    'consumer cyclical': '可选消费',
    'consumer defensive': '必需消费',
    energy: '能源',
    financials: '金融',
    healthcare: '医疗保健',
    industrials: '工业',
    'real estate': '房地产',
    technology: '科技',
    utilities: '公用事业',
  };

  return sectorLabels[lower] || normalized;
}

function getSignalCommand(locale: 'zh' | 'en', signalLabel: string, tone: SignalTone): { actionKey: SignalActionKey; bias: string; command: string } {
  const actionKey = resolveSignalActionKey(signalLabel, tone);
  const explicitCommand = normalizeSignalCommandLabel(locale, signalLabel);

  if (explicitCommand) {
    return locale === 'en'
      ? { actionKey, command: 'RISK REVIEW', bias: actionKey === 'sell' ? 'RISK UP' : 'NEUTRAL' }
      : { actionKey, command: '风险复核', bias: actionKey === 'sell' ? '风险升高' : '中性' };
  }

  if (actionKey === 'sell') {
    return locale === 'en'
      ? { actionKey, command: 'NOT READY', bias: 'RISK UP' }
      : { actionKey, command: '不建议判断', bias: '风险升高' };
  }

  if (actionKey === 'hold') {
    if (locale === 'zh') {
      if (/有条件观察/.test(signalLabel)) {
        return { actionKey, command: '有条件观察', bias: '建设性' };
      }
      if (/等待确认/.test(signalLabel)) {
        return { actionKey, command: '等待确认', bias: '中性' };
      }
      if (/数据不足/.test(signalLabel)) {
        return { actionKey, command: '数据不足', bias: '中性' };
      }
    }
    return locale === 'en'
      ? { actionKey, command: 'OBSERVE', bias: 'NEUTRAL' }
      : { actionKey, command: '仅观察', bias: '中性' };
  }

  return locale === 'en'
    ? { actionKey, command: 'WATCHLIST', bias: 'CONSTRUCTIVE' }
    : { actionKey, command: '有条件观察', bias: '建设性' };
}

function getActionTone(actionKey: SignalActionKey): SignalTone {
  return actionKey === 'buy' ? 'bullish' : actionKey === 'sell' ? 'bearish' : 'neutral';
}

function getActionToneClass(
  tone: SignalTone,
  marketColorConvention: import('../../utils/marketColors').MarketColorConvention,
): string {
  return tone === 'neutral' ? 'text-white' : getToneTextClass(tone, marketColorConvention);
}

function getActionToneStyle(
  tone: SignalTone,
  marketColorConvention: import('../../utils/marketColors').MarketColorConvention,
): React.CSSProperties {
  if (tone !== 'neutral') {
    return getToneTextStyle(tone, marketColorConvention, true);
  }
  return {
    color: '#F8FAFC',
    textShadow: '0 0 18px rgba(99, 102, 241, 0.18)',
  };
}

function getConvictionSegmentClass(tone: SignalTone, active: boolean): string {
  if (!active) {
    return 'bg-white/[0.08]';
  }
  if (tone === 'bearish') {
    return 'bg-rose-300 shadow-[0_0_10px_rgba(248,113,113,0.55)]';
  }
  if (tone === 'neutral') {
    return 'bg-white/70 shadow-[0_0_10px_rgba(226,232,240,0.35)]';
  }
  return 'bg-emerald-300 shadow-[0_0_10px_rgba(110,231,183,0.5)]';
}

function resolveConfidencePresentation(value: string | undefined): { display: string; activeSegments: number } {
  const text = String(value || '').trim();
  if (!text || text === '-') {
    return { display: '-', activeSegments: 0 };
  }

  const normalized = text.toLowerCase();
  if (/(极高|very high)/.test(normalized)) {
    return { display: text, activeSegments: 5 };
  }
  if (/(高|high)/.test(normalized)) {
    return { display: text, activeSegments: 4 };
  }
  if (/(中等|中|medium|moderate)/.test(normalized)) {
    return { display: text, activeSegments: 3 };
  }
  if (/(低|low)/.test(normalized)) {
    return { display: text, activeSegments: 2 };
  }

  const percentMatch = text.match(/^(-?\d+(?:\.\d+)?)\s*%$/);
  if (percentMatch) {
    const percent = Number.parseFloat(percentMatch[1]);
    if (Number.isFinite(percent)) {
      return {
        display: text,
        activeSegments: Math.max(0, Math.min(5, Math.ceil(percent / 20))),
      };
    }
  }

  if (/^-?\d+(?:\.\d+)?$/.test(text)) {
    const numeric = Number.parseFloat(text);
    if (Number.isFinite(numeric)) {
      if (numeric >= 0 && numeric <= 1) {
        return {
          display: text,
          activeSegments: Math.max(0, Math.min(5, Math.ceil(numeric * 5))),
        };
      }
      if (numeric >= 0 && numeric <= 100) {
        return {
          display: text,
          activeSegments: Math.max(0, Math.min(5, Math.ceil(numeric / 20))),
        };
      }
    }
  }

  return { display: text, activeSegments: 0 };
}

function getSupportingIndicators(locale: 'zh' | 'en', tone: SignalTone): SupportingIndicator[] {
  if (tone === 'bearish') {
    return locale === 'en'
      ? [
          { label: 'MA ALIGNMENT', value: 'BEARISH', context: 'MA20 < MA60' },
          { label: 'LIQUIDITY AB.', value: 'THIN', context: 'Bid weakens' },
          { label: 'RSI-14', value: '41', context: 'Weak zone' },
          { label: 'MACD-12/26/9', value: 'BEAR CROSS', context: 'Below zero' },
          { label: 'VOLUME CONF.', value: 'NO', context: 'Failed follow-through' },
        ]
      : [
          { label: '均线排列', value: '空头', context: 'MA20 低于 MA60' },
          { label: '资金承接', value: '偏弱', context: '买盘退潮' },
          { label: 'RSI-14', value: '41', context: '弱势区' },
          { label: 'MACD-12/26/9', value: '死叉', context: '零轴下方' },
          { label: '量能确认', value: '否', context: '承接不足' },
        ];
  }

  if (tone === 'neutral') {
    return locale === 'en'
      ? [
          { label: 'MA ALIGNMENT', value: 'MIXED', context: 'Short-term repair' },
          { label: 'LIQUIDITY AB.', value: 'BALANCED', context: 'Flow stabilizing' },
          { label: 'RSI-14', value: '54', context: 'Repair zone' },
          { label: 'MACD-12/26/9', value: 'EARLY TURN', context: 'Histogram improving' },
          { label: 'VOLUME CONF.', value: 'PENDING', context: 'Needs a second push' },
        ]
      : [
          { label: '均线排列', value: '混合', context: '短线修复中' },
          { label: '资金承接', value: '均衡', context: '流向趋稳' },
          { label: 'RSI-14', value: '54', context: '修复区' },
          { label: 'MACD-12/26/9', value: '拐点初现', context: '柱体改善' },
          { label: '量能确认', value: '待确认', context: '需要二次放量' },
        ];
  }

  return locale === 'en'
    ? [
        { label: 'MA ALIGNMENT', value: 'BULLISH', context: 'Stacked higher' },
        { label: 'LIQUIDITY AB.', value: 'STRONG', context: 'Institutional bid' },
        { label: 'RSI-14', value: '68', context: 'Strong zone' },
        { label: 'MACD-12/26/9', value: 'BULL CROSSOVER', context: 'Above zero' },
        { label: 'VOLUME CONF.', value: 'YES', context: 'Quiet pullback / active breakout' },
      ]
      : [
          { label: '均线排列', value: '多头', context: '均线多头排列' },
          { label: '资金承接', value: '强力', context: '机构承接' },
          { label: 'RSI-14', value: '68', context: '强势区' },
          { label: 'MACD-12/26/9', value: '金叉', context: '零轴上方' },
          { label: '量能确认', value: '是', context: '缩量回踩 / 放量突破' },
        ];
}

export const DecisionCard: React.FC<DecisionCardProps> = ({
  company,
  eyebrow,
  heroUnit,
  heroValue,
  confidenceValue,
  locale,
  qualityChip,
  reason,
  reportActions,
  riskBoundaryValue,
  scoreValue,
  signalLabel,
  signalTone,
  sourceSummary,
  sector,
  summary,
  ticker,
  triggerLevelsValue,
  isGuest = false,
  guestPaywall,
}) => {
  const { marketColorConvention } = useUiPreferences();
  const signalCommand = getSignalCommand(locale, signalLabel, signalTone);
  const actionTone = getActionTone(signalCommand.actionKey);
  const supportingIndicators = getSupportingIndicators(locale, signalTone);
  const isEnglish = locale === 'en';
  const insightCopy = reason.body || summary || scoreValue || '-';
  const sectorLabel = formatSectorLabel(locale, sector);
  const confidencePresentation = resolveConfidencePresentation(confidenceValue);
  const convictionDisplay = confidencePresentation.display;
  const activeConvictionSegments = confidencePresentation.activeSegments;
  const researchStateTiles = [
    {
      label: isEnglish ? 'Conclusion' : '结论',
      value: signalCommand.command,
      tone: actionTone,
    },
    {
      label: isEnglish ? 'Risk Boundary' : '风险边界',
      value: riskBoundaryValue || '-',
      tone: 'bearish' as SignalTone,
    },
    {
      label: isEnglish ? 'Trigger Levels' : '触发位',
      value: triggerLevelsValue || '-',
      tone: 'neutral' as SignalTone,
    },
    {
      label: isEnglish ? 'Conviction' : '置信度',
      value: convictionDisplay,
      tone: signalTone,
    },
  ];

  return (
    <BentoCard
      eyebrow={eyebrow}
      tone={signalTone}
      accentGlow
      accentGlowClassName={SYSTEM_ACCENT_GLOW_CLASS}
      className="w-full overflow-visible rounded-[24px] xl:flex xl:h-full xl:flex-col xl:overflow-hidden"
      contentClassName="h-auto xl:h-full xl:min-h-0"
      researchCard="decision"
      testId="home-bento-card-decision"
      action={reportActions ? (
        <div className="flex max-w-[min(100%,16rem)] flex-wrap items-center justify-end gap-2 sm:max-w-[min(100%,28rem)]" data-testid="home-bento-decision-header-actions">
          {reportActions}
        </div>
      ) : undefined}
    >
      <div className="flex h-auto flex-col gap-5 xl:h-full xl:min-h-0">
        <div className="flex flex-wrap items-start justify-between gap-3" data-testid="home-bento-decision-company-header">
          <div className="min-w-0 flex-1">
            <div className="flex min-w-0 flex-wrap items-baseline gap-x-3 gap-y-1">
              <span className="min-w-0 truncate text-xl font-bold leading-tight text-white">{company}</span>
              <span className="font-mono text-base text-white/40">({ticker})</span>
            </div>
            <div
              className="mt-1 text-[10px] font-semibold uppercase tracking-[0.24em] text-white/34"
              data-testid="home-bento-decision-sector"
            >
              {sectorLabel}
            </div>
          </div>
        </div>
        {sourceSummary ? (
          <p className="min-w-0 rounded-xl border border-white/[0.05] bg-white/[0.018] px-3 py-2 text-xs leading-5 text-white/46" data-testid="home-bento-decision-source-summary">
            {sourceSummary}
          </p>
        ) : null}

        <div
          className="grid gap-3 rounded-[24px] border border-white/[0.05] bg-white/[0.02] p-3 sm:grid-cols-2 xl:grid-cols-4"
          data-testid="home-bento-research-state-row"
        >
          {researchStateTiles.map((tile) => (
            <div key={tile.label} className="min-w-0 rounded-2xl border border-white/[0.05] bg-black/15 px-3 py-2.5">
              <p className="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/36">{tile.label}</p>
              <p className={`mt-2 break-words text-sm font-medium leading-relaxed ${getActionToneClass(tile.tone, marketColorConvention)}`} style={getActionToneStyle(tile.tone, marketColorConvention)}>
                {tile.value}
              </p>
            </div>
          ))}
        </div>

        <div
          className="overflow-visible pr-2 pb-6 xl:min-h-0 xl:flex-1 xl:overflow-y-auto xl:no-scrollbar xl:[&::-webkit-scrollbar]:hidden xl:[-ms-overflow-style:none] xl:[scrollbar-width:none]"
          data-testid="home-bento-decision-scroll-body"
        >
          <div
            className="grid w-full grid-cols-2 items-end gap-8 mt-6 mb-10 xl:grid-cols-3"
            data-testid="home-bento-decision-hero-row"
          >
            <div className="col-span-1 min-w-0" data-testid="home-bento-decision-action">
              <Label micro className="text-white/28">{isEnglish ? 'ANALYSIS STATE' : '分析状态'}</Label>
              <span
                className={`mt-3 block text-4xl font-black leading-none tracking-[0] md:text-5xl ${getActionToneClass(actionTone, marketColorConvention)}`}
                data-testid="home-bento-decision-signal-hero"
                style={getActionToneStyle(actionTone, marketColorConvention)}
              >
                {signalCommand.command}
              </span>
            </div>

            <div className="col-span-1 min-w-0" data-testid="home-bento-decision-score">
              <Label micro className="text-white/28">{isEnglish ? 'SCORE' : '评分'}</Label>
              <div
                className="mt-3 flex items-end gap-2"
                data-testid="home-bento-decision-core-metrics"
              >
                <p
                  className="font-mono text-4xl font-semibold leading-none text-white md:text-5xl"
                  data-testid="home-bento-decision-score-value"
                >
                  {heroValue}
                </p>
                <span className="pb-1 text-sm font-medium text-white/42">{heroUnit}</span>
              </div>
            </div>

            <div className="col-span-2 min-w-0 w-full xl:col-span-1" data-testid="home-bento-decision-conviction">
              <div className="flex items-end justify-between gap-4">
                <div className="flex min-w-0 items-center gap-2">
                  <Label micro className="text-white/40">{isEnglish ? 'AI CONVICTION' : '置信度'}</Label>
                  {qualityChip}
                </div>
                <span className="font-mono text-2xl font-semibold leading-none text-white md:text-3xl" data-testid="home-bento-decision-conviction-value">
                  {convictionDisplay}
                </span>
              </div>
              <div className="mt-4 grid grid-cols-5 gap-2">
                {Array.from({ length: 5 }, (_, index) => {
                  const isActive = index < activeConvictionSegments;
                  return (
                    <div
                      key={index}
                      className={`h-3 min-w-0 ${getConvictionSegmentClass(signalTone, isActive)}`}
                      data-testid={`home-bento-decision-conviction-segment-${index + 1}`}
                    />
                  );
                })}
              </div>
              <div className="mt-2 h-px w-full bg-gradient-to-r from-white/0 via-white/18 to-white/0" />
            </div>
          </div>

          <div
            className="max-w-3xl text-sm text-white/70 leading-relaxed mb-10"
            data-testid="home-bento-decision-insight"
          >
            <Label micro className="text-white/28">{isEnglish ? 'AI INSIGHT' : '分析主线'}</Label>
            <p className="mt-3" data-testid="home-bento-decision-insight-copy">
              {insightCopy}
            </p>
          </div>

          <div className="relative flex flex-col overflow-hidden rounded-[28px] border border-white/[0.06] bg-black/10 px-5 py-4 backdrop-blur-xl md:px-6">
            <div className="flex items-center justify-between gap-3 border-b border-white/8 pb-3">
              <Label micro className="text-white/30">{isEnglish ? 'SUPPORTING INDICATORS' : '量化佐证指标'}</Label>
              <span className="text-[10px] font-semibold uppercase tracking-[0.22em] text-white/28">
                {isEnglish ? 'SIMULATED FEED' : '模拟信号流'}
              </span>
            </div>
            <div
              className={isGuest ? 'pointer-events-none opacity-80' : undefined}
              data-testid="home-bento-decision-support-grid"
            >
              {supportingIndicators.map((indicator) => (
                <div
                  key={indicator.label}
                  className="flex items-center justify-between gap-3 border-b border-white/5 py-2.5 text-xs last:border-b-0"
                >
                  <div className="min-w-0 flex-1">
                    <Label micro className="text-[10px] text-white/40">{indicator.label}</Label>
                  </div>
                  <div
                    className={`min-w-0 shrink-0 text-center text-xs font-medium uppercase tracking-[0.12em] ${getToneTextClass(signalTone, marketColorConvention)}`}
                    style={getToneTextStyle(signalTone, marketColorConvention, true)}
                  >
                    <span className="block truncate">{indicator.value}</span>
                  </div>
                  <div className="min-w-0 flex-1 text-right text-xs font-medium text-white/56">
                    <span className="block truncate">{indicator.context}</span>
                  </div>
                </div>
              ))}
            </div>
            {isGuest ? guestPaywall : null}
          </div>
        </div>
      </div>
    </BentoCard>
  );
};
