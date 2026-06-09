<template>
  <ActivityLayout
    v-model:collapsed="collapsed"
    :activity-type="MessageContentType.FlowAgent"
    class="flow-agent-activity"
  >
    <template #title>
      <!-- hover 整条执行情况栏展示统计 tooltip（设计稿 annotation） -->
      <Tippy
        class="flow-agent-title-bar"
        theme="ai-chat-box-light light"
        v-bind="{
          ...commonTippyOptions,
          tag: 'div',
          arrow: true,
          followCursor: false,
          offset: [0, 10],
        }"
      >
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
          <span class="flow-agent-title-label">{{ t('执行情况') }}：</span>
          <span
            v-for="stat in visibleStats"
            :key="stat.key"
            class="flow-agent-stat-item"
          >
            <Loading
              v-if="stat.key === 'running'"
              class="flow-agent-stat-loading"
              mode="spin"
              size="mini"
              theme="primary"
            />
            <span
              v-else
              class="flow-agent-stat-dot"
              :style="{ borderColor: stat.dotColor }"
            />
            <span
              class="flow-agent-stat-count"
              :style="{ color: stat.color }"
              >{{ stat.display }}</span
            >
          </span>
        </span>
        <template #content>
          <div class="flow-agent-stat-tooltip">
            <div
              v-for="stat in visibleStats"
              :key="stat.key"
              class="flow-agent-stat-tooltip-item"
            >
              <span class="flow-agent-stat-tooltip-status">
                <Loading
                  v-if="stat.key === 'running'"
                  mode="spin"
                  size="mini"
                  theme="primary"
                />
                <span
                  v-else
                  class="flow-agent-stat-dot"
                  :style="{ borderColor: stat.dotColor }"
                />
              </span>
              <span class="flow-agent-stat-tooltip-label">{{ stat.label }}：</span>
              <span
                class="flow-agent-stat-tooltip-count"
                :style="{ color: stat.color }"
                >{{ stat.display }}</span
              >
            </div>
          </div>
        </template>
      </Tippy>
    </template>
    <div
      v-for="task in viewTasks"
      :key="task.taskId"
      class="flow-agent-task-group"
    >
      <div
        class="flow-agent-task-header"
        :class="{
          'has-confidence': task.hasConfidence,
          'is-selected': isTaskSelected(task.raw),
        }"
      >
        <span
          class="flow-agent-task-arrow"
          :class="{ 'is-expanded': isTaskExpanded(task.raw) }"
        >
          <ArrowRightIcon @click.stop="toggleTaskExpanded(task.raw)" />
        </span>
        <span class="flow-agent-task-state-icon">
          <Loading
            v-if="task.convergedState === 'running'"
            mode="spin"
            size="mini"
            theme="primary"
          />
          <component
            :is="task.stateIcon"
            v-else
          />
        </span>
        <span
          v-overflow-tips="{ ...commonTippyOptions }"
          class="flow-agent-task-name"
        >
          <HighlightKeyword :text="task.taskName" />
        </span>
        <span
          v-if="showActions"
          class="flow-agent-task-trailing"
        >
          <span class="flow-agent-task-time">{{ task.totalTimeText }}</span>
          <span
            v-if="task.hasConfidence"
            class="flow-agent-task-action-btn flow-agent-task-confidence-btn"
            @click.stop="openConfidence(task.raw)"
          >
            <NodeOutputIcon />
            {{ task.confidenceTitle ?? t('有效证据') }}
          </span>
        </span>
      </div>
      <div
        v-show="isTaskExpanded(task.raw)"
        class="flow-agent-task-nodes"
      >
        <div
          v-for="node in task.nodes"
          :key="node.id"
          class="flow-agent-node-item"
          :class="{ 'is-selected': isNodeSelected(task.raw, node.raw) }"
        >
          <span class="flow-agent-node-status">
            <Loading
              v-if="node.convergedState === 'running'"
              mode="spin"
              size="mini"
              theme="primary"
            />
            <span
              v-else
              class="flow-agent-status-dot"
              :style="{ borderColor: node.dotColor }"
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
            v-if="showActions"
            class="flow-agent-node-trailing"
          >
            <span class="flow-agent-node-time">{{ node.elapsedTimeText }}</span>
            <span
              class="flow-agent-node-detail-btn"
              @click.stop="openNodeDetail(task.raw, node.raw)"
            >
              <NodeOutputIcon />
              {{ t('详情') }}
            </span>
          </span>
        </div>
      </div>
    </div>
  </ActivityLayout>
</template>
<script setup lang="ts">
  import { computed, toRef } from 'vue';

  import { Loading } from 'bkui-vue';
  import { Tippy } from 'vue-tippy';

  import { MessageContentType, MessageStatus } from '../../../ag-ui/types/constants';
  import { RenderMode } from '../../../common/constants';
  import { useCommonTippyInject, useRenderModeInject } from '../../../composables/use-common';
  import { OverflowTips as vOverflowTips } from '../../../directives/overflow-tips';
  import { ArrowRightIcon, NodeOutputIcon } from '../../../icons';
  import { t } from '../../../lang/lang';
  import AiLoading from '../../ai-loading/ai-loading.vue';
  import HighlightKeyword from '../../highlight-keyword/highlight-keyword';
  import ActivityLayout from '../activity-layout/activity-layout.vue';
  import { useFlowAgent } from './use-flow-agent';
  import { useFlowTab } from './use-flow-tab';

  import type { MessageStatus as MessageStatusType } from '../../../ag-ui/types/constants';
  import type { BkFlowMessageContent } from '../../../ag-ui/types/contents';

  import 'tippy.js/dist/tippy.css';

  const props = defineProps<{
    content?: BkFlowMessageContent;
    messageUid?: string;
    status?: MessageStatusType;
  }>();

  const commonTippyOptions = useCommonTippyInject();
  const collapsed = defineModel<boolean>('collapsed', {
    default: false,
  });

  const renderMode = useRenderModeInject();
  /** 分享态下隐藏耗时与详情等交互入口 */
  const showActions = computed(() => renderMode.value !== RenderMode.Share);

  const isLoading = computed(() => props.status === MessageStatus.Pending || props.status === MessageStatus.Streaming);

  // 视图模型层：任务 / 节点视图模型、统计概览、展开态
  const { isTaskExpanded, taskList, toggleTaskExpanded, viewTasks, visibleStats } = useFlowAgent(
    toRef(props, 'content'),
  );

  // 自定义 Tab 集成层：选中态、打开节点详情 / 有效证据、生命周期
  const { isNodeSelected, isTaskSelected, openConfidence, openNodeDetail } = useFlowTab({
    messageUid: toRef(props, 'messageUid'),
    taskList,
  });
</script>
<style lang="scss">
  // 状态圆环：空心环，颜色由视图模型按状态注入（模板内联 borderColor）。
  // 置于文件顶层 placeholder，供组件内（node 状态点）与根级（tooltip 统计点）共用，
  // 因统计 tooltip 内容会被 tippy 挂载到 body（脱离组件容器）。
  %flow-dot {
    flex-shrink: 0;
    width: 8px;
    height: 8px;
    border: 1.5px solid transparent;
    border-radius: 50%;
  }

  .flow-agent-activity {
    $color-text: #4d4f56;
    $color-text-secondary: #979ba5;
    $color-primary: #3a84ff;
    $color-primary-light: #699df4;
    $color-hover-bg: #eaebf0;
    $color-selected-bg: #e1ecff;

    font-size: 12px;

    /* ---------- 通用 placeholder ---------- */
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

    // 16×16 状态图标容器（task 状态图标 / node 状态点共用）
    %icon-box {
      flex-shrink: 0;
      width: 16px;
      height: 16px;
      margin-right: 8px;

      @extend %flex-center;
    }

    // 行内主标题文本（task / node 名称共用截断与配色）
    %row-name {
      flex: 1;
      color: $color-text;

      @extend %text-truncate;
    }

    // 行尾区域：耗时 / 操作按钮容器（task / node 共用）
    %row-trailing {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      margin-left: 8px;
    }

    // 行尾耗时文本（task / node 共用）
    %row-time {
      color: $color-text-secondary;
      text-align: right;
      white-space: nowrap;
    }

    // 单行容器：固定高度 + hover / 选中态背景（task header / node item 共用）
    %row {
      display: flex;
      align-items: center;
      height: 32px;
      border-radius: 2px;

      &:hover {
        background: $color-hover-bg;
      }

      &.is-selected {
        background: $color-selected-bg;

        &:hover {
          background: $color-selected-bg;
        }
      }
    }

    // hover 行时浮现的操作按钮（详情 / 有效证据），默认隐藏
    %action-btn {
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

    /* ---------- 标题：执行情况栏 ---------- */
    .ai-activity-message-title {
      width: 100%;
      height: 40px;
      background: #fafbfd;
      border: 1px solid #dcdee5;

      &-icon {
        font-size: 14px;
        font-weight: bold;
        color: $color-text;
        transform: rotate(90deg);

        &.icon-collapsed {
          transform: rotate(0deg);
        }
      }

      // 覆盖基础布局：执行情况栏需横向排布标签与各状态统计项
      &-text {
        display: flex;
        flex: 1;
        align-items: center;
        min-width: 0;
        overflow: hidden;
      }
    }

    .ai-activity-message-content {
      padding: 8px 0;
      font-size: 12px;
    }

    // 撑满整条以承载 hover 区域（设计稿 hover 整体出 tooltip）
    .flow-agent-title-bar {
      display: flex;
      flex: 1;
      align-items: center;
      min-width: 0;
      height: 100%;
    }

    .flow-agent-title-label {
      flex-shrink: 0;
      font-weight: bold;
      color: #313238;
    }

    /* ---------- 统计项（标题栏内联展示） ---------- */
    .flow-agent-stat {
      overflow: hidden;
      text-overflow: ellipsis;
      white-space: nowrap;

      &-item {
        display: inline-flex;
        flex-shrink: 0;
        gap: 4px;
        align-items: center;
        margin-right: 16px;
        white-space: nowrap;
      }

      &-loading {
        width: 16px;
        height: 16px;

        @extend %flex-center;
      }

      &-count {
        font-family: Arial, sans-serif;
        font-size: 14px;
        font-weight: bold;
        line-height: 1;
      }
    }

    /* ---------- 任务行 ---------- */
    .flow-agent-task {
      &-group {
        padding: 0;
      }

      &-header {
        padding: 0 12px 0 13px;
        cursor: pointer;

        @extend %row;

        // hover / 选中态下隐藏耗时，露出「有效证据」按钮
        &.has-confidence:hover .flow-agent-task-confidence-btn {
          display: flex;
        }

        &.has-confidence:hover .flow-agent-task-time,
        &.has-confidence.is-selected .flow-agent-task-time {
          display: none;
        }
      }

      &-arrow {
        flex-shrink: 0;
        width: 12px;
        height: 12px;
        margin-right: 4px;
        font-size: 12px;
        color: $color-text-secondary;
        transform: rotate(90deg);
        transition: transform 0.15s;

        @extend %flex-center;

        &:not(.is-expanded) {
          transform: rotate(0deg);
        }
      }

      &-state-icon {
        @extend %icon-box;
      }

      &-name {
        font-weight: bold;

        @extend %row-name;
      }

      &-trailing {
        @extend %row-trailing;
      }

      &-time {
        @extend %row-time;
      }

      &-action-btn {
        @extend %action-btn;
      }
    }

    /* ---------- 节点行 ---------- */
    .flow-agent-node {
      &-item {
        padding: 0 12px 0 34px;

        @extend %row;

        // hover 行时隐藏耗时，露出「详情」按钮
        &:hover {
          .flow-agent-node-detail-btn {
            display: flex;
          }

          .flow-agent-node-time {
            display: none;
          }
        }
      }

      &-status {
        @extend %icon-box;

        .flow-agent-status-dot {
          @extend %flow-dot;
        }
      }

      &-name {
        @extend %row-name;
      }

      &-trailing {
        @extend %row-trailing;
      }

      &-time {
        @extend %row-time;
      }

      &-detail-btn {
        @extend %action-btn;
      }
    }
  }

  // 统计 tooltip：状态图标 + 文字标签 + 计数（设计稿 hover 整体出 tooltip）。
  // 内容被 tippy 挂载到 body，故置于根级；ai-chat-box-light 主题已将 .tippy-content
  // padding 置 0，此处内边距对齐设计稿（12/16）。
  .flow-agent-stat-dot {
    @extend %flow-dot;
  }

  .flow-agent-stat-tooltip {
    display: flex;
    flex-direction: column;
    gap: 4px;
    padding: 12px 16px;
    border-radius: 4px;
    box-shadow: 0 0 20px 0 rgb(0 0 0 / 16%);

    &-item {
      display: flex;
      align-items: center;
      font-size: 12px;
      line-height: 20px;
      white-space: nowrap;
    }

    &-status {
      display: flex;
      flex-shrink: 0;
      align-items: center;
      justify-content: center;
      width: 16px;
      height: 16px;
      margin-right: 4px;
    }

    &-label {
      color: #4d4f56;
    }

    &-count {
      font-weight: bold;
    }
  }
</style>
