export type UnifiedStatus =
  | 'success'
  | 'failed'
  | 'error'
  | 'running'
  | 'pending'
  | 'partial'
  | 'skipped'
  | 'unknown'
  | 'cancelled'
  | 'warning'
  | 'info'
  | 'disabled';

export interface StatusBadgeProps {
  status: string;
  label?: string;
  size?: 'sm' | 'md';
  variant?: 'solid' | 'soft' | 'outline';
  className?: string;
}

export type StatusBadgeTone = 'success' | 'danger' | 'warning' | 'info' | 'default';

function normalizeToken(status: string): string {
  return String(status || '')
    .trim()
    .toLowerCase()
    .replace(/[\s-]+/g, '_');
}

export function normalizeStatus(status: string): UnifiedStatus {
  const normalized = normalizeToken(status);

  if ([
    'success',
    'succeeded',
    'completed',
    'validated',
    'ready',
    'ok',
    'passed',
    '成功',
    '已完成',
    '已验证',
  ].includes(normalized)) return 'success';

  if ([
    'failed',
    'fail',
    'failure',
    '失败',
  ].includes(normalized)) return 'failed';

  if ([
    'error',
    'errored',
    'failed_runtime',
    'invalid_response',
    '异常',
  ].includes(normalized)) return 'error';

  if ([
    'running',
    'attempting',
    'processing',
    'in_progress',
    'loading',
    'parsing',
    '运行中',
    '校验中',
  ].includes(normalized)) return 'running';

  if ([
    'pending',
    'queued',
    'waiting',
    'configured_pending',
    '待验证',
    '等待中',
  ].includes(normalized)) return 'pending';

  if ([
    'partial',
    'partial_success',
    'partial_failure',
    '部分失败',
    '部分成功',
  ].includes(normalized)) return 'partial';

  if ([
    'skipped',
    'not_needed',
    'not_required',
    '跳过',
    '已跳过',
  ].includes(normalized)) return 'skipped';

  if ([
    'unknown',
    'unconfirmed',
    '未确认',
  ].includes(normalized)) return 'unknown';

  if ([
    'cancelled',
    'canceled',
    'aborted',
    '已取消',
  ].includes(normalized)) return 'cancelled';

  if ([
    'warning',
    'partial_available',
    'missing_key',
    'unsupported',
    'insufficient_data',
    '部分可用',
    '警告',
  ].includes(normalized)) return 'warning';

  if ([
    'info',
    'summarizing',
    'builtin',
    '信息',
  ].includes(normalized)) return 'info';

  if ([
    'disabled',
    'not_configured',
    '已禁用',
    '未配置',
  ].includes(normalized)) return 'disabled';

  return 'unknown';
}

export function getStatusLabel(status: string): string {
  switch (normalizeStatus(status)) {
    case 'success':
      return '成功';
    case 'failed':
    case 'error':
      return '失败';
    case 'running':
      return '运行中';
    case 'pending':
      return '等待中';
    case 'partial':
      return '部分失败';
    case 'skipped':
      return '跳过';
    case 'unknown':
      return '未确认';
    case 'cancelled':
      return '已取消';
    case 'warning':
      return '警告';
    case 'info':
      return '信息';
    case 'disabled':
      return '已禁用';
  }
}

export function getStatusTone(status: string): StatusBadgeTone {
  switch (normalizeStatus(status)) {
    case 'success':
      return 'success';
    case 'failed':
    case 'error':
      return 'danger';
    case 'partial':
    case 'warning':
    case 'cancelled':
      return 'warning';
    case 'running':
    case 'pending':
    case 'info':
      return 'info';
    case 'skipped':
    case 'unknown':
    case 'disabled':
    default:
      return 'default';
  }
}
