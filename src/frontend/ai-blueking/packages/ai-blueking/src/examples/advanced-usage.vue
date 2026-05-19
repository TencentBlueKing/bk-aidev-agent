<template>
  <div class="adv-demo">
    <!-- 页面 Header -->
    <div class="adv-header">
      <div class="adv-header-text">
        <h2>AIBlueking 编程式 API</h2>
        <p>
          通过 <code>ref</code> 获取组件实例，调用暴露的方法来编程式控制 AI 面板行为。<br />
          以下每张卡片展示一个 API：左侧为说明和代码实现，右侧为可运行的演示。
        </p>
      </div>
      <div class="ref-setup-block">
        <span class="ref-label">组件引用绑定</span>
        <pre class="ref-code"><span class="c-keyword">const</span> aiBluekingRef = <span class="c-fn">ref</span>&lt;<span class="c-type">AIBluekingExpose</span>&gt;()
<span class="c-comment">// template 中：</span>
<span class="c-tag">&lt;AIBlueking</span> <span class="c-attr">ref</span>=<span class="c-str">"aiBluekingRef"</span> <span class="c-tag">/&gt;</span></pre>
        <div class="mount-status" :class="{ mounted: isMounted }">
          <span class="mount-dot" />
          {{ isMounted ? '组件已挂载，可调用方法' : '组件未挂载' }}
        </div>
      </div>
    </div>

    <!-- ==================== Section 1: 基础操作 ==================== -->
    <div class="section-title">
      <span class="section-icon">⚡</span>基础操作
    </div>
    <div class="api-grid">
      <!-- show() -->
      <div class="api-card" :class="{ running: runningKey === 'show' }">
        <div class="card-left">
          <div class="method-sig">
            <span class="method-name">show</span><span class="method-parens">(target?, options?)</span>
          </div>
          <p class="card-desc">打开 AI 面板。可传入 <code>{ isTemporary: true }</code> 以临时会话模式打开。</p>
          <div class="code-block">
            <div class="code-header">
              <span class="code-lang">TypeScript</span>
            </div>
            <pre><span class="c-comment">// 普通模式打开</span>
<span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">show</span>()

<span class="c-comment">// 临时会话模式（不记录历史）</span>
<span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">show</span>(<span class="c-keyword">undefined</span>, { isTemporary: <span class="c-bool">true</span> })</pre>
          </div>
        </div>
        <div class="card-right">
          <div class="demo-label">演示</div>
          <div class="demo-btns">
            <button
              class="demo-btn primary"
              :disabled="runningKey === 'show'"
              @click="handleShowPanel"
            >
              {{ runningKey === 'show' ? '执行中…' : '打开面板' }}
            </button>
          </div>
          <FeedbackBadge :feedback="feedbacks.show" />
        </div>
      </div>

      <!-- sendMessage() -->
      <div class="api-card" :class="{ running: runningKey === 'sendMessage' }">
        <div class="card-left">
          <div class="method-sig">
            <span class="method-name">sendMessage</span><span class="method-parens">(message)</span>
          </div>
          <p class="card-desc">编程式发送一条消息，等同于用户在输入框中输入并提交。</p>
          <div class="code-block">
            <div class="code-header">
              <span class="code-lang">TypeScript</span>
            </div>
            <pre><span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">sendMessage</span>(<span class="c-str">'这是一条编程式发送的消息'</span>)</pre>
          </div>
        </div>
        <div class="card-right">
          <div class="demo-label">演示</div>
          <div class="demo-btns">
            <button
              class="demo-btn primary"
              :disabled="runningKey === 'sendMessage'"
              @click="handleSendMessage"
            >
              {{ runningKey === 'sendMessage' ? '发送中…' : '发送消息' }}
            </button>
          </div>
          <FeedbackBadge :feedback="feedbacks.sendMessage" />
        </div>
      </div>

      <!-- stopGeneration() -->
      <div class="api-card" :class="{ running: runningKey === 'stop' }">
        <div class="card-left">
          <div class="method-sig">
            <span class="method-name">stopGeneration</span><span class="method-parens">()</span>
          </div>
          <p class="card-desc">中止当前正在生成的 AI 回复，适用于用户想提前终止长回复的场景。</p>
          <div class="code-block">
            <div class="code-header">
              <span class="code-lang">TypeScript</span>
            </div>
            <pre><span class="c-comment">// 同步方法，无需 await</span>
aiBluekingRef.value?.<span class="c-fn">stopGeneration</span>()</pre>
          </div>
        </div>
        <div class="card-right">
          <div class="demo-label">演示</div>
          <div class="demo-note">先发送消息，再点击停止</div>
          <div class="demo-btns">
            <button
              class="demo-btn danger"
              @click="handleStopGeneration"
            >
              停止生成
            </button>
          </div>
          <FeedbackBadge :feedback="feedbacks.stop" />
        </div>
      </div>

      <!-- setCiteText() -->
      <div class="api-card" :class="{ running: runningKey === 'cite' }">
        <div class="card-left">
          <div class="method-sig">
            <span class="method-name">setCiteText</span><span class="method-parens">(text)</span>
          </div>
          <p class="card-desc">
            设置输入框的引用文本（划词引用场景）。常与 <code>show()</code> 配合使用，让面板打开时自动带上引用内容。
          </p>
          <div class="code-block">
            <div class="code-header">
              <span class="code-lang">TypeScript</span>
            </div>
            <pre><span class="c-comment">// 设置引用文本并打开面板</span>
aiBluekingRef.value?.<span class="c-fn">setCiteText</span>(<span class="c-str">'这是引用的文本内容'</span>)
aiBluekingRef.value?.<span class="c-fn">show</span>()</pre>
          </div>
        </div>
        <div class="card-right">
          <div class="demo-label">演示</div>
          <div class="demo-btns">
            <button
              class="demo-btn primary"
              :disabled="runningKey === 'cite'"
              @click="handleSetCiteText"
            >
              设置引用文本
            </button>
          </div>
          <FeedbackBadge :feedback="feedbacks.cite" />
        </div>
      </div>
    </div>

    <!-- ==================== Section 2: 快捷指令 ==================== -->
    <div class="section-title">
      <span class="section-icon">⚡</span>编程式触发快捷指令
      <span class="section-badge">旧版迁移</span>
    </div>
    <div class="migration-tip">
      <span class="tip-icon">💡</span>
      <span>
        旧版 <code>window.aiBlueking.handleShortcutClick</code> 已废弃，新版通过
        <code>selectShortcut</code> / <code>sendShortcut</code> 实现，语义更清晰。
      </span>
    </div>

    <!-- 三种方式对比 -->
    <div class="shortcut-compare">
      <!-- 方式 1 -->
      <div
        class="shortcut-card"
        :class="{ running: runningKey === 'shortcut1', active: activeShortcutIdx === 0 }"
        @click="activeShortcutIdx = 0"
      >
        <div class="sc-head">
          <span class="sc-num">方式 1</span>
          <span class="sc-method">selectShortcut(cmd)</span>
          <span class="sc-tag">用户手动提交</span>
        </div>
        <p class="sc-desc">打开面板，显示快捷指令表单，<strong>字段为空</strong>，等待用户填写后手动点击提交。</p>
        <div class="code-block">
          <div class="code-header">
            <span class="code-lang">TypeScript</span>
          </div>
          <pre><span class="c-keyword">const</span> chatHelper = aiBluekingRef.value?.<span class="c-fn">getChatHelper</span>()
<span class="c-keyword">const</span> command = chatHelper?.agent.info.value
  ?.conversationSettings?.commands?.[<span class="c-num">0</span>]

<span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">show</span>(<span class="c-keyword">undefined</span>, { isTemporary: <span class="c-bool">true</span> })
aiBluekingRef.value?.<span class="c-fn">selectShortcut</span>(command)</pre>
        </div>
        <div class="sc-action" @click.stop>
          <button
            class="demo-btn primary"
            :disabled="runningKey === 'shortcut1'"
            @click="triggerShortcutShowForm"
          >
            {{ runningKey === 'shortcut1' ? '执行中…' : '显示表单' }}
          </button>
          <FeedbackBadge :feedback="feedbacks.shortcut1" />
        </div>
      </div>

      <!-- 方式 2 -->
      <div
        class="shortcut-card"
        :class="{ running: runningKey === 'shortcut2', active: activeShortcutIdx === 1 }"
        @click="activeShortcutIdx = 1"
      >
        <div class="sc-head">
          <span class="sc-num">方式 2</span>
          <span class="sc-method">selectShortcut(cmd, prefill)</span>
          <span class="sc-tag">预填充 · 手动提交</span>
        </div>
        <p class="sc-desc">打开面板，<strong>预填充表单字段</strong>，用户可修改后手动提交。适用于"智能填充"场景。</p>
        <div class="code-block">
          <div class="code-header">
            <span class="code-lang">TypeScript</span>
          </div>
          <pre><span class="c-comment">// 深拷贝 command 并修改 default 值</span>
<span class="c-keyword">const</span> command = {
  ...originalCommand,
  components: originalCommand.components.<span class="c-fn">map</span>((comp, i) =&gt; ({
    ...comp,
    default: i === <span class="c-num">0</span> ? <span class="c-str">'预填充的 SQL'</span>
           : i === <span class="c-num">1</span> ? <span class="c-str">'预填充的错误信息'</span>
           : comp.default,
  })),
}

<span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">show</span>(<span class="c-keyword">undefined</span>, { isTemporary: <span class="c-bool">true</span> })
aiBluekingRef.value?.<span class="c-fn">selectShortcut</span>(command, <span class="c-str">''</span>)</pre>
        </div>
        <div class="sc-action" @click.stop>
          <button
            class="demo-btn primary"
            :disabled="runningKey === 'shortcut2'"
            @click="triggerShortcutWithPrefill"
          >
            {{ runningKey === 'shortcut2' ? '执行中…' : '预填充表单' }}
          </button>
          <FeedbackBadge :feedback="feedbacks.shortcut2" />
        </div>
      </div>

      <!-- 方式 3：独占一行，包含 requestOptions 完整说明 -->
      <div
        class="shortcut-card highlight sc-full"
        :class="{ running: runningKey === 'shortcut3', active: activeShortcutIdx === 2 }"
        @click="activeShortcutIdx = 2"
      >
        <div class="sc-head">
          <span class="sc-num">方式 3</span>
          <span class="sc-method">sendShortcut(cmd) + requestOptions 注入</span>
          <span class="sc-tag recommended">直接发送 ★ 推荐</span>
        </div>
        <p class="sc-desc">
          预填充后<strong>跳过表单直接发送</strong>，等价旧版 <code>handleShortcutClick(_, true)</code>。
          同时演示如何通过 <code>requestOptions</code> 为<strong>单次请求</strong>动态注入自定义 Header 和 body 数据。
        </p>

        <!-- 两列代码 -->
        <div class="sc-code-cols">
          <!-- 左列：requestOptions 初始化 -->
          <div class="sc-code-col">
            <div class="sc-code-label">① 初始化时传入稳定的 requestOptions</div>
            <div class="code-block">
              <div class="code-header">
                <span class="code-lang">TypeScript</span>
                <span class="code-tip">函数引用整个生命周期不变</span>
              </div>
              <pre><span class="c-comment">// ChatHelper 初始化时一次性捕获函数引用</span>
<span class="c-comment">// 每次发请求时动态调用 → 实现"仅目标请求注入"</span>
<span class="c-keyword">const</span> activeReqOpts = <span class="c-fn">shallowRef</span>&lt;ReqOpts | <span class="c-keyword">undefined</span>&gt;(<span class="c-keyword">undefined</span>)

<span class="c-keyword">const</span> requestOptions = {
  headers: (): <span class="c-type">Record</span>&lt;<span class="c-type">string</span>, <span class="c-type">string</span>&gt; =&gt;
    activeReqOpts.value?.<span class="c-fn">headers</span>?.() ?? {},
  data: (): <span class="c-type">Record</span>&lt;<span class="c-type">string</span>, <span class="c-type">unknown</span>&gt; =&gt;
    ({ ...(activeReqOpts.value?.<span class="c-fn">data</span>?.() ?? {}) }),
}

<span class="c-comment">// 传给组件（整个生命周期只传一次）</span>
<span class="c-tag">&lt;AIBlueking</span> <span class="c-attr">:request-options</span>=<span class="c-str">"requestOptions"</span> <span class="c-tag">/&gt;</span></pre>
            </div>
          </div>

          <!-- 右列：发送时临时注入 -->
          <div class="sc-code-col">
            <div class="sc-code-label">② 发送时临时注入，完成后自动清除</div>
            <div class="code-block">
              <div class="code-header">
                <span class="code-lang">TypeScript</span>
                <span class="code-tip">try/finally 保证清除</span>
              </div>
              <pre><span class="c-comment">// 定义本次请求要注入的参数</span>
<span class="c-keyword">const</span> directSendOpts = {
  headers: () =&gt; ({ set_ai_message: <span class="c-str">'true'</span> }),
  data: () =&gt; ({ data: codeContent }),
}

<span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">show</span>(<span class="c-keyword">undefined</span>, { isTemporary: <span class="c-bool">true</span> })

<span class="c-comment">// 注入 → 发送 → 清除（try/finally 保证不污染后续请求）</span>
activeReqOpts.value = directSendOpts
<span class="c-keyword">try</span> {
  <span class="c-keyword">await</span> aiBluekingRef.value?.<span class="c-fn">sendShortcut</span>(command, <span class="c-str">''</span>)
} <span class="c-keyword">finally</span> {
  activeReqOpts.value = <span class="c-keyword">undefined</span>
}</pre>
            </div>
          </div>
        </div>

        <!-- 设计要点说明 -->
        <div class="sc-insight">
          <span class="insight-icon">💡</span>
          <span>
            <strong>单次请求临时注入：</strong>
            可将 <code>activeReqOpts</code> 设为 ref，在发送前赋值、<code>finally</code> 中清空；
            也可直接传 <code>computed</code> / <code>ref</code> 包裹的 <code>requestOptions</code>，后续请求会自动读取最新 headers / data。
            下方示例仍使用包装函数，用于「仅某次 sendShortcut 注入」的场景。
          </span>
        </div>

        <div class="sc-action" @click.stop>
          <button
            class="demo-btn success"
            :disabled="runningKey === 'shortcut3'"
            @click="triggerShortcutDirectSend"
          >
            {{ runningKey === 'shortcut3' ? '发送中…' : '预填充 + 直接发送' }}
          </button>
          <FeedbackBadge :feedback="feedbacks.shortcut3" />
        </div>
      </div>
    </div>

    <!-- AIBlueking 组件实例 -->
    <AIBlueking
      ref="aiBluekingRef"
      :enable-chat-session="true"
      :enable-popup="true"
      :resize-props="{ min: 300, max: 600, initialDivide: 350 }"
      :url="apiUrl"
      :request-options="requestOptions"
      @close="() => console.log('[Advanced] closed')"
      @show="() => console.log('[Advanced] shown')"
    />
  </div>
</template>

<script setup lang="ts">
  import { computed, defineComponent, h, onMounted, ref, shallowRef } from 'vue';

  import AIBlueking from '../ai-blueking.vue';

  import type { AIBluekingExpose } from '../types';

  // ==================== 反馈 Badge 子组件 ====================

  interface FeedbackItem {
    type: 'success' | 'error' | 'info';
    text: string;
  }

  const FeedbackBadge = defineComponent({
    props: {
      feedback: { type: Object as () => FeedbackItem | null, default: null },
    },
    setup(props) {
      return () => {
        if (!props.feedback) return null;
        return h(
          'div',
          { class: ['fb-badge', `fb-${props.feedback.type}`] },
          [
            h('span', { class: 'fb-icon' }, props.feedback.type === 'success' ? '✓' : props.feedback.type === 'error' ? '✗' : 'ℹ'),
            h('span', props.feedback.text),
          ],
        );
      };
    },
  });

  // ==================== 状态 ====================

  const apiUrl = import.meta.env.VITE_API_URL || '';
  const aiBluekingRef = ref<AIBluekingExpose>();
  const isMounted = computed(() => !!aiBluekingRef.value);
  const runningKey = ref<string | null>(null);
  const activeShortcutIdx = ref<number | null>(null);

  /** 每个操作的反馈状态 */
  const feedbacks = shallowRef<Record<string, FeedbackItem | null>>({
    show: null,
    sendMessage: null,
    stop: null,
    cite: null,
    shortcut1: null,
    shortcut2: null,
    shortcut3: null,
  });

  onMounted(() => {
    // 触发 isMounted 更新
  });

  /** 显示反馈，3 秒后自动清除 */
  const setFeedback = (key: string, feedback: FeedbackItem) => {
    feedbacks.value = { ...feedbacks.value, [key]: feedback };
    setTimeout(() => {
      feedbacks.value = { ...feedbacks.value, [key]: null };
    }, 3000);
  };

  /** 包装执行器：设置 runningKey、捕获错误 */
  const run = async (key: string, fn: () => Promise<void> | void) => {
    if (runningKey.value) return;
    runningKey.value = key;
    try {
      await fn();
      setFeedback(key, { type: 'success', text: '执行成功' });
    } catch (err) {
      const msg = err instanceof Error ? err.message : '执行失败';
      setFeedback(key, { type: 'error', text: msg });
    } finally {
      runningKey.value = null;
    }
  };

  // ==================== 基础操作 ====================

  const handleShowPanel = () =>
    run('show', async () => {
      if (!aiBluekingRef.value) throw new Error('组件 ref 未绑定');
      await aiBluekingRef.value.show();
    });

  const handleSendMessage = () =>
    run('sendMessage', async () => {
      if (!aiBluekingRef.value) throw new Error('组件 ref 未绑定');
      await aiBluekingRef.value.sendMessage('这是一条编程式发送的消息');
    });

  const handleStopGeneration = () =>
    run('stop', () => {
      aiBluekingRef.value?.stopGeneration();
    });

  const handleSetCiteText = () =>
    run('cite', () => {
      aiBluekingRef.value?.setCiteText('这是引用的文本内容');
      aiBluekingRef.value?.show();
    });

  // ==================== 快捷指令 ====================

  const getFirstCommand = () => {
    const chatHelper = aiBluekingRef.value?.getChatHelper?.();
    const commands = chatHelper?.agent.info.value?.conversationSettings?.commands;
    if (!commands?.[0]?.components) throw new Error('AI 命令配置不完整，请确认 Agent 已初始化且配置了 commands');
    return commands[0];
  };

  const triggerShortcutShowForm = () =>
    run('shortcut1', async () => {
      if (!aiBluekingRef.value) throw new Error('组件 ref 未绑定');
      const originalCommand = getFirstCommand();
      await aiBluekingRef.value.show(undefined, { isTemporary: true });
      aiBluekingRef.value.selectShortcut(originalCommand);
    });

  const triggerShortcutWithPrefill = () =>
    run('shortcut2', async () => {
      if (!aiBluekingRef.value) throw new Error('组件 ref 未绑定');
      const originalCommand = getFirstCommand();
      const command = {
        ...originalCommand,
        components: originalCommand.components.map((comp, index) => ({
          ...comp,
          default: index === 0 ? '预填充的 SQL 内容' : index === 1 ? '预填充的错误信息' : comp.default,
        })),
      };
      await aiBluekingRef.value.show(undefined, { isTemporary: true });
      aiBluekingRef.value.selectShortcut(command, '');
    });

  // code-block 中展示的示例代码，作为 requestOptions.data.data 传入
  const codeBlockContent = `const command = {
  ...originalCommand,
  components: originalCommand.components.map((comp, i) => ({
    ...comp,
    default: i === 0 ? sql : i === 1 ? errorMessage : comp.default,
  })),
};
await aiBluekingRef.value?.show(undefined, { isTemporary: true });
await aiBluekingRef.value?.sendShortcut(command, '');`;

  const directSendRequestOptions = {
    headers: () => ({ set_ai_message: 'true' }),
    data: () => ({ data: codeBlockContent }),
  };

  const activeRequestOptions = shallowRef<typeof directSendRequestOptions | undefined>(undefined);

  const requestOptions = {
    headers: (): Record<string, string> => activeRequestOptions.value?.headers?.() ?? {},
    data: (): Record<string, unknown> => ({ ...(activeRequestOptions.value?.data?.() ?? {}) }),
  };

  const triggerShortcutDirectSend = () =>
    run('shortcut3', async () => {
      if (!aiBluekingRef.value) throw new Error('组件 ref 未绑定');
      const originalCommand = getFirstCommand();
      const command = {
        ...originalCommand,
        components: originalCommand.components.map((comp, index) => ({
          ...comp,
          default: index === 0 ? '预填充的 SQL 内容' : index === 1 ? '预填充的错误信息' : comp.default,
        })),
      };
      await aiBluekingRef.value.show(undefined, { isTemporary: true });
      activeRequestOptions.value = directSendRequestOptions;
      try {
        await aiBluekingRef.value.sendShortcut(command, '');
      } finally {
        activeRequestOptions.value = undefined;
      }
    });
</script>

<style scoped>
  /* ==================== 页面容器 ==================== */
  .adv-demo {
    box-sizing: border-box;
    max-width: 1100px;
    padding: 24px 28px 48px;
    margin: 0 auto;
    overflow-x: hidden;
  }

  /* ==================== Header ==================== */
  .adv-header {
    display: flex;
    flex-wrap: wrap;
    gap: 24px;
    align-items: flex-start;
    padding: 24px;
    margin-bottom: 32px;
    background: linear-gradient(135deg, #f0f5ff 0%, #fafbff 100%);
    border: 1px solid #d4e8ff;
    border-radius: 8px;
  }

  .adv-header-text {
    flex: 1;
  }

  .adv-header-text h2 {
    margin: 0 0 8px;
    font-size: 20px;
    font-weight: 600;
    color: #1a1a2e;
  }

  .adv-header-text p {
    margin: 0;
    font-size: 13px;
    line-height: 1.7;
    color: #63656e;
  }

  .adv-header-text code {
    padding: 1px 5px;
    font-size: 12px;
    color: #3a84ff;
    background: #e8f3ff;
    border-radius: 3px;
  }

  .ref-setup-block {
    flex-shrink: 0;
    min-width: 0;
    width: 340px;
    max-width: 100%;
  }

  .ref-label {
    display: block;
    margin-bottom: 6px;
    font-size: 11px;
    font-weight: 600;
    color: #979ba5;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .ref-code {
    padding: 12px 14px;
    margin: 0 0 8px;
    overflow-x: auto;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    line-height: 1.7;
    white-space: pre-wrap;
    word-break: break-all;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 6px;
  }

  .mount-status {
    display: flex;
    gap: 6px;
    align-items: center;
    font-size: 12px;
    color: #979ba5;
  }

  .mount-status.mounted {
    color: #2dcb56;
  }

  .mount-dot {
    display: inline-block;
    width: 7px;
    height: 7px;
    background: #dcdee5;
    border-radius: 50%;
  }

  .mount-status.mounted .mount-dot {
    background: #2dcb56;
    box-shadow: 0 0 0 3px rgb(45 203 86 / 20%);
  }

  /* ==================== Section Title ==================== */
  .section-title {
    display: flex;
    gap: 8px;
    align-items: center;
    margin: 0 0 16px;
    font-size: 15px;
    font-weight: 600;
    color: #313238;
  }

  .section-icon {
    font-size: 14px;
  }

  .section-badge {
    padding: 2px 8px;
    font-size: 11px;
    font-weight: normal;
    color: #ff9c01;
    background: #fff4e2;
    border-radius: 10px;
  }

  /* ==================== 迁移提示 ==================== */
  .migration-tip {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 10px 14px;
    margin-bottom: 16px;
    font-size: 13px;
    color: #63656e;
    background: #fffbf0;
    border: 1px solid #ffe8a3;
    border-radius: 6px;
  }

  .tip-icon {
    flex-shrink: 0;
    font-size: 14px;
    line-height: 1.5;
  }

  .migration-tip code {
    padding: 1px 5px;
    font-size: 12px;
    color: #ff9c01;
    background: #fff4e2;
    border-radius: 3px;
  }

  /* ==================== API Cards Grid ==================== */
  .api-grid {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 40px;
  }

  .api-card {
    display: flex;
    gap: 0;
    min-width: 0;
    overflow: hidden;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
    transition: box-shadow 0.2s, border-color 0.2s;
  }

  .api-card:hover {
    border-color: #a3c5fd;
    box-shadow: 0 2px 12px rgb(58 132 255 / 10%);
  }

  .api-card.running {
    border-color: #3a84ff;
    box-shadow: 0 0 0 2px rgb(58 132 255 / 20%);
  }

  .card-left {
    flex: 1;
    padding: 18px 16px;
    border-right: 1px solid #f0f1f5;
  }

  .card-right {
    display: flex;
    flex-direction: column;
    gap: 10px;
    align-items: flex-start;
    justify-content: flex-start;
    width: 160px;
    padding: 18px 14px;
    background: #fafbff;
  }

  .method-sig {
    margin-bottom: 6px;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    line-height: 1.4;
  }

  .method-name {
    font-size: 15px;
    font-weight: 600;
    color: #3a84ff;
  }

  .method-parens {
    font-size: 13px;
    color: #979ba5;
  }

  .card-desc {
    margin: 0 0 12px;
    font-size: 12px;
    line-height: 1.6;
    color: #63656e;
  }

  .card-desc code {
    padding: 1px 4px;
    font-size: 11px;
    color: #3a84ff;
    background: #f0f5ff;
    border-radius: 3px;
  }

  .demo-label {
    font-size: 11px;
    font-weight: 600;
    color: #979ba5;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .demo-note {
    font-size: 11px;
    line-height: 1.5;
    color: #c4c6cc;
  }

  .demo-btns {
    display: flex;
    flex-direction: column;
    gap: 8px;
    width: 100%;
  }

  /* ==================== Code Block ==================== */
  .code-block {
    overflow: hidden;
    background: #fafafa;
    border: 1px solid #eaebf0;
    border-radius: 6px;
  }

  .code-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    padding: 5px 10px;
    background: #f0f1f5;
    border-bottom: 1px solid #eaebf0;
  }

  .code-lang {
    font-size: 11px;
    color: #979ba5;
    text-transform: uppercase;
    letter-spacing: 0.5px;
  }

  .code-block pre {
    padding: 12px 14px;
    margin: 0;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    line-height: 1.7;
    color: #313238;
    white-space: pre-wrap;
    word-break: break-all;
  }

  /* ==================== Syntax Colors ==================== */
  .c-keyword { color: #d73a49; }
  .c-fn { color: #6f42c1; }
  .c-str { color: #032f62; }
  .c-type { color: #e36209; }
  .c-comment { color: #6a737d; font-style: italic; }
  .c-num { color: #005cc5; }
  .c-bool { color: #d73a49; }
  .c-tag { color: #22863a; }
  .c-attr { color: #6f42c1; }

  /* ==================== Shortcut Compare ==================== */
  .shortcut-compare {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 40px;
  }

  .shortcut-card {
    min-width: 0;
    padding: 18px;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 8px;
    transition: box-shadow 0.2s, border-color 0.2s;
  }

  /* 方式 3 独占一行 */
  .shortcut-card.sc-full {
    grid-column: 1 / -1;
  }

  .shortcut-card:hover {
    border-color: #a3c5fd;
    box-shadow: 0 2px 12px rgb(58 132 255 / 10%);
  }

  .shortcut-card.active {
    border-color: #3a84ff;
    box-shadow: 0 0 0 2px rgb(58 132 255 / 15%);
  }

  .shortcut-card.running {
    border-color: #3a84ff;
    box-shadow: 0 0 0 3px rgb(58 132 255 / 20%);
  }

  .shortcut-card.highlight {
    background: linear-gradient(180deg, #f5fff8 0%, #fff 100%);
    border-color: #c5ebd0;
  }

  .shortcut-card.highlight.active {
    border-color: #2dcb56;
    box-shadow: 0 0 0 2px rgb(45 203 86 / 15%);
  }

  .sc-head {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    align-items: center;
    margin-bottom: 8px;
  }

  .sc-num {
    padding: 1px 6px;
    font-size: 11px;
    font-weight: 600;
    color: #fff;
    background: #3a84ff;
    border-radius: 10px;
  }

  .sc-method {
    flex: 1;
    font-family: 'SFMono-Regular', Consolas, 'Liberation Mono', Menlo, monospace;
    font-size: 12px;
    font-weight: 600;
    color: #6f42c1;
  }

  .sc-tag {
    padding: 1px 7px;
    font-size: 11px;
    color: #979ba5;
    background: #f0f1f5;
    border-radius: 10px;
  }

  .sc-tag.recommended {
    color: #2dcb56;
    background: #e8f9ec;
  }

  .sc-desc {
    margin: 0 0 12px;
    font-size: 12px;
    line-height: 1.6;
    color: #63656e;
  }

  .sc-desc strong {
    color: #313238;
  }

  .sc-desc code {
    padding: 1px 4px;
    font-size: 11px;
    color: #ff9c01;
    background: #fff4e2;
    border-radius: 3px;
  }

  .sc-action {
    display: flex;
    flex-wrap: wrap;
    gap: 8px;
    align-items: center;
    margin-top: 12px;
  }

  /* ==================== Buttons ==================== */
  .demo-btn {
    padding: 6px 14px;
    font-size: 12px;
    font-weight: 500;
    cursor: pointer;
    border: none;
    border-radius: 4px;
    transition: background 0.15s, opacity 0.15s;
  }

  .demo-btn:disabled {
    cursor: not-allowed;
    opacity: 0.6;
  }

  .demo-btn.primary {
    color: #fff;
    background: #3a84ff;
  }

  .demo-btn.primary:hover:not(:disabled) {
    background: #2b76f0;
  }

  .demo-btn.success {
    color: #fff;
    background: #2dcb56;
  }

  .demo-btn.success:hover:not(:disabled) {
    background: #22b84a;
  }

  .demo-btn.danger {
    color: #fff;
    background: #ea3636;
  }

  .demo-btn.danger:hover:not(:disabled) {
    background: #d42f2f;
  }

  /* ==================== Feedback Badge ==================== */
  :deep(.fb-badge) {
    display: inline-flex;
    gap: 5px;
    align-items: center;
    padding: 3px 9px;
    font-size: 12px;
    border-radius: 12px;
    animation: fb-in 0.2s ease;
  }

  :deep(.fb-success) {
    color: #2dcb56;
    background: #e8f9ec;
  }

  :deep(.fb-error) {
    color: #ea3636;
    background: #feecec;
  }

  :deep(.fb-info) {
    color: #3a84ff;
    background: #e8f3ff;
  }

  :deep(.fb-icon) {
    font-weight: 700;
  }

  /* ==================== 方式3 双列代码布局 ==================== */
  .sc-code-cols {
    display: grid;
    grid-template-columns: 1fr 1fr;
    gap: 16px;
    margin-bottom: 12px;
  }

  .sc-code-col {
    min-width: 0;
  }

  .sc-code-label {
    margin-bottom: 6px;
    font-size: 12px;
    font-weight: 600;
    color: #313238;
  }

  .code-tip {
    font-size: 11px;
    font-style: italic;
    color: #979ba5;
    text-transform: none;
    letter-spacing: 0;
  }

  /* ==================== 设计要点 ==================== */
  .sc-insight {
    display: flex;
    gap: 8px;
    align-items: flex-start;
    padding: 10px 14px;
    margin-bottom: 12px;
    font-size: 12px;
    line-height: 1.65;
    color: #63656e;
    background: #fff8f0;
    border: 1px solid #ffd89b;
    border-left: 3px solid #ff9c01;
    border-radius: 0 6px 6px 0;
  }

  .insight-icon {
    flex-shrink: 0;
    font-size: 14px;
    line-height: 1.5;
  }

  .sc-insight strong {
    display: block;
    margin-bottom: 2px;
    color: #313238;
  }

  .sc-insight code {
    padding: 1px 4px;
    font-size: 11px;
    color: #d73a49;
    background: #fff0f0;
    border-radius: 3px;
  }

  @keyframes fb-in {
    from {
      opacity: 0;
      transform: translateY(-4px);
    }

    to {
      opacity: 1;
      transform: translateY(0);
    }
  }
</style>
