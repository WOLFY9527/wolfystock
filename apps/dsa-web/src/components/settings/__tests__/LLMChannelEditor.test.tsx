import { fireEvent, render, screen } from '@testing-library/react';
import type { ReactElement } from 'react';
import { describe, expect, it, vi } from 'vitest';
import { systemConfigApi } from '../../../api/systemConfig';
import { UiLanguageProvider } from '../../../contexts/UiLanguageContext';
import { translate } from '../../../i18n/core';
import { LLMChannelEditor } from '../LLMChannelEditor';

vi.mock('../../../api/systemConfig', () => ({
  systemConfigApi: {
    testLLMChannel: vi.fn(),
  },
}));

describe('LLMChannelEditor', () => {
  const renderEditor = (ui: ReactElement) => render(
    <UiLanguageProvider>
      {ui}
    </UiLanguageProvider>,
  );

  it('renders API Key input with controlled visibility', async () => {
    renderEditor(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        onSaveItems={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.openai')) }));

    const input = await screen.findByLabelText(translate('zh', 'settings.llmEditor.fieldApiKey'));
    expect(input).toHaveAttribute('type', 'password');

    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'common.showContent') }));
    expect(input).toHaveAttribute('type', 'text');
  });

  it('shows clear guidance when fallback contains cross-provider model without runtime source', async () => {
    const { container } = renderEditor(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'zhipu' },
          { key: 'LLM_ZHIPU_PROTOCOL', value: 'openai' },
          { key: 'LLM_ZHIPU_BASE_URL', value: 'https://open.bigmodel.cn/api/paas/v4' },
          { key: 'LLM_ZHIPU_ENABLED', value: 'true' },
          { key: 'LLM_ZHIPU_API_KEY', value: 'zhipu-secret-key' },
          { key: 'LLM_ZHIPU_MODELS', value: 'glm-4-flash' },
          { key: 'LITELLM_MODEL', value: 'zhipu/glm-4-flash' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o-free' },
          { key: 'LLM_TEMPERATURE', value: '0.7' },
        ]}
        onSaveItems={() => {}}
      />,
    );

    const slider = container.querySelector('input[type="range"]') as HTMLInputElement;
    expect(slider).not.toBeNull();
    fireEvent.change(slider, { target: { value: '0.8' } });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'settings.llmEditor.saveRuntime') }));

    expect(await screen.findByText(translate('zh', 'settings.llmEditor.validationFallbackRuntimeOnly'))).toBeInTheDocument();
  });

  it('renders only the selected provider channels in scoped mode', async () => {
    renderEditor(
      <LLMChannelEditor
        providerScopeName="zhipu"
        items={[
          { key: 'LLM_CHANNELS', value: 'zhipu,gemini' },
          { key: 'LLM_ZHIPU_PROTOCOL', value: 'openai' },
          { key: 'LLM_ZHIPU_BASE_URL', value: 'https://open.bigmodel.cn/api/paas/v4' },
          { key: 'LLM_ZHIPU_ENABLED', value: 'true' },
          { key: 'LLM_ZHIPU_API_KEY', value: 'zhipu-secret-key' },
          { key: 'LLM_ZHIPU_MODELS', value: 'glm-4-flash' },
          { key: 'LLM_GEMINI_PROTOCOL', value: 'gemini' },
          { key: 'LLM_GEMINI_ENABLED', value: 'true' },
          { key: 'LLM_GEMINI_API_KEY', value: 'gemini-secret-key' },
          { key: 'LLM_GEMINI_MODELS', value: 'gemini-2.5-flash' },
        ]}
        onSaveItems={() => {}}
      />,
    );

    expect(screen.getByText(translate('zh', 'settings.llmEditor.scopedTitle', {
      provider: translate('zh', 'settings.llmEditor.channelPreset.zhipu'),
    }))).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.zhipu')) }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.gemini')) })).toBeNull();
    expect(screen.queryByText(translate('zh', 'settings.llmEditor.runtimeTitle'))).toBeNull();
  });

  it('clears runtime model references when a deleted channel was the only source', async () => {
    const onSaveItems = vi.fn().mockResolvedValue(undefined);
    renderEditor(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
          { key: 'LITELLM_MODEL', value: 'openai/gpt-4o-mini' },
          { key: 'AGENT_LITELLM_MODEL', value: 'openai/gpt-4o-mini' },
          { key: 'LITELLM_FALLBACK_MODELS', value: 'openai/gpt-4o-mini' },
          { key: 'VISION_MODEL', value: 'openai/gpt-4o-mini' },
          { key: 'LLM_TEMPERATURE', value: '0.7' },
        ]}
        onSaveItems={onSaveItems}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.openai')) }));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'settings.llmEditor.deleteChannelTitle') }));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'settings.llmEditor.saveRuntime') }));

    expect(onSaveItems).toHaveBeenCalledWith(
      expect.arrayContaining([
        { key: 'LLM_CHANNELS', value: '' },
        { key: 'LITELLM_MODEL', value: '' },
        { key: 'AGENT_LITELLM_MODEL', value: '' },
        { key: 'LITELLM_FALLBACK_MODELS', value: '' },
        { key: 'VISION_MODEL', value: '' },
      ]),
      translate('zh', 'settings.llmEditor.saveRuntimeSuccess'),
    );
    expect(await screen.findByText(translate('zh', 'settings.llmEditor.saveRuntimeSuccess'))).toBeInTheDocument();
  });

  it('persists extra headers and shows connectivity feedback', async () => {
    vi.mocked(systemConfigApi.testLLMChannel).mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'openai/gpt-4o-mini',
      latencyMs: 123,
    });

    renderEditor(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'openai' },
          { key: 'LLM_OPENAI_PROTOCOL', value: 'openai' },
          { key: 'LLM_OPENAI_BASE_URL', value: 'https://api.openai.com/v1' },
          { key: 'LLM_OPENAI_ENABLED', value: 'true' },
          { key: 'LLM_OPENAI_API_KEY', value: 'secret-key' },
          { key: 'LLM_OPENAI_MODELS', value: 'gpt-4o-mini' },
        ]}
        onSaveItems={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.openai')) }));
    fireEvent.change(await screen.findByLabelText(translate('zh', 'settings.llmEditor.fieldExtraHeaders')), {
      target: { value: '{"x-env":"staging"}' },
    });
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'settings.llmEditor.testAction') }));

    expect(await screen.findByText(translate('zh', 'settings.llmEditor.testSuccess', {
      model: 'openai/gpt-4o-mini',
      latency: 123,
    }))).toBeInTheDocument();
  });

  it('keeps DeepSeek v4 model selection on the success feedback path', async () => {
    vi.mocked(systemConfigApi.testLLMChannel).mockResolvedValue({
      success: true,
      message: 'ok',
      resolvedModel: 'deepseek/deepseek-v4-pro',
      latencyMs: 88,
    });

    renderEditor(
      <LLMChannelEditor
        items={[
          { key: 'LLM_CHANNELS', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_PROTOCOL', value: 'deepseek' },
          { key: 'LLM_DEEPSEEK_BASE_URL', value: 'https://api.deepseek.com/v1' },
          { key: 'LLM_DEEPSEEK_ENABLED', value: 'true' },
          { key: 'LLM_DEEPSEEK_API_KEY', value: 'secret-key' },
          { key: 'LLM_DEEPSEEK_MODELS', value: 'deepseek-v4-pro,deepseek-v4-flash' },
        ]}
        onSaveItems={() => {}}
      />,
    );

    fireEvent.click(screen.getByRole('button', { name: new RegExp(translate('zh', 'settings.llmEditor.channelPreset.deepseek')) }));
    fireEvent.click(screen.getByRole('button', { name: translate('zh', 'settings.llmEditor.testAction') }));

    expect(await screen.findByText(translate('zh', 'settings.llmEditor.testSuccess', {
      model: 'deepseek/deepseek-v4-pro',
      latency: 88,
    }))).toBeInTheDocument();
    expect(systemConfigApi.testLLMChannel).toHaveBeenCalledWith(expect.objectContaining({
      protocol: 'deepseek',
      models: ['deepseek-v4-pro', 'deepseek-v4-flash'],
    }), expect.anything());
  });
});
