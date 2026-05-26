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
    shortDesc: 'getSideRenderComponent，内置 getFlowAgentTaskNodeInfo',
    longDesc:
      '覆盖侧栏内容与 Tab 标签，节点详情仍由 ChatBot 在切换 Tab 时自动请求 flow_agent/{taskId}/task_node_info/{nodeId}/，无需实现 onCustomTabChange。',
    demoMode: 'default-api',
    props: [
      { name: 'getSideRenderComponent', note: '必填 · 侧栏内容 VNode' },
      { name: 'getSideTabRenderComponent', note: '可选 · Tab 标签' },
      { name: 'onCustomTabChange', note: '不传 · 走内置拉取' },
    ],
    trySteps: [
      '发送一条会触发 FlowAgent 的对话，等待 flow_agent_result',
      '展开右侧「执行情况」，点击某节点「详情」',
      '侧栏标题区应显示绿色「内置 getFlowAgentTaskNodeInfo」徽标',
    ],
  },
  {
    id: 'custom-fetch',
    badge: '场景 2',
    title: '自定义 UI · 自定义详情接口',
    shortDesc: '再加 onCustomTabChange，完全接管拉取',
    longDesc:
      '传入 onCustomTabChange 后，ChatBot 不再调用内置 getFlowAgentTaskNodeInfo；你在回调里自行 fetch / SDK 请求，返回值合并进 tab.data.props.data。本演示为便于联调，仍请求同一路径，但经业务回调发起，并在页面上标注请求 URL。',
    demoMode: 'custom-fetch',
    props: [
      { name: 'getSideRenderComponent', note: '必填 · 侧栏内容 VNode' },
      { name: 'getSideTabRenderComponent', note: '可选 · Tab 标签' },
      { name: 'onCustomTabChange', note: '必填 · 自定义详情拉取' },
    ],
    trySteps: [
      '切换到本场景后发送对话并打开节点「详情」',
      '查看上方「自定义拉取观测」中的最近请求 URL',
      '侧栏内应显示橙色「onCustomTabChange」徽标与 props.data 预览',
    ],
  },
];

export function getSideRenderScenarioById(id: SideRenderScenarioId): SideRenderScenarioItem {
  return SIDE_RENDER_SCENARIOS.find(s => s.id === id) ?? SIDE_RENDER_SCENARIOS[0];
}
