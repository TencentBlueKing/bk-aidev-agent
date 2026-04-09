import bkuiLint from '@blueking/bkui-lint/eslint.mjs';
export default [
  ...bkuiLint,
  {
    files: ['packages/chat-x/src/**/*.{spec,test}.{ts,vue}'],
    rules: {
      'vue/one-component-per-file': 'off',
      'vue/multi-word-component-names': 'off',
    },
  },
  {
    ignores: ['**/dist/**'],
  },
];
