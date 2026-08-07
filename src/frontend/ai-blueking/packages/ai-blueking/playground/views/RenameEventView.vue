<template>
  <div class="rename-event-view">
    <div class="view-header">
      <h2>rename 事件</h2>
      <p class="view-desc">
        验证会话自动重命名 / 手动改名时是否触发
        <code>@rename</code>
        。首条消息发送成功后 AI 会调用
        <code>ai_rename</code>
        ，成功时应出现日志。
      </p>
    </div>

    <DemoRequestOptionsBar
      :token="token"
      :app-id="appId"
      :tenant-id="tenantId"
      :preview-json="previewJson"
      @rotate-token="rotateToken"
      @rotate-app-id="rotateAppId"
      @rotate-tenant-id="rotateTenantId"
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
              name="renameMode"
              type="radio"
              :value="mode.value"
            />
            <span class="radio-text">{{ mode.label }}</span>
          </label>
        </div>
      </div>
      <div class="control-item">
        <BkButton
          v-if="currentMode === 'aiblueking'"
          size="small"
          @click="showAIBlueking"
        >
          打开小鲸面板
        </BkButton>
        <BkButton
          size="small"
          theme="primary"
          @click="clearLogs"
        >
          清空日志
        </BkButton>
      </div>
    </div>

    <div class="tips">
      <strong>测试步骤：</strong>
      <ol>
        <li>确保下方是「新会话」（本页开启了 <code>alwaysCreateNewSession</code>）</li>
        <li>发送第一条消息，等待 AI 自动重命名成功</li>
        <li>右侧应出现 <code>rename</code> 日志，payload 含 <code>newName</code> 与 <code>sessionCode</code></li>
        <li>也可在 Header 手动改名，应同样触发 <code>rename</code>（仅 AIBlueking 模式）</li>
      </ol>
    </div>

    <div class="content-area">
      <div class="chatbot-section">
        <div class="section-title">
          {{ currentMode === 'aiblueking' ? 'AIBlueking' : 'ChatBot' }}
          <span class="section-hint">最新会话名：{{ latestName || '（尚未收到 rename）' }}</span>
        </div>
        <div class="chatbot-wrapper">
          <AIBlueking
            v-if="currentMode === 'aiblueking'"
            :key="`aiblueking-${instanceKey}`"
            ref="aiBluekingRef"
            :always-create-new-session="true"
            :enable-popup="false"
            :request-options="requestOptions"
            :url="apiUrl"
            :dropdown-menu-config="{ showRename: true, showAutoGenerate: true, showShare: true }"
            @rename="handleRename"
            @send-message="handleSendMessage"
          />
          <ChatBot
            v-else
            :key="`chatbot-${instanceKey}`"
            ref="chatBotRef"
            :always-create-new-session="true"
            height="100%"
            :request-options="requestOptions"
            :url="apiUrl"
            @rename="handleRename"
            @send-message="handleSendMessage"
            @error="handleError"
          />
        </div>
      </div>

      <div class="log-section">
        <div class="section-title">
          事件日志
          <span
            v-if="logs.length"
            class="log-count"
            >{{ logs.length }}</span
          >
        </div>
        <div class="log-container">
          <div
            v-if="!logs.length"
            class="log-empty"
          >
            暂无事件。发送首条消息或手动改名后，此处会显示日志。
          </div>
          <div
            v-for="(log, index) in logs"
            :key="`${log.time}-${index}`"
            class="log-item"
            :class="`log-item--${log.event}`"
          >
            <div class="log-header">
              <span
                class="log-badge"
                :class="`log-badge--${log.event}`"
                >{{ log.event }}</span
              >
              <span class="log-time">{{ log.time }}</span>
            </div>
            <div class="log-body">
              <div class="log-field">
                <span class="log-field-label">payload:</span>
                <code>{{ log.payload }}</code>
              </div>
              <div class="log-field">
                <span class="log-field-label">mode:</span>
                <code>{{ log.mode }}</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { nextTick, ref, watch } from 'vue';

  import { AIBlueking, ChatBot, type ChatBotExpose } from '@blueking/ai-blueking';
  import { Button as BkButton } from 'bkui-vue';

  import DemoRequestOptionsBar from '../components/DemoRequestOptionsBar.vue';
  import { useDemoRequestOptions } from '../composables/use-demo-request-options';

  type DemoMode = 'aiblueking' | 'chatbot';

  interface EventLog {
    event: 'rename' | 'send-message' | 'error';
    time: string;
    payload: string;
    mode: DemoMode;
  }

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const chatBotRef = ref<ChatBotExpose>();
  const aiBluekingRef = ref<InstanceType<typeof AIBlueking>>();
  const currentMode = ref<DemoMode>('chatbot');
  const instanceKey = ref(0);
  const latestName = ref('');
  const logs = ref<EventLog[]>([]);

  const modes: Array<{ value: DemoMode; label: string }> = [
    { value: 'chatbot', label: 'ChatBot 独立' },
    { value: 'aiblueking', label: 'AIBlueking' },
  ];

  const { token, appId, tenantId, requestOptions, previewJson, rotateToken, rotateAppId, rotateTenantId } =
    useDemoRequestOptions();

  const getTimestamp = () => {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;
  };

  const pushLog = (event: EventLog['event'], payload: string) => {
    logs.value.unshift({
      event,
      time: getTimestamp(),
      payload,
      mode: currentMode.value,
    });
  };

  const handleRename = (newName: string, sessionCode?: string) => {
    console.log('[RenameEvent] @rename:', { newName, sessionCode });
    latestName.value = newName;
    pushLog('rename', JSON.stringify({ newName, sessionCode }));
  };

  const handleSendMessage = (message: string) => {
    console.log('[RenameEvent] @send-message:', message);
    pushLog('send-message', message);
  };

  const handleError = (error: Error) => {
    console.error('[RenameEvent] @error:', error);
    pushLog('error', error.message);
  };

  const clearLogs = () => {
    logs.value = [];
    latestName.value = '';
  };

  const showAIBlueking = async () => {
    await nextTick();
    aiBluekingRef.value?.handleShow?.();
  };

  watch(currentMode, async () => {
    instanceKey.value += 1;
    clearLogs();
    if (currentMode.value === 'aiblueking') {
      await nextTick();
      await showAIBlueking();
    }
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

  .view-desc code {
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

  .tips ol {
    margin: 6px 0 0;
    padding-left: 20px;
  }

  .tips code {
    padding: 1px 4px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 2px;
  }

  .content-area {
    display: flex;
    gap: 16px;
    height: 640px;
  }

  .chatbot-section {
    display: flex;
    flex: 1;
    flex-direction: column;
    min-width: 0;
  }

  .section-title {
    display: flex;
    gap: 12px;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 500;
    color: #313238;
  }

  .section-hint {
    font-size: 12px;
    font-weight: 400;
    color: #979ba5;
  }

  .chatbot-wrapper {
    flex: 1;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .chatbot-wrapper :deep(.ai-blueking),
  .chatbot-wrapper :deep(.ai-chatbot) {
    height: 100%;
  }

  .log-section {
    display: flex;
    flex-direction: column;
    width: 380px;
  }

  .log-count {
    display: inline-flex;
    align-items: center;
    justify-content: center;
    min-width: 20px;
    height: 18px;
    padding: 0 6px;
    font-size: 11px;
    color: #fff;
    background: #3a84ff;
    border-radius: 9px;
  }

  .log-container {
    flex: 1;
    padding: 12px;
    overflow-y: auto;
    background: #1a1a2e;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .log-empty {
    font-size: 13px;
    color: #63656e;
    text-align: center;
  }

  .log-item {
    padding: 10px 12px;
    margin-bottom: 8px;
    background: rgb(58 132 255 / 12%);
    border-radius: 4px;
  }

  .log-item--rename {
    background: rgb(45 164 78 / 15%);
  }

  .log-item--error {
    background: rgb(234 54 54 / 15%);
  }

  .log-header {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 6px;
  }

  .log-badge {
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 600;
    color: #fff;
    background: #3a84ff;
    border-radius: 2px;
  }

  .log-badge--rename {
    background: #2da44e;
  }

  .log-badge--error {
    background: #ea3636;
  }

  .log-time {
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #979ba5;
  }

  .log-body {
    padding-left: 4px;
  }

  .log-field {
    margin-bottom: 4px;
  }

  .log-field-label {
    font-size: 12px;
    color: #979ba5;
  }

  .log-field code {
    padding: 1px 4px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #e0e0e0;
    word-break: break-all;
    background: rgb(255 255 255 / 8%);
    border-radius: 2px;
  }
</style>
