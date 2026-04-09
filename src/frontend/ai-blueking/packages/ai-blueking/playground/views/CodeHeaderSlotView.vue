<template>
  <div class="slot-demo-view">
    <div class="view-header">
      <h2>codeHeader 插槽</h2>
      <p class="view-desc">演示在 AIBlueking 中自定义代码块头部操作按钮（插入/应用）</p>
      <p class="view-tip">可发送“请输出一段 TypeScript 代码并使用 markdown 代码块包裹”来观察效果</p>
    </div>
    <AIBlueking :url="apiUrl">
      <template #codeHeader="{ language, token }">
        <span
          class="code-header-action"
          @click="handleCodeInsert(language, token)"
        >
          插入
        </span>
        <span
          class="code-header-action"
          @click="handleCodeApply(language, token)"
        >
          应用
        </span>
      </template>
    </AIBlueking>
  </div>
</template>

<script setup lang="ts">
  import AIBlueking from '@blueking/ai-blueking';

  const apiUrl = import.meta.env.VITE_API_URL || '';

  const handleCodeInsert = (language: string, token: Token[]) => {
    console.log('[CodeHeaderSlotDemo] insert code, language:', language, 'token:', token);
  };

  const handleCodeApply = (language: string, token: Token[]) => {
    console.log('[CodeHeaderSlotDemo] apply code, language:', language, 'token:', token);
  };
</script>

<style scoped>
  .view-header {
    margin-bottom: 24px;
  }

  .view-header h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: #313238;
  }

  .view-desc {
    margin: 0 0 8px;
    font-size: 13px;
    color: #979ba5;
  }

  .view-tip {
    margin: 0;
    font-size: 12px;
    color: #63656e;
  }

  .code-header-action {
    padding: 2px 8px;
    font-size: 12px;
    color: #979ba5;
    cursor: pointer;
    border-radius: 2px;
  }

  .code-header-action:hover {
    color: #3a84ff;
    background: rgb(58 132 255 / 10%);
  }
</style>
