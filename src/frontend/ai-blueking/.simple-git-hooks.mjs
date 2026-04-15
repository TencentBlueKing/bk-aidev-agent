// biome-ignore assist/source/organizeImports: <explanation>
import simpleGitHooksConfig from '@blueking/bkui-lint/.simple-git-hooks.mjs';
import { execSync } from 'node:child_process';
import { join, relative } from 'node:path';

const gitRoot = execSync('git rev-parse --show-toplevel', { encoding: 'utf-8' }).trim();
const testScript = relative(gitRoot, join(import.meta.dirname, 'scripts/pre-commit-test.mjs'));
const commitMsgScript = relative(
  gitRoot,
  join(import.meta.dirname, 'node_modules/@blueking/bkui-lint/verify-commit.mjs'),
);
const basePreCommit = simpleGitHooksConfig['pre-commit'];

export default {
  'commit-msg': `node ${commitMsgScript} $1`,
  'pre-commit': basePreCommit ? `${basePreCommit} && node ${testScript}` : `node ${testScript}`,
};
