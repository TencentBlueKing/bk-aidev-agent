<template>
  <div class="example-container">
    <h2>高级用法示例</h2>
    <p>编程式调用 AIBlueking 暴露的方法</p>

    <div class="controls">
      <button @click="handleShowPanel">打开面板</button>
      <button @click="handleSendMessage">发送消息</button>
      <button @click="handleStopGeneration">停止生成</button>
      <button @click="handleSetCiteText">设置引用文本</button>
    </div>

    <!-- 编程式触发快捷指令示例 -->
    <div class="shortcut-section">
      <h3>编程式触发快捷指令</h3>
      <p class="hint">
        等价于旧版 <code>window.aiBlueking.handleShortcutClick</code>， 新版通过 <code>selectShortcut</code> /
        <code>sendShortcut</code> 实现。
      </p>

      <div class="controls">
        <button @click="triggerShortcutShowForm">显示表单（用户手动提交）</button>
        <button @click="triggerShortcutWithPrefill">预填充表单（用户手动提交）</button>
        <button
          class="btn-success"
          @click="triggerShortcutDirectSend"
        >
          预填充 + 直接发送
        </button>
      </div>

      <div class="code-block">
        <pre><code>// === 旧版用法（已废弃） ===
const command = window.aiBlueking.agentInfo?.conversationSettings?.commands?.[0];
window.aiBlueking.handleShow(undefined, { isTemporary: true });
window.aiBlueking.handleShortcutClick({ shortcut: command, source: 'popup' }, true);

// === 新版用法（AIBlueking 集成模式） ===

// 方式 1：selectShortcut — 显示表单，用户手动提交
const chatHelper = aiBluekingRef.value?.getChatHelper?.();
const command = chatHelper?.agent.info.value?.conversationSettings?.commands?.[0];
await aiBluekingRef.value?.show(undefined, { isTemporary: true });
aiBluekingRef.value?.selectShortcut(command, '预填充文本');

// 方式 2：sendShortcut — 预填充 + 直接发送（等价旧版 handleShortcutClick(_, true)）
const modifiedCommand = {
  ...originalCommand,
  components: originalCommand.components.map((comp, i) => ({
    ...comp,
    default: i === 0 ? sql : i === 1 ? errorMessage : comp.default,
  })),
};
await aiBluekingRef.value?.show(undefined, { isTemporary: true });
await aiBluekingRef.value?.sendShortcut(modifiedCommand);</code></pre>
      </div>
    </div>

    <!-- AIBlueking 组件实例 -->
    <AIBlueking
      ref="aiBluekingRef"
      :enable-chat-session="true"
      :enable-popup="true"
      :resize-props="{ min: 300, max: 600, initialDivide: 350 }"
      :url="apiUrl"
      @close="() => console.log('[Advanced] closed')"
      @show="() => console.log('[Advanced] shown')"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import AIBlueking from '../ai-blueking.vue';

  import type { AIBluekingExpose } from '../types';

  const apiUrl = import.meta.env.VITE_API_URL || '';

  // AIBlueking 组件 ref
  const aiBluekingRef = ref<AIBluekingExpose>();

  // ==================== 基础操作 ====================

  const handleShowPanel = async () => {
    if (!aiBluekingRef.value) {
      console.error('AIBlueking ref 未绑定');
      return;
    }
    await aiBluekingRef.value.show();
  };

  const handleSendMessage = async () => {
    if (!aiBluekingRef.value) {
      console.error('AIBlueking ref 未绑定');
      return;
    }
    await aiBluekingRef.value.sendMessage('这是一条编程式发送的消息');
  };

  const handleStopGeneration = () => {
    aiBluekingRef.value?.stopGeneration();
  };

  const handleSetCiteText = () => {
    aiBluekingRef.value?.setCiteText('这是引用的文本内容');
    aiBluekingRef.value?.show();
  };

  // ==================== 编程式触发快捷指令 ====================

  /** 辅助：获取第一个快捷指令 */
  const getFirstCommand = () => {
    const chatHelper = aiBluekingRef.value?.getChatHelper?.();
    const commands = chatHelper?.agent.info.value?.conversationSettings?.commands;
    return commands?.[0];
  };

  /**
   * 方式 1：显示表单，用户手动提交
   *
   * 等价旧版：handleShortcutClick({ shortcut, source: 'popup' }, false)
   */
  const triggerShortcutShowForm = async () => {
    if (!aiBluekingRef.value) return;

    const originalCommand = getFirstCommand();
    if (!originalCommand?.components) {
      console.error('AI 命令配置不完整，请确认 Agent 已初始化且配置了 commands');
      return;
    }

    await aiBluekingRef.value.show(undefined, { isTemporary: true });
    aiBluekingRef.value.selectShortcut(originalCommand);
  };

  /**
   * 方式 2：预填充表单字段，用户手动提交
   *
   * 深拷贝 command 修改 components.default 后传入 selectShortcut
   */
  const triggerShortcutWithPrefill = async () => {
    if (!aiBluekingRef.value) return;

    const originalCommand = getFirstCommand();
    if (!originalCommand?.components) {
      console.error('AI 命令配置不完整，请确认 Agent 已初始化且配置了 commands');
      return;
    }

    const command = {
      ...originalCommand,
      components: originalCommand.components.map((comp, index) => ({
        ...comp,
        default: index === 0 ? '预填充的 SQL 内容' : index === 1 ? '预填充的错误信息' : comp.default,
      })),
    };

    await aiBluekingRef.value.show(undefined, { isTemporary: true });
    aiBluekingRef.value.selectShortcut(command, '');
  };

  /**
   * 方式 3：预填充 + 直接发送（等价旧版 handleShortcutClick(_, true)）
   *
   * 使用 sendShortcut 跳过表单，直接用 components.default 构建 formModel 发送
   */
  const triggerShortcutDirectSend = async () => {
    if (!aiBluekingRef.value) return;

    const originalCommand = getFirstCommand();
    if (!originalCommand?.components) {
      console.error('AI 命令配置不完整，请确认 Agent 已初始化且配置了 commands');
      return;
    }

    // 深拷贝并修改 default（与旧版逻辑一致）
    const command = {
      ...originalCommand,
      components: originalCommand.components.map((comp, index) => ({
        ...comp,
        default: index === 0 ? '预填充的 SQL 内容' : index === 1 ? '预填充的错误信息' : comp.default,
      })),
    };

    // 先打开面板
    await aiBluekingRef.value.show(undefined, { isTemporary: true });

    // 直接发送，跳过表单
    await aiBluekingRef.value.sendShortcut(command, '');
  };
</script>

<style scoped>
  .example-container {
    padding: 24px;
  }

  .controls {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    margin-bottom: 20px;
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

  .btn-success {
    background: #2dcb56;
  }

  .btn-success:hover {
    background: #45d469;
  }

  .shortcut-section {
    padding: 20px;
    margin-bottom: 24px;
    background: #f0f5ff;
    border: 1px solid #d4e8ff;
    border-radius: 4px;
  }

  .shortcut-section h3 {
    margin: 0 0 8px;
    color: #313238;
  }

  .hint {
    margin: 0 0 16px;
    font-size: 13px;
    color: #63656e;
  }

  .hint code {
    padding: 2px 6px;
    font-size: 12px;
    color: #ff9c01;
    background: #fff4e2;
    border-radius: 2px;
  }

  .code-block {
    margin-top: 16px;
    overflow-x: auto;
  }

  .code-block pre {
    padding: 16px;
    margin: 0;
    font-size: 12px;
    line-height: 1.6;
    color: #313238;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }
</style>
