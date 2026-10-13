import assert from 'node:assert/strict';
import { test } from 'node:test';

import { DEFAULT_HEADER_CONFIG, buildHeaderTemplate, buildRenderModeTemplate } from './header-template';

test('无插槽时输出自闭合标签', () => {
  const text = buildHeaderTemplate({ leftTag: '', customAction: false, showHistoryIcon: true });
  assert.equal(text, '<AIBlueking\n  ref="aiBluekingRef"\n  :url="apiUrl"\n/>');
});

test('默认配置包含 headerLeft 与 headerActions 两个插槽', () => {
  const text = buildHeaderTemplate({ ...DEFAULT_HEADER_CONFIG });
  assert.match(text, /<template #headerLeft>\n {4}<span class="env-tag">测试环境<\/span>/);
  assert.match(text, /<template #headerActions>/);
  assert.ok(text.endsWith('</AIBlueking>'));
  assert.doesNotMatch(text, /show-history-icon/);
});

test('关闭历史图标只增加对应属性', () => {
  const text = buildHeaderTemplate({ leftTag: '', customAction: false, showHistoryIcon: false });
  assert.match(text, /:show-history-icon="false"/);
});

test('renderMode：chat 省略属性，其余输出 render-mode', () => {
  assert.doesNotMatch(buildRenderModeTemplate('chat'), /render-mode/);
  assert.match(buildRenderModeTemplate('test'), /render-mode="test"/);
  assert.match(buildRenderModeTemplate('share'), /render-mode="share"/);
});
