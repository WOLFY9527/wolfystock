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
  blockers: AdminOpsCockpitBlocker[];
  safeNextActions: string[];
  limitations: string[];
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

function arrayOfStrings(value: unknown): string[] {
  return Array.isArray(value) ? value.flatMap((item) => {
    const text = String(item || '').trim();
    return text ? [text] : [];
  }) : [];
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
    followUpProposals: Array.isArray(normalized.followUpProposals)
      ? normalized.followUpProposals.map((item) => normalizeProposal(item as unknown as Record<string, unknown>))
      : [],
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
    blockers: Array.isArray(normalized.blockers)
      ? normalized.blockers.map((item) => normalizeBlocker(item as unknown as Record<string, unknown>))
      : [],
    safeNextActions: arrayOfStrings(normalized.safeNextActions),
    limitations: arrayOfStrings(normalized.limitations),
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
};
