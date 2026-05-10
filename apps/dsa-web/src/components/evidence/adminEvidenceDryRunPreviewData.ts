export type AdminEvidenceDryRunPreviewItem = {
  engine: 'scanner' | 'rotation' | 'options' | 'backtest' | 'portfolio_risk';
  engineLabel: string;
  representativePacket: string;
  explanationMode: 'dry_run';
  sourcePacketVersion: string;
  posture: 'blocked' | 'observe_only' | 'allowed_metadata_only' | 'review_required';
  confidenceCap: number;
  disabledClaims: string[];
  safeSummary: string;
  limitationLabels: string[];
  adminReasonCodeCount: number;
  generatedAt: string;
  validationState: 'valid' | 'invalid' | 'not_evaluated';
};

export const ADMIN_EVIDENCE_DRY_RUN_PREVIEWS: AdminEvidenceDryRunPreviewItem[] = [
  {
    engine: 'scanner',
    engineLabel: 'Scanner',
    representativePacket: '最近候选 · WULF · run #42',
    explanationMode: 'dry_run',
    sourcePacketVersion: 'ai_evidence_packet_v1',
    posture: 'allowed_metadata_only',
    confidenceCap: 82,
    disabledClaims: [],
    safeSummary: '当前证据链已校验，可用于观察，不提升任何判断强度。',
    limitationLabels: ['仅供观察'],
    adminReasonCodeCount: 2,
    generatedAt: '2026-05-10T08:10:00Z',
    validationState: 'valid',
  },
  {
    engine: 'rotation',
    engineLabel: 'Rotation',
    representativePacket: '主题样本 · AI 应用 · APP',
    explanationMode: 'dry_run',
    sourcePacketVersion: 'ai_evidence_packet_v1',
    posture: 'observe_only',
    confidenceCap: 68,
    disabledClaims: ['real_fund_flow_claim'],
    safeSummary: '当前为轮动代理证据，真实资金流暂缺，仅供观察。',
    limitationLabels: ['真实资金流暂缺', '仅供观察'],
    adminReasonCodeCount: 4,
    generatedAt: '2026-05-10T08:12:00Z',
    validationState: 'valid',
  },
  {
    engine: 'options',
    engineLabel: 'Options',
    representativePacket: '样本标的 · WULF · bull_call_spread',
    explanationMode: 'dry_run',
    sourcePacketVersion: 'ai_evidence_packet_v1',
    posture: 'blocked',
    confidenceCap: 35,
    disabledClaims: ['options_recommendation', 'options_tradeability'],
    safeSummary: '当前期权证据不足，数据不足，禁止判断，仅保留观察与人工复核。',
    limitationLabels: ['数据不足，禁止判断', '演示数据'],
    adminReasonCodeCount: 5,
    generatedAt: '2026-05-10T08:14:00Z',
    validationState: 'valid',
  },
  {
    engine: 'backtest',
    engineLabel: 'Backtest',
    representativePacket: '最近回测 · NVDA · #2084',
    explanationMode: 'dry_run',
    sourcePacketVersion: 'ai_evidence_packet_v1',
    posture: 'observe_only',
    confidenceCap: 62,
    disabledClaims: ['professional_backtest_claim'],
    safeSummary: '当前仅为研究级回测证据，仅供观察，不构成机构级验证结论。',
    limitationLabels: ['研究级回测', '仅供观察'],
    adminReasonCodeCount: 3,
    generatedAt: '2026-05-10T08:16:00Z',
    validationState: 'valid',
  },
  {
    engine: 'portfolio_risk',
    engineLabel: 'Portfolio',
    representativePacket: '账户样本 · 2 个账户 · AAPL',
    explanationMode: 'dry_run',
    sourcePacketVersion: 'ai_evidence_packet_v1',
    posture: 'observe_only',
    confidenceCap: 58,
    disabledClaims: ['strong_risk_conclusion'],
    safeSummary: '当前组合风险证据链不完整，仅供风险观察，不输出确定性风险结论。',
    limitationLabels: ['仅供风险观察', 'FX 汇率已过期', '持仓来源待核验'],
    adminReasonCodeCount: 4,
    generatedAt: '2026-05-10T08:18:00Z',
    validationState: 'valid',
  },
];
