<!--
  Playground 侧栏自定义 Tab 内容示例：与 FlowAgent addCustomTab 的 data.props 语义对齐（在 chat-bot-new 中映射为 camelCase），
  模板内需保留 locateButton 插槽，以便 ChatContainer 注入「在对话中定位」按钮。
-->
<template>
  <div class="playground-custom-tab-root">
    <header class="playground-custom-tab-header">
      <div class="playground-custom-tab-header-main">
        <h3 class="playground-custom-tab-title">
          <template v-if="loading">
            <span class="playground-custom-tab-title-text">自定义侧栏</span>
            <span class="playground-custom-tab-skeleton-title ai-skeleton-element" />
          </template>
          <template v-else>
            {{ titleText }}
          </template>
        </h3>
        <span
          v-if="!loading"
          class="playground-custom-tab-badge"
          :class="detailSource === 'custom' ? 'is-custom' : 'is-builtin'"
        >
          {{ detailSource === 'custom' ? 'onCustomTabChange' : '内置 getFlowAgentTaskNodeInfo' }}
        </span>
      </div>
      <div class="playground-custom-tab-actions">
        <slot name="locateButton" />
      </div>
    </header>

    <div class="playground-custom-tab-body">
      <p
        v-if="!loading"
        class="playground-custom-tab-hint"
      >
        <template v-if="detailSource === 'custom'">
          场景 2：<code>onCustomTabChange</code> 返回值已写入 <code>props.data</code>；下方展示本次请求与详情字段。
        </template>
        <template v-else>
          场景 1：<code>getSideRenderComponent</code> 自定义 UI；详情由 ChatBot 内置
          <code>getFlowAgentTaskNodeInfo</code> 拉取并写入 <code>props.data</code>。
        </template>
      </p>

      <div
        v-if="!loading && customFetchMeta"
        class="playground-custom-tab-fetch"
      >
        <div class="playground-custom-tab-fetch-label">本次自定义请求</div>
        <code class="playground-custom-tab-fetch-url">{{ customFetchMeta.requestUrl }}</code>
      </div>

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

      <details
        v-if="!loading && dataPreview"
        class="playground-custom-tab-data"
        open
      >
        <summary>props.data（详情接口返回）</summary>
        <pre class="playground-custom-tab-data-pre">{{ dataPreview }}</pre>
      </details>

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

  import type { SideRenderCustomFetchMeta } from './use-side-render-custom-tab-change';
  import type { SideRenderDetailSource } from './use-side-render-handlers';

  const props = withDefaults(
    defineProps<{
      /** 节点详情等业务数据（与侧栏 data.props.data 对齐） */
      data?: Record<string, unknown>;
      detailSource?: SideRenderDetailSource;
      loading?: boolean;
      nodeId?: string;
      nodeName?: string;
      taskId?: number;
      taskName?: string;
    }>(),
    {
      data: () => ({}),
      detailSource: 'builtin',
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

  const customFetchMeta = computed((): SideRenderCustomFetchMeta | null => {
    if (props.detailSource !== 'custom') {
      return null;
    }
    const meta = props.data?._demoMeta;
    if (typeof meta !== 'object' || meta === null || Array.isArray(meta)) {
      return null;
    }
    const record = meta as Record<string, unknown>;
    if (record.fetchedBy !== 'onCustomTabChange' || typeof record.requestUrl !== 'string') {
      return null;
    }
    return {
      fetchedBy: 'onCustomTabChange',
      requestUrl: record.requestUrl,
      fetchedAt: typeof record.fetchedAt === 'string' ? record.fetchedAt : '',
    };
  });

  const dataPreview = computed(() => {
    const { _demoMeta: _meta, ...rest } = props.data ?? {};
    if (Object.keys(rest).length === 0) {
      return '';
    }
    try {
      return JSON.stringify(rest, null, 2);
    } catch {
      return String(rest);
    }
  });
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
    gap: 12px;
    align-items: flex-start;
    justify-content: space-between;
    padding: 12px 16px;
    background: #fff;
    border-bottom: 1px solid #dcdee5;
  }

  .playground-custom-tab-header-main {
    display: flex;
    flex: 1;
    flex-direction: column;
    gap: 6px;
    min-width: 0;
  }

  .playground-custom-tab-badge {
    display: inline-flex;
    align-self: flex-start;
    padding: 2px 8px;
    font-size: 10px;
    font-weight: 500;
    line-height: 16px;
    border-radius: 10px;

    &.is-builtin {
      color: #2dcb56;
      background: #e5f6ea;
    }

    &.is-custom {
      color: #ff9c01;
      background: #fff3e0;
    }
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

  .playground-custom-tab-fetch {
    padding: 10px 12px;
    margin-bottom: 12px;
    background: #fff;
    border: 1px dashed #c4c6cc;
    border-radius: 4px;
  }

  .playground-custom-tab-fetch-label {
    margin-bottom: 6px;
    font-size: 11px;
    font-weight: 500;
    color: #979ba5;
  }

  .playground-custom-tab-fetch-url {
    display: block;
    font-family: monospace;
    font-size: 11px;
    line-height: 18px;
    color: #3a84ff;
    word-break: break-all;
  }

  .playground-custom-tab-data {
    margin-top: 12px;

    summary {
      margin-bottom: 8px;
      font-size: 12px;
      font-weight: 500;
      color: #63656e;
      cursor: pointer;
    }
  }

  .playground-custom-tab-data-pre {
    max-height: 200px;
    padding: 10px 12px;
    margin: 0;
    overflow: auto;
    font-family: monospace;
    font-size: 11px;
    line-height: 18px;
    color: #313238;
    background: #fff;
    border: 1px solid #eaebf0;
    border-radius: 4px;
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
