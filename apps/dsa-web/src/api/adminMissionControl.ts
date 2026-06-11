import apiClient from './index';
import { toCamelCase } from './utils';

export interface MissionControlPosture {
  landedFoundation: boolean;
  evidenceToolingExists: boolean;
  realOperatorEvidenceMissing: boolean;
  approvalRequired: boolean;
  publicLaunchNoGo: boolean;
}

export interface MissionControlSourceRef {
  kind: 'admin_route' | 'api' | 'doc' | 'test' | 'script' | 'fixture' | string;
  label: string;
  ref: string;
}

export interface MissionControlDomainSlice {
  id: string;
  title: string;
  status: string;
  statusLabel: string;
  summary: string;
  posture: MissionControlPosture;
  readOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  dataSources: string[];
  evidenceRefs: MissionControlSourceRef[];
  blockerRefs: MissionControlSourceRef[];
  approvalRefs: MissionControlSourceRef[];
  linkedAdminRoutes: string[];
  opsStatus?: {
    available?: boolean;
    status?: string;
    reasonCode?: string | null;
    summary?: Record<string, unknown>;
    limitations?: string[];
  } | null;
  limitations: string[];
}

export interface MissionControlSummary {
  domainCount: number;
  landedFoundationCount: number;
  evidenceToolingCount: number;
  realOperatorEvidenceMissingCount: number;
  approvalRequiredCount: number;
  publicLaunchNoGoCount: number;
}

export interface MissionControlResponse {
  generatedAt: string;
  readOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
  runtimeBehaviorChanged: boolean;
  publicLaunchApproved: boolean;
  releaseApproved: boolean;
  launchVerdict: 'NO_GO' | string;
  opsSnapshotAvailable: boolean;
  summary: MissionControlSummary;
  domains: MissionControlDomainSlice[];
  postureLegend: Record<string, string>;
  metadata: Record<string, unknown>;
}

function safeArray<T>(value: unknown): T[] {
  return Array.isArray(value) ? value as T[] : [];
}

function normalizeDomain(value: Record<string, unknown>): MissionControlDomainSlice {
  const normalized = toCamelCase<MissionControlDomainSlice>(value);
  return {
    ...normalized,
    dataSources: safeArray<string>(normalized.dataSources),
    evidenceRefs: safeArray<MissionControlSourceRef>(normalized.evidenceRefs),
    blockerRefs: safeArray<MissionControlSourceRef>(normalized.blockerRefs),
    approvalRefs: safeArray<MissionControlSourceRef>(normalized.approvalRefs),
    linkedAdminRoutes: safeArray<string>(normalized.linkedAdminRoutes),
    limitations: safeArray<string>(normalized.limitations),
    readOnly: normalized.readOnly === true,
    noExternalCalls: normalized.noExternalCalls === true,
    liveEnforcement: normalized.liveEnforcement === true,
    runtimeBehaviorChanged: normalized.runtimeBehaviorChanged === true,
  };
}

export const adminMissionControlApi = {
  async getSnapshot(): Promise<MissionControlResponse> {
    const response = await apiClient.get<Record<string, unknown>>('/api/v1/admin/mission-control');
    const normalized = toCamelCase<MissionControlResponse>(response.data);
    return {
      ...normalized,
      readOnly: normalized.readOnly === true,
      noExternalCalls: normalized.noExternalCalls === true,
      liveEnforcement: normalized.liveEnforcement === true,
      runtimeBehaviorChanged: normalized.runtimeBehaviorChanged === true,
      publicLaunchApproved: normalized.publicLaunchApproved === true,
      releaseApproved: normalized.releaseApproved === true,
      opsSnapshotAvailable: normalized.opsSnapshotAvailable === true,
      domains: safeArray<Record<string, unknown>>(normalized.domains).map(normalizeDomain),
      postureLegend: normalized.postureLegend || {},
      metadata: normalized.metadata || {},
    };
  },
};
