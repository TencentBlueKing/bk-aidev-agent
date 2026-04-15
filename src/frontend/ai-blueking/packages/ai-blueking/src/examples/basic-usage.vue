<template>
  <div class="example-container">
    <h2>基础使用示例 - 完整小鲸组件</h2>
    <p>包含 Nimbus 悬浮球、选中文本弹窗、拖拽功能</p>

    <!-- 使用完整的 AIBlueking 组件 -->
    <AIBlueking ref="aiBluekingRef" :draggable="true" :enable-popup="true" :shortcuts="shortcuts" title="AI 助手"
      :url="apiUrl" @send-message="handleSendMessage" @shortcut-click="handleShortcutClick" />

    <div class="controls">
      <button @click="showAI">显示小鲸</button>
      <button @click="hideAI">隐藏小鲸</button>
      <button @click="sendTestMessage">发送测试消息</button>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue';

import AIBlueking from '../vue3';

import type { IShortcut } from '../types';

const apiUrl = import.meta.env.VITE_API_URL || '';
const aiBluekingRef = ref<InstanceType<typeof AIBlueking>>();

// 快捷方式配置
const shortcuts = ref<IShortcut[]>([
  {
    id: 'translate',
    name: '翻译',
    icon: 'translate',
    prompt: '请帮我翻译以下内容：',
  },
  {
    id: 'summarize',
    name: '总结',
    icon: 'summarize',
    prompt: '请帮我总结以下内容：',
  },
  {
    id: 'explain',
    name: '解释',
    icon: 'explain',
    prompt: '请帮我解释以下内容：',
  },
]);

// 事件处理
const handleSendMessage = (message: string) => {
  console.log('发送消息:', message);
};

const handleShortcutClick = (data: { shortcut: IShortcut; source: string }) => {
  console.log('快捷方式点击:', data);
};

// 控制方法
const showAI = () => {
  aiBluekingRef.value?.handleShow();
};

const hideAI = () => {
  aiBluekingRef.value?.handleClose();
};

const sendTestMessage = () => {
  aiBluekingRef.value?.sendMessage('你好，这是一条测试消息');
};
</script>

<style scoped>
.example-container {
  padding: 24px;
}

.controls {
  display: flex;
  gap: 12px;
  margin-top: 20px;
}

button {
  padding: 8px 16px;
  color: #fff;
  cursor: pointer;
  background: #3a84ff;
  border: none;
  border-radius: 2px;
}

button:hover {
  background: #5594fa;
}
</style>
