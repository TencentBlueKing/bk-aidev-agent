import { defineComponent, h, shallowRef } from 'vue';

import { flushPromises, mount } from '@vue/test-utils';
import { afterEach, describe, expect, it, vi } from 'vitest';

import { useArtifactPreviewLoader } from './use-artifact-preview-loader';

import type { AIFileInfo, ArtifactUrlResult } from '../../../../../ag-ui/types/file';

const createFile = (type: string, name = `a.${type}`): AIFileInfo => ({
  name,
  outputId: '1',
  size: 1,
  type,
});

const createDeferred = <T,>() => {
  let resolve: ((value: T) => void) | undefined;
  const promise = new Promise<T>((resolvePromise) => {
    resolve = resolvePromise;
  });
  if (!resolve) {
    throw new Error('延迟 Promise 未初始化');
  }
  return { promise, resolve };
};

describe('use-artifact-preview-loader', () => {
  afterEach(() => {
    vi.unstubAllGlobals();
    vi.restoreAllMocks();
  });

  const mountLoader = (opts: {
    canResolve?: boolean;
    file: AIFileInfo | undefined;
    resolveUrls: (file: AIFileInfo) => Promise<ArtifactUrlResult>;
  }) => {
    let api: ReturnType<typeof useArtifactPreviewLoader> | undefined;
    const fileRef = shallowRef(opts.file);
    const Comp = defineComponent({
      setup() {
        api = useArtifactPreviewLoader({
          canResolve: () => opts.canResolve !== false,
          getFile: () => fileRef.value,
          resolveUrls: opts.resolveUrls,
        });
        return () => h('div');
      },
    });
    const wrapper = mount(Comp);
    if (!api) {
      throw new Error('加载器未初始化');
    }
    return {
      api,
      setFile: (file: AIFileInfo | undefined) => {
        fileRef.value = file;
      },
      wrapper,
    };
  };

  it('无取链能力时应为 empty', async () => {
    const { api, wrapper } = mountLoader({
      canResolve: false,
      file: createFile('pdf'),
      resolveUrls: vi.fn(),
    });

    await api.load();

    expect(api.status.value).toBe('empty');
    wrapper.unmount();
  });

  it('pdf 应使用 preview_url 且不 fetch', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const { api, wrapper } = mountLoader({
      file: createFile('pdf'),
      resolveUrls: vi.fn().mockResolvedValue({ preview_url: 'https://example.com/a.pdf' }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.previewUrl.value).toBe('https://example.com/a.pdf');
    expect(api.renderer.value).toBe('urlIframe');
    expect(fetchSpy).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('图片应使用 download_url 且不 fetch', async () => {
    const fetchSpy = vi.fn();
    vi.stubGlobal('fetch', fetchSpy);
    const { api, wrapper } = mountLoader({
      file: createFile('png', 'shot.png'),
      resolveUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/shot.png' }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.downloadUrl.value).toBe('https://example.com/shot.png');
    expect(api.renderer.value).toBe('image');
    expect(fetchSpy).not.toHaveBeenCalled();
    wrapper.unmount();
  });

  it('图片缺 download_url 时应为 empty', async () => {
    const { api, wrapper } = mountLoader({
      file: createFile('png', 'shot.png'),
      resolveUrls: vi.fn().mockResolvedValue({ preview_url: 'https://example.com/shot.png' }),
    });

    await api.load();

    expect(api.status.value).toBe('empty');
    wrapper.unmount();
  });

  it('txt 应 fetch download_url 得到 content', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('hello txt') }),
    );
    const { api, wrapper } = mountLoader({
      file: createFile('txt'),
      resolveUrls: vi.fn().mockResolvedValue({
        download_url: 'https://example.com/a.txt',
        preview_url: 'https://example.com/a.pdf',
      }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.content.value).toBe('hello txt');
    expect(api.renderer.value).toBe('txt');
    expect(api.previewUrl.value).toBe('');
    wrapper.unmount();
  });

  it('markdown 应使用下载内容及 markdown 渲染器', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('# 标题') }),
    );
    const { api, wrapper } = mountLoader({
      file: createFile('markdown'),
      resolveUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/a.md' }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.content.value).toBe('# 标题');
    expect(api.renderer.value).toBe('markdown');
    wrapper.unmount();
  });

  it('type 为 Md 时应按 markdown 直渲染', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('# md alias') }),
    );
    const { api, wrapper } = mountLoader({
      file: createFile('md', '说明.md'),
      resolveUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/a.md' }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.content.value).toBe('# md alias');
    expect(api.renderer.value).toBe('markdown');
    wrapper.unmount();
  });

  it('加载失败时应为 error', async () => {
    const { api, wrapper } = mountLoader({
      file: createFile('pdf'),
      resolveUrls: vi.fn().mockRejectedValue(new Error('resolve failed')),
    });

    await api.load();

    expect(api.status.value).toBe('error');
    wrapper.unmount();
  });

  it('缺 preview_url 时应为 empty', async () => {
    const { api, wrapper } = mountLoader({
      file: createFile('pdf'),
      resolveUrls: vi.fn().mockResolvedValue({}),
    });

    await api.load();

    expect(api.status.value).toBe('empty');
    wrapper.unmount();
  });

  it('缺 download_url 的文本类文件时应为 empty', async () => {
    const { api, wrapper } = mountLoader({
      file: createFile('txt'),
      resolveUrls: vi.fn().mockResolvedValue({ preview_url: 'https://example.com/a.pdf' }),
    });

    await api.load();

    expect(api.status.value).toBe('empty');
    wrapper.unmount();
  });

  it('json 应按 code 高亮渲染', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('{"ok":true}') }),
    );
    const { api, wrapper } = mountLoader({
      file: createFile('json', 'a.json'),
      resolveUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/a.json' }),
    });

    await api.load();

    expect(api.status.value).toBe('ready');
    expect(api.content.value).toBe('{"ok":true}');
    expect(api.renderer.value).toBe('code');
    wrapper.unmount();
  });

  it('load() 默认只向 resolveUrls 传 file', async () => {
    const file = createFile('pdf');
    const resolveUrls = vi.fn().mockResolvedValue({ preview_url: 'https://example.com/a.pdf' });
    const { api, wrapper } = mountLoader({ file, resolveUrls });

    await api.load();

    expect(resolveUrls).toHaveBeenCalledTimes(1);
    expect(resolveUrls).toHaveBeenCalledWith(file);
    expect(resolveUrls.mock.calls[0]).toHaveLength(1);
    wrapper.unmount();
  });

  it('dispose 后 abort 不应置为 error', async () => {
    const fetchMock = vi.fn(
      (_url: string, options: { signal: AbortSignal }) => new Promise((_resolve, reject) => {
        options.signal.addEventListener('abort', () => reject(new DOMException('Aborted', 'AbortError')));
      }),
    );
    vi.stubGlobal('fetch', fetchMock);
    const { api, wrapper } = mountLoader({
      file: createFile('txt'),
      resolveUrls: vi.fn().mockResolvedValue({ download_url: 'https://example.com/a.txt' }),
    });

    const loading = api.load();
    await flushPromises();
    api.dispose();
    await loading;

    expect(fetchMock).toHaveBeenCalledOnce();
    expect(api.status.value).not.toBe('error');
    wrapper.unmount();
  });

  it('切换文件后过期结果不应覆盖最新内容', async () => {
    const first = createDeferred<ArtifactUrlResult>();
    const resolveUrls = vi.fn()
      .mockReturnValueOnce(first.promise)
      .mockResolvedValueOnce({ download_url: 'https://example.com/b.txt' });
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({ ok: true, text: () => Promise.resolve('new content') }),
    );
    const { api, setFile, wrapper } = mountLoader({
      file: createFile('txt', 'a.txt'),
      resolveUrls,
    });

    const firstLoad = api.load();
    setFile(createFile('txt', 'b.txt'));
    await api.load();
    first.resolve({ download_url: 'https://example.com/a.txt' });
    await firstLoad;

    expect(api.content.value).toBe('new content');
    expect(api.status.value).toBe('ready');
    wrapper.unmount();
  });

  it('清空文件后过期结果不应覆盖 empty 状态', async () => {
    const first = createDeferred<ArtifactUrlResult>();
    const { api, setFile, wrapper } = mountLoader({
      file: createFile('pdf'),
      resolveUrls: vi.fn().mockReturnValue(first.promise),
    });

    const firstLoad = api.load();
    setFile(undefined);
    await api.load();
    first.resolve({ preview_url: 'https://example.com/a.pdf' });
    await firstLoad;

    expect(api.status.value).toBe('empty');
    expect(api.previewUrl.value).toBe('');
    wrapper.unmount();
  });
});
