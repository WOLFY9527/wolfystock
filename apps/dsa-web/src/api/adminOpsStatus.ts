import apiClient from './index';
import { toCamelCase } from './utils';

export interface AdminOpsStatusSection {
  available: boolean;
  status: string;
  label: string;
  reasonCode?: string | null;
  readOnly: boolean;
  noExternalCalls: boolean;
  advisoryOnly: boolean;
  liveEnforcement: boolean;
  enforcementEnabled: boolean;
  runtimeBehaviorChanged: boolean;
  consumerVisible: boolean;
  providerBehaviorChanged: boolean;
  marketCacheBehaviorChanged: boolean;
  deleteAllowed: boolean;
  dataSources: string[];
  summary: Record<string, unknown>;
  limitations: string[];
}

export interface AdminOpsAdvisoryVsEnforcement {
  label: string;
  enforcementLabel: string;
  sourceUnavailableBehavior: string;
  readOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  consumerVisible: boolean;
}

export interface AdminOpsCockpitFollowUpProposal {
  proposalKey: string;
  title: string;
  approvalNeeded: boolean;
  likelyFiles: string[];
  risk: string;
  validation: string[];
}

export interface AdminOpsCockpitDomain {
  domainKey: string;
  label: string;
  status: string;
  statusLabel: string;
  detailRoute: string;
  foundationLanded: boolean;
  evidenceToolingPresent: boolean;
  realOperatorEvidenceMissing: boolean;
  approvalRequired: boolean;
  publicLaunchNoGo: boolean;
  readOnly: boolean;
  advisoryOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  providerRuntimeChanged: boolean;
  externalActionsEnabled: boolean;
  evidenceRefs: string[];
  blockerRefs: string[];
  safeNextActions: string[];
  limitations: string[];
  priorityRank: number;
  priorityTier: string;
  impactLevel: string;
  recommendedNextAction: string;
  blockingReasonSummary: string;
  ownerSurface: string;
  remediationSurface: string;
  followUpProposals: AdminOpsCockpitFollowUpProposal[];
}

export interface AdminOpsCockpitBlocker {
  blockerKey: string;
  title: string;
  severity: string;
  publicLaunchNoGo: boolean;
  approvalRequired: boolean;
  affectedDomains: string[];
  evidenceRefs: string[];
  nextAction: string;
}

export interface AdminOpsCockpitMaintenanceQueueItem {
  domainKey: string;
  label: string;
  status: string;
  priorityRank: number;
  priorityTier: string;
  impactLevel: string;
  recommendedNextAction: string;
  blockingReasonSummary: string;
  ownerSurface: string;
  remediationSurface: string;
}

export interface AdminOpsLaunchCockpit {
  contract: string;
  readOnly: boolean;
  advisoryOnly: boolean;
  noExternalCalls: boolean;
  publicLaunchApproved: boolean;
  publicLaunchNoGo: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  approvalRequired: boolean;
  summaryCounts: Record<string, number>;
  unsafeActionStates: Record<string, boolean>;
  domains: AdminOpsCockpitDomain[];
  recommendedMaintenanceQueue: AdminOpsCockpitMaintenanceQueueItem[];
  blockers: AdminOpsCockpitBlocker[];
  safeNextActions: string[];
  limitations: string[];
  prioritySummary: Record<string, number>;
}

export interface AdminOpsStatusResponse {
  generatedAt: string;
  readOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  consumerVisible: boolean;
  advisoryVsEnforcement: AdminOpsAdvisoryVsEnforcement;
  providerStatusSummary?: AdminOpsStatusSection;
  quotaCostAdvisoryStatusSummary?: AdminOpsStatusSection;
  storageReadinessSummary?: AdminOpsStatusSection;
  taskQueueStatusSummary?: AdminOpsStatusSection;
  adminLogEvidenceSummary?: AdminOpsStatusSection;
  launchCockpit: AdminOpsLaunchCockpit;
  metadata?: Record<string, unknown>;
}

export interface AdminScannerUniverseReadinessResponse {
  contractVersion: string;
  status: string;
  scannerUniverseStatus?: string | null;
  market: string;
  profile: string;
  freshnessState: string;
  lastUpdatedAt?: string | null;
  universeSize: number;
  affectedProductSurfaces: string[];
  nextOperatorAction: string;
  scannerUniverseReadiness: Record<string, unknown>;
  candidateGenerationState?: string | null;
  candidateGenerationBlockers: string[];
  readOnly: boolean;
  noExternalCalls: boolean;
  mutationEnabled: boolean;
  providerCallsEnabled: boolean;
  consumerVisible: boolean;
}

export interface AdminScannerUniverseRefreshResponse {
  contractVersion: string;
  status: string;
  actionStatus: string;
  market: string;
  profile: string;
  refreshExecuted: boolean;
  mutationEnabled: boolean;
  noExternalCalls: boolean;
  providerCallsEnabled: boolean;
  runtimeBehaviorChanged: boolean;
  nextOperatorAction: string;
  before: Record<string, unknown>;
  after: Record<string, unknown>;
}

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value)
    ? value.flatMap((item) => {
      const text = String(item || '').trim();
      return text ? [text] : [];
    })
    : [];
}

function normalizeProposal(payload: Record<string, unknown>): AdminOpsCockpitFollowUpProposal {
  const normalized = toCamelCase<AdminOpsCockpitFollowUpProposal>(payload);
  return {
    proposalKey: String(normalized.proposalKey || ''),
    title: String(normalized.title || ''),
    approvalNeeded: normalized.approvalNeeded !== false,
    likelyFiles: arrayOfStrings(normalized.likelyFiles),
    risk: String(normalized.risk || ''),
    validation: arrayOfStrings(normalized.validation),
  };
}

function normalizeDomain(payload: Record<string, unknown>): AdminOpsCockpitDomain {
  const normalized = toCamelCase<AdminOpsCockpitDomain>(payload);
  return {
    domainKey: String(normalized.domainKey || ''),
    label: String(normalized.label || ''),
    status: String(normalized.status || ''),
    statusLabel: String(normalized.statusLabel || ''),
    detailRoute: String(normalized.detailRoute || '/settings/system'),
    foundationLanded: Boolean(normalized.foundationLanded),
    evidenceToolingPresent: Boolean(normalized.evidenceToolingPresent),
    realOperatorEvidenceMissing: Boolean(normalized.realOperatorEvidenceMissing),
    approvalRequired: normalized.approvalRequired !== false,
    publicLaunchNoGo: normalized.publicLaunchNoGo !== false,
    readOnly: normalized.readOnly !== false,
    advisoryOnly: normalized.advisoryOnly !== false,
    noExternalCalls: normalized.noExternalCalls !== false,
    liveEnforcement: Boolean(normalized.liveEnforcement),
    runtimeBehaviorChanged: Boolean(normalized.runtimeBehaviorChanged),
    providerRuntimeChanged: Boolean(normalized.providerRuntimeChanged),
    externalActionsEnabled: Boolean(normalized.externalActionsEnabled),
    evidenceRefs: arrayOfStrings(normalized.evidenceRefs),
    blockerRefs: arrayOfStrings(normalized.blockerRefs),
    safeNextActions: arrayOfStrings(normalized.safeNextActions),
    limitations: arrayOfStrings(normalized.limitations),
    priorityRank: Number(normalized.priorityRank || 0),
    priorityTier: String(normalized.priorityTier || 'watch'),
    impactLevel: String(normalized.impactLevel || 'low'),
    recommendedNextAction: String(normalized.recommendedNextAction || ''),
    blockingReasonSummary: String(normalized.blockingReasonSummary || ''),
    ownerSurface: String(normalized.ownerSurface || 'admin_maintenance'),
    remediationSurface: String(normalized.remediationSurface || normalized.detailRoute || '/admin'),
    followUpProposals: Array.isArray(normalized.followUpProposals)
      ? normalized.followUpProposals.map((item) => normalizeProposal(item as unknown as Record<string, unknown>))
      : [],
  };
}

function normalizeQueueItem(payload: Record<string, unknown>): AdminOpsCockpitMaintenanceQueueItem {
  const normalized = toCamelCase<AdminOpsCockpitMaintenanceQueueItem>(payload);
  return {
    domainKey: String(normalized.domainKey || ''),
    label: String(normalized.label || ''),
    status: String(normalized.status || ''),
    priorityRank: Number(normalized.priorityRank || 0),
    priorityTier: String(normalized.priorityTier || 'watch'),
    impactLevel: String(normalized.impactLevel || 'low'),
    recommendedNextAction: String(normalized.recommendedNextAction || ''),
    blockingReasonSummary: String(normalized.blockingReasonSummary || ''),
    ownerSurface: String(normalized.ownerSurface || 'admin_maintenance'),
    remediationSurface: String(normalized.remediationSurface || '/admin'),
  };
}

function normalizeBlocker(payload: Record<string, unknown>): AdminOpsCockpitBlocker {
  const normalized = toCamelCase<AdminOpsCockpitBlocker>(payload);
  return {
    blockerKey: String(normalized.blockerKey || ''),
    title: String(normalized.title || ''),
    severity: String(normalized.severity || 'high'),
    publicLaunchNoGo: normalized.publicLaunchNoGo !== false,
    approvalRequired: normalized.approvalRequired !== false,
    affectedDomains: arrayOfStrings(normalized.affectedDomains),
    evidenceRefs: arrayOfStrings(normalized.evidenceRefs),
    nextAction: String(normalized.nextAction || ''),
  };
}

function normalizeLaunchCockpit(payload: Record<string, unknown> | undefined): AdminOpsLaunchCockpit {
  const normalized = toCamelCase<AdminOpsLaunchCockpit>(payload || {});
  return {
    contract: String(normalized.contract || 'admin_ops_launch_cockpit_v1'),
    readOnly: normalized.readOnly !== false,
    advisoryOnly: normalized.advisoryOnly !== false,
    noExternalCalls: normalized.noExternalCalls !== false,
    publicLaunchApproved: Boolean(normalized.publicLaunchApproved),
    publicLaunchNoGo: normalized.publicLaunchNoGo !== false,
    liveEnforcement: Boolean(normalized.liveEnforcement),
    runtimeBehaviorChanged: Boolean(normalized.runtimeBehaviorChanged),
    approvalRequired: normalized.approvalRequired !== false,
    summaryCounts: normalized.summaryCounts && typeof normalized.summaryCounts === 'object'
      ? Object.fromEntries(Object.entries(normalized.summaryCounts).map(([key, value]) => [key, Number(value || 0)]))
      : {},
    unsafeActionStates: normalized.unsafeActionStates && typeof normalized.unsafeActionStates === 'object'
      ? Object.fromEntries(Object.entries(normalized.unsafeActionStates).map(([key, value]) => [key, Boolean(value)]))
      : {},
    domains: Array.isArray(normalized.domains)
      ? normalized.domains.map((item) => normalizeDomain(item as unknown as Record<string, unknown>))
      : [],
    recommendedMaintenanceQueue: Array.isArray(normalized.recommendedMaintenanceQueue)
      ? normalized.recommendedMaintenanceQueue.map((item) => normalizeQueueItem(item as unknown as Record<string, unknown>))
      : [],
    blockers: Array.isArray(normalized.blockers)
      ? normalized.blockers.map((item) => normalizeBlocker(item as unknown as Record<string, unknown>))
      : [],
    safeNextActions: arrayOfStrings(normalized.safeNextActions),
    limitations: arrayOfStrings(normalized.limitations),
    prioritySummary: normalized.prioritySummary && typeof normalized.prioritySummary === 'object'
      ? Object.fromEntries(Object.entries(normalized.prioritySummary).map(([key, value]) => [key, Number(value || 0)]))
      : {},
  };
}

function normalizeScannerUniverseReadiness(
  payload: Record<string, unknown>,
): AdminScannerUniverseReadinessResponse {
  const normalized = toCamelCase<AdminScannerUniverseReadinessResponse>(payload || {});
  return {
    contractVersion: String(normalized.contractVersion || 'scanner_universe_operator_readiness_v1'),
    status: String(normalized.status || 'unavailable'),
    scannerUniverseStatus: normalized.scannerUniverseStatus ? String(normalized.scannerUniverseStatus) : null,
    market: String(normalized.market || ''),
    profile: String(normalized.profile || ''),
    freshnessState: String(normalized.freshnessState || 'unknown'),
    lastUpdatedAt: normalized.lastUpdatedAt ? String(normalized.lastUpdatedAt) : null,
    universeSize: Number(normalized.universeSize || 0),
    affectedProductSurfaces: arrayOfStrings(normalized.affectedProductSurfaces),
    nextOperatorAction: String(normalized.nextOperatorAction || ''),
    scannerUniverseReadiness: normalized.scannerUniverseReadiness && typeof normalized.scannerUniverseReadiness === 'object'
      ? normalized.scannerUniverseReadiness as Record<string, unknown>
      : {},
    candidateGenerationState: normalized.candidateGenerationState ? String(normalized.candidateGenerationState) : null,
    candidateGenerationBlockers: arrayOfStrings(normalized.candidateGenerationBlockers),
    readOnly: normalized.readOnly !== false,
    noExternalCalls: normalized.noExternalCalls !== false,
    mutationEnabled: Boolean(normalized.mutationEnabled),
    providerCallsEnabled: Boolean(normalized.providerCallsEnabled),
    consumerVisible: Boolean(normalized.consumerVisible),
  };
}

function normalizeScannerUniverseRefresh(
  payload: Record<string, unknown>,
): AdminScannerUniverseRefreshResponse {
  const normalized = toCamelCase<AdminScannerUniverseRefreshResponse>(payload || {});
  return {
    contractVersion: String(normalized.contractVersion || 'scanner_universe_operator_action_v1'),
    status: String(normalized.status || 'manual_action_required'),
    actionStatus: String(normalized.actionStatus || 'deferred'),
    market: String(normalized.market || ''),
    profile: String(normalized.profile || ''),
    refreshExecuted: Boolean(normalized.refreshExecuted),
    mutationEnabled: Boolean(normalized.mutationEnabled),
    noExternalCalls: normalized.noExternalCalls !== false,
    providerCallsEnabled: Boolean(normalized.providerCallsEnabled),
    runtimeBehaviorChanged: Boolean(normalized.runtimeBehaviorChanged),
    nextOperatorAction: String(normalized.nextOperatorAction || ''),
    before: normalized.before && typeof normalized.before === 'object'
      ? normalized.before as Record<string, unknown>
      : {},
    after: normalized.after && typeof normalized.after === 'object'
      ? normalized.after as Record<string, unknown>
      : {},
  };
}

export const adminOpsStatusApi = {
  async getStatus(): Promise<AdminOpsStatusResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/ops/status');
    const normalized = toCamelCase<AdminOpsStatusResponse>(response.data || {});
    return {
      ...normalized,
      readOnly: normalized.readOnly !== false,
      noExternalCalls: normalized.noExternalCalls !== false,
      liveEnforcement: Boolean(normalized.liveEnforcement),
      runtimeBehaviorChanged: Boolean(normalized.runtimeBehaviorChanged),
      consumerVisible: Boolean(normalized.consumerVisible),
      launchCockpit: normalizeLaunchCockpit(normalized.launchCockpit as unknown as Record<string, unknown>),
    };
  },
  async getScannerUniverseReadiness(market: 'us' | 'cn'): Promise<AdminScannerUniverseReadinessResponse> {
    const response = await apiClient.get<Record<string, unknown>>(
      `/api/v1/admin/ops/scanner-universe-readiness?market=${encodeURIComponent(market)}`,
    );
    return normalizeScannerUniverseReadiness(response.data || {});
  },
  async requestScannerUniverseRefresh(market: 'us' | 'cn'): Promise<AdminScannerUniverseRefreshResponse> {
    const response = await apiClient.post<Record<string, unknown>>(
      `/api/v1/admin/ops/scanner-universe-refresh?market=${encodeURIComponent(market)}`,
    );
    return normalizeScannerUniverseRefresh(response.data || {});
  },
};
