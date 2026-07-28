/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */
import { computed, defineComponent, h, ref } from 'vue';

import { type VueWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../../../../ag-ui/types/file';
import { ARTIFACT_PREVIEW_TOKEN, buildArtifactId } from '../../../../composables/use-artifact-preview';
import FileArtifactPanel from './file-artifact-panel.vue';

import type { SessionArtifact } from '../../../../composables/use-artifact-preview';

vi.mock('tippy.js/dist/tippy.css', () => ({}));

vi.mock('vue-tippy', () => ({
  directive: { mounted: vi.fn(), unmounted: vi.fn() },
}));

vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    emits: ['click'],
    setup:
      (_, { emit, slots }) =>
      () =>
        h('button', { class: 'mock-btn', onClick: () => emit('click') }, slots.default?.()),
  }),
  Input: defineComponent({
    props: { modelValue: { default: '', type: String } },
    emits: ['update:modelValue'],
    setup:
      (props, { emit }) =>
      () =>
        h('input', {
          class: 'mock-input',
          value: props.modelValue,
          onInput: (e: Event) => emit('update:modelValue', (e.target as HTMLInputElement).value),
        }),
  }),
  Loading: defineComponent({
    setup: () => () => h('span', { class: 'mock-loading' }),
  }),
}));

vi.mock('../../../message-loading/message-loading.vue', () => ({
  default: defineComponent({
    name: 'MessageLoading',
    setup: () => () => h('div', { class: 'mock-message-loading' }),
  }),
}));

const createArtifact = (overrides: Partial<SessionArtifact> = {}): SessionArtifact => {
  const messageUid = overrides.messageUid ?? 'm1';
  const outputId = overrides.outputId ?? 'o1';
  return {
    artifactId: buildArtifactId(messageUid, 0, outputId),
    messageUid,
    name: '项目立项书.pdf',
    outputId,
    size: 1024,
    type: AIFileType.Pdf,
    ...overrides,
  };
};

const createPreviewContext = (overrides: Record<string, unknown> = {}) => ({
  activeArtifactId: ref(''),
  canResolveArtifactUrl: computed(() => true),
  openPreview: vi.fn(),
  resolveArtifactUrls: vi.fn().mockResolvedValue({
    download_url: 'https://example.com/download.pdf',
    preview_url: 'https://example.com/preview.pdf',
  }),
  setActiveArtifactId: vi.fn(),
  ...overrides,
});

const mountPanel = (props: { activeId: string; artifacts: SessionArtifact[] }, previewCtx?: unknown) =>
  mount(FileArtifactPanel, {
    global: previewCtx ? { provide: { [ARTIFACT_PREVIEW_TOKEN]: previewCtx } } : {},
    props,
  });

describe('FileArtifactPanel', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
  });

  it('应该渲染文件列表与数量', () => {
    const artifacts = [
      createArtifact({ outputId: 'a', name: '文档.pdf' }),
      createArtifact({ outputId: 'b', name: '统计.xlsx' }),
    ];
    wrapper = mountPanel({ activeId: '', artifacts });

    expect(wrapper.findAll('.ai-artifact-file-card.is-list').length).toBe(2);
    expect(wrapper.find('.ai-file-artifact-panel-list-title').text()).toContain('2');
  });

  it('命中文件的列表项应带 is-active 态', () => {
    const artifacts = [createArtifact({ outputId: 'a' }), createArtifact({ outputId: 'b' })];
    wrapper = mountPanel({ activeId: artifacts[1].artifactId, artifacts });

    const items = wrapper.findAll('.ai-artifact-file-card.is-list');
    expect(items[0].classes()).not.toContain('is-active');
    expect(items[1].classes()).toContain('is-active');
  });

  it('点击其它文件项应 emit select', async () => {
    const artifacts = [createArtifact({ outputId: 'a' }), createArtifact({ outputId: 'b' })];
    wrapper = mountPanel({ activeId: artifacts[0].artifactId, artifacts });

    await wrapper.findAll('.ai-artifact-file-card.is-list')[1].trigger('click');

    expect(wrapper.emitted('select')?.[0]).toEqual([artifacts[1].artifactId]);
  });

  it('搜索应过滤文件列表', async () => {
    const artifacts = [
      createArtifact({ outputId: 'a', name: '运维文档.pdf' }),
      createArtifact({ outputId: 'b', name: '统计.xlsx' }),
    ];
    wrapper = mountPanel({ activeId: '', artifacts });

    await wrapper.find('.mock-input').setValue('统计');

    const items = wrapper.findAll('.ai-artifact-file-card.is-list');
    expect(items.length).toBe(1);
    expect(items[0].text()).toContain('统计');
  });

  it('未传 onArtifactClick 时预览区应展示无数据', async () => {
    const artifact = createArtifact();
    wrapper = mountPanel({ activeId: artifact.artifactId, artifacts: [artifact] });
    await flushPromises();

    expect(wrapper.find('.ai-artifact-preview-host-empty').exists()).toBe(true);
    expect(wrapper.find('.ai-artifact-url-iframe-preview').exists()).toBe(false);
  });

  it('pdf 文件应异步取链后用 iframe src 展示 preview_url', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/download.pdf',
      preview_url: 'https://example.com/x.pdf',
    });
    const artifact = createArtifact({ type: AIFileType.Pdf });
    wrapper = mountPanel(
      { activeId: artifact.artifactId, artifacts: [artifact] },
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    const iframe = wrapper.find('.ai-artifact-url-iframe-preview');
    expect(iframe.attributes('src')).toBe('https://example.com/x.pdf');
    expect(fetchSpy).not.toHaveBeenCalled();
    expect(resolveArtifactUrls).toHaveBeenCalledTimes(1);
    vi.unstubAllGlobals();
  });

  it('html 文件应使用 download_url 拉取并用 iframe srcdoc 渲染', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('<h1>hi</h1>') });
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/page.html',
      preview_url: 'https://example.com/preview.pdf',
    });
    const artifact = createArtifact({
      name: 'page.html',
      type: AIFileType.Html,
    });
    wrapper = mountPanel(
      { activeId: artifact.artifactId, artifacts: [artifact] },
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    expect(fetchSpy).toHaveBeenCalledWith('https://example.com/page.html', expect.any(Object));
    const iframe = wrapper.find('.ai-artifact-html-preview');
    expect(iframe.attributes('srcdoc')).toBe('<h1>hi</h1>');
    vi.unstubAllGlobals();
  });

  it('html 拉取失败应展示错误态', async () => {
    const fetchSpy = vi.fn().mockRejectedValue(new Error('EOF'));
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/page.html',
    });
    const artifact = createArtifact({ name: 'page.html', type: AIFileType.Html });
    wrapper = mountPanel(
      { activeId: artifact.artifactId, artifacts: [artifact] },
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    expect(wrapper.find('.ai-artifact-preview-host-error').exists()).toBe(true);
    vi.unstubAllGlobals();
  });

  it('异步取链过程中应展示 MessageLoading', async () => {
    let resolveUrls: (value: { preview_url: string }) => void = () => {};
    const resolveArtifactUrls = vi.fn(
      () =>
        new Promise<{ preview_url: string }>(resolve => {
          resolveUrls = resolve;
        }),
    );
    const artifact = createArtifact();
    wrapper = mountPanel(
      { activeId: artifact.artifactId, artifacts: [artifact] },
      createPreviewContext({ resolveArtifactUrls }),
    );

    expect(wrapper.find('.mock-message-loading').exists()).toBe(true);

    resolveUrls({ preview_url: 'https://example.com/x.pdf' });
    await flushPromises();

    expect(wrapper.find('.mock-message-loading').exists()).toBe(false);
    expect(wrapper.find('.ai-artifact-url-iframe-preview').exists()).toBe(true);
  });

  it('无命中文件时应展示空态', () => {
    wrapper = mountPanel({ activeId: 'not-exist', artifacts: [createArtifact()] });

    expect(wrapper.find('.ai-artifact-preview-host-empty').exists()).toBe(true);
  });
});
