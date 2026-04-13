<template>
  <div class="embedded-view">
    <div class="view-header">
      <h2>ChatBot 嵌入模式</h2>
      <p class="view-desc">将 ChatBotV2 嵌入页面布局（无 Nimbus、无浮窗壳层）</p>
    </div>

    <div class="page-layout">
      <div class="sidebar">
        <h3>页面导航</h3>
        <ul>
          <li>首页</li>
          <li>设置</li>
          <li>关于</li>
        </ul>
      </div>
      <div class="main-content">
        <h3>主内容区域</h3>
        <p>以下为 ChatBotV2 嵌入区域（命名导出自 <code>@blueking/ai-blueking/vue2</code>）。</p>
        <div class="chatbot-wrapper">
          <chat-bot-v2
            ref="chatBotRef"
            height="560px"
            hello-text="你好，我是小鲸（Vue2 嵌入 Demo）"
            :shortcuts="shortcuts"
            :url="apiUrl"
            @error="onEmbeddedError"
            @send-message="onEmbeddedSendMessage"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script>
  import { ChatBotV2 } from '@blueking/ai-blueking/vue2';

  export default {
    name: 'EmbeddedView',
    components: { ChatBotV2 },
    data() {
      return {
        apiUrl: import.meta.env.VITE_API_URL || '',
        shortcuts: [
          {
            id: 'translate',
            name: '翻译',
            icon: 'translate',
            prompt: '请帮我翻译以下内容：',
          },
          {
            id: 'code-review',
            name: '代码审查',
            icon: 'code',
            prompt: '请帮我审查以下代码：',
          },
        ],
      };
    },
    methods: {
      onEmbeddedSendMessage(message) {
        console.log('[Vue2 Playground] [ChatBotV2] send-message:', message);
      },
      onEmbeddedError(error) {
        console.error('[Vue2 Playground] [ChatBotV2] error:', error);
      },
    },
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
    margin: 0;
    font-size: 13px;
    color: #979ba5;
  }

  .page-layout {
    display: flex;
    gap: 24px;
  }

  .sidebar {
    width: 200px;
    padding: 16px;
    background: #f5f7fa;
    border-radius: 2px;
  }

  .sidebar h3 {
    margin-top: 0;
    font-size: 14px;
  }

  .sidebar ul {
    padding: 0;
    list-style: none;
  }

  .sidebar li {
    padding: 8px 0;
    cursor: pointer;
  }

  .sidebar li:hover {
    color: #3a84ff;
  }

  .main-content {
    flex: 1;
    min-width: 0;
  }

  .main-content h3 {
    margin-top: 0;
  }

  .main-content p {
    margin-bottom: 12px;
    font-size: 14px;
    color: #63656e;
  }

  .main-content code {
    padding: 2px 6px;
    font-size: 12px;
    background: #f0f1f5;
    border-radius: 2px;
  }

  .chatbot-wrapper {
    margin-top: 12px;
    overflow: hidden;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }
</style>
