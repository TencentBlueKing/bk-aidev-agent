import vue2 from '@vitejs/plugin-vue2';
import { resolve } from 'path';
import { defineConfig } from 'vite';

const localNodeModules = resolve(__dirname, 'node_modules');

export default defineConfig({
  plugins: [vue2()],
  server: {
    host: '0.0.0.0',
    port: 8002,
    allowedHosts: true,
    fs: {
      // 限制仅扫描 vue2-playground 目录，避免扫描到 monorepo 其他空包（如 mcp）导致 tsconfig 找不到
      allow: [resolve(__dirname)],
    },
  },
  resolve: {
    alias: {
      vue: resolve(localNodeModules, 'vue/dist/vue.esm.js'),
      '@blueking/bkui-library': resolve(localNodeModules, '@blueking/bkui-library'),
    },
  },
  optimizeDeps: {
    exclude: ['vue'],
  },
});
