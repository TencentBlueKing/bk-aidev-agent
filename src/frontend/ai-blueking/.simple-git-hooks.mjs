import simpleGitHooksConfig from '@blueking/bkui-lint/.simple-git-hooks.mjs';

export default {
  ...simpleGitHooksConfig,
  // 在原有的 lint-staged 之后，添加测试检查
  'pre-commit': `${simpleGitHooksConfig['pre-commit']} && node ./scripts/pre-commit-test.mjs`,
};
