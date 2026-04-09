<template>
  <div class="url-switch-view">
    <div class="view-header">
      <h2>URL 动态切换</h2>
      <p class="view-desc">测试运行时切换 API URL，验证 ChatBot 自动重新初始化（destroy → recreate → reinit）</p>
    </div>

    <div class="control-bar">
      <div class="url-indicator">
        <span :class="['status-dot', { ready: isReady }]" />
        <span class="url-label">{{ isReady ? '当前 URL：' : '初始化中：' }}</span>
        <code class="url-value">{{ activeUrl || '(空)' }}</code>
      </div>
      <div class="switch-control">
        <span :class="['env-tag', { active: !useAlternative }]">默认环境</span>
        <BkSwitcher
          v-model="useAlternative"
          size="small"
          theme="primary"
        />
        <span :class="['env-tag', { active: useAlternative }]">备选环境</span>
      </div>
    </div>

    <div class="chatbot-area">
      <ChatBot
        height="600px"
        :url="activeUrl"
        @agent-info-loaded="handleAgentInfoLoaded"
        @error="handleError"
        @send-message="handleSendMessage"
      />
    </div>
    <AIBlueking :url="activeUrl" />
  </div>
</template>

<script setup lang="ts">
  import { computed, ref, watch } from 'vue';

  import { ChatBot } from '@blueking/ai-blueking';
  import { AIBlueking } from '@blueking/ai-blueking';
  import { Switcher as BkSwitcher } from 'bkui-vue';

  const defaultUrl = import.meta.env.VITE_API_URL || '';
  const alternativeUrl = import.meta.env.VITE_ALTERNATIVE_API_URL || '';

  const useAlternative = ref(false);
  const isReady = ref(false);

  const activeUrl = computed(() => (useAlternative.value ? alternativeUrl : defaultUrl));

  watch(activeUrl, () => {
    isReady.value = false;
  });

  const handleSendMessage = (message: string) => {
    console.log('[UrlSwitch] send:', message);
  };

  const handleError = (error: Error) => {
    console.error('[UrlSwitch] error:', error);
    isReady.value = false;
  };

  const handleAgentInfoLoaded = (helper: unknown) => {
    console.log('[UrlSwitch] agent-info-loaded, new helper:', helper);
    isReady.value = true;
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
    gap: 24px;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
    transition: border-color 0.3s ease;
  }

  .url-indicator {
    display: flex;
    gap: 8px;
    align-items: center;
    min-width: 0;
    overflow: hidden;
  }

  .status-dot {
    flex-shrink: 0;
    width: 8px;
    height: 8px;
    background: #ff9c01;
    border-radius: 50%;
    transition: background-color 0.3s ease;
    animation: status-pulse 1.5s ease-in-out infinite;
  }

  .status-dot.ready {
    background: #2dcb56;
    animation: none;
  }

  @keyframes status-pulse {
    0%,
    100% {
      opacity: 1;
    }

    50% {
      opacity: 0.4;
    }
  }

  .url-label {
    flex-shrink: 0;
    font-size: 13px;
    color: #63656e;
    transition: color 0.2s ease;
  }

  .url-value {
    padding: 2px 8px;
    overflow: hidden;
    text-overflow: ellipsis;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #3a84ff;
    white-space: nowrap;
    background: #f0f5ff;
    border-radius: 2px;
    transition:
      color 0.2s ease,
      background-color 0.2s ease;
  }

  .switch-control {
    display: flex;
    flex-shrink: 0;
    gap: 8px;
    align-items: center;
  }

  .env-tag {
    font-size: 12px;
    color: #979ba5;
    transition: color 0.2s;
  }

  .env-tag.active {
    font-weight: 500;
    color: #313238;
  }

  .chatbot-area {
    display: flex;
    height: 600px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }
</style>
