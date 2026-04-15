<template>
  <div class="full-view">
    <div class="view-header">
      <h2>AIBlueking 完整模式</h2>
      <p class="view-desc">完整的 AIBlueking 组件，包含 Nimbus 悬浮球、拖拽窗口等功能</p>
    </div>

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
</template>

<script>
  import AiBlueking from '@blueking/ai-blueking/vue2';

  export default {
    name: 'FullView',
    components: { AiBlueking },
    data() {
      return {
        apiUrl: import.meta.env.VITE_API_URL || '',
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
</style>
