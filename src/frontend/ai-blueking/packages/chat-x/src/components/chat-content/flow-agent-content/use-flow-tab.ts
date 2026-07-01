/*
 * Tencent is pleased to support the open source community by making
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) available.
 *
 * Copyright (C) 2021 THL A29 Limited, a Tencent company.  All rights reserved.
 *
 * 蓝鲸智云PaaS平台 (BlueKing PaaS) is licensed under the MIT License.
 *
 * License for 蓝鲸智云PaaS平台 (BlueKing PaaS):
 *
 * ---------------------------------------------------
 * Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
 * documentation files (the "Software"), to deal in the Software without restriction, including without limitation
 * the rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software, and
 * to permit persons to whom the Software is furnished to do so, subject to the following conditions:
 *
 * The above copyright notice and this permission notice shall be included in all copies or substantial portions of
 * the Software.
 *
 * THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO
 * THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
 * AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF
 * CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS
 * IN THE SOFTWARE.
 */

import { type Ref, computed, onMounted, onUnmounted, shallowRef, watch } from 'vue';

import { DEFAULT_TAB_ORDER, useContainerScrollConsumer, useCustomTabConsumer } from '../../../composables';
import { t } from '../../../lang/lang';
import BkFlowNodeDetail from './flow-agent-node-detail.vue';

import type { BkFlowNode, BkFlowTask } from '../../../ag-ui/types/contents';
import type { CustomBkFlowTabData } from '../../../types';

/** task 自定义 Tab name（与选中态联动的唯一标识） */
const buildTaskTabName = (task: BkFlowTask) => (task.task_id != null ? `${task.task_id}` : '');
/**
 * 置信度（有效证据）Tab 与 task 复用同一 name：
 * is_active 默认高亮的是 task header，同时自动打开的就是该 task 的证据 Tab，
 * 二者需指向同一 name 才能联动高亮，属有意为之。
 */
const buildConfidenceTabName = buildTaskTabName;
/** node 详情 Tab name */
const buildNodeTabName = (task: BkFlowTask, node: BkFlowNode) =>
  task.task_id != null ? `${task.task_id}|${node.id}|${node.name}` : '';

/**
 * flow-agent 自定义 Tab 集成 composable。
 * 收敛与 useCustomTab 的交互：选中态计算、打开节点详情 / 有效证据、
 * 以及挂载时默认激活、卸载时清理 Tab 的生命周期。
 */
export const useFlowTab = (options: { messageUid: Ref<string | undefined>; taskList: Ref<BkFlowTask[]> }) => {
  const { messageUid, taskList } = options;
  const customTab = useCustomTabConsumer<CustomBkFlowTabData>()!;
  const provideContainerScrollData = useContainerScrollConsumer();

  const selectedTabName = computed(() => customTab.selectedTab.value?.name ?? '');
  /** 用户手动切换 Tab 后不再沿用 is_active 默认高亮 */
  const hasUserSelectedTab = shallowRef(false);
  const markUserTabSelection = () => {
    hasUserSelectedTab.value = true;
  };

  /** 用于高亮判断的 Tab name：用户未手动选择时回退到 is_active 的 task */
  const displaySelectedTabName = computed(() => {
    if (hasUserSelectedTab.value) {
      return selectedTabName.value;
    }
    const activeTask = taskList.value.find(task => task.is_active);
    if (activeTask?.task_id != null) {
      return buildTaskTabName(activeTask);
    }
    return selectedTabName.value;
  });

  const isTaskSelected = (task: BkFlowTask) => {
    const name = displaySelectedTabName.value;
    return name === buildTaskTabName(task) || name === buildConfidenceTabName(task);
  };
  const isNodeSelected = (task: BkFlowTask, node: BkFlowNode) =>
    displaySelectedTabName.value === buildNodeTabName(task, node);

  const openNodeDetail = (task: BkFlowTask, node: BkFlowNode) => {
    const taskId = task.task_id;
    if (taskId == null) return;
    markUserTabSelection();
    customTab.addCustomTab?.({
      // 是否可关闭由后端下发的 closable 控制，缺省（undefined）保持默认可关闭
      closable: node.closable,
      label: node.name,
      name: buildNodeTabName(task, node),
      // 排序优先采用后端下发的 tab_order（越小越靠前），缺省回退默认权重
      order: node.tab_order ?? DEFAULT_TAB_ORDER,
      data: {
        component: BkFlowNodeDetail,
        messageUid: messageUid.value,
        props: {
          data: {},
          loading: true,
          node_id: node.id,
          node_name: node.name,
          task_id: taskId,
          task_name: task.task_name,
        },
      },
    });
  };

  const openConfidence = (task?: BkFlowTask) => {
    const taskId = task?.task_id;
    if (!taskId) return;
    markUserTabSelection();
    customTab.addCustomTab?.({
      // 是否可关闭由后端下发的 closable 控制，缺省（undefined）保持默认可关闭
      closable: task.closable,
      label: t('有效证据'),
      name: buildConfidenceTabName(task),
      // 排序优先采用后端下发的 tab_order（越小越靠前）；
      // 缺省回退 10，固定排在「执行情况」(order 0) 之后、节点详情(默认 100)之前
      order: task.tab_order ?? 10,
      data: {
        component: BkFlowNodeDetail,
        messageUid: messageUid.value,
        props: {
          data: {},
          has_confidence: task.has_confidence,
          loading: true,
          task_id: taskId,
          task_name: task.task_name,
        },
      },
    });
  };

  watch(selectedTabName, (_name, oldName) => {
    if (oldName === undefined) return;
    markUserTabSelection();
  });

  onMounted(() => {
    if (!provideContainerScrollData?.value) {
      return;
    }
    openConfidence(taskList.value.find(task => task.is_active && task.has_confidence));
  });

  onUnmounted(() => {
    // 仅在 message-container 中（存在滚动上下文）被销毁时移除 Tab；
    // 若是在执行情况面板内的销毁则不移除。
    if (!provideContainerScrollData?.value) {
      return;
    }
    for (const task of taskList.value) {
      customTab.removeCustomTab?.(buildTaskTabName(task));
      customTab.removeCustomTab?.(buildConfidenceTabName(task));
      for (const node of Object.values(task.nodes ?? {})) {
        customTab.removeCustomTab?.(buildNodeTabName(task, node));
      }
    }
  });

  return {
    displaySelectedTabName,
    isNodeSelected,
    isTaskSelected,
    markUserTabSelection,
    openConfidence,
    openNodeDetail,
  };
};
