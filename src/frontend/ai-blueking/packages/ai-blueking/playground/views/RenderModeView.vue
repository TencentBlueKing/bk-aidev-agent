<template>
  <div class="render-mode-view">
    <div class="view-header">
      <h2>RenderMode 渲染模式</h2>
      <p class="view-desc">切换 renderMode 查看不同模式下的表现，test 模式下 Header 的「分享会话」不显示</p>
    </div>

    <div class="control-bar">
      <label class="control-label">renderMode：</label>
      <div class="radio-group">
        <label
          v-for="mode in modes"
          :key="mode.value"
          class="radio-item"
          :class="{ active: currentMode === mode.value }"
        >
          <input
            v-model="currentMode"
            name="renderMode"
            type="radio"
            :value="mode.value"
          />
          <span class="radio-dot" />
          <span class="radio-text">{{ mode.label }}</span>
          <span class="radio-desc">{{ mode.desc }}</span>
        </label>
      </div>
    </div>

    <AIBlueking
      :key="currentMode"
      :render-mode="currentMode"
      :url="apiUrl"
      :dropdown-menu-config="{ showRename: true, showAutoGenerate: true, showShare: true }"
      @close="handleClose"
      @show="handleShow"
    />
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import AIBlueking from '@blueking/ai-blueking';
  import { RenderMode } from '@blueking/ai-blueking';

  const apiUrl = ref(import.meta.env.VITE_API_URL || '');

  const modes = [
    { value: RenderMode.Chat, label: 'Chat', desc: '默认模式' },
    { value: RenderMode.Test, label: 'Test', desc: '测试模式（隐藏分享按钮）' },
    { value: RenderMode.Share, label: 'Share', desc: '分享模式' },
  ];

  const currentMode = ref<RenderMode>(RenderMode.Chat);

  const handleShow = () => {
    console.log('[RenderMode] AIBlueking shown, mode:', currentMode.value);
  };

  const handleClose = () => {
    console.log('[RenderMode] AIBlueking closed');
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

  .control-bar {
    display: flex;
    gap: 12px;
    align-items: flex-start;
    padding: 16px 20px;
    margin-bottom: 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
  }

  .control-label {
    flex-shrink: 0;
    padding-top: 6px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .radio-group {
    display: flex;
    flex-direction: column;
    gap: 8px;
  }

  .radio-item {
    display: flex;
    gap: 6px;
    align-items: center;
    padding: 6px 12px;
    font-size: 13px;
    cursor: pointer;
    border-radius: 4px;
    transition: background 0.15s;
  }

  .radio-item:hover {
    background: #f0f5ff;
  }

  .radio-item.active {
    background: #e1ecff;
  }

  .radio-item input {
    display: none;
  }

  .radio-dot {
    width: 14px;
    height: 14px;
    border: 2px solid #c4c6cc;
    border-radius: 50%;
    transition: all 0.15s;
  }

  .radio-item.active .radio-dot {
    border-color: #3a84ff;
    border-width: 4px;
  }

  .radio-text {
    font-weight: 500;
    color: #313238;
  }

  .radio-desc {
    font-size: 12px;
    color: #979ba5;
  }
</style>
