<template>
  <div class="standalone-view">
    <div class="view-header">
      <h2>独立模式</h2>
      <p class="view-desc">
        ChatBot 组件独立使用，可嵌入到任意页面区域（无 Nimbus、无浮窗、无拖拽）。侧栏展开/收起与会话标题需业务方自行实现，见「嵌入模式业务 Header」。
      </p>
    </div>

    <DemoRequestOptionsBar
      :token="token"
      :app-id="appId"
      :tenant-id="tenantId"
      :preview-json="previewJson"
      @rotate-token="rotateToken"
      @rotate-app-id="rotateAppId"
      @rotate-tenant-id="rotateTenantId"
    />

    <div class="page-simulation">
      <div class="page-sidebar">
        <div class="page-sidebar-title">模拟页面导航</div>
        <div class="page-sidebar-item active">首页</div>
        <div class="page-sidebar-item">设置</div>
        <div class="page-sidebar-item">关于</div>
      </div>

      <div class="page-main">
        <div class="page-main-header">主内容区域 — ChatBot 嵌入在此处</div>
        <div class="chatbot-wrapper">
          <ChatBot
            ref="chatBotRef"
            height="600px"
            :request-options="requestOptions"
            :url="apiUrl"
            @error="handleError"
            @send-message="handleSendMessage"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { onMounted, ref } from 'vue';

  import { ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';

  import DemoRequestOptionsBar from '../components/DemoRequestOptionsBar.vue';
  import { useDemoRequestOptions } from '../composables/use-demo-request-options';

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const chatBotRef = ref<ChatBotExpose>();

  const { token, appId, tenantId, requestOptions, previewJson, rotateToken, rotateAppId, rotateTenantId } =
    useDemoRequestOptions();

  const handleSendMessage = (message: string) => {
    console.log('[Standalone] send:', message);
  };

  const handleError = (error: Error) => {
    console.error('[Standalone] error:', error);
  };

  onMounted(async () => {
    await chatBotRef.value?.whenReady();
    console.log('[Standalone] ChatBot ready, isReady:', chatBotRef.value?.isReady);
  });
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
    margin: 0;
    font-size: 13px;
    color: #979ba5;
  }

  .page-simulation {
    display: flex;
    gap: 0;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .page-sidebar {
    flex-shrink: 0;
    width: 180px;
    padding: 16px 0;
    background: #f5f7fa;
    border-right: 1px solid #dcdee5;
  }

  .page-sidebar-title {
    padding: 0 16px 12px;
    font-size: 12px;
    font-weight: 500;
    color: #979ba5;
  }

  .page-sidebar-item {
    padding: 8px 16px;
    font-size: 13px;
    color: #63656e;
    cursor: pointer;
  }

  .page-sidebar-item:hover {
    color: #3a84ff;
    background: #e1ecff;
  }

  .page-sidebar-item.active {
    font-weight: 500;
    color: #3a84ff;
    background: #e1ecff;
  }

  .page-main {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .page-main-header {
    padding: 12px 16px;
    font-size: 13px;
    color: #979ba5;
    background: #fafbfd;
    border-bottom: 1px solid #f0f1f5;
  }

  .chatbot-wrapper {
    display: flex;
    flex: 1;
  }
</style>
