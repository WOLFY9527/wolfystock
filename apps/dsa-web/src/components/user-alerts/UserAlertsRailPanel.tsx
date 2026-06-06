import { useEffect, useState, type FormEvent } from 'react';
import { Checkbox } from '../common/Checkbox';
import { Input } from '../common/Input';
import { Select } from '../common/Select';
import {
  CompactEmptyRow,
  DenseSecondaryDisclosure,
} from '../terminal/DenseWorkbenchPrimitives';
import {
  TerminalButton,
  TerminalChip,
  TerminalNotice,
} from '../terminal/TerminalPrimitives';
import { userAlertsApi } from '../../api/userAlerts';
import type {
  UserAlertDirection,
  UserAlertRule,
  UserAlertRuleCreateRequest,
  UserAlertRuleUpdateRequest,
} from '../../types/userAlerts';

type UserAlertsRailPanelProps = {
  symbol: string;
  language?: 'zh' | 'en';
};

type FormState = {
  direction: UserAlertDirection;
  thresholdPrice: string;
  enabled: boolean;
  note: string;
};

const INITIAL_FORM: FormState = {
  direction: 'above',
  thresholdPrice: '',
  enabled: true,
  note: '',
};

const THRESHOLD_FORMATTERS = {
  integer: {
    zh: new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
    en: new Intl.NumberFormat('en-US', { minimumFractionDigits: 0, maximumFractionDigits: 2 }),
  },
  decimal: {
    zh: new Intl.NumberFormat('zh-CN', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    en: new Intl.NumberFormat('en-US', { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
  },
} as const;

const RULE_DATE_FORMATTERS = {
  zh: new Intl.DateTimeFormat('zh-CN', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
  en: new Intl.DateTimeFormat('en-US', {
    month: '2-digit',
    day: '2-digit',
    hour: '2-digit',
    minute: '2-digit',
  }),
} as const;

const zhCopy = {
  title: '站内提醒',
  summary: '仅当前标的 · 默认收起',
  helper: '仅当前账户可见，仅观察，不构成投资建议，不会下单或触发交易动作，也不会发送邮件/短信/浏览器推送/Webhook/管理员通知通道。不承诺实时盯盘或固定触发时点。',
  loading: '正在读取当前标的提醒…',
  loadError: '暂时无法读取当前标的的站内提醒，请稍后重试。',
  empty: '当前标的还没有价格阈值提醒规则。',
  create: '新建提醒',
  edit: '编辑',
  createTitle: '新增价格阈值提醒',
  editTitle: '编辑价格阈值提醒',
  cancel: '取消',
  save: '保存提醒',
  saving: '保存中…',
  direction: '方向',
  thresholdPrice: '阈值价格',
  enabled: '启用提醒',
  note: '备注（可选）',
  noteHint: '只记录当前账户的观察备注，不外发。',
  above: '高于',
  below: '低于',
  statusOn: '已启用',
  statusOff: '已停用',
  updatedAt: '更新时间',
  submitError: '保存失败，请稍后重试。',
  invalidThreshold: '阈值价格必须大于 0。',
};

const enCopy: typeof zhCopy = {
  title: 'In-app alerts',
  summary: 'Current symbol only · collapsed',
  helper: 'Visible only to the current account, observation only, not investment advice, will not place orders or trigger trading actions, and will not send email/SMS/browser push/Webhook/admin notification channels. No live polling or guaranteed trigger timing is implied.',
  loading: 'Loading current-symbol alerts…',
  loadError: 'Unable to load in-app alerts for the current symbol right now.',
  empty: 'No price-threshold alert rules exist for the current symbol yet.',
  create: 'New alert',
  edit: 'Edit',
  createTitle: 'Add price-threshold alert',
  editTitle: 'Edit price-threshold alert',
  cancel: 'Cancel',
  save: 'Save alert',
  saving: 'Saving…',
  direction: 'Direction',
  thresholdPrice: 'Threshold price',
  enabled: 'Enabled',
  note: 'Note (optional)',
  noteHint: 'Stored only for the current account and never delivered externally.',
  above: 'Above',
  below: 'Below',
  statusOn: 'Enabled',
  statusOff: 'Disabled',
  updatedAt: 'Updated',
  submitError: 'Unable to save the alert right now.',
  invalidThreshold: 'Threshold price must be greater than 0.',
};

function formatRuleThreshold(direction: UserAlertDirection, thresholdPrice: number, language: 'zh' | 'en'): string {
  const formatter = THRESHOLD_FORMATTERS[thresholdPrice % 1 === 0 ? 'integer' : 'decimal'][language];
  const prefix = direction === 'above'
    ? (language === 'en' ? 'Above' : '高于')
    : (language === 'en' ? 'Below' : '低于');
  return `${prefix} ${formatter.format(thresholdPrice)}`;
}

function formatRuleDate(value?: string | null, language: 'zh' | 'en' = 'zh'): string {
  if (!value) return '--';
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return RULE_DATE_FORMATTERS[language].format(parsed);
}

function normalizeRules(symbol: string, items: UserAlertRule[]): UserAlertRule[] {
  return items.filter((rule) => rule.ruleType === 'watchlist_price_threshold' && rule.symbol === symbol);
}

export default function UserAlertsRailPanel({
  symbol,
  language = 'zh',
}: UserAlertsRailPanelProps) {
  const copy = language === 'en' ? enCopy : zhCopy;
  const [rules, setRules] = useState<UserAlertRule[]>([]);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const [thresholdError, setThresholdError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [formOpen, setFormOpen] = useState(false);
  const [editingRuleId, setEditingRuleId] = useState<number | null>(null);
  const [form, setForm] = useState<FormState>(INITIAL_FORM);

  useEffect(() => {
    let cancelled = false;

    setLoading(true);
    setLoadError(null);
    setSubmitError(null);
    setThresholdError(null);
    setFormOpen(false);
    setEditingRuleId(null);
    setForm(INITIAL_FORM);

    void userAlertsApi.listRules()
      .then((response) => {
        if (cancelled) return;
        setRules(normalizeRules(symbol, response.items));
      })
      .catch(() => {
        if (cancelled) return;
        setLoadError(copy.loadError);
        setRules([]);
      })
      .finally(() => {
        if (cancelled) return;
        setLoading(false);
      });

    return () => {
      cancelled = true;
    };
  }, [copy.loadError, symbol]);

  function openCreateForm() {
    setEditingRuleId(null);
    setForm(INITIAL_FORM);
    setThresholdError(null);
    setSubmitError(null);
    setFormOpen(true);
  }

  function openEditForm(rule: UserAlertRule) {
    setEditingRuleId(rule.id);
    setForm({
      direction: rule.direction,
      thresholdPrice: String(rule.thresholdPrice),
      enabled: rule.enabled,
      note: rule.note ?? '',
    });
    setThresholdError(null);
    setSubmitError(null);
    setFormOpen(true);
  }

  function closeForm() {
    setFormOpen(false);
    setEditingRuleId(null);
    setThresholdError(null);
    setSubmitError(null);
    setForm(INITIAL_FORM);
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    const parsedThreshold = Number(form.thresholdPrice.trim());
    if (!Number.isFinite(parsedThreshold) || parsedThreshold <= 0) {
      setThresholdError(copy.invalidThreshold);
      return;
    }

    setSaving(true);
    setThresholdError(null);
    setSubmitError(null);

    const trimmedNote = form.note.trim();

    try {
      if (editingRuleId == null) {
        const payload: UserAlertRuleCreateRequest = {
          symbol,
          direction: form.direction,
          thresholdPrice: parsedThreshold,
          enabled: form.enabled,
          note: trimmedNote ? trimmedNote : null,
        };
        const created = await userAlertsApi.createRule(payload);
        setRules((current) => [created, ...current.filter((rule) => rule.id !== created.id)]);
      } else {
        const payload: UserAlertRuleUpdateRequest = {
          direction: form.direction,
          thresholdPrice: parsedThreshold,
          enabled: form.enabled,
          note: trimmedNote ? trimmedNote : null,
        };
        const updated = await userAlertsApi.updateRule(editingRuleId, payload);
        setRules((current) => current.map((rule) => (rule.id === updated.id ? updated : rule)));
      }

      closeForm();
    } catch {
      setSubmitError(copy.submitError);
    } finally {
      setSaving(false);
    }
  }

  return (
    <DenseSecondaryDisclosure
      data-testid="user-alerts-rail-panel"
      variant="row"
      title={copy.title}
      summary={copy.summary}
      className="pt-4"
    >
      <div className="space-y-3 text-xs leading-5 text-white/68">
        <TerminalNotice variant="info">
          {copy.helper}
        </TerminalNotice>

        {loading ? <p>{copy.loading}</p> : null}
        {!loading && loadError ? <TerminalNotice variant="caution">{loadError}</TerminalNotice> : null}

        {!loading && !loadError ? (
          <>
            {rules.length > 0 ? (
              <div className="space-y-2">
                {rules.map((rule) => (
                  <div
                    key={rule.id}
                    data-testid={`user-alert-rule-${rule.id}`}
                    className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3"
                  >
                    <div className="flex min-w-0 items-start justify-between gap-3">
                      <div className="min-w-0">
                        <p className="text-sm text-white/82">
                          {formatRuleThreshold(rule.direction, rule.thresholdPrice, language)}
                        </p>
                        <div className="mt-2 flex min-w-0 flex-wrap gap-1.5">
                          <TerminalChip variant={rule.enabled ? 'info' : 'neutral'}>
                            {rule.enabled ? copy.statusOn : copy.statusOff}
                          </TerminalChip>
                        </div>
                      </div>
                      <TerminalButton
                        type="button"
                        variant="compact"
                        className="shrink-0"
                        onClick={() => openEditForm(rule)}
                      >
                        {copy.edit}
                      </TerminalButton>
                    </div>
                    {rule.note ? (
                      <p className="mt-2 whitespace-pre-wrap break-words text-white/65">{rule.note}</p>
                    ) : null}
                    <p className="mt-2 text-[11px] text-white/42">
                      {copy.updatedAt} {formatRuleDate(rule.updatedAt || rule.createdAt, language)}
                    </p>
                  </div>
                ))}
              </div>
            ) : (
              <CompactEmptyRow className="rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3">
                {copy.empty}
              </CompactEmptyRow>
            )}

            <div className="flex min-w-0 flex-wrap items-center gap-2">
              <TerminalButton
                type="button"
                variant="secondary"
                onClick={openCreateForm}
              >
                {copy.create}
              </TerminalButton>
            </div>

            {formOpen ? (
              <form
                data-testid="user-alert-form"
                className="space-y-3 rounded-lg border border-[color:var(--wolfy-border-subtle)] bg-[var(--wolfy-surface-input)] px-3 py-3"
                onSubmit={(event) => void handleSubmit(event)}
              >
                <div className="flex min-w-0 items-center justify-between gap-3">
                  <p className="text-sm font-medium text-white/82">
                    {editingRuleId == null ? copy.createTitle : copy.editTitle}
                  </p>
                </div>
                <div className="grid min-w-0 gap-3 sm:grid-cols-2">
                  <Select
                    label={copy.direction}
                    value={form.direction}
                    onChange={(value) => {
                      setForm((current) => ({ ...current, direction: value as UserAlertDirection }));
                    }}
                    options={[
                      { value: 'above', label: copy.above },
                      { value: 'below', label: copy.below },
                    ]}
                  />
                  <Input
                    label={copy.thresholdPrice}
                    inputMode="decimal"
                    value={form.thresholdPrice}
                    error={thresholdError ?? undefined}
                    onChange={(event) => {
                      setForm((current) => ({ ...current, thresholdPrice: event.target.value }));
                      if (thresholdError) {
                        setThresholdError(null);
                      }
                    }}
                  />
                </div>
                <Checkbox
                  label={copy.enabled}
                  checked={form.enabled}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, enabled: event.target.checked }));
                  }}
                />
                <Input
                  label={copy.note}
                  value={form.note}
                  hint={copy.noteHint}
                  onChange={(event) => {
                    setForm((current) => ({ ...current, note: event.target.value }));
                  }}
                />
                {submitError ? <TerminalNotice variant="caution">{submitError}</TerminalNotice> : null}
                <div className="flex min-w-0 flex-wrap items-center gap-2">
                  <TerminalButton type="submit" variant="secondary" disabled={saving}>
                    {saving ? copy.saving : copy.save}
                  </TerminalButton>
                  <TerminalButton type="button" variant="compact" onClick={closeForm} disabled={saving}>
                    {copy.cancel}
                  </TerminalButton>
                </div>
              </form>
            ) : null}
          </>
        ) : null}
      </div>
    </DenseSecondaryDisclosure>
  );
}
