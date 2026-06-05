<template>
  <div class="demo-request-options-bar">
    <div class="bar-row">
      <span class="bar-label">requestOptions（响应式）</span>
      <div class="bar-actions">
        <button
          class="demo-btn"
          type="button"
          @click="emit('rotate-token')"
        >
          切换 Token（{{ token }}）
        </button>
        <button
          class="demo-btn"
          type="button"
          @click="emit('rotate-app-id')"
        >
          切换 app_id（{{ appId }}）
        </button>
        <button
          class="demo-btn"
          type="button"
          @click="emit('rotate-tenant-id')"
        >
          切换 tenant_id（{{ tenantId }}）
        </button>
        <button
          class="demo-btn context-btn"
          type="button"
          @click="emit('rotate-context-env')"
        >
          切换 context.env（{{ contextEnv }}）
        </button>
        <button
          class="demo-btn context-btn"
          type="button"
          @click="emit('rotate-context-region')"
        >
          切换 context.region（{{ contextRegion }}）
        </button>
      </div>
    </div>
    <pre class="preview-json">{{ previewJson }}</pre>
    <p class="bar-hint">
      打开 DevTools → Network：GET（如 getAgentInfo / getSessions）应在 URL 上看到
      <code>app_id</code>、<code>tenant_id</code>；POST（如发消息）应在 Request Payload 中看到相同字段。
      切换按钮后<strong>无需重建组件</strong>，下一次请求即生效。 <code>context</code> 字段会合并到消息的
      <code>property.extra.context</code>，与 shortcuts 表单数据同级。
    </p>
  </div>
</template>

<script setup lang="ts">
  defineProps<{
    appId: string;
    contextEnv: string;
    contextRegion: string;
    previewJson: string;
    tenantId: string;
    token: string;
  }>();

  const emit = defineEmits<{
    'rotate-app-id': [];
    'rotate-context-env': [];
    'rotate-context-region': [];
    'rotate-tenant-id': [];
    'rotate-token': [];
  }>();
</script>

<style scoped>
  .demo-request-options-bar {
    padding: 12px 16px;
    margin-bottom: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .bar-row {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }

  .bar-label {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .bar-actions {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .demo-btn {
    padding: 4px 12px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: #f0f5ff;
    border: 1px solid #a3c5fd;
    border-radius: 2px;
    transition: background 0.15s;
  }

  .demo-btn:hover {
    background: #e1ecff;
  }

  .demo-btn.context-btn {
    color: #2dcb56;
    background: #f0fff4;
    border-color: #95de64;
  }

  .demo-btn.context-btn:hover {
    background: #d9f7be;
  }

  .preview-json {
    max-height: 120px;
    padding: 10px 12px;
    margin: 0 0 10px;
    overflow: auto;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    line-height: 1.5;
    color: #63656e;
    background: #fafbfd;
    border: 1px solid #f0f1f5;
    border-radius: 2px;
  }

  .bar-hint {
    margin: 0;
    font-size: 12px;
    line-height: 1.6;
    color: #979ba5;
  }

  .bar-hint code {
    padding: 1px 4px;
    font-size: 11px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 2px;
  }
</style>
