<template>
  <ActivityLayout
    v-model:collapsed="collapsed"
    :activity-type="MessageContentType.FlowAgent"
    class="flow-agent-activity"
  >
    <template #title>
      <span
        class="ai-activity-message-title-icon"
        :class="{
          'icon-collapsed': collapsed,
        }"
      >
        <AiLoading
          v-if="isLoading"
          :size="12"
        />
        <ArrowRightIcon v-else />
      </span>
      <span class="ai-activity-message-title-text">
        <span class="flow-agent-title-label">{{ t('执行情况') }}: </span>
        <span
          v-for="stat in visibleStats"
          :key="stat.key"
          class="flow-agent-stat-item"
        >
          {{ stat.label }}：<span
            class="flow-agent-stat-count"
            :style="{ color: stat.color }"
            >{{ stat.display }}</span
          >
        </span>
      </span>
    </template>
    <div
      v-for="task in taskList"
      :key="task.task_id"
      class="flow-agent-task-group"
    >
      <div
        class="flow-agent-task-header"
        @click.stop="toggleTaskExpanded(task)"
      >
        <span
          class="flow-agent-task-arrow"
          :class="{ 'is-expanded': isTaskExpanded(task) }"
        >
          <ArrowRightIcon />
        </span>
        <span class="flow-agent-task-state-icon">
          <Loading
            v-if="getTaskConvergedState(task) === 'running'"
            mode="spin"
            size="mini"
            theme="primary"
          />
          <component
            :is="getTaskStateIcon(task)"
            v-else
          />
        </span>
        <span
          v-overflow-tips="{ ...commonTippyOptions }"
          class="flow-agent-task-name"
        >
          <HighlightKeyword :text="task.task_name" />
        </span>
        <span class="flow-agent-task-time">{{ getTaskTotalTime(task) }}</span>
      </div>
      <div
        v-show="isTaskExpanded(task)"
        class="flow-agent-task-nodes"
      >
        <div
          v-for="node in getNodeList(task)"
          :key="node.id"
          class="flow-agent-node-item"
        >
          <span
            class="flow-agent-node-status"
            :class="`is-${getConvergedState(node.state)}`"
          >
            <Loading
              v-if="getConvergedState(node.state) === 'running'"
              mode="spin"
              size="mini"
              theme="primary"
            />
            <span
              v-else
              class="flow-agent-status-dot"
            />
          </span>
          <span
            v-overflow-tips="{ ...commonTippyOptions }"
            class="flow-agent-node-name"
            :title="node.name"
          >
            <HighlightKeyword :text="node.name" />
          </span>
          <span
            v-if="renderMode !== RenderMode.Share"
            class="flow-agent-node-trailing"
          >
            <span class="flow-agent-node-time">{{ formatElapsedTime(node.elapsed_time) }}</span>
            <span
              class="flow-agent-node-detail-btn"
              @click.stop="handleNodeDetail(task, node)"
            >
              <NodeOutputIcon />
              {{ t('详情') }}
            </span>
          </span>
        </div>
      </div>
    </div>
  </ActivityLayout>
  <!-- <div
    v-if="taskList.some(task => task.task_outputs)"
    class="flow-agent-task-outputs"
  >
    {{ taskList.map(task => task.task_outputs).filter(Boolean) }}
  </div> -->
</template>
<script setup lang="ts">
  import { type ComputedRef, cloneVNode, computed, onUnmounted, shallowRef } from 'vue';

  import { Loading } from 'bkui-vue';

  import { MessageContentType, MessageStatus } from '../../../ag-ui/types/constants';
  import { RenderMode } from '../../../common/constants';
  import { useContainerScrollConsumer } from '../../../composables';
  import { useCommonTippyInject, useRenderModeInject } from '../../../composables/use-common';
  import { useCustomTabConsumer } from '../../../composables/use-custom-tab';
  import { OverflowTips as vOverflowTips } from '../../../directives/overflow-tips';
  import {
    ArrowRightIcon,
    BkFlowFailedIcon,
    BkFlowPendingIcon,
    BkFlowSuccessIcon,
    BkFlowSuspendedIcon,
    NodeOutputIcon,
  } from '../../../icons';
  import { t } from '../../../lang/lang';
  import AiLoading from '../../ai-loading/ai-loading.vue';
  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';
  import ActivityLayout from '../activity-layout/activity-layout.vue';
  import BkFlowNodeDetail from './flow-agent-node-detail.vue';

  import type { MessageStatus as MessageStatusType } from '../../../ag-ui/types/constants';
  import type { BkFlowMessageContent, BkFlowNode, BkFlowTask } from '../../../ag-ui/types/contents';
  import type { CustomBkFlowTabData } from '../../../types';

  type ConvergedState = 'failed' | 'pending' | 'running' | 'success' | 'suspended';

  const commonTippyOptions = useCommonTippyInject();

  const RUNNING_STATES = new Set([
    'CREATED',
    'LOOP_READY',
    'READY',
    'RUNNING',
    'BLOCKED',
    'ROLLING_BACK',
    'ROLL_BACK_SUCCESS',
  ]);
  const FAILED_STATES = new Set(['FAILED', 'REVOKED', 'ROLL_BACK_FAILED']);

  const STATE_CONFIG: { color: string; key: ConvergedState; label: string }[] = [
    { color: '#3A84FF', key: 'running', label: t('执行中') },
    { color: '#18B456', key: 'success', label: t('成功') },
    { color: '#EA3636', key: 'failed', label: t('失败') },
    { color: '#F59500', key: 'suspended', label: t('挂起') },
    { color: '#4D4F56', key: 'pending', label: t('待执行') },
  ];

  const STATE_ICON_MAP: Record<string, typeof BkFlowSuccessIcon> = {
    success: BkFlowSuccessIcon,
    failed: BkFlowFailedIcon,
    suspended: BkFlowSuspendedIcon,
    pending: BkFlowPendingIcon,
  };

  const props = defineProps<{
    content?: BkFlowMessageContent;
    messageUid?: string;
    status?: MessageStatusType;
  }>();

  const { addCustomTab, removeCustomTab } = useCustomTabConsumer<CustomBkFlowTabData>()!;
  const provideContainerScrollData = useContainerScrollConsumer();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });

  const renderMode = useRenderModeInject();

  const isLoading = computed(() => {
    return props.status === MessageStatus.Pending || props.status === MessageStatus.Streaming;
  });

  const taskList = computed(() =>
    Array.isArray(props.content) ? props.content : [props.content ?? {}],
  ) as ComputedRef<BkFlowTask[]>;
  const taskExpandedMap = shallowRef<Record<number, boolean>>({});

  const isTaskExpanded = (task: BkFlowTask) => taskExpandedMap.value[task.task_id] !== false;

  const toggleTaskExpanded = (task: BkFlowTask) => {
    taskExpandedMap.value = {
      ...taskExpandedMap.value,
      [task.task_id]: !isTaskExpanded(task),
    };
  };

  const getTaskConvergedState = (task: BkFlowTask) => getConvergedState(task.task_state ?? '');

  const getTaskStateIcon = (task: BkFlowTask) => {
    const icon = STATE_ICON_MAP[getTaskConvergedState(task)];
    return icon ? cloneVNode(icon) : cloneVNode(BkFlowSuspendedIcon);
  };

  const getTaskTotalTime = (task: BkFlowTask) => {
    const nodes = getNodeList(task);
    const total = nodes.reduce((sum, node) => sum + node.elapsed_time, 0);
    return formatElapsedTime(total);
  };

  const getNodeList = (task: BkFlowTask) => Object.values(task.nodes ?? {});

  const getConvergedState = (state: string): ConvergedState => {
    if (state === 'FINISHED') return 'success';
    if (FAILED_STATES.has(state)) return 'failed';
    if (state === 'SUSPENDED') return 'suspended';
    if (state === 'PENDING') return 'pending';
    if (RUNNING_STATES.has(state)) return 'running';
    return 'running';
  };

  const visibleStats = computed(() => {
    const aggregated: Record<ConvergedState, number> = {
      failed: 0,
      pending: 0,
      running: 0,
      success: 0,
      suspended: 0,
    };

    for (const task of taskList.value) {
      for (const [state, count] of Object.entries(task.statistics?.state_counts ?? {})) {
        aggregated[getConvergedState(state)] += count;
      }
    }

    return STATE_CONFIG.filter(s => aggregated[s.key] > 0).map(s => ({
      ...s,
      display: aggregated[s.key] > 99 ? '99+' : String(aggregated[s.key]),
    }));
  });

  const formatElapsedTime = (seconds: number): string => {
    if (seconds < 1) return '<1s';

    const d = Math.floor(seconds / 86400);
    const h = Math.floor((seconds % 86400) / 3600);
    const m = Math.floor((seconds % 3600) / 60);
    const s = seconds % 60;

    const parts: string[] = [];
    if (d > 0) parts.push(`${d}d`);
    if (h > 0) parts.push(`${h}h`);
    if (m > 0) parts.push(`${m}m`);
    if (s > 0) parts.push(`${s}s`);

    return parts.join('');
  };

  const handleNodeDetail = (task: BkFlowTask, node: BkFlowNode) => {
    const taskId = task.task_id;
    if (taskId != null) {
      addCustomTab?.({
        label: node.name,
        name: `${taskId}|${node.id}|${node.name}`,
        data: {
          component: BkFlowNodeDetail,
          messageUid: props.messageUid,
          props: {
            loading: true,
            node_id: node.id,
            node_name: node.name,
            task_id: taskId,
            task_name: task.task_name,
            data: {},
          },
        },
      });
    }
  };
  onUnmounted(() => {
    // 这里用于判断是否是在 message-container 中被销毁的.
    // 如果是执行情况下的销毁，则不进行移除
    if (!provideContainerScrollData?.value) {
      return;
    }
    for (const task of taskList.value) {
      for (const node of getNodeList(task)) {
        removeCustomTab?.(`${task.task_id}|${node.id}|${node.name}`);
      }
    }
  });
</script>
<style lang="scss">
  .flow-agent-activity {
    $color-text: #4d4f56;
    $color-text-secondary: #979ba5;
    $color-primary: #3a84ff;
    $color-primary-light: #699df4;
    $color-success: #18b456;
    $color-danger: #ea3636;
    $color-warning: #f59500;
    $color-hover-bg: #eaebf0;
    $color-pending: #dcdee5;
    $status-colors: (
      success: $color-success,
      failed: $color-danger,
      suspended: $color-warning,
      running: $color-primary,
      pending: $color-pending,
    );

    font-size: 12px;

    %flex-center {
      display: flex;
      align-items: center;
      justify-content: center;
    }

    %text-truncate {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;
    }

    .ai-activity-message-title {
      width: 100%;
      height: 40px;
      background: #fafbfd;
      border: 1px solid #dcdee5;

      &-icon {
        font-size: 14px;
        font-weight: bold;
        color: #4d4f56;
        transform: rotate(90deg);

        &.icon-collapsed {
          transform: rotate(0deg);
        }
      }
    }

    .ai-activity-message-content {
      padding: 8px 0;
      font-size: 12px;
    }

    .flow-agent-title-label {
      font-weight: bold;
    }

    .flow-agent-stat {
      &-item {
        margin-left: 8px;
        white-space: nowrap;
      }

      &-count {
        font-weight: bold;
      }
    }

    .flow-agent-task {
      &-group {
        padding: 0;
      }

      &-header {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 0 12px 0 13px;
        cursor: pointer;
        border-radius: 2px;

        &:hover {
          background: $color-hover-bg;
        }
      }

      &-arrow {
        flex-shrink: 0;
        width: 12px;
        height: 12px;
        margin-right: 4px;
        font-size: 12px;
        color: #979ba5;
        transform: rotate(90deg);
        transition: transform 0.15s;

        @extend %flex-center;

        &:not(.is-expanded) {
          transform: rotate(0deg);
        }
      }

      &-state-icon {
        flex-shrink: 0;
        width: 16px;
        height: 16px;
        margin-right: 8px;

        @extend %flex-center;
      }

      &-name {
        flex: 1;
        font-weight: bold;
        color: $color-text;

        @extend %text-truncate;
      }

      &-time {
        flex-shrink: 0;
        margin-left: 8px;
        color: $color-text-secondary;
      }
    }

    .flow-agent-state-svg {
      width: 14px;
      height: 14px;
    }

    .flow-agent-node {
      &-status {
        flex-shrink: 0;
        width: 16px;
        height: 16px;
        margin-right: 8px;

        @extend %flex-center;

        @each $state, $color in $status-colors {
          &.is-#{$state} .flow-agent-status-dot {
            border-color: $color;
          }
        }

        .flow-agent-status-dot {
          width: 8px;
          height: 8px;
          border: 1.5px solid transparent;
          border-radius: 50%;
        }
      }

      &-name {
        flex: 1;
        color: $color-text;

        @extend %text-truncate;
      }

      &-trailing {
        display: flex;
        flex-shrink: 0;
        align-items: center;
        margin-left: 8px;
      }

      &-time {
        color: $color-text-secondary;
        text-align: right;
        white-space: nowrap;
      }

      &-detail-btn {
        display: none;
        gap: 2px;
        align-items: center;
        justify-content: center;
        font-size: 12px;
        color: $color-primary;
        cursor: pointer;

        &:hover {
          color: $color-primary-light;
        }
      }

      &-item {
        display: flex;
        align-items: center;
        height: 32px;
        padding: 0 12px 0 34px;
        border-radius: 2px;

        &:hover {
          background: $color-hover-bg;

          .flow-agent-node-detail-btn {
            display: flex;
          }

          .flow-agent-node-time {
            display: none;
          }
        }
      }
    }
  }

  .flow-agent-task-outputs {
    font-size: 12px;
    line-height: 20px;
    color: #4d4f56;
    word-break: break-all;
  }
</style>
