import type { SourceGuideSection } from './source-guide';

export const HEADER_ACTIONS_LAYOUT = `[logo] [title] [more] | #headerLeft | [new-chat] [history] [help] | #headerActions | [compress] [close] | [aside]
     .left-section                              .right-section（关闭与侧栏之间有竖线分隔）`;

export const AI_HEADER_SLOT_CODE = `<!-- packages/ai-blueking/src/components/ai-header/index.vue -->
<!-- 转人工之后、压缩/关闭之前；无插槽时不渲染空容器 -->
<div
  v-if="$slots.headerActions"
  class="header-actions"
>
  <slot name="headerActions" />
</div>

<!-- defineSlots：与 headerLeft 并列，无 slot props -->
defineSlots<{
  headerActions?: () => unknown;
  headerLeft?: () => unknown;
}>();

<!-- 插槽内 .bkai-icon 通过 :deep 套用工具栏 20px / hover -->
.header-actions {
  display: flex;
  gap: 12px;
  align-items: center;
}

.bkai-icon,
.header-actions :deep(.bkai-icon) {
  display: inline-flex;
  width: 20px;
  height: 20px;
  /* ... */
}`;

export const AIBLUEKING_FORWARD_CODE = `<!-- packages/ai-blueking/src/ai-blueking.vue -->
<AIHeader ...>
  <template
    v-if="$slots.headerLeft"
    #headerLeft
  >
    <slot name="headerLeft" />
  </template>
  <template
    v-if="$slots.headerActions"
    #headerActions
  >
    <slot name="headerActions" />
  </template>
</AIHeader>

<!-- Vue2 包装层 packages/ai-blueking/src/vue2.ts -->
slots: ['codeHeader', 'headerActions', 'headerLeft', 'message', 'welcome']`;

export const VUE3_USAGE_CODE = `<template>
  <AIBlueking
    :url="apiUrl"
    :show-history-icon="true"
  >
    <template #headerActions>
      <i
        class="bkai-icon"
        title="自定义操作"
        @click="onCustomAction"
      >
        <!-- svg / 图标字体 -->
      </i>
    </template>
  </AIBlueking>
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';
  import '@blueking/ai-blueking/dist/vue3/style.css';

  const apiUrl = '/api/';
  const onCustomAction = () => {
    // 点击逻辑由接入方自己写，不经过历史下拉
  };
</script>`;

export const VUE2_USAGE_CODE = `import AIBluekingV2, { h } from '@blueking/ai-blueking/vue2';

// template scoped slot
<AIBluekingV2 :url="apiUrl" :show-history-icon="true">
  <template #headerActions>
    <i class="bkai-icon" @click="onCustomAction"></i>
  </template>
</AIBluekingV2>

// render 必须用包导出的 h（Vue3 VNode），不能用 Vue2 createElement
render(h2) {
  return h2(AIBluekingV2, {
    props: { url: apiUrl, showHistoryIcon: true },
    scopedSlots: {
      headerActions: () => h('i', { class: 'bkai-icon', onClick: onCustomAction }),
    },
  });
}`;

export const headerActionsGuideSections: SourceGuideSection[] = [
  {
    id: 'principle',
    label: '实现原理',
    notes: [
      '#headerLeft 在标题区和右侧工具栏之间，不能用来塞工具栏图标。',
      '#headerActions 插在 AIHeader .right-section 内部：会话操作（新增 / 历史 / 转人工）之后，窗口控制（压缩 / 关闭 / 侧栏）之前。',
      'showHistoryIcon 只控制内置历史按钮；与 #headerActions 独立。隐藏历史时自定义图标仍在同一排。',
      '历史下拉仍绑 historyIconRef + useHistoryDropdown，自定义 DOM 不会打断 tippy 定位。',
      '插槽链路：业务 #headerActions → AIBlueking → AIHeader。Vue2 须在 vue2.ts slots 数组注册，否则包装层丢插槽。',
      '子节点带 bkai-icon 时，AIHeader 用 :deep 套上 20px / hover，和内置图标对齐。',
    ],
    blocks: [
      {
        title: 'Header 布局',
        desc: '自定义图标与内置历史同一排，但在压缩/关闭之前，避免挡住窗口控制。',
        code: HEADER_ACTIONS_LAYOUT,
      },
    ],
  },
  {
    id: 'source',
    label: '组件源码',
    notes: [
      '实现只加插槽，不引入 action 配置数组或 render-fn prop，与 #headerLeft 保持一致。',
    ],
    blocks: [
      {
        title: 'AIHeader 插槽落点',
        fileHint: 'src/components/ai-header/index.vue',
        desc: 'v-if="$slots.headerActions" 避免空容器；样式与 .right-section 同 gap。',
        code: AI_HEADER_SLOT_CODE,
      },
      {
        title: 'AIBlueking 透传',
        fileHint: 'src/ai-blueking.vue + src/vue2.ts',
        desc: 'Vue3 条件透传；Vue2 createVue2Wrapper 必须登记 slot 名。',
        code: AIBLUEKING_FORWARD_CODE,
      },
    ],
  },
  {
    id: 'usage',
    label: '接入示例',
    notes: [
      '只留自定义图标：:show-history-icon="false" + #headerActions。',
      '点击逻辑自己写；不要指望组件转发 header-actions-click。',
    ],
    blocks: [
      {
        title: 'Vue3',
        fileHint: 'YourApp.vue',
        code: VUE3_USAGE_CODE,
      },
      {
        title: 'Vue2',
        fileHint: 'YourApp.vue',
        desc: 'Vue2 createElement 产出的 VNode 无法被内部 Vue3 应用渲染。',
        code: VUE2_USAGE_CODE,
      },
    ],
  },
];
