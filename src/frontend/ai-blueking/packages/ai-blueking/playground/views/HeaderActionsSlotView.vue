<template>
  <div class="slot-demo-view">
    <div class="view-header">
      <div class="view-header-row">
        <h2>headerActions 插槽</h2>
        <SourceGuideDialog
          title="headerActions：实现原理与源码"
          :sections="headerActionsGuideSections"
        />
      </div>
      <p class="view-desc">
        在 AIBlueking Header 右侧工具栏插入自定义图标。与
        <code>showHistoryIcon</code> 独立，不要用 <code>#headerLeft</code> 塞工具栏按钮。点击「查看源码」可复制完整片段。
      </p>
    </div>

    <section class="doc-panel">
      <h3 class="doc-panel-title">实现原理</h3>
      <ol class="principle-list">
        <li>
          <strong>位置</strong>：插在 <code>AIHeader .right-section</code> 内，会话操作（新增 / 历史 / 转人工）之后、窗口控制（压缩 / 关闭 / 侧栏）之前。
        </li>
        <li>
          <strong>和 #headerLeft 的区别</strong>：<code>#headerLeft</code> 在标题区与工具栏之间，不在同一排图标里。
        </li>
        <li>
          <strong>和 showHistoryIcon 独立</strong>：prop 只控制内置历史；自定义图标不走 <code>historyIconRef</code> / 历史下拉。
        </li>
        <li>
          <strong>透传链路</strong>：业务 <code>#headerActions</code> → <code>AIBlueking</code> → <code>AIHeader</code>。Vue2 须在
          <code>vue2.ts</code> 的 <code>slots</code> 数组登记，否则包装层丢插槽。
        </li>
        <li>
          <strong>样式</strong>：子节点带 <code>bkai-icon</code> 时，Header 用 <code>:deep</code> 套 20px / hover，与内置图标对齐。
        </li>
      </ol>
      <pre class="guide-code"><code>{{ HEADER_ACTIONS_LAYOUT }}</code></pre>
    </section>

    <section class="doc-panel">
      <h3 class="doc-panel-title">组件源码</h3>
      <article
        v-for="block in sourceBlocks"
        :key="block.title"
        class="source-block"
      >
        <header class="source-block-header">
          <div>
            <h4>{{ block.title }}</h4>
            <p
              v-if="block.desc"
              class="source-block-desc"
            >
              {{ block.desc }}
            </p>
          </div>
          <span
            v-if="block.fileHint"
            class="source-block-file"
          >
            {{ block.fileHint }}
          </span>
        </header>
        <pre class="guide-code"><code>{{ block.code }}</code></pre>
      </article>
    </section>

    <section class="doc-panel">
      <h3 class="doc-panel-title">接入示例（Vue3）</h3>
      <pre class="guide-code"><code>{{ VUE3_USAGE_CODE }}</code></pre>
    </section>

    <section class="doc-panel demo-panel">
      <div class="demo-panel-head">
        <h3 class="doc-panel-title">效果预览</h3>
        <label class="history-toggle">
          <input
            v-model="showHistoryIcon"
            type="checkbox"
          />
          showHistoryIcon（内置历史）
        </label>
      </div>
      <p class="demo-hint">
        点右侧工具栏「+」自定义图标会记一条日志。关掉历史开关后，自定义图标仍在压缩/关闭左侧。
      </p>
      <p
        v-if="lastAction"
        class="demo-log"
      >
        {{ lastAction }}
      </p>
    </section>

    <AIBlueking
      :show-history-icon="showHistoryIcon"
      :url="apiUrl"
    >
      <template #headerActions>
        <i
          class="bkai-icon"
          title="自定义操作"
          @click="onCustomAction"
        >
          <svg
            fill="none"
            height="14"
            viewBox="0 0 16 16"
            width="14"
            xmlns="http://www.w3.org/2000/svg"
          >
            <path
              d="M8 2.5a1 1 0 0 1 1 1V7h3.5a1 1 0 1 1 0 2H9v3.5a1 1 0 1 1-2 0V9H3.5a1 1 0 0 1 0-2H7V3.5a1 1 0 0 1 1-1Z"
              fill="currentColor"
            />
          </svg>
        </i>
      </template>
    </AIBlueking>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import AIBlueking from '@blueking/ai-blueking';

  import {
    HEADER_ACTIONS_LAYOUT,
    VUE3_USAGE_CODE,
    headerActionsGuideSections,
  } from '../components/header-actions-guide';
  import SourceGuideDialog from '../components/SourceGuideDialog.vue';

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const showHistoryIcon = ref(true);
  const lastAction = ref('');

  const sourceBlocks = computed(
    () => headerActionsGuideSections.find(section => section.id === 'source')?.blocks ?? [],
  );

  const onCustomAction = (): void => {
    lastAction.value = `自定义图标点击 ${new Date().toLocaleTimeString()}`;
  };
</script>

<style scoped>
  .view-header {
    margin-bottom: 24px;
  }

  .view-header-row {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
  }

  .view-header h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .view-header-row h2 {
    margin-bottom: 0;
  }

  .view-desc {
    margin: 8px 0 0;
    font-size: 13px;
    line-height: 22px;
    color: #979ba5;
  }

  .view-desc code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .doc-panel {
    padding: 16px;
    margin-bottom: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
  }

  .doc-panel-title {
    margin: 0 0 12px;
    font-size: 14px;
    font-weight: 600;
    color: #313238;
  }

  .principle-list {
    padding-left: 20px;
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 22px;
    color: #63656e;
  }

  .principle-list li + li {
    margin-top: 8px;
  }

  .principle-list strong {
    color: #313238;
  }

  .principle-list code,
  .demo-hint code {
    padding: 1px 6px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .guide-code {
    display: block;
    padding: 12px 14px;
    margin: 0;
    overflow: auto;
    font-size: 12px;
    line-height: 18px;
    color: #313238;
    white-space: pre;
    background: #f5f7fa;
    border-radius: 4px;
  }

  .source-block + .source-block {
    margin-top: 16px;
  }

  .source-block-header {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .source-block-header h4 {
    margin: 0 0 4px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .source-block-desc {
    margin: 0;
    font-size: 12px;
    line-height: 18px;
    color: #979ba5;
  }

  .source-block-file {
    flex-shrink: 0;
    font-size: 11px;
    color: #979ba5;
  }

  .demo-panel-head {
    display: flex;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
  }

  .demo-panel-head .doc-panel-title {
    margin-bottom: 0;
  }

  .history-toggle {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
  }

  .demo-hint {
    margin: 12px 0 0;
    font-size: 13px;
    line-height: 20px;
    color: #979ba5;
  }

  .demo-log {
    margin: 8px 0 0;
    font-size: 12px;
    color: #3a84ff;
  }
</style>
