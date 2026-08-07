import { computed, defineComponent, h, ref } from 'vue';

import { type VueWrapper, flushPromises, mount } from '@vue/test-utils';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { AIFileType } from '../../../../../ag-ui/types/file';
import { ARTIFACT_PREVIEW_TOKEN } from '../../../../../composables/use-artifact-preview';
import ArtifactPreviewHost from './artifact-preview-host.vue';

import type { AIFileInfo } from '../../../../../ag-ui/types/file';

vi.mock('bkui-vue', () => ({
  Button: defineComponent({
    emits: ['click'],
    setup: (_, { emit, slots }) => () =>
      h('button', { class: 'mock-btn', onClick: () => emit('click') }, slots.default?.()),
  }),
}));

vi.mock('../../../../message-loading/message-loading.vue', () => ({
  default: defineComponent({
    name: 'MessageLoading',
    setup: () => () => h('div', { class: 'mock-message-loading' }),
  }),
}));

vi.mock('../../../../chat-content/markdown-content/markdown-content.vue', () => ({
  default: defineComponent({
    name: 'MarkdownContent',
    props: { content: { required: true, type: String } },
    setup: props => () => h('div', { class: 'mock-markdown-content' }, props.content),
  }),
}));

const createFile = (overrides: Partial<AIFileInfo> = {}): AIFileInfo => ({
  name: '项目立项书.pdf',
  outputId: 'output-1',
  size: 1024,
  type: AIFileType.Pdf,
  ...overrides,
});

const createPreviewContext = (overrides: Record<string, unknown> = {}) => ({
  activeArtifactId: ref(''),
  canResolveArtifactUrl: computed(() => true),
  openPreview: vi.fn(),
  resolveArtifactUrls: vi.fn().mockResolvedValue({
    download_url: 'https://example.com/download',
    preview_url: 'https://example.com/preview.pdf',
  }),
  setActiveArtifactId: vi.fn(),
  ...overrides,
});

const mountHost = (file?: AIFileInfo, previewCtx?: unknown) =>
  mount(ArtifactPreviewHost, {
    global: previewCtx ? { provide: { [ARTIFACT_PREVIEW_TOKEN]: previewCtx } } : {},
    props: { file },
  });

describe('ArtifactPreviewHost', () => {
  let wrapper: VueWrapper;

  beforeEach(() => {
    vi.clearAllMocks();
  });

  afterEach(() => {
    wrapper?.unmount();
    vi.unstubAllGlobals();
  });

  it('未传文件时应展示空态', async () => {
    wrapper = mountHost();
    await flushPromises();

    expect(wrapper.find('.ai-artifact-preview-host-empty').exists()).toBe(true);
  });

  it('pdf 文件应使用 iframe src 展示预览地址', async () => {
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      preview_url: 'https://example.com/file.pdf',
    });
    const file = createFile();
    wrapper = mountHost(file, createPreviewContext({ resolveArtifactUrls }));
    await flushPromises();

    // 常规加载只传 file，不传第二参（避免 (file, undefined)）
    expect(resolveArtifactUrls).toHaveBeenCalledTimes(1);
    expect(resolveArtifactUrls).toHaveBeenCalledWith(file);
    expect(wrapper.find('.ai-artifact-url-iframe-preview').attributes('src')).toBe('https://example.com/file.pdf');
  });

  it('无取链能力时应展示空态', async () => {
    wrapper = mountHost(
      createFile(),
      createPreviewContext({ canResolveArtifactUrl: computed(() => false) }),
    );
    await flushPromises();

    expect(wrapper.find('.ai-artifact-preview-host-empty').exists()).toBe(true);
  });

  it('切换不同 outputId 的文件时应重新加载预览', async () => {
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      preview_url: 'https://example.com/file.pdf',
    });
    const firstFile = createFile({ outputId: 'output-1' });
    const secondFile = createFile({ outputId: 'output-2' });
    wrapper = mountHost(firstFile, createPreviewContext({ resolveArtifactUrls }));
    await flushPromises();

    await wrapper.setProps({ file: secondFile });
    await flushPromises();

    expect(resolveArtifactUrls).toHaveBeenCalledTimes(2);
    expect(resolveArtifactUrls).toHaveBeenNthCalledWith(1, firstFile);
    expect(resolveArtifactUrls).toHaveBeenLastCalledWith(secondFile);
  });

  it('切换相同 outputId 且类型不变时不应重新加载预览', async () => {
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      preview_url: 'https://example.com/file.pdf',
    });
    const firstFile = createFile({ name: 'a.pdf', outputId: 'same' });
    const secondFile = createFile({ name: 'b.pdf', outputId: 'same' });
    wrapper = mountHost(firstFile, createPreviewContext({ resolveArtifactUrls }));
    await flushPromises();

    await wrapper.setProps({ file: secondFile });
    await flushPromises();

    expect(resolveArtifactUrls).toHaveBeenCalledTimes(1);
  });

  it('相同 outputId 但 type 变更时应重新加载预览', async () => {
    const resolveArtifactUrls = vi.fn()
      .mockResolvedValueOnce({ preview_url: 'https://example.com/a.pdf' })
      .mockResolvedValueOnce({ download_url: 'https://example.com/a.txt' });
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('txt') }));
    const firstFile = createFile({ name: 'a.pdf', outputId: 'same', type: AIFileType.Pdf });
    const secondFile = createFile({ name: 'a.txt', outputId: 'same', type: AIFileType.Txt });
    wrapper = mountHost(firstFile, createPreviewContext({ resolveArtifactUrls }));
    await flushPromises();

    await wrapper.setProps({ file: secondFile });
    await flushPromises();

    expect(resolveArtifactUrls).toHaveBeenCalledTimes(2);
    expect(resolveArtifactUrls).toHaveBeenNthCalledWith(1, firstFile);
    expect(resolveArtifactUrls).toHaveBeenLastCalledWith(secondFile);
    expect(wrapper.find('.ai-artifact-txt-preview').text()).toBe('txt');
  });

  it('html 文件应使用 iframe srcdoc 展示下载内容', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('<h1>预览</h1>') });
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/file.html',
    });
    wrapper = mountHost(
      createFile({ name: 'file.html', type: AIFileType.Html }),
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    expect(fetchSpy).toHaveBeenCalledWith('https://example.com/file.html', expect.any(Object));
    expect(wrapper.find('.ai-artifact-html-preview').attributes('srcdoc')).toBe('<h1>预览</h1>');
  });

  it('txt 文件应获取下载内容并渲染文本', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('文本预览内容') });
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/file.txt',
    });
    wrapper = mountHost(
      createFile({ name: 'file.txt', type: AIFileType.Txt }),
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    expect(fetchSpy).toHaveBeenCalledWith('https://example.com/file.txt', expect.any(Object));
    expect(wrapper.find('.ai-artifact-txt-preview').text()).toBe('文本预览内容');
  });

  it('json 文件应按 txt 直渲染下载内容', async () => {
    const fetchSpy = vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('{"a":1}') });
    vi.stubGlobal('fetch', fetchSpy);
    const resolveArtifactUrls = vi.fn().mockResolvedValue({
      download_url: 'https://example.com/file.json',
    });
    wrapper = mountHost(
      createFile({ name: 'file.json', type: AIFileType.Json }),
      createPreviewContext({ resolveArtifactUrls }),
    );
    await flushPromises();

    expect(fetchSpy).toHaveBeenCalledWith('https://example.com/file.json', expect.any(Object));
    expect(wrapper.find('.ai-artifact-txt-preview').text()).toBe('{"a":1}');
  });

  it('markdown 文件应将下载内容传给 MarkdownContent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('# 标题') }));
    wrapper = mountHost(
      createFile({ name: 'file.md', type: AIFileType.Markdown }),
      createPreviewContext({ resolveArtifactUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/file.md' }) }),
    );
    await flushPromises();

    expect(wrapper.find('.mock-markdown-content').text()).toBe('# 标题');
  });

  it('type 为 Md 时应将下载内容传给 MarkdownContent', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('# Md 别名') }));
    wrapper = mountHost(
      createFile({ name: '说明.md', type: AIFileType.Md }),
      createPreviewContext({ resolveArtifactUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/file.md' }) }),
    );
    await flushPromises();

    expect(wrapper.find('.mock-markdown-content').text()).toBe('# Md 别名');
  });

  it('加载失败时应展示错误态，点击重试后再次加载', async () => {
    const resolveArtifactUrls = vi.fn()
      .mockRejectedValueOnce(new Error('请求失败'))
      .mockResolvedValueOnce({ preview_url: 'https://example.com/retry.pdf' });
    wrapper = mountHost(createFile(), createPreviewContext({ resolveArtifactUrls }));
    await flushPromises();

    expect(wrapper.find('.ai-artifact-preview-host-error').exists()).toBe(true);

    await wrapper.find('.mock-btn').trigger('click');
    await flushPromises();

    expect(resolveArtifactUrls).toHaveBeenCalledTimes(2);
    expect(resolveArtifactUrls).toHaveBeenLastCalledWith(expect.objectContaining({ outputId: 'output-1' }));
    expect(wrapper.find('.ai-artifact-url-iframe-preview').attributes('src')).toBe('https://example.com/retry.pdf');
  });
});
