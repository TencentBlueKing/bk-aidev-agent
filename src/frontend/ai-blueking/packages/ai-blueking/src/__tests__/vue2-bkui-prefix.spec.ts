import { describe, expect, it, vi } from 'vitest';

vi.mock('vue', () => ({
  createApp: vi.fn((rootComponent: unknown) => ({
    mount: vi.fn(),
    unmount: vi.fn(),
    __rootComponent: rootComponent,
  })),
  h: vi.fn((type: unknown, props?: unknown, children?: unknown) => ({
    type,
    props,
    children,
  })),
}));

const configProviderStub = { name: 'ConfigProvider' };

vi.mock('bkui-vue', () => ({
  ConfigProvider: configProviderStub,
}));

describe('Vue2 BKUI prefix isolation', () => {
  it('injects ai-bk into both SCSS and Less preprocessors for Vue2 builds', async () => {
    const { createBuildConfig, VueVersion } = await import('../../scripts/vite.utils');

    const config = createBuildConfig(VueVersion.Vue2, ['es'], true);

    expect(config.css?.preprocessorOptions?.scss?.additionalData).toContain('$bk-prefix: ai-bk;');
    expect(config.css?.preprocessorOptions?.less?.modifyVars).toMatchObject({
      'bk-prefix': 'ai-bk',
    });
  });

  it('keeps bk as the default prefix for Vue3 IIFE builds', async () => {
    const { createBuildConfig, VueVersion } = await import('../../scripts/vite.utils');

    const config = createBuildConfig(VueVersion.Vue3, ['iife'], true);

    expect(config.css?.preprocessorOptions?.scss?.additionalData).toContain('$bk-prefix: bk;');
    expect(config.css?.preprocessorOptions?.less?.modifyVars).toMatchObject({
      'bk-prefix': 'bk',
    });
    expect(config.define).toMatchObject({
      BKUI_PREFIX: '"bk"',
    });
  });

  it('compiles chat-x from source for Vue2 IIFE builds', async () => {
    const { createBuildConfig, VueVersion } = await import('../../scripts/vite.utils');

    const config = createBuildConfig(VueVersion.Vue2, ['iife'], true);
    const alias = config.resolve?.alias as Array<{ find: string; replacement: string }>;

    expect(alias).toEqual(
      expect.arrayContaining([
        expect.objectContaining({
          find: '@blueking/chat-x',
        }),
      ]),
    );
  });

  it('wraps Vue2 embedded Vue3 content with BKUI ConfigProvider using the build prefix', async () => {
    const { createApp } = await import('vue');
    const { createVue2Wrapper } = await import('../vue2-wrapper');

    vi.stubGlobal('BKUI_PREFIX', 'ai-bk');

    const wrapper = createVue2Wrapper({ name: 'InnerComponent' }, {
      name: 'WrappedComponent',
      props: {},
      emitNames: [],
      exposeKeys: [],
    }) as {
      created: (this: Record<string, unknown>) => void;
    };

    const context = {
      $attrs: {},
      $emit: vi.fn(),
      $scopedSlots: {},
      $watch: vi.fn(),
      unWatchStack: [],
    };

    wrapper.created.call(context);

    const rootComponent = vi.mocked(createApp).mock.calls[0]?.[0] as {
      setup: () => () => { props?: { prefix?: string }; type?: unknown };
    };
    const vnode = rootComponent.setup()();

    expect(vnode.type).toBe(configProviderStub);
    expect(vnode.props?.prefix).toBe('ai-bk');

    vi.unstubAllGlobals();
  });
});
