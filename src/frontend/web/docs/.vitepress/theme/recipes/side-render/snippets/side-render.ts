import type { GetSideRenderComponent, GetSideTabRenderComponent, OnCustomTabChange } from '@blueking/ai-blueking';

import NodeDetailCard from '../NodeDetailCard.vue';

type NodeDetailCardProps = InstanceType<typeof NodeDetailCard>['$props'];

// ① Tab 内容：只接管节点详情 Tab（带 node_id），「执行情况」等其余 Tab 返回 undefined 走默认渲染
export const getSideRenderComponent: GetSideRenderComponent = (h, props = {}) =>
  props.node_id
    ? h(NodeDetailCard, {
        loading: Boolean(props.loading),
        nodeName: String(props.node_name ?? ''),
        data: props.data as NodeDetailCardProps['data'],
      })
    : undefined;

// ② Tab 标签：节点 Tab 的 name 为 `${task_id}|${node_id}|${node_name}`，关闭时调用 removeCustomTab
export const getSideTabRenderComponent: GetSideTabRenderComponent = (h, tab, { removeCustomTab }) => {
  if (!tab.name.includes('|')) return undefined;
  const nodeName = tab.name.split('|')[2] || tab.label;
  return h('span', { class: 'node-tab' }, [
    h('i', { class: 'node-tab__dot' }),
    h('span', nodeName),
    h(
      'button',
      {
        class: 'node-tab__close',
        type: 'button',
        title: '关闭',
        onClick: (e: Event) => {
          e.stopPropagation();
          removeCustomTab(tab.name);
        },
      },
      '×',
    ),
  ]);
};

// ③ 自行拉取节点详情：返回值写入 tab 的 props.data，可在这里补充业务字段
export function createTabChangeHandler(apiUrl: string, headers: () => Record<string, string>): OnCustomTabChange {
  return async tab => {
    const { task_id: taskId, node_id: nodeId } = tab.data?.props ?? {};
    if (taskId == null || !nodeId) return undefined;
    const res = await fetch(`${apiUrl}flow_agent/${taskId}/task_node_info/${nodeId}/`, { headers: headers() });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const { data } = (await res.json()) as { data: Record<string, unknown> };
    return { ...data, owner: '运维值班 · 张三', runbook: 'https://example.com/runbook/disk-cleanup' };
  };
}

// 用法：<ChatBot :url="flowAgentUrl" :get-side-render-component="getSideRenderComponent"
//   :get-side-tab-render-component="getSideTabRenderComponent" :on-custom-tab-change="onCustomTabChange" />
