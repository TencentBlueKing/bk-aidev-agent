import assert from 'node:assert/strict';
import { test } from 'node:test';

import { DEMO_ENTRIES, OVERVIEW_LINK, buildDemosSidebar, listGalleryEntries, type DemoEntry, type DemoGroup } from './demos-catalog';

const entry = (over: Partial<DemoEntry>): DemoEntry => ({
  id: 'x',
  title: 'X',
  link: '/demos/x',
  group: 'business',
  summary: '',
  modes: [],
  recipes: 1,
  mockReady: true,
  status: 'available',
  ...over,
});

const groups: DemoGroup[] = [
  { id: 'start', title: '示例' },
  { id: 'integration', title: '集成形态' },
  { id: 'business', title: '业务联动' },
  { id: 'ui', title: '界面与渲染' },
];

test('侧栏过滤 planned、保持顺序、省略空分组', () => {
  const sidebar = buildDemosSidebar(
    [
      entry({ id: 'b2', title: 'B2', group: 'business', link: '/b2' }),
      entry({ id: 'i1', title: 'I1', group: 'integration', link: '/i1' }),
      entry({ id: 'b1', title: 'B1', group: 'business', link: '/b1' }),
      entry({ id: 'u1', title: 'U1', group: 'ui', link: '/u1', status: 'planned' }),
    ],
    groups,
  );
  assert.deepEqual(
    sidebar.map(g => g.text),
    ['集成形态', '业务联动'],
  );
  assert.deepEqual(
    sidebar[1].items.map(i => i.text),
    ['B2', 'B1'],
  );
});

test('总览卡片不含总览自身与 planned', () => {
  const list = listGalleryEntries([
    entry({ id: 'overview', link: OVERVIEW_LINK, group: 'start' }),
    entry({ id: 'a' }),
    entry({ id: 'p', status: 'planned' }),
  ]);
  assert.deepEqual(
    list.map(e => e.id),
    ['a'],
  );
});

test('实际目录：id 与 link 唯一，集成形态条目都带 pick', () => {
  assert.equal(new Set(DEMO_ENTRIES.map(e => e.id)).size, DEMO_ENTRIES.length);
  assert.equal(new Set(DEMO_ENTRIES.map(e => e.link)).size, DEMO_ENTRIES.length);
  for (const e of DEMO_ENTRIES.filter(x => x.group === 'integration')) {
    assert.ok(e.pick, `${e.id} 缺少 pick`);
  }
  assert.equal(buildDemosSidebar()[0].items[0].link, OVERVIEW_LINK);
});
