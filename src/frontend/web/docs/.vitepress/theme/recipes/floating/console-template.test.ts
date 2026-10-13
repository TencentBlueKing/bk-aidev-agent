import assert from 'node:assert/strict';
import { test } from 'node:test';

import { DEFAULT_CONSOLE_CONFIG, buildFloatingTemplate, diffLines, toFloatingConfig } from './console-template';

test('默认配置只输出 ref 与 url', () => {
  assert.equal(buildFloatingTemplate({ ...DEFAULT_CONSOLE_CONFIG }), '<AIBlueking\n  ref="aiBluekingRef"\n  :url="apiUrl"\n/>');
});

test('每个开关只增加对应的一行', () => {
  const base = buildFloatingTemplate({ ...DEFAULT_CONSOLE_CONFIG }).split('\n').length;
  const cases: [Partial<typeof DEFAULT_CONSOLE_CONFIG>, string][] = [
    [{ draggable: false }, '  :draggable="false"'],
    [{ showNimbus: false }, '  hide-nimbus'],
    [{ nimbusSize: 'large' }, '  nimbus-size="large"'],
    [{ defaultWidth: 520 }, '  :default-width="520"'],
    [{ enablePopup: true }, '  :enable-popup="true"'],
  ];
  for (const [patch, line] of cases) {
    const lines = buildFloatingTemplate({ ...DEFAULT_CONSOLE_CONFIG, ...patch }).split('\n');
    assert.equal(lines.length, base + 1, JSON.stringify(patch));
    assert.ok(lines.includes(line), line);
  }
});

test('前端快捷指令追加 shortcuts 属性与定义', () => {
  const text = buildFloatingTemplate({ ...DEFAULT_CONSOLE_CONFIG, frontendShortcuts: true });
  assert.match(text, /:shortcuts="shortcuts"/);
  assert.match(text, /const shortcuts = \[/);
});

test('toFloatingConfig：默认复用 default 实例，其他配置 key 稳定', () => {
  assert.deepEqual(toFloatingConfig({ ...DEFAULT_CONSOLE_CONFIG }), { props: {}, key: 'default' });
  const a = toFloatingConfig({ ...DEFAULT_CONSOLE_CONFIG, showNimbus: false });
  const b = toFloatingConfig({ ...DEFAULT_CONSOLE_CONFIG, showNimbus: false });
  assert.equal(a.key, b.key);
  assert.equal(a.props.hideNimbus, true);
  assert.equal('shortcuts' in a.props, false);
});

test('diffLines：返回新增或修改的行', () => {
  assert.deepEqual(diffLines('a\nb\nc', 'a\nx\nc\nd'), [1, 3]);
  assert.deepEqual(diffLines('a', 'a'), []);
});
