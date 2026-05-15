<!--
  Playground 侧栏自定义 Tab 内容示例：与 FlowAgent addCustomTab 的 data.props 语义对齐（在 chat-bot-new 中映射为 camelCase），
  模板内需保留 locateButton 插槽，以便 ChatContainer 注入「在对话中定位」按钮。
-->
<template>
  <div class="playground-custom-tab-root">
    <header class="playground-custom-tab-header">
      <h3 class="playground-custom-tab-title">
        <template v-if="loading">
          <span class="playground-custom-tab-title-text">自定义侧栏</span>
          <span class="playground-custom-tab-skeleton-title ai-skeleton-element" />
        </template>
        <template v-else>
          {{ titleText }}
        </template>
      </h3>
      <div class="playground-custom-tab-actions">
        <slot name="locateButton" />
      </div>
    </header>

    <div class="playground-custom-tab-body">
      <p
        v-if="!loading"
        class="playground-custom-tab-hint"
      >
        Playground 示例：<code>getSideRenderComponent</code> 返回 <code>h(CustomTabContent, props)</code>；props 与
        tab.data.props 对应字段一致。
      </p>

      <dl
        v-if="!loading"
        class="playground-custom-tab-meta"
      >
        <div class="playground-custom-tab-meta-row">
          <dt>task_id</dt>
          <dd>{{ taskIdDisplay }}</dd>
        </div>
        <div class="playground-custom-tab-meta-row">
          <dt>task_name</dt>
          <dd>{{ taskName || '—' }}</dd>
        </div>
        <div class="playground-custom-tab-meta-row">
          <dt>node_id</dt>
          <dd>{{ nodeId || '—' }}</dd>
        </div>
        <div class="playground-custom-tab-meta-row">
          <dt>node_name</dt>
          <dd>{{ nodeName || '—' }}</dd>
        </div>
      </dl>

      <div
        v-if="loading"
        class="playground-custom-tab-loading"
      >
        <div
          v-for="i in 4"
          :key="i"
          class="playground-custom-tab-skeleton-row ai-skeleton-element"
        />
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { computed } from 'vue';

  const props = withDefaults(
    defineProps<{
      /** 节点详情等业务数据（与侧栏 data.props.data 对齐） */
      data?: Record<string, unknown>;
      loading?: boolean;
      nodeId?: string;
      nodeName?: string;
      taskId?: number;
      taskName?: string;
    }>(),
    {
      data: () => ({}),
      loading: false,
      nodeId: '',
      nodeName: '',
      taskName: '',
    },
  );

  const titleText = computed(() => {
    const name = props.nodeName?.trim();
    return name ? `自定义侧栏：${name}` : '自定义侧栏';
  });

  const taskIdDisplay = computed(() => (props.taskId != null ? String(props.taskId) : '—'));
</script>

<style lang="scss" scoped>
  .playground-custom-tab-root {
    box-sizing: border-box;
    display: flex;
    flex-direction: column;
    height: 100%;
    overflow: hidden;
    font-size: 12px;
    line-height: 1.5;
    color: #63656e;
    background: #f5f7fa;
  }

  .playground-custom-tab-header {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
  }

  .playground-custom-tab-title {
    display: flex;
    gap: 8px;
    align-items: center;
    min-height: 22px;
    margin: 0;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .playground-custom-tab-title-text {
    flex-shrink: 0;
  }

  .playground-custom-tab-skeleton-title {
    display: inline-block;
    width: 120px;
    height: 14px;
    vertical-align: middle;
    border-radius: 2px;
  }

  .playground-custom-tab-actions {
    display: flex;
    flex-shrink: 0;
    align-items: center;
    margin-left: 12px;
  }

  .playground-custom-tab-body {
    flex: 1;
    padding: 12px 16px;
    overflow: auto;
  }

  .playground-custom-tab-hint {
    margin: 0 0 12px;
    color: #979ba5;

    code {
      padding: 0 4px;
      font-family: monospace;
      font-size: 11px;
      color: #313238;
      background: #eaebf0;
      border-radius: 2px;
    }
  }

  .playground-custom-tab-meta {
    margin: 0;
  }

  .playground-custom-tab-meta-row {
    display: grid;
    grid-template-columns: 88px 1fr;
    gap: 8px;
    padding: 6px 0;
    border-bottom: 1px solid #eaebf0;

    &:last-child {
      border-bottom: none;
    }

    dt {
      margin: 0;
      font-weight: 500;
      color: #979ba5;
    }

    dd {
      margin: 0;
      color: #313238;
      word-break: break-all;
    }
  }

  .playground-custom-tab-loading {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding-top: 8px;
  }

  .playground-custom-tab-skeleton-row {
    height: 12px;
    border-radius: 2px;
  }
</style>
