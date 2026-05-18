import { h } from 'vue';

import CustomTabContent from './CustomTabContent.vue';

import type { GetSideRenderComponent, GetSideTabRenderComponent } from '@blueking/ai-blueking';

/** FlowAgent 节点 Tab：{task_id}|{node_id}|{node_name} */
function isFlowNodeTab(tab: { name: string }): boolean {
  return tab.name.includes('|');
}

/**
 * 侧栏自定义渲染（对齐 chat-x/playground/chat-bot-new.vue）。
 * 不传 onCustomTabChange，节点详情走 ChatBot 内置 getFlowAgentTaskNodeInfo。
 */
export function useSideRenderHandlers() {
  const getSideRenderComponent: GetSideRenderComponent = (createElement, props) => {
    const raw = props ?? {};
    const taskIdRaw = raw.task_id;
    const taskId =
      typeof taskIdRaw === 'number'
        ? taskIdRaw
        : typeof taskIdRaw === 'string' && taskIdRaw !== ''
          ? Number(taskIdRaw)
          : undefined;

    return createElement(CustomTabContent, {
      loading: Boolean(raw.loading),
      nodeId: typeof raw.node_id === 'string' ? raw.node_id : '',
      nodeName: typeof raw.node_name === 'string' ? raw.node_name : '',
      taskId: Number.isFinite(taskId as number) ? (taskId as number) : undefined,
      taskName: typeof raw.task_name === 'string' ? raw.task_name : '',
      data:
        typeof raw.data === 'object' && raw.data !== null && !Array.isArray(raw.data)
          ? (raw.data as Record<string, unknown>)
          : {},
    });
  };

  const getSideTabRenderComponent: GetSideTabRenderComponent = (createElement, tab, { removeCustomTab }) => {
    if (!isFlowNodeTab(tab)) {
      return undefined;
    }

    const [, , nodeName = ''] = tab.name.split('|');

    return createElement(
      'span',
      {
        style: {
          display: 'inline-flex',
          gap: '6px',
          alignItems: 'center',
          maxWidth: '180px',
        },
      },
      [
        createElement(
          'span',
          {
            style: {
              flexShrink: '0',
              padding: '0 4px',
              fontSize: '10px',
              color: '#3a84ff',
              background: '#e1ecff',
              borderRadius: '2px',
            },
          },
          '节点',
        ),
        createElement(
          'span',
          {
            style: {
              overflow: 'hidden',
              textOverflow: 'ellipsis',
              whiteSpace: 'nowrap',
            },
            title: nodeName || tab.label,
          },
          nodeName || tab.label,
        ),
        createElement(
          'button',
          {
            type: 'button',
            style: {
              flexShrink: '0',
              marginLeft: '2px',
              padding: '0 4px',
              fontSize: '14px',
              lineHeight: 1,
              color: '#979ba5',
              cursor: 'pointer',
              background: 'transparent',
              border: 'none',
            },
            onClick: (e: Event) => {
              e.stopPropagation();
              removeCustomTab(tab.name);
            },
          },
          '×',
        ),
      ],
    );
  };

  return {
    getSideRenderComponent,
    getSideTabRenderComponent,
  };
}
