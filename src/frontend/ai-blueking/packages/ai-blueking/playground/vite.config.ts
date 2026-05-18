import vue from '@vitejs/plugin-vue';
import { defineConfig } from 'vite';

export default defineConfig({
  plugins: [vue()],
  root: '.',
  envDir: '..',
  server: {
    host: '0.0.0.0',
    port: 8001,
    allowedHosts: true,
  },
  css: {
    preprocessorOptions: {
      scss: {
        additionalData: '$bk-prefix: bk;',
      },
    },
  },
});
