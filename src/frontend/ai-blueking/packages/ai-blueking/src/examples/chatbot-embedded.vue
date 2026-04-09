<template>
  <div class="example-container">
    <h2>ChatBot 嵌入使用示例</h2>
    <p>将 ChatBot 嵌入到任意页面中使用（无 Nimbus、无浮窗、无拖拽）</p>

    <div class="page-layout">
      <!-- 左侧边栏 -->
      <div class="sidebar">
        <h3>页面导航</h3>
        <ul>
          <li>首页</li>
          <li>设置</li>
          <li>关于</li>
        </ul>
      </div>

      <!-- 主内容区 -->
      <div class="main-content">
        <h3>主内容区域</h3>
        <p>这是主内容区域，可以放置任何内容。</p>

        <!-- 嵌入 ChatBot -->
        <div class="chatbot-wrapper">
          <ChatBot
            ref="chatBotRef"
            :url="apiUrl"
            title="AI 助手"
            :shortcuts="shortcuts"
            height="600px"
            @send-message="handleSendMessage"
            @error="handleError"
          />
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';
import { ChatBot } from '../components';
import type { IShortcut } from '../types';

const apiUrl = import.meta.env.VITE_API_URL || '';
const chatBotRef = ref<InstanceType<typeof ChatBot>>();

// 快捷方式配置
const shortcuts = ref<IShortcut[]>([
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
]);

// 事件处理
const handleSendMessage = (message: string) => {
  console.log('发送消息:', message);
};

const handleError = (error: Error) => {
  console.error('ChatBot 错误:', error);
};
</script>

<style scoped>
.example-container {
  padding: 24px;
}

.page-layout {
  display: flex;
  gap: 24px;
  margin-top: 20px;
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
  list-style: none;
  padding: 0;
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
}

.main-content h3 {
  margin-top: 0;
}

.chatbot-wrapper {
  margin-top: 20px;
  border: 1px solid #dcdee5;
  border-radius: 2px;
  overflow: hidden;
}
</style>













