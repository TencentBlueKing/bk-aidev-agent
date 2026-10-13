<template>
  <DemoRecipe
    :id="RECIPE_ID"
    file="snippets/sdk-error-handler.ts"
    :floating-config="currentConfig()"
    kicker="配方 1"
    :source="source"
    title="注入接口故障，观察 sdk-error"
    when="适用：统一处理小鲸的接口错误，用业务自己的提示替代内置 toast"
  >
    <DemoStage
      app="蓝鲸监控"
      crumbs="告警中心"
    >
      <div class="demo-card">
        <div class="demo-field-label">注入的故障（Mock 根据请求头 x-mock-fault 返回错误）</div>
        <div
          class="fi-faults"
          role="radiogroup"
          aria-label="注入的故障"
        >
          <button
            v-for="f in FAULTS"
            :key="f.id"
            type="button"
            role="radio"
            class="fi-fault"
            :aria-checked="fault.id === f.id"
            :class="{ 'is-on': fault.id === f.id }"
            @click="fault = f"
          >
            <span class="fi-fault__title">{{ f.label }}</span>
            <span class="fi-fault__desc">{{ f.desc }}</span>
          </button>
        </div>
        <label class="fi-toast">
          <input
            v-model="toastOff"
            type="checkbox"
          >
          关闭内置 toast（<code>:error-toast="false"</code>），只显示业务提示
        </label>
        <div class="demo-actions">
          <bk-button
            theme="primary"
            @click="handleTrigger"
          >
            触发故障
          </bk-button>
          <bk-button @click="handleClear">
            清除故障
          </bk-button>
          <DemoFeedback
            :feedback="feedback"
            :recipe-id="RECIPE_ID"
          />
        </div>
      </div>
      <div
        v-if="notice"
        class="fi-notice"
        :class="`is-${notice.level}`"
        role="alert"
      >
        <b>业务提示</b>{{ notice.text }}
      </div>
      <pre
        v-if="lastPayload"
        class="fi-payload"
      >@sdk-error {{ lastPayload }}</pre>
    </DemoStage>
  </DemoRecipe>
</template>

<script setup lang="ts">
  import { onBeforeUnmount, ref } from 'vue';

  import DemoFeedback from '../../demo-kit/DemoFeedback.vue';
  import DemoRecipe from '../../demo-kit/DemoRecipe.vue';
  import DemoStage from '../../demo-kit/DemoStage.vue';
  import type { FeedbackState, FloatingConfig } from '../../demo-kit/types';
  import { FLOATING_INSTANCE, useDemoRuntime } from '../../demo-kit/use-demo-runtime';
  import { httpStatusOf, toBusinessNotice, type BusinessNotice, type SdkError } from './snippets/sdk-error-handler';
  import source from './snippets/sdk-error-handler.ts?raw';

  interface FaultOption {
    id: 'agent_info:500' | 'session_content:500' | 'stream:run_error' | 'all:401';
    label: string;
    desc: string;
    /** 影响初始化：需要带着故障重新挂载浮窗 */
    init: boolean;
    /** 触发后的说明（与 sdk-error 无关的行为） */
    note?: string;
  }

  const RECIPE_ID = 'fault-injection';
  const FAULT_HEADER = 'x-mock-fault';
  const FAULTS: FaultOption[] = [
    { id: 'agent_info:500', label: '智能体信息 500', desc: '初始化失败', init: true },
    { id: 'session_content:500', label: '发送消息 500', desc: '写入用户消息失败', init: false },
    {
      id: 'stream:run_error',
      label: '流中途 RUN_ERROR',
      desc: '模型服务异常',
      init: false,
      note: 'RUN_ERROR 由协议层渲染为一条失败的助手消息，不经过 @sdk-error，看右侧面板。',
    },
    { id: 'all:401', label: '鉴权 401', desc: '所有接口登录态失效', init: true },
  ];

  const runtime = useDemoRuntime();
  const fault = ref<FaultOption>(FAULTS[0]);
  const toastOff = ref(true);
  const notice = ref<BusinessNotice | null>(null);
  const lastPayload = ref('');
  const feedback = ref<FeedbackState | null>(null);

  /** 初始化类故障的配置标识包含故障本身：切换时带着故障头重新挂载 */
  const currentConfig = (active?: FaultOption): FloatingConfig => ({
    props: { errorToast: !toastOff.value },
    key: `fault:${active?.init ? active.id : 'none'}:${toastOff.value ? 'no-toast' : 'toast'}`,
  });

  const stop = runtime.onComponentEvent((instanceId, name, payload) => {
    if (instanceId !== FLOATING_INSTANCE || name !== 'sdk-error') return;
    const error = payload as SdkError;
    notice.value = toBusinessNotice(error);
    lastPayload.value = JSON.stringify({
      apiName: error.apiName,
      code: error.code,
      message: error.message,
      source: error.source,
      'data.response.status': httpStatusOf(error),
    });
  });

  onBeforeUnmount(() => {
    stop();
    runtime.setInstanceHeaders(FLOATING_INSTANCE, {});
  });

  const handleTrigger = async () => {
    const active = fault.value;
    notice.value = null;
    lastPayload.value = '';
    runtime.setInstanceHeaders(FLOATING_INSTANCE, { [FAULT_HEADER]: active.id });
    runtime.updateFloatingConfig(RECIPE_ID, currentConfig(active));
    const result = await runtime.run(RECIPE_ID, '①', async ai => {
      await ai.show();
      if (!active.init) await ai.sendMessage('请诊断告警「CPU 使用率 97%」，主机 10.0.0.12');
    });
    feedback.value = result.ok
      ? { kind: 'ok', text: active.note ?? `已触发「${active.label}」。`, goto: 'events', gotoLabel: active.note ? '查看事件' : '查看 @sdk-error' }
      : { kind: 'info', text: `调用被 reject（符合预期）：${result.error}`, goto: 'events', gotoLabel: '查看 @sdk-error' };
  };

  const handleClear = async () => {
    runtime.setInstanceHeaders(FLOATING_INSTANCE, {});
    runtime.updateFloatingConfig(RECIPE_ID, currentConfig());
    notice.value = null;
    lastPayload.value = '';
    const result = await runtime.run(RECIPE_ID, '①', ai => ai.show());
    feedback.value = result.ok
      ? { kind: 'ok', text: result.remounted ? '已清除故障并重新挂载，小鲸恢复正常。' : '已清除故障。' }
      : { kind: 'err', text: result.error ?? '清除失败' };
  };
</script>

<style scoped>
  .fi-faults {
    display: grid;
    grid-template-columns: repeat(4, 1fr);
    gap: 8px;
  }

  .fi-fault {
    display: flex;
    flex-direction: column;
    gap: 2px;
    padding: 10px 12px;
    text-align: left;
    cursor: pointer;
    background: #fff;
    border: 1px solid #dcdee5;
    border-radius: 2px;
  }

  .fi-fault.is-on {
    border-color: #ea3636;
    box-shadow: inset 0 0 0 1px #ea3636;
  }

  .fi-fault__title {
    font-size: 13px;
    font-weight: 600;
    color: #313238;
  }

  .fi-fault__desc {
    font-size: 12px;
    color: #979ba5;
  }

  .fi-toast {
    display: flex;
    gap: 6px;
    align-items: center;
    margin-top: 12px;
    font-size: 12px;
    color: #63656e;
  }

  .fi-toast code {
    font-size: 11px;
  }

  .fi-notice {
    display: flex;
    gap: 10px;
    padding: 10px 14px;
    margin-top: 12px;
    font-size: 13px;
    border-radius: 2px;
  }

  .fi-notice.is-error {
    color: #ea3636;
    background: #ffeded;
    border: 1px solid #fdd;
  }

  .fi-notice.is-warning {
    color: #b45309;
    background: #fff3e1;
    border: 1px solid #ffe2b8;
  }

  .fi-payload {
    padding: 8px 12px;
    margin: 8px 0 0;
    font-family: var(--vp-font-family-mono);
    font-size: 12px;
    color: #63656e;
    white-space: pre-wrap;
    word-break: break-all;
    background: #fff;
    border: 1px dashed #dcdee5;
    border-radius: 2px;
  }

  @media (max-width: 760px) {
    .fi-faults {
      grid-template-columns: repeat(2, 1fr);
    }
  }
</style>
