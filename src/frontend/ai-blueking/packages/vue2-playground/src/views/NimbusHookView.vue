<template>
  <div class="nimbus-hook-view">
    <div class="view-header">
      <h2>Nimbus 点击自定义</h2>
      <p class="view-desc">通过 beforeNimbusClick 钩子拦截 Nimbus 点击，自定义打开行为</p>
    </div>

    <div class="controls">
      <button
        type="button"
        @click="showHookAI"
      >
        显示 AI 小鲸
      </button>
      <label class="toggle-label">
        <input
          v-model="nimbusHookBlock"
          type="checkbox"
        />
        阻止默认打开（return false）
      </label>
    </div>

    <ai-blueking
      ref="hookAIBlueking"
      :url="apiUrl"
      :before-nimbus-click="handleBeforeNimbusClick"
      @close="onClose"
      @send-message="onSendMessage"
      @show="onShow"
    />
  </div>
</template>

<script>
  import AiBlueking from '@blueking/ai-blueking/vue2';

  export default {
    name: 'NimbusHookView',
    components: { AiBlueking },
    data() {
      return {
        apiUrl: import.meta.env.VITE_API_URL || '',
        nimbusHookBlock: true,
      };
    },
    methods: {
      showHookAI() {
        this.$refs.hookAIBlueking.show();
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
      async handleBeforeNimbusClick() {
        console.log('[Vue2 Playground] beforeNimbusClick triggered');
        if (this.nimbusHookBlock) {
          console.log('[Vue2 Playground] 阻止默认 showPanel，手动调用 switchToSession + show');
          this.$refs.hookAIBlueking.switchToSession('new_session_1775618757894');
          this.$refs.hookAIBlueking.show('new_session_1775618757894');
          return false;
        }
        console.log('[Vue2 Playground] 允许默认 showPanel');
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

  .toggle-label {
    display: inline-flex;
    align-items: center;
    gap: 4px;
    margin-left: 16px;
    font-size: 14px;
    color: #63656e;
    cursor: pointer;
  }

  .toggle-label input[type='checkbox'] {
    cursor: pointer;
  }
</style>
