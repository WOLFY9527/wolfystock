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

export interface MissionControlPrototypeGate {
  enabled: boolean;
  status: 'disabled' | 'enabled' | string;
  reasonCode?: string | null;
  featureFlag: string;
  readOnly: boolean;
  advisoryOnly: boolean;
  noExternalCalls: boolean;
  liveEnforcement: boolean;
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
  prototypeGate: MissionControlPrototypeGate;
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

function normalizePrototypeGate(value: unknown): MissionControlPrototypeGate {
  const normalized = toCamelCase<MissionControlPrototypeGate>(
    value && typeof value === 'object' ? value as Record<string, unknown> : {},
  );
  return {
    ...normalized,
    enabled: normalized.enabled === true,
    status: normalized.status || 'disabled',
    featureFlag: normalized.featureFlag || 'WOLFYSTOCK_ADMIN_MISSION_CONTROL_PROTOTYPE_ENABLED',
    readOnly: normalized.readOnly !== false,
    advisoryOnly: normalized.advisoryOnly !== false,
    noExternalCalls: normalized.noExternalCalls !== false,
    liveEnforcement: normalized.liveEnforcement === true,
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
      prototypeGate: normalizePrototypeGate(normalized.prototypeGate),
      opsSnapshotAvailable: normalized.opsSnapshotAvailable === true,
      domains: safeArray<Record<string, unknown>>(normalized.domains).map(normalizeDomain),
      postureLegend: normalized.postureLegend || {},
      metadata: normalized.metadata || {},
    };
  },
};
