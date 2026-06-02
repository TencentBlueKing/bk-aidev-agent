<template>
  <div class="request-options-view">
    <div class="view-header">
      <h2>requestOptions 响应式</h2>
      <p class="view-desc">
        演示 <code>requestOptions</code> 的 headers / data / context 支持 ref、computed 与动态替换。 GET 请求将
        <code>data</code> 转为 query；POST 写入 body。 <code>context</code> 会合并到消息的
        <code>property.extra.context</code>，与 shortcuts 表单数据同级。
      </p>
    </div>

    <DemoRequestOptionsBar
      :token="token"
      :app-id="appId"
      :tenant-id="tenantId"
      :context-env="contextEnv"
      :context-region="contextRegion"
      :preview-json="previewJson"
      @rotate-token="rotateToken"
      @rotate-app-id="rotateAppId"
      @rotate-tenant-id="rotateTenantId"
      @rotate-context-env="rotateContextEnv"
      @rotate-context-region="rotateContextRegion"
    />

    <section class="demo-section">
      <h3 class="section-title">集成模式 · AIBlueking</h3>
      <AIBlueking
        :enable-popup="true"
        :request-options="requestOptions"
        :url="apiUrl"
      />
    </section>

    <section class="demo-section">
      <h3 class="section-title">独立模式 · ChatBot</h3>
      <p class="section-desc">
        便于在 Network 面板观察 GET query 与 POST body，切换上方按钮后刷新会话或发消息即可验证。
      </p>
      <div class="chatbot-area">
        <ChatBot
          height="560px"
          :use-agent-name="true"
          :request-options="requestOptions"
          :url="apiUrl"
          @error="handleError"
        />
      </div>
    </section>

    <section class="demo-section code-section">
      <h3 class="section-title">参考代码</h3>
      <pre class="code-sample">{{ sampleCode }}</pre>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { ChatBot, AIBlueking } from '@blueking/ai-blueking';

  import DemoRequestOptionsBar from '../components/DemoRequestOptionsBar.vue';
  import { useDemoRequestOptions } from '../composables/use-demo-request-options';

  const apiUrl = import.meta.env.VITE_API_URL || '';

  const {
    token,
    appId,
    tenantId,
    contextEnv,
    contextRegion,
    requestOptions,
    previewJson,
    rotateToken,
    rotateAppId,
    rotateTenantId,
    rotateContextEnv,
    rotateContextRegion,
  } = useDemoRequestOptions();

  const sampleCode = `import { computed, ref } from 'vue';
import { AIBlueking, type IRequestOptions } from '@blueking/ai-blueking';

const token = ref('token-alpha');
const appId = ref('playground-app');
const contextEnv = ref('prod');

const requestOptions = computed<IRequestOptions>(() => ({
  headers: { Authorization: \`Bearer \${token.value}\` },
  data: { app_id: appId.value },
  // context 合并到消息的 property.extra.context（与 shortcuts 同级）
  context: { env: contextEnv.value },
}));

// headers → HTTP headers
// data: GET → ?app_id=... ；POST → body 合并 app_id
// context → 消息 property.extra.context（动态生效，发消息时取最新值）
<AIBlueking :url="apiUrl" :request-options="requestOptions" />`;

  const handleError = (error: Error) => {
    console.error('[RequestOptions] error:', error);
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
    line-height: 1.6;
    color: #979ba5;
  }

  .view-desc code {
    padding: 1px 4px;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 2px;
  }

  .demo-section {
    margin-bottom: 32px;
  }

  .section-title {
    margin: 0 0 8px;
    font-size: 15px;
    font-weight: 600;
    color: #313238;
  }

  .section-desc {
    margin: 0 0 12px;
    font-size: 12px;
    color: #979ba5;
  }

  .chatbot-area {
    display: flex;
    height: 560px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .code-sample {
    padding: 12px 16px;
    margin: 0;
    overflow: auto;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    line-height: 1.5;
    color: #63656e;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }
</style>
