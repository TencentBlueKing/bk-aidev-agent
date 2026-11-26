<template>
  <div class="welcome-context-view">
    <div class="view-header">
      <div class="view-header-row">
        <div>
          <h2>动态上下文 + 欢迎快捷按钮（方案 A）</h2>
          <p class="view-desc">
            演示「<strong>#welcome 欢迎区动态按钮</strong> + <strong>computed requestOptions.context</strong>」组合：
            打开小鲸即可看到 <code>分析 &#123;trace_id&#125; 的日志</code> 按钮；点击或直接问「日志分析」时，
            <code>trace_id</code> 会随用户消息写入 <code>property.extra.context</code> 交给后台二开组装 Prompt。
          </p>
        </div>
        <SourceGuideDialog
          button-text="查看 / 复制完整代码"
          title="动态上下文 + 欢迎按钮（方案 A）：前后端接入文档"
          :sections="welcomeContextGuideSections"
        />
      </div>
    </div>

    <!-- ==================== 一、交互效果预览 ==================== -->
    <section class="workbench">
      <!-- 左侧：模拟业务页面 + 实时请求载荷 -->
      <div class="business-panel">
        <div class="panel-card">
          <div class="card-head">
            <h3>1. 模拟业务页：选择当前查看的 Trace</h3>
            <button
              class="text-action-btn"
              type="button"
              @click="clearTrace"
            >
              清空上下文
            </button>
          </div>
          <p class="card-hint">
            切换下方 Trace，观察右侧小鲸欢迎区的快捷按钮文案和下方 <code>property.extra.context</code> 载荷实时变化。
          </p>

          <div class="trace-list">
            <button
              v-for="item in TRACE_SAMPLES"
              :key="item.id"
              class="trace-item"
              :class="{ 'is-active': selectedTraceId === item.id }"
              type="button"
              @click="selectPresetTrace(item)"
            >
              <div class="trace-item-top">
                <code class="trace-id">{{ item.id }}</code>
                <span
                  class="trace-badge"
                  :class="`is-${item.status}`"
                >
                  {{ item.status === 'error' ? '异常' : '慢查询' }} · {{ item.duration }}
                </span>
              </div>
              <div class="trace-meta">
                <span class="trace-service">{{ item.service }}</span>
                <span class="trace-summary">{{ item.summary }}</span>
              </div>
            </button>
          </div>

          <div class="custom-trace-row">
            <label
              class="custom-trace-label"
              for="custom-trace-input"
            >
              自定义 Trace ID：
            </label>
            <input
              id="custom-trace-input"
              v-model.trim="customTraceInput"
              class="custom-trace-input"
              placeholder="输入任意 trace_id（如 trace-2026-xyz）"
              type="text"
              @input="applyCustomTrace"
            />
          </div>
        </div>

        <div class="panel-card">
          <div class="card-head">
            <h3>2. 实时载荷预览（POST session_content/）</h3>
            <span class="status-pill">
              {{ activeTraceId ? `trace_id = ${activeTraceId}` : '无页面上下文' }}
            </span>
          </div>
          <p class="card-hint">
            点击欢迎按钮或手输「日志分析」时，前端实际写入用户消息的 <code>property.extra.context</code> 如下：
          </p>
          <pre class="payload-preview"><code>{{ livePayloadPreview }}</code></pre>
        </div>

        <div
          v-if="actionLogs.length"
          class="panel-card"
        >
          <div class="card-head">
            <h3>3. 触发日志</h3>
            <button
              class="text-action-btn"
              type="button"
              @click="actionLogs = []"
            >
              清空日志
            </button>
          </div>
          <ul class="action-log-list">
            <li
              v-for="(log, index) in actionLogs"
              :key="index"
            >
              <span class="log-time">{{ log.time }}</span>
              <span class="log-text">{{ log.message }}</span>
            </li>
          </ul>
        </div>
      </div>

      <!-- 右侧：小鲸效果预览 -->
      <div class="ai-preview-panel">
        <div class="preview-toolbar">
          <div class="mode-switch">
            <span class="toolbar-label">渲染模式：</span>
            <label
              v-for="mode in demoModes"
              :key="mode.value"
              class="mode-option"
              :class="{ 'is-active': currentMode === mode.value }"
            >
              <input
                v-model="currentMode"
                name="welcomeDemoMode"
                type="radio"
                :value="mode.value"
              />
              {{ mode.label }}
            </label>
          </div>
          <div class="toolbar-actions">
            <BkButton
              v-if="currentMode === 'aiblueking'"
              size="small"
              theme="primary"
              @click="openFloatingPanel"
            >
              打开小鲸浮窗
            </BkButton>
            <BkButton
              size="small"
              @click="resetToWelcome"
            >
              新建空会话（回到欢迎页）
            </BkButton>
          </div>
        </div>

        <div
          v-if="currentMode === 'chatbot'"
          class="chatbot-stage"
        >
          <ChatBot
            :key="`welcome-chatbot-${instanceKey}`"
            ref="chatBotRef"
            :always-create-new-session="true"
            height="100%"
            :request-options="requestOptions"
            :url="apiUrl"
            :use-agent-name="true"
            @error="handleError"
            @send-message="handleMessageSent"
          >
            <template #welcome="{ welcomeTitle, openingRemark }">
              <TraceWelcomeCard
                :opening-remark="openingRemark"
                :service="activeService"
                :trace-id="activeTraceId"
                :welcome-title="welcomeTitle"
                @analyze="handleQuickAnalyze"
                @fill-only="handleFillOnly"
              />
            </template>
          </ChatBot>
        </div>

        <div
          v-else
          class="floating-stage"
        >
          <div class="floating-stage-inner">
            <p class="floating-stage-title">AIBlueking 浮窗模式已挂载</p>
            <p class="floating-stage-desc">
              点击上方「打开小鲸浮窗」或右下角小鲸悬浮球即可看到同样的 <code>#welcome</code> 动态按钮。
              切到左侧其他 Trace 后，空会话欢迎按钮会自动同步更新。
            </p>
            <BkButton
              theme="primary"
              @click="openFloatingPanel"
            >
              打开小鲸浮窗查看效果
            </BkButton>
          </div>
          <AIBlueking
            :key="`welcome-aiblueking-${instanceKey}`"
            ref="aiBluekingRef"
            :always-create-new-session="true"
            :enable-popup="true"
            :request-options="requestOptions"
            :url="apiUrl"
            :use-agent-name="true"
            @send-message="handleMessageSent"
          >
            <template #welcome="{ welcomeTitle, openingRemark }">
              <TraceWelcomeCard
                :opening-remark="openingRemark"
                :service="activeService"
                :trace-id="activeTraceId"
                :welcome-title="welcomeTitle"
                @analyze="handleQuickAnalyze"
                @fill-only="handleFillOnly"
              />
            </template>
          </AIBlueking>
        </div>
      </div>
    </section>

    <!-- ==================== 二、版本要求 ==================== -->
    <section class="doc-panel">
      <h3 class="doc-panel-title">一、版本与 SDK 要求</h3>
      <p class="doc-desc">
        <code>requestOptions.context</code> 是小鲸组件能力（非 chat-x UI 能力），chat-helper 负责原样透传消息
        <code>property</code>。新接入建议直接锁定推荐组合，避免跨大版本混用。
      </p>
      <table class="version-table">
        <thead>
          <tr>
            <th>npm 包</th>
            <th>最低可用版本</th>
            <th>建议锁定版本</th>
            <th>说明</th>
          </tr>
        </thead>
        <tbody>
          <tr
            v-for="row in VERSION_REQUIREMENTS"
            :key="row.pkg"
          >
            <td><code>{{ row.pkg }}</code></td>
            <td>{{ row.minVersion }}</td>
            <td><strong>{{ row.recommended }}</strong></td>
            <td>{{ row.note }}</td>
          </tr>
        </tbody>
      </table>
    </section>

    <!-- ==================== 三、完整数据流 ==================== -->
    <section class="doc-panel">
      <h3 class="doc-panel-title">二、完整数据流（前端 → 小鲸 → 后台 → LLM）</h3>
      <pre class="doc-code"><code>{{ DATA_FLOW_DIAGRAM }}</code></pre>
      <ol class="flow-step-list">
        <li
          v-for="item in DATA_FLOW_STEPS"
          :key="item.step"
          class="flow-step-item"
        >
          <span class="step-num">{{ item.step }}</span>
          <span class="step-actor">{{ item.actor }}</span>
          <div class="step-body">
            <strong>{{ item.title }}</strong>
            <p>{{ item.detail }}</p>
          </div>
        </li>
      </ol>
    </section>

    <!-- ==================== 四、前后端如何配合 ==================== -->
    <section class="doc-panel">
      <h3 class="doc-panel-title">三、前后端配合契约</h3>
      <div class="collab-grid">
        <div class="collab-col">
          <h4>前端职责</h4>
          <ul class="doc-list">
            <li>
              将当前页面动态信息（<code>trace_id</code>、<code>service</code>、<code>page</code>）放入
              <code>computed&lt;IRequestOptions&gt;</code> 的 <code>context</code> 对象中（不要把 <code>context</code> 写成函数）。
            </li>
            <li>
              利用 <code>#welcome</code> 插槽在空会话绘制 <code>分析 &#123;&#123; traceId &#125;&#125; 的日志</code> 按钮；点击直接调用
              <code>sendMessage('日志分析')</code>，用户气泡保持简洁。
            </li>
            <li>
              注意边界：<code>#welcome</code> 只在<strong>空会话</strong>显示；有历史消息后，用户直接在输入框输入「日志分析」同样会自动携带最新
              <code>requestOptions.context</code>。
            </li>
            <li>
              <code>trace_id</code> 只走 <code>context</code>，不要放进 <code>requestOptions.data</code> 或 HTTP Header。
            </li>
          </ul>
          <div class="code-header-bar">
            <span>前端接入片段（Vue3）</span>
            <BkButton
              size="small"
              @click="copySnippet('frontend', FRONTEND_VUE3_CODE)"
            >
              {{ copiedKey === 'frontend' ? '已复制' : '复制' }}
            </BkButton>
          </div>
          <pre class="doc-code"><code>{{ FRONTEND_VUE3_CODE }}</code></pre>
        </div>

        <div class="collab-col">
          <h4>后端接收协议（POST session_content/）</h4>
          <ul class="doc-list">
            <li>
              前端发消息分为两步：先 <code>POST session_content/</code>（携带 <code>property.extra.context</code>），再
              <code>POST chat_completion/</code>（只传 <code>session_code</code>）。
            </li>
            <li>
              后台读取本轮最后一条 <code>role == "user"</code> 消息的 <code>extra.context</code>（兼容平铺的
              <code>msg["extra"]</code> 与原始 <code>msg["property"]["extra"]</code>）。
            </li>
            <li>
              按数组中每条记录的 <code>__key</code> 与 <code>__value</code> 取值；若无 <code>trace_id</code> 应明确提示缺少页面上下文，不要编造排查结果。
            </li>
            <li>
              若同时使用了快捷指令（<code>extra.command</code>），<code>requestOptions.context</code> 会追加在后面并在 <code>__key</code> 冲突时覆盖表单字段。
            </li>
          </ul>
          <div class="code-header-bar">
            <span>用户消息完整请求体示例</span>
            <BkButton
              size="small"
              @click="copySnippet('payload', SESSION_CONTENT_PAYLOAD_JSON)"
            >
              {{ copiedKey === 'payload' ? '已复制' : '复制' }}
            </BkButton>
          </div>
          <pre class="doc-code"><code>{{ SESSION_CONTENT_PAYLOAD_JSON }}</code></pre>
        </div>
      </div>
    </section>

    <!-- ==================== 五、后端二次开发指南 ==================== -->
    <section class="doc-panel">
      <div class="doc-panel-head">
        <h3 class="doc-panel-title">四、后端二次开发指南</h3>
        <div class="doc-tabs">
          <button
            v-for="tab in backendTabs"
            :key="tab.id"
            class="doc-tab"
            :class="{ 'is-active': activeBackendTab === tab.id }"
            type="button"
            @click="activeBackendTab = tab.id"
          >
            {{ tab.label }}
          </button>
        </div>
      </div>

      <div v-if="activeBackendTab === 'plain'">
        <p class="doc-desc">
          官方 Chat Agent <strong>不会</strong>根据 <code>extra.context</code> 自动改写 Prompt。针对「只说日志分析（无
          <code>extra.command</code>）」场景，在把 <code>session_context_data</code> 送给 LLM 前组装上下文 Prompt；
          <strong>只改内存对象，不要覆写落库的 <code>content</code></strong>，保证前端聊天记录仍展示「日志分析」。
        </p>
        <div class="code-header-bar">
          <span>Python 二开参考：抽取 __key/__value 并组装本轮 LLM Prompt</span>
          <BkButton
            size="small"
            @click="copySnippet('backend-plain', BACKEND_EXTRACT_AND_PROMPT_PY)"
          >
            {{ copiedKey === 'backend-plain' ? '已复制' : '复制' }}
          </BkButton>
        </div>
        <pre class="doc-code"><code>{{ BACKEND_EXTRACT_AND_PROMPT_PY }}</code></pre>
      </div>

      <div v-else-if="activeBackendTab === 'command'">
        <p class="doc-desc">
          如果业务同时通过快捷指令发送（带 <code>extra.command</code>），可复用仓库内
          <code>aidev_agent/services/command_handler.py</code> 的 <code>CommandHandler</code> 与 <code>CommandProcessor</code>
          用 Jinja2 模板渲染 Prompt（注意：默认未自动注册到 <code>ChatAgentBuilder</code>，需在二开中显式注册并调用）。
        </p>
        <div class="code-header-bar">
          <span>Python 二开参考：CommandHandler 模板渲染</span>
          <BkButton
            size="small"
            @click="copySnippet('backend-command', BACKEND_COMMAND_HANDLER_PY)"
          >
            {{ copiedKey === 'backend-command' ? '已复制' : '复制' }}
          </BkButton>
        </div>
        <pre class="doc-code"><code>{{ BACKEND_COMMAND_HANDLER_PY }}</code></pre>
      </div>

      <div v-else-if="activeBackendTab === 'prompt'">
        <p class="doc-desc">
          除了后台代码组装与工具调用，建议在 AIDev 平台配置 Agent 的<strong>系统提示词</strong>，约定模型对
          <code>trace_id</code> 上下文的行为边界（缺失时不瞎编、存在时不反问）。
        </p>
        <div class="code-header-bar">
          <span>AIDev Agent 系统提示词参考模板</span>
          <BkButton
            size="small"
            @click="copySnippet('system-prompt', SYSTEM_PROMPT_TEMPLATE)"
          >
            {{ copiedKey === 'system-prompt' ? '已复制' : '复制' }}
          </BkButton>
        </div>
        <pre class="doc-code"><code>{{ SYSTEM_PROMPT_TEMPLATE }}</code></pre>
      </div>

      <div v-else>
        <p class="doc-desc">联调与二开过程中最容易踩坑的 5 件事：</p>
        <ul class="pitfall-list">
          <li
            v-for="item in PITFALL_ITEMS"
            :key="item.doNot"
            class="pitfall-item"
          >
            <strong>{{ item.doNot }}</strong>
            <p>{{ item.why }}</p>
          </li>
        </ul>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
  import { computed, ref } from 'vue';

  import { AIBlueking, ChatBot, type AIBluekingExpose, type ChatBotExpose, type IRequestOptions } from '@blueking/ai-blueking';
  import { Button as BkButton, Message } from 'bkui-vue';

  import SourceGuideDialog from '../components/SourceGuideDialog.vue';
  import TraceWelcomeCard from '../components/TraceWelcomeCard.vue';
  import {
    BACKEND_COMMAND_HANDLER_PY,
    BACKEND_EXTRACT_AND_PROMPT_PY,
    DATA_FLOW_DIAGRAM,
    DATA_FLOW_STEPS,
    FRONTEND_VUE3_CODE,
    PITFALL_ITEMS,
    SESSION_CONTENT_PAYLOAD_JSON,
    SYSTEM_PROMPT_TEMPLATE,
    TRACE_SAMPLES,
    VERSION_REQUIREMENTS,
    welcomeContextGuideSections,
    type TraceSample,
  } from '../components/welcome-context-guide';

  type DemoMode = 'aiblueking' | 'chatbot';
  type BackendTabId = 'command' | 'pitfalls' | 'plain' | 'prompt';

  interface ActionLogItem {
    message: string;
    time: string;
  }

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const chatBotRef = ref<ChatBotExpose>();
  const aiBluekingRef = ref<AIBluekingExpose>();

  const currentMode = ref<DemoMode>('chatbot');
  const instanceKey = ref(0);
  const selectedTraceId = ref<string>(TRACE_SAMPLES[0].id);
  const customTraceInput = ref<string>('');
  const actionLogs = ref<ActionLogItem[]>([]);
  const activeBackendTab = ref<BackendTabId>('plain');
  const copiedKey = ref<string>('');

  const demoModes: Array<{ label: string; value: DemoMode }> = [
    { value: 'chatbot', label: 'ChatBot 独立嵌入' },
    { value: 'aiblueking', label: 'AIBlueking 浮窗' },
  ];

  const backendTabs: Array<{ id: BackendTabId; label: string }> = [
    { id: 'plain', label: '普通提问「日志分析」二开' },
    { id: 'command', label: '快捷指令 CommandHandler' },
    { id: 'prompt', label: 'AIDev 系统提示词' },
    { id: 'pitfalls', label: '避坑清单' },
  ];

  const selectedPreset = computed<TraceSample | undefined>(() =>
    TRACE_SAMPLES.find(item => item.id === selectedTraceId.value),
  );

  const activeTraceId = computed<string>(() => customTraceInput.value || selectedTraceId.value);

  const activeService = computed<string>(() => {
    if (customTraceInput.value) {
      return 'custom-trace-service';
    }
    return selectedPreset.value?.service ?? '';
  });

  const activeContextMap = computed<Record<string, string> | undefined>(() => {
    if (!activeTraceId.value) {
      return undefined;
    }
    return {
      trace_id: activeTraceId.value,
      service: activeService.value || 'unknown',
      page: selectedPreset.value?.page ?? 'trace-detail',
    };
  });

  // 关键点：整个 requestOptions 写成 computed，让 context 保持普通对象形态
  const requestOptions = computed<IRequestOptions>(() => ({
    ...(activeContextMap.value ? { context: activeContextMap.value } : {}),
  }));

  // 实时模拟小鲸 applyRequestOptionsContext 写入 POST session_content/ 的结构
  const livePayloadPreview = computed<string>(() => {
    const entries = Object.entries(activeContextMap.value ?? {}).map(([key, value]) => ({
      [key]: value,
      context_type: 'input',
      __label: key,
      __key: key,
      __value: value,
    }));

    return JSON.stringify(
      {
        role: 'user',
        content: '日志分析',
        property: entries.length > 0 ? { extra: { context: entries } } : {},
      },
      null,
      2,
    );
  });

  const appendLog = (message: string) => {
    actionLogs.value = [
      {
        time: new Date().toLocaleTimeString(),
        message,
      },
      ...actionLogs.value.slice(0, 7),
    ];
  };

  const selectPresetTrace = (sample: TraceSample) => {
    customTraceInput.value = '';
    selectedTraceId.value = sample.id;
    appendLog(`切换页面上下文 → trace_id=${sample.id}（${sample.service}）`);
  };

  const applyCustomTrace = () => {
    if (customTraceInput.value) {
      selectedTraceId.value = '';
    }
  };

  const clearTrace = () => {
    selectedTraceId.value = '';
    customTraceInput.value = '';
    appendLog('已清空页面 Trace 上下文（验证无上下文降级态）');
  };

  const openFloatingPanel = async () => {
    await aiBluekingRef.value?.show();
  };

  const resetToWelcome = async () => {
    if (currentMode.value === 'aiblueking') {
      await aiBluekingRef.value?.show();
      await aiBluekingRef.value?.addNewSession();
      appendLog('AIBlueking 已新建空会话并回到欢迎区');
      return;
    }
    instanceKey.value += 1;
    appendLog('ChatBot 已重置并新建空会话，回到欢迎区');
  };

  const handleQuickAnalyze = async () => {
    if (!activeTraceId.value) {
      return;
    }
    appendLog(`点击欢迎按钮「分析 ${activeTraceId.value} 的日志」→ sendMessage("日志分析") + context.trace_id=${activeTraceId.value}`);
    if (currentMode.value === 'aiblueking') {
      await aiBluekingRef.value?.sendMessage('日志分析');
      return;
    }
    await chatBotRef.value?.sendMessage('日志分析');
  };

  const handleFillOnly = () => {
    const targetRef = currentMode.value === 'aiblueking' ? aiBluekingRef.value : chatBotRef.value;
    targetRef?.setInputContent('日志分析');
    appendLog(`已将「日志分析」写入输入框（发送时会自动附带 trace_id=${activeTraceId.value}）`);
  };

  const handleMessageSent = (message: string) => {
    appendLog(
      `已发出用户消息：「${message}」；随消息附带 context = ${activeTraceId.value ? `trace_id=${activeTraceId.value}` : '无'}`,
    );
  };

  const handleError = (error: Error) => {
    console.error('[WelcomeContextAction] error:', error);
  };

  const copySnippet = async (key: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      copiedKey.value = key;
      Message({ theme: 'success', message: '已复制到剪贴板' });
      window.setTimeout(() => {
        if (copiedKey.value === key) {
          copiedKey.value = '';
        }
      }, 1600);
    } catch {
      Message({ theme: 'error', message: '复制失败，请手动选择代码' });
    }
  };
</script>

<style scoped>
  .welcome-context-view {
    display: flex;
    flex-direction: column;
    gap: 16px;
  }

  .view-header-row {
    display: flex;
    gap: 16px;
    align-items: flex-start;
    justify-content: space-between;
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
    line-height: 1.7;
    color: #63656e;
  }

  .view-desc code,
  .card-hint code,
  .doc-desc code,
  .doc-list code,
  .floating-stage-desc code,
  .version-table code {
    padding: 1px 5px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  /* ===== 交互工作台 ===== */
  .workbench {
    display: grid;
    grid-template-columns: minmax(320px, 400px) minmax(420px, 1fr);
    gap: 16px;
    align-items: stretch;
  }

  @media (max-width: 1120px) {
    .workbench {
      grid-template-columns: 1fr;
    }
  }

  .business-panel {
    display: flex;
    flex-direction: column;
    gap: 12px;
  }

  .panel-card {
    padding: 14px 16px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
  }

  .card-head {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
  }

  .card-head h3 {
    margin: 0;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .card-hint {
    margin: 0 0 10px;
    font-size: 12px;
    line-height: 1.6;
    color: #979ba5;
  }

  .text-action-btn {
    padding: 0;
    font-size: 12px;
    color: #3a84ff;
    cursor: pointer;
    background: transparent;
    border: none;
  }

  .text-action-btn:hover {
    text-decoration: underline;
  }

  .trace-list {
    display: flex;
    flex-direction: column;
    gap: 8px;
    margin-bottom: 12px;
  }

  .trace-item {
    display: flex;
    flex-direction: column;
    gap: 4px;
    width: 100%;
    padding: 10px 12px;
    text-align: left;
    cursor: pointer;
    background: #fafbfd;
    border: 1px solid #dcdee5;
    border-radius: 6px;
    transition: all 0.15s;
  }

  .trace-item:hover {
    border-color: #a3c5fd;
    background: #f5f9ff;
  }

  .trace-item.is-active {
    background: #f0f5ff;
    border-color: #3a84ff;
    box-shadow: 0 0 0 1px rgb(58 132 255 / 15%);
  }

  .trace-item-top {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
  }

  .trace-id {
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    font-weight: 600;
    color: #313238;
  }

  .trace-badge {
    padding: 1px 6px;
    font-size: 11px;
    border-radius: 10px;
  }

  .trace-badge.is-error {
    color: #ea3636;
    background: #ffeded;
  }

  .trace-badge.is-slow {
    color: #ff9c01;
    background: #fff4e2;
  }

  .trace-meta {
    display: flex;
    flex-direction: column;
    gap: 2px;
    font-size: 12px;
  }

  .trace-service {
    font-weight: 500;
    color: #63656e;
  }

  .trace-summary {
    color: #979ba5;
  }

  .custom-trace-row {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .custom-trace-label {
    flex-shrink: 0;
    font-size: 12px;
    color: #63656e;
  }

  .custom-trace-input {
    flex: 1;
    height: 30px;
    padding: 0 10px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    color: #313238;
    background: #fff;
    border: 1px solid #c4c6cc;
    border-radius: 3px;
    outline: none;
  }

  .custom-trace-input:focus {
    border-color: #3a84ff;
  }

  .status-pill {
    padding: 2px 8px;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    color: #14a568;
    background: #e4faf0;
    border-radius: 10px;
  }

  .payload-preview {
    max-height: 210px;
    padding: 10px 12px;
    margin: 0;
    overflow: auto;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    line-height: 1.5;
    color: #313238;
    background: #f5f7fa;
    border-radius: 4px;
  }

  .action-log-list {
    display: flex;
    flex-direction: column;
    gap: 6px;
    max-height: 140px;
    padding: 0;
    margin: 0;
    overflow-y: auto;
    list-style: none;
    font-size: 12px;
  }

  .action-log-list li {
    display: flex;
    gap: 8px;
    line-height: 1.5;
    color: #63656e;
  }

  .log-time {
    flex-shrink: 0;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    color: #979ba5;
  }

  /* ===== 右侧小鲸预览 ===== */
  .ai-preview-panel {
    display: flex;
    flex-direction: column;
    min-height: 620px;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
  }

  .preview-toolbar {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
    align-items: center;
    justify-content: space-between;
    padding: 10px 14px;
    background: #fafbfd;
    border-bottom: 1px solid #eaebf0;
  }

  .mode-switch {
    display: flex;
    gap: 8px;
    align-items: center;
  }

  .toolbar-label {
    font-size: 12px;
    color: #63656e;
  }

  .mode-option {
    display: inline-flex;
    align-items: center;
    padding: 3px 10px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 4px;
  }

  .mode-option.is-active {
    font-weight: 500;
    color: #3a84ff;
    background: #f0f5ff;
    border-color: #3a84ff;
  }

  .mode-option input {
    display: none;
  }

  .toolbar-actions {
    display: flex;
    gap: 8px;
  }

  .chatbot-stage {
    flex: 1;
    min-height: 560px;
  }

  .floating-stage {
    display: flex;
    flex: 1;
    align-items: center;
    justify-content: center;
    min-height: 560px;
    padding: 24px;
    background: #fafbfd;
  }

  .floating-stage-inner {
    max-width: 420px;
    text-align: center;
  }

  .floating-stage-title {
    margin: 0 0 8px;
    font-size: 15px;
    font-weight: 600;
    color: #313238;
  }

  .floating-stage-desc {
    margin: 0 0 16px;
    font-size: 13px;
    line-height: 1.6;
    color: #63656e;
  }

  /* ===== 文档面板 ===== */
  .doc-panel {
    padding: 18px 20px;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
  }

  .doc-panel-head {
    display: flex;
    flex-wrap: wrap;
    gap: 12px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 12px;
  }

  .doc-panel-head .doc-panel-title {
    margin-bottom: 0;
  }

  .doc-panel-title {
    margin: 0 0 12px;
    font-size: 15px;
    font-weight: 600;
    color: #313238;
  }

  .doc-desc {
    margin: 0 0 12px;
    font-size: 13px;
    line-height: 1.65;
    color: #63656e;
  }

  .version-table {
    width: 100%;
    font-size: 13px;
    border-collapse: collapse;
  }

  .version-table th,
  .version-table td {
    padding: 10px 12px;
    text-align: left;
    border: 1px solid #eaebf0;
  }

  .version-table th {
    font-weight: 600;
    color: #313238;
    background: #fafbfd;
  }

  .version-table td {
    color: #63656e;
  }

  .doc-code {
    display: block;
    padding: 12px 14px;
    margin: 0;
    overflow: auto;
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    line-height: 1.55;
    color: #313238;
    white-space: pre;
    background: #f5f7fa;
    border: 1px solid #eaebf0;
    border-radius: 4px;
  }

  .flow-step-list {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 10px;
    padding: 0;
    margin: 14px 0 0;
    list-style: none;
  }

  .flow-step-item {
    display: flex;
    flex-direction: column;
    gap: 6px;
    padding: 12px;
    background: #fafbfd;
    border: 1px solid #eaebf0;
    border-radius: 6px;
  }

  .step-num {
    font-family: SFMono-Regular, Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 11px;
    font-weight: 700;
    color: #3a84ff;
  }

  .step-actor {
    display: inline-block;
    align-self: flex-start;
    padding: 1px 6px;
    font-size: 11px;
    color: #3a84ff;
    background: #e1ecff;
    border-radius: 3px;
  }

  .step-body strong {
    display: block;
    margin-bottom: 4px;
    font-size: 13px;
    color: #313238;
  }

  .step-body p {
    margin: 0;
    font-size: 12px;
    line-height: 1.55;
    color: #63656e;
  }

  .collab-grid {
    display: grid;
    grid-template-columns: repeat(2, minmax(0, 1fr));
    gap: 16px;
  }

  @media (max-width: 1080px) {
    .collab-grid {
      grid-template-columns: 1fr;
    }
  }

  .collab-col h4 {
    margin: 0 0 8px;
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .doc-list {
    padding-left: 18px;
    margin: 0 0 12px;
    font-size: 12px;
    line-height: 1.7;
    color: #63656e;
  }

  .doc-list li + li {
    margin-top: 6px;
  }

  .code-header-bar {
    display: flex;
    gap: 8px;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 6px;
    font-size: 12px;
    font-weight: 500;
    color: #63656e;
  }

  .doc-tabs {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
  }

  .doc-tab {
    height: 28px;
    padding: 0 12px;
    font-size: 12px;
    color: #63656e;
    cursor: pointer;
    background: #f5f7fa;
    border: 1px solid transparent;
    border-radius: 14px;
  }

  .doc-tab.is-active {
    font-weight: 600;
    color: #3a84ff;
    background: #e1ecff;
  }

  .pitfall-list {
    display: flex;
    flex-direction: column;
    gap: 10px;
    padding: 0;
    margin: 0;
    list-style: none;
  }

  .pitfall-item {
    padding: 10px 14px;
    background: #fff9f0;
    border-left: 3px solid #ff9c01;
    border-radius: 4px;
  }

  .pitfall-item strong {
    display: block;
    margin-bottom: 4px;
    font-size: 13px;
    color: #313238;
  }

  .pitfall-item p {
    margin: 0;
    font-size: 12px;
    line-height: 1.55;
    color: #63656e;
  }
</style>
