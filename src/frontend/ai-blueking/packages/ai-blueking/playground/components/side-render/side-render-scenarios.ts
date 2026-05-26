export type SideRenderScenarioId = 'default-api' | 'custom-fetch';

export type FlowSideRenderDemoMode = 'default-api' | 'custom-fetch';

export interface SideRenderScenarioItem {
  id: SideRenderScenarioId;
  badge: string;
  title: string;
  shortDesc: string;
  longDesc: string;
  demoMode: FlowSideRenderDemoMode;
  props: Array<{ name: string; note: string }>;
  trySteps: string[];
}

export const SIDE_RENDER_SCENARIOS: SideRenderScenarioItem[] = [
  {
    id: 'default-api',
    badge: '场景 1',
    title: '自定义 UI · 默认详情接口',
    shortDesc: '只传 getSideRenderComponent',
    longDesc: '只自定义侧栏怎么渲染。节点详情仍由 ChatBot 内置接口拉取，不需要写 onCustomTabChange。',
    demoMode: 'default-api',
    props: [
      { name: 'getSideRenderComponent', note: '必填 · 侧栏内容 VNode' },
      { name: 'getSideTabRenderComponent', note: '可选 · Tab 标签' },
      { name: 'onCustomTabChange', note: '不传 · 走内置拉取' },
    ],
    trySteps: [
      '发送会触发 FlowAgent 的对话',
      '展开「执行情况」，点击节点「详情」',
      '侧栏展示内置接口返回的节点详情',
    ],
  },
  {
    id: 'custom-fetch',
    badge: '场景 2',
    title: '自定义 UI · 自定义详情接口',
    shortDesc: '再传 onCustomTabChange',
    longDesc:
      '在 onCustomTabChange 里自己拉取详情并 return。返回值会进入 props.data，侧栏组件直接读取即可。',
    demoMode: 'custom-fetch',
    props: [
      { name: 'getSideRenderComponent', note: '必填 · 侧栏内容 VNode' },
      { name: 'getSideTabRenderComponent', note: '可选 · Tab 标签' },
      { name: 'onCustomTabChange', note: '必填 · 自定义详情拉取' },
    ],
    trySteps: [
      '切换到本场景后发送对话',
      '点击节点「详情」，查看上方请求 URL',
      '侧栏展示 onCustomTabChange 返回的数据',
    ],
  },
];

export function getSideRenderScenarioById(id: SideRenderScenarioId): SideRenderScenarioItem {
  return SIDE_RENDER_SCENARIOS.find(s => s.id === id) ?? SIDE_RENDER_SCENARIOS[0];
}
