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
