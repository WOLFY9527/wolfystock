import { describe, expect, it } from 'vitest';
import {
  describeAdminLogLevel,
  describeAdminNotificationStatus,
  describeBooleanEnabled,
  describeDisplayStatus,
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
});
