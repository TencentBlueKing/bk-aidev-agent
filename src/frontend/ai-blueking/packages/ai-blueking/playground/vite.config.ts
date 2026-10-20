import vue from '@vitejs/plugin-vue';
import { resolve } from 'path';
import { defineConfig, loadEnv } from 'vite';

import { createDevApiProxy } from '../scripts/dev-api-proxy';

export default defineConfig(({ mode }) => {
  const env = loadEnv(mode, resolve(__dirname, '..'), '');
  const proxy = createDevApiProxy(env.API_PROXY_TARGET);

  return {
    plugins: [vue()],
    root: '.',
    envDir: '..',
    resolve: {
      alias: [
        // 开发模式下让 playground 直接引用源码，支持断点调试
        {
          find: /^@blueking\/ai-blueking$/,
          replacement: resolve(__dirname, '../src/vue3.ts'),
        },
        {
          find: '@blueking/chat-x',
          replacement: resolve(__dirname, '../../chat-x/src'),
        },
      ],
    },
    server: {
      host: '0.0.0.0',
      port: 8001,
      allowedHosts: true,
      ...(proxy ? { proxy } : {}),
    },
    css: {
      preprocessorOptions: {
        scss: {
          additionalData: '$bk-prefix: bk;',
        },
      },
    },
  };
});
