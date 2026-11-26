<template>
  <div class="custom-welcome">
    <div class="welcome-badge">AI</div>
    <h2 class="welcome-title">{{ welcomeTitle || '你好，我是小鲸' }}</h2>
    <p class="welcome-remark">
      {{ openingRemark || '已自动感知当前页面上下文，点击下方快捷入口或直接输入「日志分析」即可排查。' }}
    </p>

    <div
      v-if="traceId"
      class="welcome-action-card"
    >
      <div class="welcome-action-meta">
        <span class="meta-dot" />
        <span>当前页面对象：</span>
        <code>{{ service || 'custom-service' }}</code>
      </div>
      <div class="welcome-action-btns">
        <button
          class="quick-analyze-btn"
          type="button"
          @click="emit('analyze')"
        >
          <span class="btn-sparkle">✦</span>
          <span>分析 {{ traceId }} 的日志</span>
          <span class="btn-arrow">→</span>
        </button>
        <button
          class="secondary-fill-btn"
          type="button"
          @click="emit('fill-only')"
        >
          仅填入「日志分析」
        </button>
      </div>
      <p class="welcome-action-tip">
        点击主按钮发送原文 <code>日志分析</code>，同时隐式附带 <code>trace_id={{ traceId }}</code>
      </p>
    </div>

    <div
      v-else
      class="welcome-empty-context"
    >
      当前页面未选中 Trace。请在左侧选择一条 Trace，欢迎区会实时出现「分析 xxx 的日志」快捷按钮。
    </div>
  </div>
</template>

<script setup lang="ts">
  interface TraceWelcomeCardProps {
    openingRemark?: string;
    service?: string;
    traceId?: string;
    welcomeTitle?: string;
  }

  defineProps<TraceWelcomeCardProps>();

  const emit = defineEmits<{
    analyze: [];
    'fill-only': [];
  }>();
</script>

<style scoped>
  .custom-welcome {
    display: flex;
    flex-direction: column;
    align-items: center;
    width: 100%;
    max-width: 520px;
    padding: 20px 16px 8px;
    text-align: center;
  }

  .welcome-badge {
    display: flex;
    align-items: center;
    justify-content: center;
    width: 44px;
    height: 44px;
    margin-bottom: 12px;
    font-size: 15px;
    font-weight: 700;
    color: #fff;
    background: linear-gradient(135deg, #3a84ff 0%, #699df4 100%);
    border-radius: 12px;
    box-shadow: 0 6px 16px rgb(58 132 255 / 24%);
  }

  .welcome-title {
    margin: 0 0 8px;
    font-size: 19px;
    font-weight: 600;
    color: #313238;
  }

  .welcome-remark {
    margin: 0 0 18px;
    font-size: 13px;
    line-height: 1.6;
    color: #63656e;
  }

  .welcome-action-card {
    width: 100%;
    padding: 14px 16px;
    background: #f5f9ff;
    border: 1px solid #d4e4ff;
    border-radius: 10px;
  }

  .welcome-action-meta {
    display: flex;
    gap: 6px;
    align-items: center;
    justify-content: center;
    margin-bottom: 12px;
    font-size: 12px;
    color: #63656e;
  }

  .welcome-action-meta code,
  .welcome-action-tip code {
    padding: 1px 5px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #3a84ff;
    background: #fff;
    border-radius: 3px;
  }

  .meta-dot {
    width: 6px;
    height: 6px;
    background: #2dcb56;
    border-radius: 50%;
  }

  .welcome-action-btns {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    justify-content: center;
    margin-bottom: 10px;
  }

  .quick-analyze-btn {
    display: inline-flex;
    gap: 8px;
    align-items: center;
    padding: 8px 16px;
    font-size: 13px;
    font-weight: 500;
    color: #fff;
    cursor: pointer;
    background: linear-gradient(135deg, #3a84ff 0%, #2670eb 100%);
    border: none;
    border-radius: 20px;
    box-shadow: 0 4px 12px rgb(58 132 255 / 28%);
    transition: transform 0.15s, box-shadow 0.15s;
  }

  .quick-analyze-btn:hover {
    transform: translateY(-1px);
    box-shadow: 0 6px 16px rgb(58 132 255 / 36%);
  }

  .btn-sparkle,
  .btn-arrow {
    font-size: 12px;
    opacity: 0.9;
  }

  .secondary-fill-btn {
    padding: 8px 12px;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: #fff;
    border: 1px solid #a3c5fd;
    border-radius: 20px;
    transition: background 0.15s;
  }

  .secondary-fill-btn:hover {
    background: #e1ecff;
  }

  .welcome-action-tip {
    margin: 0;
    font-size: 11px;
    color: #979ba5;
  }

  .welcome-empty-context {
    width: 100%;
    padding: 12px 14px;
    font-size: 12px;
    line-height: 1.6;
    color: #979ba5;
    background: #fafbfd;
    border: 1px dashed #dcdee5;
    border-radius: 8px;
  }
</style>
