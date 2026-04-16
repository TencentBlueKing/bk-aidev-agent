<template>
  <div class="error-handling-view">
    <div class="view-header">
      <h2>错误处理</h2>
      <p class="view-desc">演示接口错误捕获机制，使用不存在的 URL 触发请求失败，业务方可通过 @sdk-error 自定义处理</p>
    </div>

    <div class="control-bar">
      <div class="control-item">
        <span class="control-label">当前 URL：</span>
        <code class="url-value">{{ invalidUrl }}</code>
        <span class="control-hint">（不存在的地址，必定报错）</span>
      </div>
      <div class="control-item">
        <BkButton
          theme="primary"
          size="small"
          @click="clearLogs"
        >
          清空日志
        </BkButton>
      </div>
    </div>

    <div class="content-area">
      <div class="chatbot-section">
        <div class="section-title">AIBlueking 组件</div>
        <div class="chatbot-wrapper">
          <AIBlueking
            :url="invalidUrl"
            @sdk-error="handleSdkError"
          />
        </div>
      </div>

      <div class="log-section">
        <div class="section-title">
          sdk-error 日志
          <span
            v-if="errorLogs.length"
            class="log-count"
          >{{ errorLogs.length }}</span>
        </div>
        <div class="log-container">
          <div
            v-if="!errorLogs.length"
            class="log-empty"
          >
            暂无错误，组件初始化后将在此显示捕获的错误...
          </div>
          <div
            v-for="(log, index) in errorLogs"
            :key="index"
            class="log-item"
          >
            <div class="log-header">
              <span class="log-badge">sdk-error</span>
              <span class="log-time">{{ log.time }}</span>
            </div>
            <div class="log-body">
              <div class="log-field">
                <span class="log-field-label">apiName:</span>
                <code>{{ log.data.apiName }}</code>
              </div>
              <div class="log-field">
                <span class="log-field-label">code:</span>
                <code>{{ log.data.code }}</code>
              </div>
              <div class="log-field">
                <span class="log-field-label">message:</span>
                <code>{{ log.data.message }}</code>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
  import { ref } from 'vue';

  import { AIBlueking } from '@blueking/ai-blueking';
  import { Button as BkButton } from 'bkui-vue';

  // 使用一个不存在的 URL，必定触发接口错误
  const invalidUrl = 'https://ai-blueking.example.com/api/invalid-endpoint';

  interface SdkErrorData {
    apiName: string;
    code: number;
    message: string;
    data: unknown;
  }

  interface ErrorLog {
    time: string;
    data: SdkErrorData;
  }

  const errorLogs = ref<ErrorLog[]>([]);

  const getTimestamp = () => {
    const now = new Date();
    return `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}:${now.getSeconds().toString().padStart(2, '0')}.${now.getMilliseconds().toString().padStart(3, '0')}`;
  };

  // 监听 @sdk-error 事件 — AIBlueking 统一的错误输出
  const handleSdkError = (data: SdkErrorData) => {
    console.error('[ErrorHandling] @sdk-error:', data);
    errorLogs.value.unshift({
      time: getTimestamp(),
      data,
    });
  };

  const clearLogs = () => {
    errorLogs.value = [];
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
    gap: 16px;
    align-items: center;
    justify-content: space-between;
    padding: 12px 16px;
    margin-bottom: 16px;
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

  .control-hint {
    font-size: 12px;
    color: #ea3636;
  }

  .url-value {
    padding: 2px 8px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #ea3636;
    background: #ffeeee;
    border-radius: 2px;
  }

  .content-area {
    display: flex;
    gap: 16px;
    height: 600px;
  }

  .chatbot-section {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-width: 0;
  }

  .section-title {
    display: flex;
    gap: 8px;
    align-items: center;
    margin-bottom: 8px;
    font-size: 14px;
    font-weight: 500;
    color: #313238;
  }

  .chatbot-wrapper {
    flex: 1;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .log-section {
    display: flex;
    flex-direction: column;
    width: 420px;
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
    background: #ea3636;
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
    background: rgb(234 54 54 / 15%);
    border-radius: 4px;
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
    background: #ea3636;
    border-radius: 2px;
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
    background: rgb(255 255 255 / 8%);
    border-radius: 2px;
  }
</style>
