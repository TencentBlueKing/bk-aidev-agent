<template>
  <div class="set-input-content-view">
    <div class="view-header">
      <h2>setInputContent</h2>
      <p class="view-desc">
        用一份文本加标签的文档替换输入框，不发送、不清引用。
        <code>AIBlueking</code>
        与
        <code>ChatBot</code>
        都是同一个方法。整篇替换会进入编辑器撤销历史，500ms 内可能和打字合并。
      </p>
    </div>

    <DemoRequestOptionsBar
      :app-id="appId"
      :preview-json="previewJson"
      :tenant-id="tenantId"
      :token="token"
      @rotate-app-id="rotateAppId"
      @rotate-tenant-id="rotateTenantId"
      @rotate-token="rotateToken"
    />

    <div class="control-bar">
      <div class="control-item">
        <span class="control-label">组件模式：</span>
        <div class="radio-group">
          <label
            v-for="mode in modes"
            :key="mode.value"
            class="radio-item"
            :class="{ active: currentMode === mode.value }"
          >
            <input
              v-model="currentMode"
              name="inputMode"
              type="radio"
              :value="mode.value"
            />
            <span class="radio-text">{{ mode.label }}</span>
          </label>
        </div>
      </div>
      <div class="control-item">
        <BkButton
          size="small"
          theme="primary"
          @click="writeHostDoc"
        >
          写入标签文档
        </BkButton>
        <BkButton
          size="small"
          @click="writePlainText"
        >
          写入纯文本
        </BkButton>
        <BkButton
          size="small"
          @click="clearInput"
        >
          清空
        </BkButton>
      </div>
    </div>

    <div class="tips">
      「写入标签文档」后，输入框里应显示
      <code>帮我分析</code>
      和一个「生产服务器」标签芯片，悬停可见描述「上海机房」，而不是纯文本
      <code>@生产服务器</code>
      。
    </div>

    <div class="chatbot-wrapper">
      <AIBlueking
        v-if="currentMode === 'aiblueking'"
        :key="`aiblueking-${instanceKey}`"
        ref="aiBluekingRef"
        :enable-popup="false"
        :request-options="requestOptions"
        :url="apiUrl"
      />
      <ChatBot
        v-else
        :key="`chatbot-${instanceKey}`"
        ref="chatBotRef"
        height="100%"
        :request-options="requestOptions"
        :url="apiUrl"
      />
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref, watch } from 'vue';

  import { AIBlueking, ChatBot, type AIBluekingExpose, type ChatBotExpose } from '@blueking/ai-blueking';
  import { type TagSchema } from '@blueking/chat-x';
  import { Button as BkButton } from 'bkui-vue';

  import DemoRequestOptionsBar from '../components/DemoRequestOptionsBar.vue';
  import { useDemoRequestOptions } from '../composables/use-demo-request-options';

  type DemoMode = 'aiblueking' | 'chatbot';

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const chatBotRef = ref<ChatBotExpose>();
  const aiBluekingRef = ref<AIBluekingExpose>();
  const currentMode = ref<DemoMode>('chatbot');
  const instanceKey = ref(0);

  const modes: Array<{ label: string; value: DemoMode }> = [
    { value: 'chatbot', label: 'ChatBot 独立' },
    { value: 'aiblueking', label: 'AIBlueking' },
  ];

  const { token, appId, tenantId, requestOptions, previewJson, rotateToken, rotateAppId, rotateTenantId } =
    useDemoRequestOptions();

  const hostDoc = (): TagSchema => [
    [
      { type: 'text', text: '帮我分析 ' },
      {
        type: 'tag',
        data: {
          description: '上海机房',
          icon: '',
          label: '生产服务器',
          type: 'hostxxx',
          value: 'host-001',
        },
      },
    ],
  ];

  const writeInput = async (value: string | TagSchema) => {
    if (currentMode.value === 'aiblueking') {
      await aiBluekingRef.value?.show();
      aiBluekingRef.value?.setInputContent(value);
      return;
    }
    chatBotRef.value?.setInputContent(value);
  };

  const writeHostDoc = () => writeInput(hostDoc());
  const writePlainText = () => writeInput('帮我看一下这台机器的负载');
  const clearInput = () => writeInput([[]]);

  watch(currentMode, () => {
    instanceKey.value += 1;
  });
</script>

<style scoped>
  .view-header {
    margin-bottom: 16px;
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
    line-height: 1.6;
    color: #979ba5;
  }

  .view-desc code,
  .tips code {
    padding: 1px 4px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 2px;
  }

  .control-bar {
    display: flex;
    gap: 16px;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 12px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .control-item {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .control-label {
    font-size: 13px;
    color: #63656e;
  }

  .radio-group {
    display: flex;
    gap: 8px;
  }

  .radio-item {
    display: inline-flex;
    gap: 6px;
    align-items: center;
    padding: 4px 10px;
    font-size: 13px;
    color: #63656e;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .radio-item.active {
    color: #3a84ff;
    background: #f0f5ff;
    border-color: #3a84ff;
  }

  .radio-item input {
    display: none;
  }

  .tips {
    padding: 12px 16px;
    margin-bottom: 16px;
    font-size: 13px;
    line-height: 1.6;
    color: #63656e;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .chatbot-wrapper {
    height: 640px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .chatbot-wrapper :deep(.ai-blueking),
  .chatbot-wrapper :deep(.ai-chatbot) {
    height: 100%;
  }
</style>
