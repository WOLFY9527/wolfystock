import { describe, expect, it } from 'vitest';
import {
  describeAdminLogLevel,
  describeAdminNotificationStatus,
  describeBooleanEnabled,
  describeDisplayStatus,
  describeSettingsDuckDBDataMode,
  describeSettingsDuckDBDiagnosticStatus,
  describeSettingsEnabledState,
  describeSettingsSystemHealthStatus,
  normalizeDisplayStatus,
} from '../displayStatus';

describe('displayStatus', () => {
  it('normalizes display status values safely', () => {
    expect(normalizeDisplayStatus(' SUCCESS ')).toBe('success');
    expect(normalizeDisplayStatus('Provider Down')).toBe('provider_down');
    expect(normalizeDisplayStatus(null)).toBe('');
    expect(normalizeDisplayStatus(undefined)).toBe('');
  });

  it('describes enabled and disabled boolean states with stable tones', () => {
    expect(describeBooleanEnabled(true)).toEqual({
      label: '已启用',
      tone: 'success',
    });
    expect(describeBooleanEnabled(false)).toEqual({
      label: '已停用',
      tone: 'muted',
    });
    expect(describeBooleanEnabled(null)).toEqual({
      label: '未确认',
      tone: 'info',
    });
  });

  it('returns chinese labels and stable tones for common display statuses', () => {
    expect(describeDisplayStatus('success')).toEqual({
      label: '成功',
      tone: 'success',
    });
    expect(describeDisplayStatus('failed')).toEqual({
      label: '失败',
      tone: 'danger',
    });
    expect(describeDisplayStatus('partial')).toEqual({
      label: '部分成功',
      tone: 'warning',
    });
    expect(describeDisplayStatus('pending')).toEqual({
      label: '等待中',
      tone: 'warning',
    });
  });

  it('does not leak raw unknown values as visible labels', () => {
    expect(describeDisplayStatus('unknown')).toEqual({
      label: '未确认',
      tone: 'info',
    });
    expect(describeDisplayStatus('provider_error')).toEqual({
      label: '未确认',
      tone: 'info',
    });
    expect(describeDisplayStatus('raw_internal_status')).toEqual({
      label: '未确认',
      tone: 'info',
    });
  });

  it('handles nullish and fallback labels safely', () => {
    expect(describeDisplayStatus(null)).toEqual({
      label: '未确认',
      tone: 'info',
    });
    expect(describeDisplayStatus(undefined, '未提供')).toEqual({
      label: '未提供',
      tone: 'info',
    });
  });

  it('keeps admin notification status mapping domain-specific', () => {
    expect(describeAdminNotificationStatus('delivered')).toEqual({
      label: '成功',
      tone: 'success',
    });
    expect(describeAdminNotificationStatus('no_channels')).toEqual({
      label: '未配置',
      tone: 'muted',
    });
    expect(describeAdminNotificationStatus('provider_down')).toEqual({
      label: '服务异常',
      tone: 'danger',
    });
    expect(describeAdminNotificationStatus('provider_error')).toEqual({
      label: '通道异常',
      tone: 'danger',
    });
  });

  it('supports english labels for the admin notifications adapter', () => {
    expect(describeAdminNotificationStatus('provider_error', { language: 'en' })).toEqual({
      label: 'Channel error',
      tone: 'danger',
    });
    expect(describeAdminNotificationStatus('raw_internal_status', { language: 'en' })).toEqual({
      label: 'Unknown',
      tone: 'info',
    });
  });

  it('keeps admin log levels chinese-first with stable tones', () => {
    expect(describeAdminLogLevel('INFO')).toEqual({
      label: '信息',
      tone: 'info',
    });
    expect(describeAdminLogLevel('WARNING')).toEqual({
      label: '警告',
      tone: 'warning',
    });
    expect(describeAdminLogLevel('ERROR')).toEqual({
      label: '错误',
      tone: 'danger',
    });
    expect(describeAdminLogLevel('CRITICAL')).toEqual({
      label: '严重',
      tone: 'danger',
    });
    expect(describeAdminLogLevel('DEBUG')).toEqual({
      label: '调试',
      tone: 'muted',
    });
  });

  it('normalizes admin log level input without leaking raw unknown values', () => {
    expect(describeAdminLogLevel('warning')).toEqual({
      label: '警告',
      tone: 'warning',
    });
    expect(describeAdminLogLevel('critical_error')).toEqual({
      label: '严重',
      tone: 'danger',
    });
    expect(describeAdminLogLevel('unknown')).toEqual({
      label: '未确认',
      tone: 'info',
    });
    expect(describeAdminLogLevel(null)).toEqual({
      label: '未确认',
      tone: 'info',
    });
    expect(describeAdminLogLevel(undefined)).toEqual({
      label: '未确认',
      tone: 'info',
    });
  });

  it('keeps settings enabled-state labels local to settings surfaces', () => {
    expect(describeSettingsEnabledState('enabled')).toEqual({
      label: '已启用',
      tone: 'success',
    });
    expect(describeSettingsEnabledState('disabled')).toEqual({
      label: '未启用',
      tone: 'muted',
    });
    expect(describeSettingsEnabledState('unknown')).toEqual({
      label: '状态未知',
      tone: 'info',
    });
  });

  it('describes settings system health statuses without collapsing optional states into errors', () => {
    expect(describeSettingsSystemHealthStatus('available')).toEqual({
      label: '正常',
      tone: 'success',
    });
    expect(describeSettingsSystemHealthStatus('attention')).toEqual({
      label: '需关注',
      tone: 'warning',
    });
    expect(describeSettingsSystemHealthStatus('not_configured')).toEqual({
      label: '未配置',
      tone: 'muted',
    });
    expect(describeSettingsSystemHealthStatus('disabled')).toEqual({
      label: '未启用',
      tone: 'info',
    });
    expect(describeSettingsSystemHealthStatus('unavailable')).toEqual({
      label: '暂不可用',
      tone: 'danger',
    });
    expect(describeSettingsSystemHealthStatus('unknown')).toEqual({
      label: '状态未知',
      tone: 'muted',
    });
  });

  it('describes DuckDB diagnostic statuses with existing Chinese labels', () => {
    expect(describeSettingsDuckDBDiagnosticStatus('ok')).toEqual({
      label: '正常',
      tone: 'success',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('disabled')).toEqual({
      label: '未启用',
      tone: 'info',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('empty')).toEqual({
      label: '暂无数据',
      tone: 'muted',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('dry_run')).toEqual({
      label: '预检',
      tone: 'info',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('invalid_request')).toEqual({
      label: '请求需调整',
      tone: 'warning',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('unavailable')).toEqual({
      label: '暂不可用',
      tone: 'danger',
    });
    expect(describeSettingsDuckDBDiagnosticStatus('internal_raw_status')).toEqual({
      label: '诊断态',
      tone: 'info',
    });
  });

  it('describes DuckDB data modes without leaking raw unknown modes', () => {
    expect(describeSettingsDuckDBDataMode('real')).toEqual({
      label: '真实样本',
      tone: 'success',
    });
    expect(describeSettingsDuckDBDataMode('disabled')).toEqual({
      label: '未启用',
      tone: 'info',
    });
    expect(describeSettingsDuckDBDataMode('unavailable')).toEqual({
      label: '暂不可用',
      tone: 'danger',
    });
    expect(describeSettingsDuckDBDataMode('empty')).toEqual({
      label: '空样本',
      tone: 'muted',
    });
    expect(describeSettingsDuckDBDataMode('provider_internal_mode')).toEqual({
      label: '诊断样本',
      tone: 'info',
    });
    expect(describeSettingsDuckDBDataMode(null)).toEqual({
      label: '--',
      tone: 'muted',
    });
  });
});
