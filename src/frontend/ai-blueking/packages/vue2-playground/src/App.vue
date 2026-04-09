<template>
  <div id="vue2-playground">
    <h1>AI-Blueking Vue2 Playground</h1>
    <p class="desc">测试 @blueking/ai-blueking/vue2 在 Vue 2.7 环境中的兼容性</p>

    <div class="tabs">
      <button
        :class="{ active: activeTab === 'full' }"
        type="button"
        @click="activeTab = 'full'"
      >
        AIBlueking 完整模式
      </button>
      <button
        :class="{ active: activeTab === 'embedded' }"
        type="button"
        @click="activeTab = 'embedded'"
      >
        ChatBot 嵌入模式
      </button>
    </div>

    <div
      v-show="activeTab === 'full'"
      class="panel-full"
    >
      <div class="controls">
        <button
          type="button"
          @click="showAI"
        >
          显示 AI 小鲸
        </button>
      </div>

      <ai-blueking
        ref="aiBlueking"
        :url="apiUrl"
        @close="onClose"
        @send-message="onSendMessage"
        @show="onShow"
      />
    </div>

    <div
      v-show="activeTab === 'embedded'"
      class="panel-embedded"
    >
      <p class="embedded-desc">将 ChatBotV2 嵌入页面布局（无 Nimbus、无浮窗壳层）</p>
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
  </div>
</template>

<script>
  import AiBlueking, { ChatBotV2 } from '@blueking/ai-blueking/vue2';

  import '@blueking/ai-blueking/dist/vue2/style.css';

  export default {
    name: 'App',
    components: {
      AiBlueking,
      ChatBotV2,
    },
    data() {
      return {
        activeTab: 'full',
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
      showAI() {
        this.$refs.aiBlueking.show();
      },
      onShow() {
        console.log('[Vue2 Playground] AI panel shown');
      },
      onClose() {
        console.log('[Vue2 Playground] AI panel closed');
      },
      onSendMessage(message) {
        console.log('[Vue2 Playground] Message sent:', message);
      },
      onEmbeddedSendMessage(message) {
        console.log('[Vue2 Playground] [ChatBotV2] send-message:', message);
      },
      onEmbeddedError(error) {
        console.error('[Vue2 Playground] [ChatBotV2] error:', error);
      },
    },
  };
</script>

<style>
  * {
    box-sizing: border-box;
    padding: 0;
    margin: 0;
  }

  #vue2-playground {
    padding: 40px;
    font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
  }

  h1 {
    margin-bottom: 8px;
    font-size: 24px;
    color: #313238;
  }

  .desc {
    margin-bottom: 16px;
    font-size: 14px;
    color: #979ba5;
  }

  .tabs {
    display: flex;
    gap: 8px;
    margin-bottom: 20px;
  }

  .tabs button {
    padding: 8px 16px;
    font-size: 14px;
    cursor: pointer;
    background: #f0f1f5;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition: background 0.2s, border-color 0.2s;
  }

  .tabs button.active {
    color: #fff;
    background: #3a84ff;
    border-color: #3a84ff;
  }

  .tabs button:hover:not(.active) {
    border-color: #c4c6cc;
  }

  .controls {
    margin-bottom: 24px;
  }

  .controls button {
    padding: 8px 20px;
    font-size: 14px;
    color: #fff;
    cursor: pointer;
    background: #3a84ff;
    border: none;
    border-radius: 4px;
    transition: background 0.2s;
  }

  .controls button:hover {
    background: #699df4;
  }

  .embedded-desc {
    margin-bottom: 16px;
    font-size: 14px;
    color: #63656e;
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
